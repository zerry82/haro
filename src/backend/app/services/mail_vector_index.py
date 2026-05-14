from __future__ import annotations

import json
import re
import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from app.config import settings
from app.models.mail import MailThreadStaging
from app.services.llm import get_client


class MailVectorSearchUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class MailVectorHit:
    thread_id: str
    vector_score: float
    distance: float | None
    document: str
    evidence: list[dict[str, str]]


class GeminiEmbeddingProvider:
    def __init__(
        self,
        *,
        model: str | None = None,
        client_factory: Callable[[], Any] = get_client,
    ) -> None:
        self.model = model or settings.mail_vector_embedding_model
        self.client_factory = client_factory

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not settings.gemini_api_key:
            raise MailVectorSearchUnavailable("GEMINI_API_KEY is required for mail vector search")
        if not texts:
            return []
        response = self.client_factory().models.embed_content(model=self.model, contents=texts)
        embeddings = getattr(response, "embeddings", None) or []
        vectors = [_embedding_values(embedding) for embedding in embeddings]
        if len(vectors) != len(texts):
            raise MailVectorSearchUnavailable("mail embedding response size mismatch")
        return vectors


class MailVectorSearchStore:
    def __init__(
        self,
        workspace_path: str,
        *,
        embedding_provider: GeminiEmbeddingProvider | None = None,
        client_factory: Callable[[str], Any] | None = None,
        enabled: bool | None = None,
    ) -> None:
        self.workspace_path = Path(workspace_path).resolve()
        self.root = self.workspace_path / ".haro" / "db" / "chroma" / "mail"
        self.embedding_provider = embedding_provider or GeminiEmbeddingProvider()
        self.client_factory = client_factory or _persistent_client
        self.enabled = settings.mail_vector_search_enabled if enabled is None else enabled

    def search(
        self,
        *,
        run_id: str,
        threads: list[MailThreadStaging],
        query: str,
        limit: int,
    ) -> list[MailVectorHit]:
        if not self.enabled:
            raise MailVectorSearchUnavailable("mail vector search is disabled")
        query = query.strip()
        if not query or not threads:
            return []
        self.root.mkdir(parents=True, exist_ok=True)
        collection_name = _collection_name(run_id)
        collection = self.client_factory(str(self.root)).get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self._ensure_index(collection_name, collection, threads, run_id=run_id)
        query_embedding = self.embedding_provider.embed([query])[0]
        raw = collection.query(
            query_embeddings=[query_embedding],
            n_results=max(1, min(limit, 50)),
            include=["documents", "metadatas", "distances"],
        )
        return _parse_query_result(raw)

    def index_run(self, *, run_id: str, threads: list[MailThreadStaging]) -> dict[str, Any]:
        if not self.enabled:
            raise MailVectorSearchUnavailable("mail vector search is disabled")
        self.root.mkdir(parents=True, exist_ok=True)
        collection_name = _collection_name(run_id)
        collection = self.client_factory(str(self.root)).get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self._ensure_index(collection_name, collection, threads, run_id=run_id)
        return {"collection": collection_name, "indexed_count": len(threads)}

    def _ensure_index(
        self,
        collection_name: str,
        collection: Any,
        threads: list[MailThreadStaging],
        *,
        run_id: str,
    ) -> None:
        signature = _index_signature(threads)
        manifest_path = self._manifest_path(collection_name)
        if _index_is_current(manifest_path, collection, signature, len(threads)):
            return
        self._upsert_threads(collection, threads, run_id=run_id)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps({"signature": signature, "thread_count": len(threads)}, ensure_ascii=False),
            encoding="utf-8",
        )

    def _upsert_threads(self, collection: Any, threads: list[MailThreadStaging], *, run_id: str) -> None:
        _delete_existing_run_docs(collection, run_id)
        if not threads:
            return
        documents = [build_mail_vector_document(thread) for thread in threads]
        embeddings = self.embedding_provider.embed(documents)
        collection.upsert(
            ids=[thread.id for thread in threads],
            documents=documents,
            embeddings=embeddings,
            metadatas=[_thread_metadata(thread) for thread in threads],
        )

    def _manifest_path(self, collection_name: str) -> Path:
        return self.root / "manifests" / f"{collection_name}.json"


def build_mail_vector_document(thread: MailThreadStaging) -> str:
    recipients = _loads(thread.recipients_json, [])
    attachments = _loads(thread.attachments_json, [])
    metadata = _loads(thread.metadata_json, {})
    core_text = str(metadata.get("mail_core_text") or "").strip()
    if core_text:
        return core_text
    lines = [
        f"제목: {thread.subject}",
        f"보낸사람: {thread.sender}",
        f"받는사람: {'; '.join(str(item) for item in recipients)}",
        f"카테고리: {thread.category}",
        f"요약: {thread.summary}",
        f"요청사항: {_json_text(metadata.get('extracted_actions'))}",
        f"마감/일정: {_json_text(metadata.get('extracted_due_dates'))}",
        f"첨부파일: {_attachment_text(attachments)}",
        f"참조 링크: {_json_text(metadata.get('external_links'))}",
        f"구조화 경고: {_json_text(metadata.get('structure_warnings'))}",
    ]
    return "\n".join(line for line in lines if line.split(":", 1)[1].strip())


def merge_vector_and_text_results(
    threads: list[MailThreadStaging],
    *,
    vector_hits: list[MailVectorHit],
    text_items: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    base_items = {thread.id: _minimal_thread_item(thread) for thread in threads}
    text_by_id = {str(item.get("thread_id") or item.get("id")): item for item in text_items}
    vector_by_id = {hit.thread_id: hit for hit in vector_hits}
    max_text_score = max((float(item.get("score") or 0) for item in text_items), default=1.0) or 1.0

    candidate_ids: list[str] = []
    for hit in vector_hits:
        if hit.thread_id not in candidate_ids:
            candidate_ids.append(hit.thread_id)
    for item in text_items:
        thread_id = str(item.get("thread_id") or item.get("id") or "")
        if thread_id and thread_id not in candidate_ids:
            candidate_ids.append(thread_id)

    rows: list[tuple[float, str, dict[str, Any]]] = []
    for thread_id in candidate_ids:
        item = dict(text_by_id.get(thread_id) or base_items.get(thread_id) or {})
        if not item:
            continue
        text_score = float(text_by_id.get(thread_id, {}).get("score") or 0)
        text_component = (text_score / max_text_score) * 30.0 if text_score > 0 else 0.0
        hit = vector_by_id.get(thread_id)
        vector_component = (hit.vector_score * 70.0) if hit else 0.0
        hybrid_score = round(vector_component + text_component, 4)
        evidence = []
        matched_fields = []
        if hit:
            evidence.extend(hit.evidence)
            matched_fields.append("semantic_vector")
        evidence.extend(text_by_id.get(thread_id, {}).get("evidence") or [])
        matched_fields.extend(text_by_id.get(thread_id, {}).get("matched_fields") or [])
        item["score"] = hybrid_score
        item["matched_fields"] = _dedupe(matched_fields)
        item["evidence"] = _dedupe_evidence(evidence)[:5]
        item["retrieval"] = {
            "mode": "hybrid_vector",
            "vector_score": round(hit.vector_score, 4) if hit else 0.0,
            "vector_distance": hit.distance if hit else None,
            "text_score": text_score,
        }
        rows.append((hybrid_score, str(item.get("received_at") or ""), item))

    rows.sort(key=lambda row: (row[0], row[1]), reverse=True)
    return [item for _score, _received_at, item in rows[: max(1, min(limit, 50))]]


def _persistent_client(path: str) -> Any:
    try:
        import chromadb
    except ImportError as exc:
        raise MailVectorSearchUnavailable("chromadb package is not installed") from exc
    return chromadb.PersistentClient(path=path)


def _parse_query_result(raw: dict[str, Any]) -> list[MailVectorHit]:
    ids = _first(raw.get("ids"), [])
    documents = _first(raw.get("documents"), [])
    metadatas = _first(raw.get("metadatas"), [])
    distances = _first(raw.get("distances"), [])
    hits: list[MailVectorHit] = []
    for index, thread_id in enumerate(ids):
        document = str(documents[index] if index < len(documents) else "")
        metadata = metadatas[index] if index < len(metadatas) and isinstance(metadatas[index], dict) else {}
        distance = _float_or_none(distances[index] if index < len(distances) else None)
        hits.append(MailVectorHit(
            thread_id=str(metadata.get("thread_id") or thread_id),
            vector_score=_distance_to_score(distance),
            distance=distance,
            document=document,
            evidence=[{"field": "semantic_vector", "snippet": _compact(document, 220)}],
        ))
    return hits


def _collection_name(run_id: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", run_id).replace("-", "")
    return f"mail_{safe}"[:63].strip("_") or "mail_analysis"


def _delete_existing_run_docs(collection: Any, run_id: str) -> None:
    try:
        collection.delete(where={"run_id": run_id})
    except Exception:
        return


def _thread_metadata(thread: MailThreadStaging) -> dict[str, str]:
    metadata = _loads(thread.metadata_json, {})
    attachments = _loads(thread.attachments_json, [])
    attachment_signals = metadata.get("attachment_signals") if isinstance(metadata.get("attachment_signals"), dict) else {}
    return {
        "source": "mail",
        "project_id": thread.project_id,
        "run_id": thread.run_id,
        "thread_id": thread.id,
        "subject": thread.subject[:500],
        "sender": thread.sender[:255],
        "sender_domain": _sender_domain(thread.sender),
        "category": thread.category[:120],
        "received_at": thread.received_at,
        "primary_context_source": str(metadata.get("primary_context_source") or "body"),
        "attachment_count": str(len(attachments) or int(attachment_signals.get("count") or 0)),
        "attachment_summary_status": str(attachment_signals.get("summary_status") or "none"),
    }


def _index_signature(threads: list[MailThreadStaging]) -> str:
    payload = [
        {
            "id": thread.id,
            "updated_at": thread.updated_at,
            "subject": thread.subject,
            "summary": thread.summary,
            "metadata_json": thread.metadata_json,
            "attachments_json": thread.attachments_json,
            "inclusion_decision": thread.inclusion_decision,
        }
        for thread in sorted(threads, key=lambda item: item.id)
    ]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _index_is_current(manifest_path: Path, collection: Any, signature: str, thread_count: int) -> bool:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        collection_count = int(collection.count())
    except Exception:
        return False
    return (
        manifest.get("signature") == signature
        and int(manifest.get("thread_count") or 0) == thread_count
        and collection_count >= thread_count
    )


def _minimal_thread_item(thread: MailThreadStaging) -> dict[str, Any]:
    return {
        "id": thread.id,
        "thread_id": thread.id,
        "subject": thread.subject,
        "sender": thread.sender,
        "recipients": _loads(thread.recipients_json, []),
        "received_at": thread.received_at,
        "summary": thread.summary,
        "category": thread.category,
        "attachments": _loads(thread.attachments_json, []),
        "inclusion_decision": thread.inclusion_decision,
        "metadata": _loads(thread.metadata_json, {}),
    }


def _embedding_values(embedding: Any) -> list[float]:
    values = getattr(embedding, "values", None)
    if values is None and isinstance(embedding, dict):
        values = embedding.get("values") or embedding.get("embedding")
    if values is None:
        values = getattr(embedding, "embedding", None)
    if not isinstance(values, Iterable):
        raise MailVectorSearchUnavailable("mail embedding response does not include vector values")
    return [float(value) for value in values]


def _attachment_text(attachments: list[Any]) -> str:
    rows: list[str] = []
    for attachment in attachments:
        if not isinstance(attachment, dict):
            continue
        title = str(attachment.get("title") or "")
        extension = str(attachment.get("extension") or "")
        summary = str(attachment.get("summary") or "")
        key_points = " ".join(str(item) for item in attachment.get("key_points") or [] if str(item).strip())
        profile = attachment.get("content_profile") if isinstance(attachment.get("content_profile"), dict) else {}
        profile_text = " ".join(
            str(profile.get(key) or "")
            for key in ("text_preview", "image_description", "visible_text")
            if str(profile.get(key) or "").strip()
        )
        rows.append(" ".join(part for part in (title, extension, summary, key_points, profile_text) if part))
    return " / ".join(rows)


def _sender_domain(value: str) -> str:
    if "@" not in value:
        return ""
    return value.rsplit("@", 1)[1].strip(" >").casefold()


def _json_text(value: Any) -> str:
    if value in (None, [], {}):
        return ""
    return json.dumps(value, ensure_ascii=False, default=str)


def _loads(value: str, default: Any) -> Any:
    try:
        parsed = json.loads(value or "")
    except (TypeError, json.JSONDecodeError):
        return default
    return parsed if isinstance(parsed, type(default)) else default


def _first(value: Any, default: Any) -> Any:
    if isinstance(value, list) and value:
        return value[0]
    return default


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _distance_to_score(distance: float | None) -> float:
    if distance is None:
        return 0.0
    return max(0.0, min(1.0, 1.0 - distance))


def _compact(value: str, limit: int) -> str:
    compact = " ".join(str(value or "").split())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit - 1].rstrip()}..."


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def _dedupe_evidence(values: list[dict[str, str]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for value in values:
        key = (str(value.get("field") or ""), str(value.get("snippet") or ""))
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result
