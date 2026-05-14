from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx
from cryptography.fernet import Fernet, InvalidToken


class OAuthConfigurationError(RuntimeError):
    pass


class OAuthProviderError(RuntimeError):
    pass


class OAuthStateError(ValueError):
    pass


class TokenStoreConfigurationError(RuntimeError):
    pass


class TokenStoreError(RuntimeError):
    pass


@dataclass(frozen=True)
class OAuthState:
    project_id: str
    user_id: str
    return_url: str
    nonce: str
    expires_at: int


class GmailOAuthService:
    AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    PROFILE_URL = "https://gmail.googleapis.com/gmail/v1/users/me/profile"

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        scopes: str,
        state_secret: str,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.client_id = client_id.strip()
        self.client_secret = client_secret.strip()
        self.redirect_uri = redirect_uri.strip()
        self.scopes = scopes.strip()
        self.state_secret = state_secret.strip()
        self.timeout_seconds = timeout_seconds

    def build_authorization_url(self, *, project_id: str, user_id: str, return_url: str) -> str:
        self._ensure_configured()
        state = create_oauth_state(
            project_id=project_id,
            user_id=user_id,
            return_url=return_url,
            secret=self.state_secret,
        )
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": self.scopes,
            "access_type": "offline",
            "include_granted_scopes": "true",
            "prompt": "consent",
            "state": state,
        }
        return f"{self.AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> dict[str, Any]:
        self._ensure_configured()
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                self.TOKEN_URL,
                data={
                    "code": code,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": self.redirect_uri,
                    "grant_type": "authorization_code",
                },
                headers={"Accept": "application/json"},
            )
        return _json_or_provider_error(response, "Google OAuth token exchange failed")

    async def fetch_profile_email(self, access_token: str) -> str:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(
                self.PROFILE_URL,
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {access_token}",
                },
            )
        data = _json_or_provider_error(response, "Gmail profile lookup failed")
        email = str(data.get("emailAddress") or "").strip()
        if not email:
            raise OAuthProviderError("Gmail profile did not include emailAddress")
        return email

    def verify_state(self, state: str) -> OAuthState:
        return verify_oauth_state(state, self.state_secret)

    def _ensure_configured(self) -> None:
        missing = [
            name
            for name, value in {
                "GOOGLE_GMAIL_CLIENT_ID": self.client_id,
                "GOOGLE_GMAIL_CLIENT_SECRET": self.client_secret,
                "GOOGLE_GMAIL_REDIRECT_URI": self.redirect_uri,
                "GOOGLE_GMAIL_SCOPES": self.scopes,
                "GOOGLE_OAUTH_STATE_SECRET or JWT_SECRET": self.state_secret,
            }.items()
            if not value
        ]
        if missing:
            raise OAuthConfigurationError(f"Missing Gmail OAuth setting: {', '.join(missing)}")


class EncryptedTokenStore:
    def __init__(self, directory: str, encryption_key: str) -> None:
        key = encryption_key.strip()
        if not key:
            raise TokenStoreConfigurationError("MAIL_TOKEN_ENCRYPTION_KEY is required")
        self.directory = Path(directory)
        self._fernet = Fernet(_fernet_key(key))

    def store(self, token_ref: str, payload: dict[str, Any]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        self._path(token_ref).write_bytes(self._fernet.encrypt(encoded))

    def load(self, token_ref: str) -> dict[str, Any]:
        try:
            encrypted = self._path(token_ref).read_bytes()
            decrypted = self._fernet.decrypt(encrypted)
            data = json.loads(decrypted.decode("utf-8"))
        except FileNotFoundError as exc:
            raise TokenStoreError("Token reference not found") from exc
        except (InvalidToken, json.JSONDecodeError) as exc:
            raise TokenStoreError("Token reference could not be decrypted") from exc
        if not isinstance(data, dict):
            raise TokenStoreError("Token payload is invalid")
        return data

    def delete(self, token_ref: str) -> None:
        try:
            self._path(token_ref).unlink()
        except FileNotFoundError:
            return

    def _path(self, token_ref: str) -> Path:
        digest = hashlib.sha256(token_ref.encode("utf-8")).hexdigest()
        return self.directory / f"{digest}.bin"


def create_oauth_state(
    *,
    project_id: str,
    user_id: str,
    return_url: str,
    secret: str,
    ttl_seconds: int = 600,
    now: float | None = None,
) -> str:
    if not secret:
        raise OAuthConfigurationError("OAuth state secret is required")
    current = int(now if now is not None else time.time())
    payload = {
        "project_id": project_id,
        "user_id": user_id,
        "return_url": return_url,
        "nonce": secrets.token_urlsafe(16),
        "exp": current + ttl_seconds,
    }
    payload_part = _b64(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8"))
    signature = _sign(payload_part, secret)
    return f"{payload_part}.{signature}"


def verify_oauth_state(state: str, secret: str, *, now: float | None = None) -> OAuthState:
    if not secret:
        raise OAuthConfigurationError("OAuth state secret is required")
    try:
        payload_part, signature = state.split(".", 1)
    except ValueError as exc:
        raise OAuthStateError("OAuth state is malformed") from exc

    expected = _sign(payload_part, secret)
    if not hmac.compare_digest(signature, expected):
        raise OAuthStateError("OAuth state signature is invalid")

    try:
        payload = json.loads(_unb64(payload_part).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OAuthStateError("OAuth state payload is invalid") from exc

    expires_at = int(payload.get("exp") or 0)
    current = int(now if now is not None else time.time())
    if expires_at < current:
        raise OAuthStateError("OAuth state has expired")

    project_id = str(payload.get("project_id") or "").strip()
    user_id = str(payload.get("user_id") or "").strip()
    return_url = str(payload.get("return_url") or "").strip()
    nonce = str(payload.get("nonce") or "").strip()
    if not project_id or not user_id or not return_url or not nonce:
        raise OAuthStateError("OAuth state is missing required fields")
    return OAuthState(
        project_id=project_id,
        user_id=user_id,
        return_url=return_url,
        nonce=nonce,
        expires_at=expires_at,
    )


def normalize_return_url(return_url: str | None, *, allowed_origins: str) -> str:
    origins = [origin.strip().rstrip("/") for origin in allowed_origins.split(",") if origin.strip()]
    default_origin = origins[0] if origins else "http://localhost:5174"
    value = (return_url or "").strip()
    if not value:
        return default_origin
    if value.startswith("/"):
        return f"{default_origin}{value}"

    parsed = urlparse(value)
    origin = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
    if parsed.scheme in {"http", "https"} and _is_allowed_return_origin(origin, origins):
        return value
    raise OAuthConfigurationError("Return URL is not allowed")


def append_query_param(url: str, key: str, value: str) -> str:
    parsed = urlparse(url)
    query = parse_qsl(parsed.query, keep_blank_values=True)
    query.append((key, value))
    return urlunparse(parsed._replace(query=urlencode(query)))


def _json_or_provider_error(response: httpx.Response, message: str) -> dict[str, Any]:
    try:
        data = response.json()
    except ValueError:
        data = {}
    if response.status_code >= 400:
        detail = data.get("error_description") or data.get("error") or response.text
        raise OAuthProviderError(f"{message}: {detail}")
    if not isinstance(data, dict):
        raise OAuthProviderError(message)
    return data


def _is_allowed_return_origin(origin: str, allowed_origins: list[str]) -> bool:
    if origin in allowed_origins:
        return True
    return _is_loopback_origin(origin) and any(_is_loopback_origin(allowed) for allowed in allowed_origins)


def _is_loopback_origin(origin: str) -> bool:
    parsed = urlparse(origin)
    return parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}


def _fernet_key(secret: str) -> bytes:
    try:
        Fernet(secret.encode("utf-8"))
        return secret.encode("utf-8")
    except (ValueError, TypeError):
        return base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())


def _sign(payload_part: str, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload_part.encode("utf-8"), hashlib.sha256).digest()
    return _b64(digest)


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
