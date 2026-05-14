from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.services.prompt_bundle import PromptBundle, PromptSection
from app.services.prompt_cache import ensure_gemini_prompt_cache_sync, gemini_prompt_cache_key


class FakeCaches:
    def __init__(self, *, get_fails: bool = False, create_fails: bool = False) -> None:
        self.get_fails = get_fails
        self.create_fails = create_fails
        self.created = []
        self.got = []

    def create(self, *, model, config):
        if self.create_fails:
            raise RuntimeError("create boom")
        name = f"cachedContents/{len(self.created) + 1}"
        self.created.append((model, config))
        return SimpleNamespace(name=name)

    def get(self, *, name, config=None):
        self.got.append(name)
        if self.get_fails:
            raise RuntimeError("get boom")
        return SimpleNamespace(name=name)


def _bundle(runtime_text: str = "runtime") -> PromptBundle:
    return PromptBundle.from_sections([
        PromptSection("system_prompt.static_core", "static_core", "static", "static"),
        PromptSection("system_prompt.project_policy", "project_policy", "project", "project"),
        PromptSection("system_prompt.stable_tool_contract", "stable_tool_contract", "stable", "stable"),
        PromptSection("system_prompt.runtime_context", "runtime_context", runtime_text, "runtime"),
    ])


def test_gemini_prompt_cache_creates_and_reuses_within_ttl(tmp_path) -> None:
    now = datetime(2026, 5, 14, tzinfo=UTC)
    store_path = tmp_path / "cache.json"
    client = SimpleNamespace(caches=FakeCaches())

    first = ensure_gemini_prompt_cache_sync(
        _bundle(),
        "gemini-3-flash-preview",
        client=client,
        store_path=store_path,
        now=now,
    )
    second = ensure_gemini_prompt_cache_sync(
        _bundle(),
        "gemini-3-flash-preview",
        client=client,
        store_path=store_path,
        now=now + timedelta(seconds=30),
    )

    assert first.cache_state == "created"
    assert second.cache_state == "reused"
    assert second.cache_name == first.cache_name
    assert len(client.caches.created) == 1
    assert client.caches.got == [first.cache_name]
    assert first.generation_config("full").model_dump(exclude_none=True) == {
        "cached_content": first.cache_name,
        "temperature": 0.7,
    }
    created_model, created_config = client.caches.created[0]
    assert created_model == "gemini-3-flash-preview"
    assert getattr(created_config, "ttl") == "300s"
    assert "static" in str(getattr(created_config, "system_instruction"))
    assert "runtime" not in str(getattr(created_config, "system_instruction"))


def test_gemini_prompt_cache_recreates_expired_entry(tmp_path) -> None:
    now = datetime(2026, 5, 14, tzinfo=UTC)
    store_path = tmp_path / "cache.json"
    client = SimpleNamespace(caches=FakeCaches())

    ensure_gemini_prompt_cache_sync(_bundle(), "gemini-3-flash-preview", client=client, store_path=store_path, now=now)
    result = ensure_gemini_prompt_cache_sync(
        _bundle(),
        "gemini-3-flash-preview",
        client=client,
        store_path=store_path,
        now=now + timedelta(seconds=301),
    )

    assert result.cache_state == "expired_recreated"
    assert result.cache_name == "cachedContents/2"
    assert len(client.caches.created) == 2


def test_gemini_prompt_cache_recreates_stale_entry_when_get_fails(tmp_path) -> None:
    now = datetime(2026, 5, 14, tzinfo=UTC)
    store_path = tmp_path / "cache.json"
    client = SimpleNamespace(caches=FakeCaches())

    ensure_gemini_prompt_cache_sync(_bundle(), "gemini-3-flash-preview", client=client, store_path=store_path, now=now)
    client.caches.get_fails = True
    result = ensure_gemini_prompt_cache_sync(
        _bundle(),
        "gemini-3-flash-preview",
        client=client,
        store_path=store_path,
        now=now + timedelta(seconds=30),
    )

    assert result.cache_state == "stale_recreated"
    assert result.cache_name == "cachedContents/2"
    assert client.caches.got == ["cachedContents/1"]
    assert len(client.caches.created) == 2


def test_gemini_prompt_cache_falls_back_on_create_failure(tmp_path) -> None:
    client = SimpleNamespace(caches=FakeCaches(create_fails=True))

    result = ensure_gemini_prompt_cache_sync(
        _bundle(),
        "gemini-3-flash-preview",
        client=client,
        store_path=tmp_path / "cache.json",
        now=datetime(2026, 5, 14, tzinfo=UTC),
    )

    assert result.cache_state == "failed_fallback"
    assert result.cache_name is None
    assert result.generation_config("full").model_dump(exclude_none=True) == {
        "system_instruction": "full",
        "temperature": 0.7,
    }


def test_cache_key_ignores_runtime_context_when_cached_system_is_same() -> None:
    first = _bundle("file tools")
    second = _bundle("mail tools")

    assert first.cached_system_sha256 == second.cached_system_sha256
    assert first.runtime_context_sha256 != second.runtime_context_sha256
    assert gemini_prompt_cache_key("gemini-3-flash-preview", first.cached_system_sha256) == (
        gemini_prompt_cache_key("gemini-3-flash-preview", second.cached_system_sha256)
    )
