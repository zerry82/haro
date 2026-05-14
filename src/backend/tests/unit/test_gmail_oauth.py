from __future__ import annotations

import pytest

from app.services.gmail_oauth import (
    EncryptedTokenStore,
    OAuthConfigurationError,
    OAuthStateError,
    append_query_param,
    create_oauth_state,
    normalize_return_url,
    verify_oauth_state,
)


def test_oauth_state_round_trips_signed_payload() -> None:
    state = create_oauth_state(
        project_id="project-1",
        user_id="user-1",
        return_url="http://localhost:5174/projects/project-1",
        secret="state-secret",
        now=100,
    )

    payload = verify_oauth_state(state, "state-secret", now=101)

    assert payload.project_id == "project-1"
    assert payload.user_id == "user-1"
    assert payload.return_url == "http://localhost:5174/projects/project-1"


def test_oauth_state_rejects_tampering_and_expiry() -> None:
    state = create_oauth_state(
        project_id="project-1",
        user_id="user-1",
        return_url="http://localhost:5174/projects/project-1",
        secret="state-secret",
        ttl_seconds=5,
        now=100,
    )
    payload_part, signature = state.split(".", 1)

    with pytest.raises(OAuthStateError):
        verify_oauth_state(f"{payload_part}x.{signature}", "state-secret", now=101)

    with pytest.raises(OAuthStateError):
        verify_oauth_state(state, "state-secret", now=106)


def test_normalize_return_url_allows_known_origins_and_relative_paths() -> None:
    allowed = "http://localhost:5174"

    assert normalize_return_url("/projects/p1", allowed_origins=allowed) == "http://localhost:5174/projects/p1"
    assert (
        normalize_return_url("http://127.0.0.1:5174/projects/p1", allowed_origins=allowed)
        == "http://127.0.0.1:5174/projects/p1"
    )
    assert (
        normalize_return_url("http://localhost:5341/projects/p1", allowed_origins=allowed)
        == "http://localhost:5341/projects/p1"
    )
    assert (
        normalize_return_url("http://127.0.0.1:8001/projects/p1", allowed_origins=allowed)
        == "http://127.0.0.1:8001/projects/p1"
    )

    with pytest.raises(OAuthConfigurationError):
        normalize_return_url("https://evil.example/callback", allowed_origins=allowed)


def test_normalize_return_url_does_not_allow_loopback_for_production_only_origins() -> None:
    with pytest.raises(OAuthConfigurationError):
        normalize_return_url("http://127.0.0.1:5174/projects/p1", allowed_origins="https://app.example.com")


def test_append_query_param_preserves_existing_query() -> None:
    assert append_query_param("http://localhost:5174/path?a=1", "gmail", "connected") == (
        "http://localhost:5174/path?a=1&gmail=connected"
    )


def test_encrypted_token_store_round_trips_without_plaintext(tmp_path) -> None:
    store = EncryptedTokenStore(str(tmp_path), "encryption-secret")
    payload = {"tokens": {"refresh_token": "refresh-token-secret"}, "email": "me@example.com"}

    store.store("gmail:connection-1", payload)
    stored_file = next(tmp_path.glob("*.bin"))

    assert b"refresh-token-secret" not in stored_file.read_bytes()
    assert store.load("gmail:connection-1") == payload
