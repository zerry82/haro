from __future__ import annotations

import asyncio
import json
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from google.genai import types

from app.config import PROJECT_ROOT, settings
from app.services.llm import get_client
from app.services.prompt_bundle import PromptBundle

PROMPT_CACHE_VERSION = "v2"
GEMINI_EXPLICIT_CACHE_TTL_SECONDS = 300
_STORE_LOCK = threading.Lock()


@dataclass(frozen=True)
class PromptCacheResult:
    strategy: str
    cache_key: str
    cache_name: str | None
    cache_state: str
    ttl_seconds: int
    cached_system_hash: str
    cached_system_chars: int
    runtime_context_hash: str
    runtime_context_chars: int
    full_hash: str
    full_chars: int
    error: str | None = None

    @property
    def use_cached_content(self) -> bool:
        return bool(self.cache_name and self.cache_state in {"created", "reused", "expired_recreated", "stale_recreated"})

    def generation_config(self, fallback_system_instruction: str, *, temperature: float = 0.7) -> types.GenerateContentConfig:
        if self.use_cached_content:
            return types.GenerateContentConfig(cached_content=self.cache_name, temperature=temperature)
        return types.GenerateContentConfig(system_instruction=fallback_system_instruction, temperature=temperature)

    def debug_summary(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "strategy": self.strategy,
            "cache_key": self.cache_key,
            "cache_name": self.cache_name,
            "cache_state": self.cache_state,
            "ttl_seconds": self.ttl_seconds,
            "cached_system_hash": self.cached_system_hash,
            "cached_system_chars": self.cached_system_chars,
            "runtime_context_hash": self.runtime_context_hash,
            "runtime_context_chars": self.runtime_context_chars,
            "full_hash": self.full_hash,
            "full_chars": self.full_chars,
        }
        if self.error:
            payload["error"] = self.error
        return payload


def prompt_cache_store_path() -> Path:
    db_data_dir = Path(settings.db_data_dir).expanduser()
    if not db_data_dir.is_absolute():
        db_data_dir = PROJECT_ROOT / db_data_dir
    return db_data_dir.parent / "cache" / "prompt" / "gemini_explicit_cache.json"


def gemini_prompt_cache_key(model_name: str, cached_system_hash: str) -> str:
    return f"gemini:{model_name}:{PROMPT_CACHE_VERSION}:{cached_system_hash}"


async def ensure_gemini_prompt_cache(
    prompt_bundle: PromptBundle,
    model_name: str,
    *,
    client: Any | None = None,
    store_path: Path | None = None,
    ttl_seconds: int = GEMINI_EXPLICIT_CACHE_TTL_SECONDS,
) -> PromptCacheResult:
    cache_client = client or get_client()
    return await asyncio.to_thread(
        ensure_gemini_prompt_cache_sync,
        prompt_bundle,
        model_name,
        client=cache_client,
        store_path=store_path,
        ttl_seconds=ttl_seconds,
    )


def ensure_gemini_prompt_cache_sync(
    prompt_bundle: PromptBundle,
    model_name: str,
    *,
    client: Any,
    store_path: Path | None = None,
    ttl_seconds: int = GEMINI_EXPLICIT_CACHE_TTL_SECONDS,
    now: datetime | None = None,
) -> PromptCacheResult:
    now = now or datetime.now(UTC)
    cache_key = gemini_prompt_cache_key(model_name, prompt_bundle.cached_system_sha256)
    path = store_path or prompt_cache_store_path()
    base = _base_result(prompt_bundle, cache_key, ttl_seconds)

    try:
        with _STORE_LOCK:
            store = _load_store(path)
            entry = store.get("entries", {}).get(cache_key)
            if entry and _entry_is_live(entry, now):
                cache_name = entry.get("cache_name")
                if cache_name:
                    try:
                        client.caches.get(name=cache_name)
                        return base_with(base, cache_name=cache_name, cache_state="reused")
                    except Exception:
                        store["entries"].pop(cache_key, None)
                        _write_store(path, store)
                        return _create_cache(
                            prompt_bundle,
                            model_name,
                            client=client,
                            path=path,
                            store=store,
                            cache_key=cache_key,
                            base=base,
                            now=now,
                            ttl_seconds=ttl_seconds,
                            cache_state="stale_recreated",
                        )

            cache_state = "expired_recreated" if entry else "created"
            if entry:
                store["entries"].pop(cache_key, None)
            return _create_cache(
                prompt_bundle,
                model_name,
                client=client,
                path=path,
                store=store,
                cache_key=cache_key,
                base=base,
                now=now,
                ttl_seconds=ttl_seconds,
                cache_state=cache_state,
            )
    except Exception as exc:
        return base_with(base, cache_state="failed_fallback", error=str(exc))


def base_with(
    base: PromptCacheResult,
    *,
    cache_name: str | None = None,
    cache_state: str,
    error: str | None = None,
) -> PromptCacheResult:
    return PromptCacheResult(
        strategy=base.strategy,
        cache_key=base.cache_key,
        cache_name=cache_name,
        cache_state=cache_state,
        ttl_seconds=base.ttl_seconds,
        cached_system_hash=base.cached_system_hash,
        cached_system_chars=base.cached_system_chars,
        runtime_context_hash=base.runtime_context_hash,
        runtime_context_chars=base.runtime_context_chars,
        full_hash=base.full_hash,
        full_chars=base.full_chars,
        error=error,
    )


def _base_result(prompt_bundle: PromptBundle, cache_key: str, ttl_seconds: int) -> PromptCacheResult:
    return PromptCacheResult(
        strategy="gemini_explicit_stable_system",
        cache_key=cache_key,
        cache_name=None,
        cache_state="not_prepared",
        ttl_seconds=ttl_seconds,
        cached_system_hash=prompt_bundle.cached_system_sha256,
        cached_system_chars=prompt_bundle.cached_system_chars,
        runtime_context_hash=prompt_bundle.runtime_context_sha256,
        runtime_context_chars=prompt_bundle.runtime_context_chars,
        full_hash=prompt_bundle.sha256,
        full_chars=prompt_bundle.chars,
    )


def _create_cache(
    prompt_bundle: PromptBundle,
    model_name: str,
    *,
    client: Any,
    path: Path,
    store: dict[str, Any],
    cache_key: str,
    base: PromptCacheResult,
    now: datetime,
    ttl_seconds: int,
    cache_state: str,
) -> PromptCacheResult:
    cache = client.caches.create(
        model=model_name,
        config=types.CreateCachedContentConfig(
            display_name=_display_name(model_name, prompt_bundle.cached_system_sha256),
            system_instruction=prompt_bundle.cached_system_text,
            ttl=f"{ttl_seconds}s",
        ),
    )
    cache_name = cache.name
    expires_at = now + timedelta(seconds=ttl_seconds)
    store.setdefault("entries", {})[cache_key] = {
        "cache_name": cache_name,
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        "ttl_seconds": ttl_seconds,
        "cached_system_hash": prompt_bundle.cached_system_sha256,
        "model": model_name,
        "cache_version": PROMPT_CACHE_VERSION,
    }
    _write_store(path, store)
    return base_with(base, cache_name=cache_name, cache_state=cache_state)


def _display_name(model_name: str, cached_system_hash: str) -> str:
    digest = cached_system_hash.replace("sha256:", "")[:24]
    return f"haro-{model_name}-{digest}"


def _entry_is_live(entry: dict[str, Any], now: datetime) -> bool:
    expires_at_raw = entry.get("expires_at")
    if not expires_at_raw:
        return False
    try:
        expires_at = datetime.fromisoformat(expires_at_raw)
    except ValueError:
        return False
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return expires_at > now


def _load_store(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"entries": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"entries": {}}
    if not isinstance(data, dict):
        return {"entries": {}}
    entries = data.get("entries")
    if not isinstance(entries, dict):
        data["entries"] = {}
    return data


def _write_store(path: Path, store: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)
