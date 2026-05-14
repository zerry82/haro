from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db
from app.models.mail import MailConnection
from app.models.project import Project
from app.services.gmail_oauth import (
    EncryptedTokenStore,
    GmailOAuthService,
    OAuthConfigurationError,
    OAuthProviderError,
    OAuthStateError,
    TokenStoreConfigurationError,
    append_query_param,
)

router = APIRouter(prefix="/api/auth/google/gmail", tags=["auth"])


@router.get("/callback")
async def gmail_oauth_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not state:
        raise HTTPException(status_code=400, detail="Missing OAuth state")

    oauth = _gmail_oauth_service()
    try:
        oauth_state = oauth.verify_state(state)
    except OAuthConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except OAuthStateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if error:
        return _redirect(oauth_state.return_url, "gmail_error", "access_denied")
    if not code:
        return _redirect(oauth_state.return_url, "gmail_error", "missing_code")

    project = await _get_project(db, oauth_state.project_id, oauth_state.user_id)
    try:
        tokens = await oauth.exchange_code(code)
        access_token = str(tokens.get("access_token") or "")
        if not access_token:
            raise OAuthProviderError("Google token response did not include access_token")
        email = await oauth.fetch_profile_email(access_token)
        connection = await _upsert_connection(db, project, oauth_state.user_id, email)
        token_ref = f"gmail:{connection.id}"
        store = _token_store()
        tokens = _merge_existing_refresh_token(store, connection.token_ref, tokens)
        store.store(token_ref, _token_payload(tokens, email))
        connection.token_ref = token_ref
        connection.email = email
        connection.status = "connected"
        connection.updated_at = _now()
        await db.commit()
    except (OAuthConfigurationError, TokenStoreConfigurationError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except OAuthProviderError:
        await db.rollback()
        return _redirect(oauth_state.return_url, "gmail_error", "oauth_failed")

    return _redirect(oauth_state.return_url, "gmail", "connected")


async def _get_project(db: AsyncSession, project_id: str, user_id: str) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id, Project.user_id == user_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def _upsert_connection(db: AsyncSession, project: Project, user_id: str, email: str) -> MailConnection:
    result = await db.execute(
        select(MailConnection).where(
            MailConnection.project_id == project.id,
            MailConnection.user_id == user_id,
            MailConnection.provider == "gmail",
        )
    )
    now = _now()
    connection = result.scalar_one_or_none()
    if connection:
        connection.email = email
        connection.status = "connected"
        connection.updated_at = now
        return connection

    connection = MailConnection(
        project_id=project.id,
        user_id=user_id,
        email=email,
        status="connected",
        created_at=now,
        updated_at=now,
    )
    db.add(connection)
    await db.flush()
    return connection


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


def _token_payload(tokens: dict[str, Any], email: str) -> dict[str, Any]:
    token_data = dict(tokens)
    _stamp_expiry(token_data)
    return {
        "provider": "gmail",
        "email": email,
        "tokens": token_data,
        "updated_at": _now(),
    }


def _merge_existing_refresh_token(
    store: EncryptedTokenStore,
    token_ref: str | None,
    tokens: dict[str, Any],
) -> dict[str, Any]:
    if tokens.get("refresh_token") or not token_ref:
        return tokens
    try:
        existing = store.load(token_ref)
    except Exception:
        return tokens
    refresh_token = ((existing.get("tokens") or {}).get("refresh_token") or "")
    if not refresh_token:
        return tokens
    return {**tokens, "refresh_token": refresh_token}


def _stamp_expiry(tokens: dict[str, Any]) -> None:
    try:
        expires_in = int(tokens.get("expires_in") or 0)
    except (TypeError, ValueError):
        expires_in = 0
    if expires_in:
        tokens["expires_at"] = int(time.time()) + expires_in


def _redirect(return_url: str, key: str, value: str) -> RedirectResponse:
    return RedirectResponse(append_query_param(return_url, key, value), status_code=303)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
