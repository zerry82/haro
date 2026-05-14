from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import database
from app.config import settings
from app.dependencies import get_current_user, get_db
from app.models.mail import (
    MailAnalysisRun,
    MailConnection,
    MailImprovementCandidate,
    MailPolicy,
    MailStructureTest,
    MailThreadStaging,
)
from app.models.project import Project
from app.models.user import User
from app.services.context_library_db import promote_mail_threads
from app.services.gmail_fetcher import (
    BODY_LIMIT,
    HTML_BODY_LIMIT,
    GmailAuthError,
    GmailFetchError,
    GmailFetcher,
    normalize_mail_body_text,
)
from app.services.gmail_oauth import (
    EncryptedTokenStore,
    GmailOAuthService,
    OAuthConfigurationError,
    TokenStoreConfigurationError,
    normalize_return_url,
)
from app.services.mail_analysis import analyze_mail_threads, recent_count_range, thread_payload_from_staging
from app.services.mail_attachment_processing import AttachmentProcessingStats, MailAttachmentProcessor
from app.services.mail_filtering import normalize_filter_rules
from app.services.mail_incremental import filter_new_threads, latest_processed_received_at
from app.services.mail_insights import build_mail_insights
from app.services.mail_management import (
    MailManagementPolicyStore,
    apply_management_to_thread,
)
from app.services.mail_search import (
    MailSearchRunNotFoundError,
    MailSearchRunNotReadyError,
    search_mail_analysis,
)
from app.services.mail_snapshot_store import MailSnapshotStore
from app.services.mail_structuring import MailStructuringService
from app.services.mail_vector_index import MailVectorSearchStore, MailVectorSearchUnavailable

router = APIRouter(prefix="/api/projects/{project_id}/mail/gmail", tags=["mail"])
_RUNNING_ANALYSIS_TASKS: dict[str, asyncio.Task] = {}
_ACTIVE_RUN_STATUSES = {
    "queued",
    "fetching",
    "normalizing",
    "attachment_downloading",
    "attachment_extracting",
    "structuring",
    "indexing",
}
_ORPHANED_RUN_GRACE_SECONDS = 30


class GmailConnectRequest(BaseModel):
    return_url: str | None = None


class MailAttachmentInput(BaseModel):
    model_config = ConfigDict(extra="allow")

    title: str | None = None
    name: str | None = None
    extension: str | None = None
    size_bytes: int | None = None
    size: int | None = None
    summary: str | None = None
    content_summary: str | None = None


class MailThreadInput(BaseModel):
    model_config = ConfigDict(extra="allow")

    source_ref: str | None = None
    subject: str = "(no subject)"
    sender: str = "unknown"
    recipients: list[str] = Field(default_factory=list)
    received_at: str | None = None
    body: str | None = None
    summary: str | None = None
    attachments: list[MailAttachmentInput] = Field(default_factory=list)


class AnalyzeRecentRequest(BaseModel):
    max_threads: int = Field(default=50, ge=1, le=500)
    force_refresh: bool = False
    threads: list[MailThreadInput] = Field(default_factory=list)


class PolicyRequest(BaseModel):
    categories: list[dict[str, Any]] = Field(default_factory=list)
    filters: list[dict[str, Any]] = Field(default_factory=list)


class ReanalyzeRequest(BaseModel):
    source_run_id: str | None = None


class LiveStartRequest(BaseModel):
    poll_interval_minutes: int = Field(default=30, ge=5, le=1440)


class MigrationRequest(BaseModel):
    range_start: str
    range_end: str
    threads: list[MailThreadInput] = Field(default_factory=list)


class MailSearchRequest(BaseModel):
    query: str = ""
    limit: int = Field(default=10, ge=1, le=50)


class MailInsightRequest(BaseModel):
    query: str = ""


class MailStructureTestRequest(BaseModel):
    query: str
    result_kind: str = "search"
    rating: str
    notes: str | None = None
    result: dict[str, Any] = Field(default_factory=dict)


class MailImprovementCandidateRequest(BaseModel):
    title: str
    reason: str
    priority: str = "medium"
    source: str = "user"
    query: str | None = None
    thread_ids: list[str] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)


class MailManagementPolicyRequest(BaseModel):
    whitelist_rules: list[dict[str, Any]] = Field(default_factory=list)
    blacklist_rules: list[dict[str, Any]] = Field(default_factory=list)
    llm_blacklist_rules: list[dict[str, Any]] = Field(default_factory=list)
    manual_overrides: list[dict[str, Any]] = Field(default_factory=list)


class ManageThreadRequest(BaseModel):
    decision: str = "managed"
    reason: str | None = None


class IncrementalMailRequest(BaseModel):
    scan_limit: int = Field(default=500, ge=1, le=500)


@dataclass(frozen=True)
class RecentThreadPayloads:
    threads: list[dict[str, Any]]
    cache_status: dict[str, Any]
    fetched_at: str | None = None


@router.post("/connect", status_code=status.HTTP_201_CREATED)
async def connect_gmail(
    project_id: str,
    body: GmailConnectRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project(db, user.id, project_id)
    connection = await _get_connection(db, project.id, user.id)
    now = _now()
    try:
        return_url = normalize_return_url(body.return_url, allowed_origins=settings.cors_origins)
        oauth = _gmail_oauth_service()
        _token_store()
        auth_url = oauth.build_authorization_url(project_id=project.id, user_id=user.id, return_url=return_url)
    except (OAuthConfigurationError, TokenStoreConfigurationError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if connection:
        if connection.status != "connected":
            connection.status = "needs_oauth"
        connection.updated_at = now
    else:
        connection = MailConnection(
            project_id=project.id,
            user_id=user.id,
            status="needs_oauth",
            created_at=now,
            updated_at=now,
        )
        db.add(connection)
    await db.commit()
    await db.refresh(connection)
    return {"auth_url": auth_url, "connection": _connection_response(connection)}


@router.get("/status")
async def gmail_status(
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project(db, user.id, project_id)
    connection = await _get_connection(db, project.id, user.id)
    policy = await _get_policy(db, project.id, user.id)
    latest_run = await _latest_run(db, project.id, user.id)
    return {
        "connection": _connection_response(connection) if connection else None,
        "policy": _policy_response(policy),
        "management_policy": _mail_management_policy_store(project.workspace_path).load(user.id),
        "latest_run": _run_summary(latest_run) if latest_run else None,
    }


@router.post("/analyze-recent", status_code=status.HTTP_201_CREATED)
async def analyze_recent(
    project_id: str,
    body: AnalyzeRecentRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project(db, user.id, project_id)
    range_start, range_end = recent_count_range(body.max_threads)
    connection = await _get_connection(db, project.id, user.id)
    if not body.threads and (not connection or connection.status != "connected" or not connection.token_ref):
        raise HTTPException(status_code=409, detail="Gmail connection is required")
    run = await _create_queued_analysis_run(
        db,
        project,
        user,
        range_start,
        range_end,
        connection=connection,
        stats_extra={
            "requested_count": body.max_threads,
            "force_refresh": body.force_refresh,
        },
    )
    await db.commit()
    _schedule_analysis_job(project.id, user.id, run.id, body.model_dump())
    return await _analysis_response(db, run)


@router.post("/incremental/preview")
async def preview_incremental_mail(
    project_id: str,
    body: IncrementalMailRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project(db, user.id, project_id)
    connection = await _get_connection(db, project.id, user.id)
    latest_run = await _latest_completed_run(db, project.id, user.id)
    if not latest_run:
        raise HTTPException(status_code=409, detail="먼저 최근 메일 분석을 한 번 실행해 주세요.")
    if not connection or connection.status != "connected" or not connection.token_ref:
        raise HTTPException(status_code=409, detail="Gmail connection is required")
    preview = await _incremental_thread_preview(db, project, user, connection, latest_run, body.scan_limit)
    await db.commit()
    return _incremental_preview_response(preview)


@router.post("/incremental/analyze", status_code=status.HTTP_201_CREATED)
async def analyze_incremental_mail(
    project_id: str,
    body: IncrementalMailRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project(db, user.id, project_id)
    connection = await _get_connection(db, project.id, user.id)
    latest_run = await _latest_completed_run(db, project.id, user.id)
    if not latest_run:
        raise HTTPException(status_code=409, detail="먼저 최근 메일 분석을 한 번 실행해 주세요.")
    if not connection or connection.status != "connected" or not connection.token_ref:
        raise HTTPException(status_code=409, detail="Gmail connection is required")
    preview = await _incremental_thread_preview(db, project, user, connection, latest_run, body.scan_limit)
    new_threads = preview["threads"]
    if not new_threads:
        raise HTTPException(status_code=409, detail="마지막 처리 이후 추가된 메일이 없습니다.")
    run = await _create_queued_analysis_run(
        db,
        project,
        user,
        f"incremental:{preview['since_received_at'] or latest_run.id}",
        _now(),
        connection=connection,
        source_run_id=latest_run.id,
        stats_extra={
            "incremental": True,
            "source_run_id": latest_run.id,
            "scan_limit": body.scan_limit,
            "new_count": len(new_threads),
            "since_received_at": preview["since_received_at"],
        },
    )
    await db.commit()
    _schedule_analysis_job(project.id, user.id, run.id, {
        "max_threads": len(new_threads),
        "force_refresh": False,
        "threads": new_threads,
        "base_run_id": latest_run.id,
    })
    return await _analysis_response(db, run)


@router.get("/analysis/{run_id}")
async def get_analysis(
    project_id: str,
    run_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project(db, user.id, project_id)
    run = await _get_run(db, project.id, user.id, run_id)
    return await _analysis_response(db, run)


@router.get("/analysis/{run_id}/threads")
async def get_analysis_threads(
    project_id: str,
    run_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project(db, user.id, project_id)
    run = await _get_run(db, project.id, user.id, run_id)
    threads = await _visible_analysis_threads(db, run)
    return {"threads": [_thread_response(thread) for thread in threads]}


@router.get("/analysis/{run_id}/threads/{thread_id}")
async def get_analysis_thread(
    project_id: str,
    run_id: str,
    thread_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project(db, user.id, project_id)
    run = await _get_run(db, project.id, user.id, run_id)
    thread = await _get_analysis_thread_row(db, project, user, run, thread_id)
    connection = await _get_connection(db, project.id, user.id)
    snapshot_detail = _thread_snapshot_detail(project, user, thread, connection)
    return {"thread": _thread_response(thread, snapshot_detail=snapshot_detail)}


@router.get("/analysis/{run_id}/attachments")
async def get_analysis_attachments(
    project_id: str,
    run_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project(db, user.id, project_id)
    run = await _get_run(db, project.id, user.id, run_id)
    threads = await _visible_analysis_threads(db, run)
    attachments: list[dict[str, Any]] = []
    for thread in threads:
        for attachment in _loads(thread.attachments_json, []):
            if not isinstance(attachment, dict):
                continue
            attachments.append({
                **_public_attachment(attachment),
                "thread_id": thread.id,
                "thread_subject": thread.subject,
                "received_at": thread.received_at,
            })
    return {"attachments": attachments}


@router.get("/analysis/{run_id}/threads/{thread_id}/attachments/{attachment_ref}")
async def get_analysis_thread_attachment(
    project_id: str,
    run_id: str,
    thread_id: str,
    attachment_ref: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project(db, user.id, project_id)
    run = await _get_run(db, project.id, user.id, run_id)
    thread = await _get_analysis_thread_row(db, project, user, run, thread_id)
    for attachment in _loads(thread.attachments_json, []):
        if str(attachment.get("attachment_ref") or "") == attachment_ref:
            return {"attachment": _attachment_detail_response(thread, attachment)}
    raise HTTPException(status_code=404, detail="Mail attachment not found")


@router.post("/analysis/{run_id}/search")
async def search_analysis_mail(
    project_id: str,
    run_id: str,
    body: MailSearchRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project(db, user.id, project_id)
    try:
        result = await search_mail_analysis(
            db,
            project_id=project.id,
            user_id=user.id,
            run_id=run_id,
            query=body.query,
            limit=body.limit,
            workspace_path=project.workspace_path,
        )
    except MailSearchRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MailSearchRunNotReadyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except MailVectorSearchUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"메일 벡터 검색을 사용할 수 없습니다: {exc}") from exc
    return {
        "query": result.query,
        "run": _run_summary(result.run),
        "retrieval": result.retrieval,
        "items": result.items,
    }


@router.get("/analysis/{run_id}/excluded")
async def get_excluded_threads(
    project_id: str,
    run_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project(db, user.id, project_id)
    run = await _get_run(db, project.id, user.id, run_id)
    threads = await _visible_analysis_threads(db, run)
    excluded = [
        thread
        for thread in threads
        if _loads(thread.metadata_json, {}).get("management_decision") == "excluded"
    ]
    return {"threads": [_thread_response(thread) for thread in excluded]}


@router.post("/analysis/{run_id}/threads/{thread_id}/manage")
async def manage_analysis_thread(
    project_id: str,
    run_id: str,
    thread_id: str,
    body: ManageThreadRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project(db, user.id, project_id)
    run = await _get_run(db, project.id, user.id, run_id)
    result = await db.execute(
        select(MailThreadStaging).where(
            MailThreadStaging.id == thread_id,
            MailThreadStaging.run_id == run.id,
            MailThreadStaging.project_id == project.id,
            MailThreadStaging.user_id == user.id,
        )
    )
    thread = result.scalar_one_or_none()
    if not thread:
        raise HTTPException(status_code=404, detail="Mail thread not found")
    decision = _allowed_value(body.decision, {"managed", "excluded"}, "managed")
    policy = _mail_management_policy_store(project.workspace_path).set_manual_override(
        user.id,
        thread.id,
        decision,
        body.reason or "",
        source_ref=thread.source_ref,
    )
    payload = thread_payload_from_staging(thread)
    payload["id"] = thread.id
    updated_payload = apply_management_to_thread(payload, policy)
    thread.attachments_json = _dumps(updated_payload["attachments"])
    thread.inclusion_decision = updated_payload["inclusion_decision"]
    thread.metadata_json = _dumps(updated_payload["metadata"] | {"matched_filter_ids": updated_payload.get("matched_filter_ids", [])})
    thread.updated_at = _now()
    await _refresh_run_stats(db, run)
    await db.commit()
    await db.refresh(thread)
    await db.refresh(run)
    return {"thread": _thread_response(thread), "management_policy": policy}


@router.post("/analysis/{run_id}/insights")
async def create_analysis_insights(
    project_id: str,
    run_id: str,
    body: MailInsightRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project(db, user.id, project_id)
    run = await _get_run(db, project.id, user.id, run_id)
    _require_completed_run(run)
    threads = await _visible_analysis_threads(db, run)
    result = build_mail_insights(threads, query=body.query)
    return {
        "query": body.query,
        "run": _run_summary(run),
        "summary": result["summary"],
        "insights": result["insights"],
    }


@router.post("/analysis/{run_id}/structure-tests", status_code=status.HTTP_201_CREATED)
async def create_structure_test(
    project_id: str,
    run_id: str,
    body: MailStructureTestRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project(db, user.id, project_id)
    run = await _get_run(db, project.id, user.id, run_id)
    _require_completed_run(run)
    now = _now()
    row = MailStructureTest(
        project_id=project.id,
        user_id=user.id,
        run_id=run.id,
        query=body.query,
        result_kind=_allowed_value(body.result_kind, {"search", "insight"}, "search"),
        rating=_allowed_value(body.rating, {"good", "warning", "bad"}, "warning"),
        notes=body.notes,
        result_json=_dumps(body.result),
        created_at=now,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return {"test": _structure_test_response(row)}


@router.get("/analysis/{run_id}/structure-tests")
async def list_structure_tests(
    project_id: str,
    run_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project(db, user.id, project_id)
    run = await _get_run(db, project.id, user.id, run_id)
    result = await db.execute(
        select(MailStructureTest)
        .where(
            MailStructureTest.run_id == run.id,
            MailStructureTest.project_id == project.id,
            MailStructureTest.user_id == user.id,
        )
        .order_by(desc(MailStructureTest.created_at))
    )
    return {"tests": [_structure_test_response(row) for row in result.scalars().all()]}


@router.post("/analysis/{run_id}/improvement-candidates", status_code=status.HTTP_201_CREATED)
async def create_improvement_candidate(
    project_id: str,
    run_id: str,
    body: MailImprovementCandidateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project(db, user.id, project_id)
    run = await _get_run(db, project.id, user.id, run_id)
    _require_completed_run(run)
    now = _now()
    row = MailImprovementCandidate(
        project_id=project.id,
        user_id=user.id,
        run_id=run.id,
        title=body.title.strip() or "메일 구조화 개선 후보",
        reason=body.reason.strip() or "사용자 품질 테스트에서 개선 필요로 표시됨",
        priority=_allowed_value(body.priority, {"low", "medium", "high"}, "medium"),
        source=_allowed_value(body.source, {"user", "search_test", "insight"}, "user"),
        query=body.query,
        thread_ids_json=_dumps(body.thread_ids[:20]),
        evidence_json=_dumps(body.evidence[:20]),
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return {"candidate": _improvement_candidate_response(row)}


@router.get("/analysis/{run_id}/improvement-candidates")
async def list_improvement_candidates(
    project_id: str,
    run_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project(db, user.id, project_id)
    run = await _get_run(db, project.id, user.id, run_id)
    result = await db.execute(
        select(MailImprovementCandidate)
        .where(
            MailImprovementCandidate.run_id == run.id,
            MailImprovementCandidate.project_id == project.id,
            MailImprovementCandidate.user_id == user.id,
        )
        .order_by(desc(MailImprovementCandidate.created_at))
    )
    return {"candidates": [_improvement_candidate_response(row) for row in result.scalars().all()]}


@router.put("/policies")
async def update_policies(
    project_id: str,
    body: PolicyRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project(db, user.id, project_id)
    policy = await _get_policy(db, project.id, user.id)
    now = _now()
    filters = normalize_filter_rules(body.filters)
    categories = body.categories
    if policy:
        policy.categories_json = _dumps(categories)
        policy.filters_json = _dumps(filters)
        policy.updated_at = now
    else:
        policy = MailPolicy(
            project_id=project.id,
            user_id=user.id,
            categories_json=_dumps(categories),
            filters_json=_dumps(filters),
            created_at=now,
            updated_at=now,
        )
        db.add(policy)
    await db.commit()
    await db.refresh(policy)
    return {"policy": _policy_response(policy)}


@router.put("/management-policies")
async def update_management_policies(
    project_id: str,
    body: MailManagementPolicyRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project(db, user.id, project_id)
    policy = _mail_management_policy_store(project.workspace_path).save(user.id, body.model_dump())
    latest_run = await _latest_run(db, project.id, user.id)
    if latest_run and latest_run.status == "completed":
        await _reapply_management_policy(db, latest_run, project, user, policy)
    return {"management_policy": policy}


@router.post("/analysis/{run_id}/index-managed")
async def index_managed_mail(
    project_id: str,
    run_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project(db, user.id, project_id)
    run = await _get_run(db, project.id, user.id, run_id)
    _require_completed_run(run)
    threads = await _visible_analysis_threads(db, run)
    managed = [_thread for _thread in threads if _loads(_thread.metadata_json, {}).get("management_decision") != "excluded"]
    try:
        result = MailVectorSearchStore(project.workspace_path).index_run(run_id=run.id, threads=managed)
    except MailVectorSearchUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"메일 벡터 인덱싱을 사용할 수 없습니다: {exc}") from exc
    return {"status": "indexed", "indexed_count": result["indexed_count"], "collection": result["collection"]}


@router.post("/reanalyze", status_code=status.HTTP_201_CREATED)
async def reanalyze(
    project_id: str,
    body: ReanalyzeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project(db, user.id, project_id)
    source_run = await _get_run(db, project.id, user.id, body.source_run_id) if body.source_run_id else await _latest_run(db, project.id, user.id)
    if not source_run:
        raise HTTPException(status_code=404, detail="Analysis run not found")
    result = await db.execute(
        select(MailThreadStaging)
        .where(MailThreadStaging.run_id == source_run.id)
        .order_by(MailThreadStaging.received_at.desc())
    )
    thread_payloads = [thread_payload_from_staging(staging) for staging in result.scalars().all()]
    run = await _create_analysis_run(
        db,
        project,
        user,
        thread_payloads,
        source_run.range_start,
        source_run.range_end,
        source_run_id=source_run.id,
    )
    await db.commit()
    return await _analysis_response(db, run)


@router.post("/analysis/{run_id}/promote")
async def promote_analysis(
    project_id: str,
    run_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project(db, user.id, project_id)
    await _get_run(db, project.id, user.id, run_id)
    result = await db.execute(
        select(MailThreadStaging)
        .where(
            MailThreadStaging.run_id == run_id,
            MailThreadStaging.project_id == project.id,
            MailThreadStaging.user_id == user.id,
            MailThreadStaging.inclusion_decision == "allowed",
        )
    )
    staging_threads = result.scalars().all()
    promoted = promote_mail_threads(project.workspace_path, staging_threads)
    promoted_by_staging_id = {item["staging_id"]: item for item in promoted}
    now = _now()
    for staging in staging_threads:
        promoted_item = promoted_by_staging_id.get(staging.id)
        if promoted_item:
            staging.promoted_at = now
            staging.clean_room_path = promoted_item["clean_room_path"]
            staging.updated_at = now
    await db.commit()
    return {"promoted_count": len(promoted), "items": promoted}


@router.post("/live/start")
async def start_live(
    project_id: str,
    body: LiveStartRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project(db, user.id, project_id)
    connection = await _get_connection(db, project.id, user.id)
    if not connection:
        raise HTTPException(status_code=404, detail="Gmail connection not found")
    connection.live_status = "running"
    connection.live_poll_interval_minutes = body.poll_interval_minutes
    connection.updated_at = _now()
    await db.commit()
    await db.refresh(connection)
    return {"connection": _connection_response(connection)}


@router.post("/live/stop")
async def stop_live(
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project(db, user.id, project_id)
    connection = await _get_connection(db, project.id, user.id)
    if not connection:
        raise HTTPException(status_code=404, detail="Gmail connection not found")
    connection.live_status = "stopped"
    connection.updated_at = _now()
    await db.commit()
    await db.refresh(connection)
    return {"connection": _connection_response(connection)}


@router.post("/migrations", status_code=status.HTTP_201_CREATED)
async def migrate_range(
    project_id: str,
    body: MigrationRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project(db, user.id, project_id)
    run = await _create_analysis_run(
        db,
        project,
        user,
        [thread.model_dump() for thread in body.threads],
        body.range_start,
        body.range_end,
    )
    await db.commit()
    return await _analysis_response(db, run)


async def _create_analysis_run(
    db: AsyncSession,
    project: Project,
    user: User,
    threads: list[dict[str, Any]],
    range_start: str,
    range_end: str,
    source_run_id: str | None = None,
    stats_extra: dict[str, Any] | None = None,
    structured_by_ref: dict[str, dict[str, Any]] | None = None,
) -> MailAnalysisRun:
    connection = await _get_connection(db, project.id, user.id)
    now = _now()
    run = MailAnalysisRun(
        project_id=project.id,
        user_id=user.id,
        connection_id=connection.id if connection else None,
        status="indexing",
        range_start=range_start,
        range_end=range_end,
        stats_json=_dumps({"stage": "indexing"}),
        proposed_categories_json=_dumps([]),
        proposed_filters_json=_dumps([]),
        source_run_id=source_run_id,
        created_at=now,
        updated_at=now,
    )
    db.add(run)
    await db.flush()
    await _complete_analysis_run(db, run, project, user, threads, stats_extra=stats_extra, structured_by_ref=structured_by_ref)
    return run


async def _create_queued_analysis_run(
    db: AsyncSession,
    project: Project,
    user: User,
    range_start: str,
    range_end: str,
    connection: MailConnection | None = None,
    source_run_id: str | None = None,
    stats_extra: dict[str, Any] | None = None,
) -> MailAnalysisRun:
    now = _now()
    stats = {"stage": "queued"} | (stats_extra or {})
    run = MailAnalysisRun(
        project_id=project.id,
        user_id=user.id,
        connection_id=connection.id if connection else None,
        status="queued",
        range_start=range_start,
        range_end=range_end,
        stats_json=_dumps(stats),
        proposed_categories_json=_dumps([]),
        proposed_filters_json=_dumps([]),
        source_run_id=source_run_id,
        created_at=now,
        updated_at=now,
    )
    db.add(run)
    await db.flush()
    return run


async def _complete_analysis_run(
    db: AsyncSession,
    run: MailAnalysisRun,
    project: Project,
    user: User,
    threads: list[dict[str, Any]],
    stats_extra: dict[str, Any] | None = None,
    structured_by_ref: dict[str, dict[str, Any]] | None = None,
) -> None:
    policy = await _get_policy(db, project.id, user.id)
    categories = _loads(policy.categories_json, []) if policy else []
    filters = _loads(policy.filters_json, []) if policy else []
    management_policy = _mail_management_policy_store(project.workspace_path).load(user.id)
    analysis = analyze_mail_threads(
        threads,
        filters=filters,
        categories=categories,
        structured_by_ref=structured_by_ref,
        management_policy=management_policy,
    )
    if stats_extra:
        analysis["stats"].update(stats_extra)
    analysis["stats"]["stage"] = "completed"
    now = _now()
    run.status = "completed"
    run.stats_json = _dumps(analysis["stats"])
    run.proposed_categories_json = _dumps(analysis["proposed_categories"])
    run.proposed_filters_json = _dumps(analysis["proposed_filters"])
    run.updated_at = now
    await db.execute(
        delete(MailThreadStaging).where(
            MailThreadStaging.run_id == run.id,
            MailThreadStaging.project_id == project.id,
            MailThreadStaging.user_id == user.id,
        )
    )

    for thread in analysis["threads"]:
        db.add(MailThreadStaging(
            run_id=run.id,
            project_id=project.id,
            user_id=user.id,
            source_ref=thread["source_ref"],
            subject=thread["subject"],
            sender=thread["sender"],
            recipients_json=_dumps(thread["recipients"]),
            received_at=thread["received_at"],
            summary=thread["summary"],
            category=thread["category"],
            attachments_json=_dumps(thread["attachments"]),
            inclusion_decision=thread["inclusion_decision"],
            metadata_json=_dumps(thread["metadata"] | {"matched_filter_ids": thread["matched_filter_ids"]}),
            created_at=now,
            updated_at=now,
        ))


def _schedule_analysis_job(project_id: str, user_id: str, run_id: str, request_payload: dict[str, Any]) -> None:
    task = asyncio.create_task(_run_analysis_job(project_id, user_id, run_id, request_payload))
    _RUNNING_ANALYSIS_TASKS[run_id] = task
    task.add_done_callback(lambda finished: _finish_analysis_task(run_id, finished))


def _finish_analysis_task(run_id: str, task: asyncio.Task) -> None:
    _RUNNING_ANALYSIS_TASKS.pop(run_id, None)
    if task.cancelled():
        return
    exc = task.exception()
    if exc:
        print(f"[mail-analysis] background task failed for run {run_id}: {exc}")


async def _run_analysis_job(project_id: str, user_id: str, run_id: str, request_payload: dict[str, Any]) -> None:
    stage = "queued"
    session_factory = database.async_session_factory
    if session_factory is None:
        print(f"[mail-analysis] DB session factory is not initialized for run {run_id}")
        return
    try:
        async with session_factory() as db:
            body = AnalyzeRecentRequest.model_validate(request_payload)
            user = await _get_user(db, user_id)
            project = await _get_project(db, user.id, project_id)
            run = await _get_run(db, project.id, user.id, run_id)
            connection = await _get_connection(db, project.id, user.id)

            stage = "fetching"
            await _set_run_progress(db, run, "fetching", stage)
            payloads = await _recent_thread_payloads(project, user, connection, body)
            if connection and payloads.fetched_at:
                connection.last_sync_at = payloads.fetched_at
                connection.updated_at = payloads.fetched_at
                await db.commit()

            stage = "normalizing"
            await _set_run_progress(db, run, "normalizing", stage)

            stage = "attachment_downloading"
            await _set_run_progress(db, run, "attachment_downloading", stage)
            attachment_stats = AttachmentProcessingStats()
            if connection and connection.token_ref:
                stage = "attachment_extracting"
                await _set_run_progress(db, run, "attachment_extracting", stage)
                account_email = connection.email or user.email
                attachment_stats = await _mail_attachment_processor().process_threads(
                    workspace_path=project.workspace_path,
                    user_id=user.id,
                    token_ref=connection.token_ref,
                    account_email=account_email,
                    threads=payloads.threads,
                    gmail_fetcher=_gmail_fetcher(),
                    management_policy=_mail_management_policy_store(project.workspace_path).load(user.id),
                )
                _mail_snapshot_store(project.workspace_path).upsert_threads(
                    account_email,
                    payloads.threads,
                    fetched_at=payloads.fetched_at or connection.last_sync_at or _now(),
                )

            stage = "structuring"
            await _set_run_progress(db, run, "structuring", stage)
            structuring = await _mail_structuring_service().structure_threads(payloads.threads)

            stage = "indexing"
            await _set_run_progress(db, run, "indexing", stage)
            completion_threads = await _completion_thread_payloads(
                db,
                project,
                user,
                payloads.threads,
                base_run_id=str(request_payload.get("base_run_id") or ""),
            )
            existing_stats = _loads(run.stats_json, {})
            await _complete_analysis_run(
                db,
                run,
                project,
                user,
                completion_threads,
                stats_extra={
                    **_preserved_run_stats(existing_stats),
                    "cache_status": payloads.cache_status,
                    "llm_structure_warning_count": structuring.warning_count,
                    "attachment_downloaded_count": attachment_stats.downloaded_count,
                    "attachment_summarized_count": attachment_stats.summarized_count,
                    "attachment_extract_failed_count": attachment_stats.failed_count,
                },
                structured_by_ref=structuring.structured_by_ref,
            )
            await db.commit()
    except GmailAuthError as exc:
        await _mark_connection_needs_oauth(project_id, user_id)
        await _mark_run_failed(run_id, project_id, user_id, stage, str(exc))
    except GmailFetchError as exc:
        await _mark_run_failed(run_id, project_id, user_id, stage, str(exc))
    except HTTPException as exc:
        await _mark_run_failed(run_id, project_id, user_id, stage, str(exc.detail))
    except Exception as exc:
        print(f"[mail-analysis] failed at {stage} for run {run_id}: {exc}")
        await _mark_run_failed(run_id, project_id, user_id, stage, "메일 분석 작업 중 오류가 발생했습니다.")


async def _completion_thread_payloads(
    db: AsyncSession,
    project: Project,
    user: User,
    new_threads: list[dict[str, Any]],
    *,
    base_run_id: str,
) -> list[dict[str, Any]]:
    if not base_run_id:
        return new_threads
    base_run = await _get_run(db, project.id, user.id, base_run_id)
    base_threads = _payloads_from_rows(await _cumulative_thread_rows(db, base_run))
    return _merge_thread_payloads(base_threads, new_threads)


async def _cumulative_thread_rows(db: AsyncSession, run: MailAnalysisRun) -> list[Any]:
    rows = await _analysis_threads(db, run)
    if not run.source_run_id:
        return rows
    result = await db.execute(
        select(MailAnalysisRun).where(
            MailAnalysisRun.id == run.source_run_id,
            MailAnalysisRun.project_id == run.project_id,
            MailAnalysisRun.user_id == run.user_id,
        )
    )
    source_run = result.scalar_one_or_none()
    if not source_run:
        return rows
    return _merge_thread_rows(await _cumulative_thread_rows(db, source_run), rows)


def _merge_thread_rows(base_rows: list[Any], new_rows: list[Any]) -> list[Any]:
    by_ref: dict[str, Any] = {}
    for row in [*base_rows, *new_rows]:
        source_ref = _row_source_ref(row)
        if source_ref:
            by_ref[source_ref] = row
    rows = list(by_ref.values())
    rows.sort(key=lambda item: _row_received_at(item), reverse=True)
    return rows


def _payloads_from_rows(rows: list[Any]) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for row in rows:
        payloads.append(row if isinstance(row, dict) else thread_payload_from_staging(row))
    return payloads


def _row_source_ref(row: Any) -> str:
    if isinstance(row, dict):
        return str(row.get("source_ref") or "")
    return str(getattr(row, "source_ref", "") or "")


def _row_received_at(row: Any) -> str:
    if isinstance(row, dict):
        return str(row.get("received_at") or "")
    return str(getattr(row, "received_at", "") or "")


def _merge_thread_payloads(base_threads: list[dict[str, Any]], new_threads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_ref: dict[str, dict[str, Any]] = {}
    for thread in base_threads:
        source_ref = str(thread.get("source_ref") or "")
        if source_ref:
            by_ref[source_ref] = thread
    for thread in new_threads:
        source_ref = str(thread.get("source_ref") or "")
        if source_ref:
            by_ref[source_ref] = thread
    rows = list(by_ref.values())
    rows.sort(key=lambda item: str(item.get("received_at") or ""), reverse=True)
    return rows


def _preserved_run_stats(stats: dict[str, Any]) -> dict[str, Any]:
    keys = {
        "incremental",
        "source_run_id",
        "scan_limit",
        "new_count",
        "since_received_at",
        "requested_count",
        "force_refresh",
    }
    return {key: stats[key] for key in keys if key in stats}


async def _set_run_progress(db: AsyncSession, run: MailAnalysisRun, status_value: str, stage: str) -> None:
    stats = _loads(run.stats_json, {})
    stats["stage"] = stage
    run.status = status_value
    run.stats_json = _dumps(stats)
    run.updated_at = _now()
    await db.commit()
    await db.refresh(run)


async def _mark_run_failed(
    run_id: str,
    project_id: str,
    user_id: str,
    stage: str,
    message: str,
) -> None:
    session_factory = database.async_session_factory
    if session_factory is None:
        return
    async with session_factory() as db:
        result = await db.execute(
            select(MailAnalysisRun).where(
                MailAnalysisRun.id == run_id,
                MailAnalysisRun.project_id == project_id,
                MailAnalysisRun.user_id == user_id,
            )
        )
        run = result.scalar_one_or_none()
        if not run:
            return
        stats = _loads(run.stats_json, {})
        stats["stage"] = stage
        stats["error"] = {"stage": stage, "message": message}
        run.status = "failed"
        run.stats_json = _dumps(stats)
        run.updated_at = _now()
        await db.commit()


async def _mark_connection_needs_oauth(project_id: str, user_id: str) -> None:
    session_factory = database.async_session_factory
    if session_factory is None:
        return
    async with session_factory() as db:
        connection = await _get_connection(db, project_id, user_id)
        if not connection:
            return
        connection.status = "needs_oauth"
        connection.updated_at = _now()
        await db.commit()


async def _recent_thread_payloads(
    project: Project,
    user: User,
    connection: MailConnection | None,
    body: AnalyzeRecentRequest,
) -> RecentThreadPayloads:
    provided_threads = [thread.model_dump() for thread in body.threads]
    if provided_threads:
        return RecentThreadPayloads(
            threads=provided_threads,
            cache_status={
                "source": "request_body",
                "hit": False,
                "requested_count": body.max_threads,
                "provided_count": len(provided_threads),
                "force_refresh": body.force_refresh,
            },
        )
    if not connection or connection.status != "connected" or not connection.token_ref:
        raise HTTPException(status_code=409, detail="Gmail connection is required")

    account_email = connection.email or user.email
    store = _mail_snapshot_store(project.workspace_path)
    cached_threads = [] if body.force_refresh else store.load_recent_threads(account_email, body.max_threads)
    if len(cached_threads) >= body.max_threads:
        return RecentThreadPayloads(
            threads=cached_threads[:body.max_threads],
            cache_status={
                "source": "cache",
                "hit": True,
                "requested_count": body.max_threads,
                "cached_count": len(cached_threads),
                "fetched_count": 0,
                "force_refresh": False,
            },
        )

    fetch_result = await _gmail_fetcher().fetch_recent_threads(
        token_ref=connection.token_ref,
        account_email=account_email,
        max_threads=body.max_threads,
    )
    store_result = store.upsert_threads(account_email, fetch_result.threads, fetched_at=fetch_result.fetched_at)
    latest_threads = store.load_recent_threads(account_email, body.max_threads)
    return RecentThreadPayloads(
        threads=latest_threads,
        fetched_at=fetch_result.fetched_at,
        cache_status={
            "source": "gmail_fetch" if body.force_refresh else "cache_miss",
            "hit": False,
            "requested_count": body.max_threads,
            "cached_count_before": len(cached_threads),
            "cached_count_after": len(latest_threads),
            "fetched_count": len(fetch_result.threads),
            "stored_count": store_result["stored_count"],
            "force_refresh": body.force_refresh,
            "updated_at": fetch_result.fetched_at,
        },
    )


async def _incremental_thread_preview(
    db: AsyncSession,
    project: Project,
    user: User,
    connection: MailConnection,
    latest_run: MailAnalysisRun,
    scan_limit: int,
) -> dict[str, Any]:
    account_email = connection.email or user.email
    fetch_result = await _gmail_fetcher().fetch_recent_threads(
        token_ref=connection.token_ref,
        account_email=account_email,
        max_threads=scan_limit,
    )
    store_result = _mail_snapshot_store(project.workspace_path).upsert_threads(
        account_email,
        fetch_result.threads,
        fetched_at=fetch_result.fetched_at,
    )
    connection.last_sync_at = fetch_result.fetched_at
    connection.updated_at = fetch_result.fetched_at

    processed_threads = await _cumulative_thread_rows(db, latest_run)
    processed_refs = {_row_source_ref(thread) for thread in processed_threads if _row_source_ref(thread)}
    since_received_at = latest_processed_received_at(processed_threads)
    new_threads = filter_new_threads(
        fetch_result.threads,
        since_received_at=since_received_at,
        processed_source_refs=processed_refs,
    )
    return {
        "latest_run": _run_summary(latest_run),
        "since_received_at": since_received_at,
        "new_count": len(new_threads),
        "scan_limit": scan_limit,
        "fetched_count": len(fetch_result.threads),
        "fetched_at": fetch_result.fetched_at,
        "cache_status": {
            "source": "gmail_fetch",
            "stored_count": store_result["stored_count"],
            "cached_count_after": store_result["cached_count"],
            "updated_at": store_result["updated_at"],
        },
        "threads": new_threads,
    }


def _incremental_preview_response(preview: dict[str, Any]) -> dict[str, Any]:
    return {
        **{key: value for key, value in preview.items() if key != "threads"},
        "threads": [
            {
                "source_ref": thread.get("source_ref"),
                "subject": thread.get("subject"),
                "sender": thread.get("sender"),
                "received_at": thread.get("received_at"),
                "summary": thread.get("summary"),
                "attachment_count": len(thread.get("attachments") or []),
            }
            for thread in preview.get("threads") or []
        ],
    }


async def _reapply_management_policy(
    db: AsyncSession,
    run: MailAnalysisRun,
    project: Project,
    user: User,
    policy: dict[str, Any],
) -> None:
    threads = await _analysis_threads(db, run)
    for thread in threads:
        payload = thread_payload_from_staging(thread)
        payload["id"] = thread.id
        updated_payload = apply_management_to_thread(payload, policy)
        metadata = updated_payload["metadata"]
        thread.attachments_json = _dumps(updated_payload["attachments"])
        thread.inclusion_decision = updated_payload["inclusion_decision"]
        thread.metadata_json = _dumps(metadata | {"matched_filter_ids": metadata.get("matched_filter_ids", [])})
        thread.updated_at = _now()
    await _refresh_run_stats(db, run)
    await db.commit()


async def _refresh_run_stats(db: AsyncSession, run: MailAnalysisRun) -> None:
    threads = await _analysis_threads(db, run)
    stats = _loads(run.stats_json, {})
    managed_count = 0
    excluded_count = 0
    attachment_primary_count = 0
    manual_managed_count = 0
    llm_excluded_count = 0
    for thread in threads:
        metadata = _loads(thread.metadata_json, {})
        decision = metadata.get("management_decision")
        if decision == "excluded":
            excluded_count += 1
        else:
            managed_count += 1
        if metadata.get("primary_context_source") == "attachment":
            attachment_primary_count += 1
        if metadata.get("decision_source") == "manual_override":
            manual_managed_count += 1
        if metadata.get("decision_source") == "llm_blacklist":
            llm_excluded_count += 1
    stats.update({
        "managed_count": managed_count,
        "excluded_count": excluded_count,
        "attachment_primary_count": attachment_primary_count,
        "manual_managed_count": manual_managed_count,
        "llm_excluded_count": llm_excluded_count,
    })
    run.stats_json = _dumps(stats)
    run.updated_at = _now()


async def _analysis_response(db: AsyncSession, run: MailAnalysisRun) -> dict[str, Any]:
    await _mark_orphaned_run_failed(db, run)
    threads = await _visible_analysis_threads(db, run)
    return {
        "run": _run_summary(run),
        "stats": _loads(run.stats_json, {}),
        "proposed_categories": _loads(run.proposed_categories_json, []),
        "proposed_filters": _loads(run.proposed_filters_json, []),
        "threads": [_thread_response(thread) for thread in threads],
    }


async def _analysis_threads(db: AsyncSession, run: MailAnalysisRun) -> list[MailThreadStaging]:
    if run.status != "completed":
        return []
    result = await db.execute(
        select(MailThreadStaging)
        .where(MailThreadStaging.run_id == run.id)
        .order_by(MailThreadStaging.received_at.desc())
    )
    return list(result.scalars().all())


async def _visible_analysis_threads(db: AsyncSession, run: MailAnalysisRun) -> list[MailThreadStaging]:
    if run.status != "completed":
        return []
    return [row for row in await _cumulative_thread_rows(db, run) if isinstance(row, MailThreadStaging)]


async def _mark_orphaned_run_failed(db: AsyncSession, run: MailAnalysisRun) -> None:
    if run.status not in _ACTIVE_RUN_STATUSES or run.id in _RUNNING_ANALYSIS_TASKS:
        return
    await db.refresh(run)
    if run.status not in _ACTIVE_RUN_STATUSES or run.id in _RUNNING_ANALYSIS_TASKS:
        return
    if not _is_orphaned_run_stale(run):
        return
    stats = _loads(run.stats_json, {})
    stage = str(stats.get("stage") or run.status)
    stats["stage"] = stage
    stats["error"] = {
        "stage": stage,
        "message": "분석 작업이 중단되었습니다. 다시 시도해 주세요.",
    }
    run.status = "failed"
    run.stats_json = _dumps(stats)
    run.updated_at = _now()
    await db.commit()
    await db.refresh(run)


def _is_orphaned_run_stale(run: MailAnalysisRun) -> bool:
    timestamp = run.updated_at or run.created_at
    try:
        updated_at = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
    except ValueError:
        return True
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - updated_at >= timedelta(seconds=_ORPHANED_RUN_GRACE_SECONDS)


async def _get_project(db: AsyncSession, user_id: str, project_id: str) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id, Project.user_id == user_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def _get_user(db: AsyncSession, user_id: str) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


async def _get_connection(db: AsyncSession, project_id: str, user_id: str) -> MailConnection | None:
    result = await db.execute(
        select(MailConnection).where(
            MailConnection.project_id == project_id,
            MailConnection.user_id == user_id,
            MailConnection.provider == "gmail",
        )
    )
    return result.scalar_one_or_none()


async def _get_policy(db: AsyncSession, project_id: str, user_id: str) -> MailPolicy | None:
    result = await db.execute(
        select(MailPolicy).where(
            MailPolicy.project_id == project_id,
            MailPolicy.user_id == user_id,
            MailPolicy.provider == "gmail",
        )
    )
    return result.scalar_one_or_none()


async def _latest_run(db: AsyncSession, project_id: str, user_id: str) -> MailAnalysisRun | None:
    result = await db.execute(
        select(MailAnalysisRun)
        .where(MailAnalysisRun.project_id == project_id, MailAnalysisRun.user_id == user_id)
        .order_by(desc(MailAnalysisRun.created_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _latest_completed_run(db: AsyncSession, project_id: str, user_id: str) -> MailAnalysisRun | None:
    result = await db.execute(
        select(MailAnalysisRun)
        .where(
            MailAnalysisRun.project_id == project_id,
            MailAnalysisRun.user_id == user_id,
            MailAnalysisRun.status == "completed",
        )
        .order_by(desc(MailAnalysisRun.created_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _get_run(db: AsyncSession, project_id: str, user_id: str, run_id: str | None) -> MailAnalysisRun:
    if not run_id:
        raise HTTPException(status_code=404, detail="Analysis run not found")
    result = await db.execute(
        select(MailAnalysisRun).where(
            MailAnalysisRun.id == run_id,
            MailAnalysisRun.project_id == project_id,
            MailAnalysisRun.user_id == user_id,
        )
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Analysis run not found")
    return run


async def _get_analysis_thread_row(
    db: AsyncSession,
    project: Project,
    user: User,
    run: MailAnalysisRun,
    thread_id: str,
) -> MailThreadStaging:
    result = await db.execute(
        select(MailThreadStaging).where(
            MailThreadStaging.id == thread_id,
            MailThreadStaging.run_id == run.id,
            MailThreadStaging.project_id == project.id,
            MailThreadStaging.user_id == user.id,
        )
    )
    thread = result.scalar_one_or_none()
    if not thread:
        for candidate in await _visible_analysis_threads(db, run):
            if candidate.id == thread_id and candidate.project_id == project.id and candidate.user_id == user.id:
                return candidate
        raise HTTPException(status_code=404, detail="Mail thread not found")
    return thread


def _connection_response(connection: MailConnection) -> dict[str, Any]:
    return {
        "id": connection.id,
        "provider": connection.provider,
        "email": connection.email,
        "status": connection.status,
        "live_status": connection.live_status,
        "live_poll_interval_minutes": connection.live_poll_interval_minutes,
        "last_sync_at": connection.last_sync_at,
        "created_at": connection.created_at,
        "updated_at": connection.updated_at,
    }


def _gmail_oauth_service() -> GmailOAuthService:
    return GmailOAuthService(
        client_id=settings.google_gmail_client_id,
        client_secret=settings.google_gmail_client_secret,
        redirect_uri=settings.google_gmail_redirect_uri,
        scopes=settings.google_gmail_scopes,
        state_secret=settings.google_oauth_state_secret or settings.jwt_secret,
        timeout_seconds=settings.google_oauth_timeout_seconds,
    )


def _token_store() -> EncryptedTokenStore:
    return EncryptedTokenStore(
        directory=settings.mail_token_store_dir,
        encryption_key=settings.mail_token_encryption_key,
    )


def _gmail_fetcher() -> GmailFetcher:
    return GmailFetcher(
        token_store=_token_store(),
        client_id=settings.google_gmail_client_id,
        client_secret=settings.google_gmail_client_secret,
        timeout_seconds=settings.google_oauth_timeout_seconds,
    )


def _mail_snapshot_store(workspace: str) -> MailSnapshotStore:
    return MailSnapshotStore(workspace)


def _mail_structuring_service() -> MailStructuringService:
    return MailStructuringService()


def _mail_attachment_processor() -> MailAttachmentProcessor:
    return MailAttachmentProcessor()


def _mail_management_policy_store(workspace: str) -> MailManagementPolicyStore:
    return MailManagementPolicyStore(workspace)


def _policy_response(policy: MailPolicy | None) -> dict[str, Any]:
    if not policy:
        return {"categories": [], "filters": []}
    return {"categories": _loads(policy.categories_json, []), "filters": _loads(policy.filters_json, [])}


def _run_summary(run: MailAnalysisRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "provider": run.provider,
        "status": run.status,
        "range_start": run.range_start,
        "range_end": run.range_end,
        "source_run_id": run.source_run_id,
        "created_at": run.created_at,
        "updated_at": run.updated_at,
    }


def _require_completed_run(run: MailAnalysisRun) -> None:
    if run.status != "completed":
        raise HTTPException(status_code=409, detail=f"Gmail 분석이 아직 완료되지 않았습니다. 현재 상태: {run.status}")


def _allowed_value(value: str, allowed: set[str], fallback: str) -> str:
    normalized = str(value or "").strip().casefold()
    return normalized if normalized in allowed else fallback


def _structure_test_response(row: MailStructureTest) -> dict[str, Any]:
    return {
        "id": row.id,
        "run_id": row.run_id,
        "query": row.query,
        "result_kind": row.result_kind,
        "rating": row.rating,
        "notes": row.notes,
        "result": _loads(row.result_json, {}),
        "created_at": row.created_at,
    }


def _improvement_candidate_response(row: MailImprovementCandidate) -> dict[str, Any]:
    return {
        "id": row.id,
        "run_id": row.run_id,
        "title": row.title,
        "reason": row.reason,
        "priority": row.priority,
        "source": row.source,
        "status": row.status,
        "query": row.query,
        "thread_ids": _loads(row.thread_ids_json, []),
        "evidence": _loads(row.evidence_json, []),
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _thread_response(
    thread: MailThreadStaging,
    *,
    snapshot_detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "id": thread.id,
        "subject": thread.subject,
        "sender": thread.sender,
        "recipients": _loads(thread.recipients_json, []),
        "received_at": thread.received_at,
        "summary": thread.summary,
        "category": thread.category,
        "attachments": _response_attachments(_loads(thread.attachments_json, [])),
        "inclusion_decision": thread.inclusion_decision,
        "promoted_at": thread.promoted_at,
        "clean_room_path": thread.clean_room_path,
        "metadata": _loads(thread.metadata_json, {}),
    }
    if snapshot_detail is not None:
        payload.update(snapshot_detail)
    return payload


def _thread_snapshot_detail(
    project: Project,
    user: User,
    thread: MailThreadStaging,
    connection: MailConnection | None,
) -> dict[str, Any]:
    account_email = (connection.email if connection else None) or user.email
    snapshot = None
    if account_email:
        try:
            snapshot = _mail_snapshot_store(project.workspace_path).load_thread(account_email, thread.source_ref)
        except Exception:
            snapshot = None

    if isinstance(snapshot, dict):
        body = normalize_mail_body_text(str(snapshot.get("body") or ""))
        body_html = str(snapshot.get("body_html") or "")
        attachments = (
            _response_attachments(snapshot.get("attachments"))
            if isinstance(snapshot.get("attachments"), list)
            else None
        )
        return {
            "body": body,
            "body_source": "snapshot" if body else "none",
            "body_truncated": len(body) >= BODY_LIMIT,
            "body_html": body_html,
            "body_html_source": "snapshot" if body_html else "none",
            "body_html_truncated": len(body_html) >= HTML_BODY_LIMIT,
            "attachments": attachments if attachments is not None else _loads(thread.attachments_json, []),
            "attachment_source": "snapshot" if attachments is not None else "staging",
        }

    metadata = _loads(thread.metadata_json, {})
    body_sample = normalize_mail_body_text(str(metadata.get("body_sample") or ""))
    return {
        "body": body_sample,
        "body_source": "staging_sample" if body_sample else "none",
        "body_truncated": bool(body_sample),
        "body_html": "",
        "body_html_source": "none",
        "body_html_truncated": False,
        "attachment_source": "staging",
    }


def _response_attachments(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for attachment in value if isinstance(value, list) else []:
        if not isinstance(attachment, dict):
            continue
        row = _public_attachment(attachment)
        row.setdefault("summary", "")
        row.setdefault("summarized", bool(row.get("summary")))
        rows.append(row)
    return rows


def _public_attachment(attachment: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in dict(attachment).items()
        if not str(key).startswith("_gmail_") and key not in {"gmail_message_id", "gmail_attachment_id", "raw_gmail_id"}
    }


def _attachment_detail_response(thread: MailThreadStaging, attachment: dict[str, Any]) -> dict[str, Any]:
    row = _public_attachment(attachment)
    row["thread_id"] = thread.id
    row["thread_subject"] = thread.subject
    row["received_at"] = thread.received_at
    row.setdefault("summary", "")
    row.setdefault("key_points", [])
    row.setdefault("content_profile", {})
    return row


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _loads(value: str, default: Any) -> Any:
    try:
        return json.loads(value or "")
    except (TypeError, json.JSONDecodeError):
        return default


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
