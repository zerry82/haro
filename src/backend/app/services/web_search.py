from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

import httpx

from app.config import settings


class WebSearchUnavailableError(RuntimeError):
    pass


class WebSearchTimeoutError(RuntimeError):
    pass


class WebSearchProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class WebSearchResult:
    title: str
    url: str
    snippet: str
    source: str | None = None
    published_at: str | None = None


async def search_web(
    query: str,
    *,
    limit: int = 5,
    recency_days: int | None = None,
    domains: list[str] | None = None,
) -> list[WebSearchResult]:
    normalized_query = _normalize_query(query, recency_days=recency_days, domains=domains)
    normalized_limit = _clamp_limit(limit)
    provider = (settings.web_search_provider or "disabled").strip().lower()
    if provider == "disabled":
        raise WebSearchUnavailableError("WEB_SEARCH_PROVIDER가 disabled로 설정되어 있습니다.")
    if provider == "searxng":
        return await _search_searxng(normalized_query, normalized_limit)
    if provider == "brave":
        return await _search_brave(normalized_query, normalized_limit)
    raise WebSearchUnavailableError(f"지원하지 않는 웹 검색 provider입니다: {provider}")


async def _search_searxng(query: str, limit: int) -> list[WebSearchResult]:
    base_url = settings.web_search_base_url.strip()
    if not base_url:
        raise WebSearchUnavailableError("WEB_SEARCH_BASE_URL이 설정되어 있지 않습니다.")

    url = urljoin(base_url.rstrip("/") + "/", "search")
    params = {"q": query, "format": "json", "language": "ko-KR"}
    try:
        async with _new_async_client() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
    except httpx.TimeoutException as exc:
        raise WebSearchTimeoutError("웹 검색 시간이 초과되었습니다.") from exc
    except Exception as exc:
        raise WebSearchProviderError("SearXNG 검색 요청에 실패했습니다.") from exc

    raw_results = data.get("results", []) if isinstance(data, dict) else []
    return _normalize_searxng_results(raw_results, limit)


async def _search_brave(query: str, limit: int) -> list[WebSearchResult]:
    api_key = settings.web_search_api_key.strip()
    if not api_key:
        raise WebSearchUnavailableError("WEB_SEARCH_API_KEY가 설정되어 있지 않습니다.")

    params = {"q": query, "count": limit, "search_lang": "ko"}
    headers = {"Accept": "application/json", "X-Subscription-Token": api_key}
    try:
        async with _new_async_client() as client:
            response = await client.get("https://api.search.brave.com/res/v1/web/search", params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
    except httpx.TimeoutException as exc:
        raise WebSearchTimeoutError("웹 검색 시간이 초과되었습니다.") from exc
    except Exception as exc:
        raise WebSearchProviderError("Brave 검색 요청에 실패했습니다.") from exc

    raw_results = ((data.get("web") or {}).get("results") or []) if isinstance(data, dict) else []
    return _normalize_brave_results(raw_results, limit)


def _normalize_query(query: str, *, recency_days: int | None, domains: list[str] | None) -> str:
    normalized = " ".join(str(query or "").split())
    if not normalized:
        raise ValueError("query가 비어 있습니다.")
    for domain in _normalize_domains(domains):
        normalized += f" site:{domain}"
    if recency_days:
        normalized += f" after:{recency_days}d"
    return normalized


def _new_async_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=settings.web_search_timeout_seconds)


def _normalize_domains(domains: list[str] | None) -> list[str]:
    normalized: list[str] = []
    for domain in domains or []:
        value = str(domain).strip().lower()
        if not value:
            continue
        value = value.removeprefix("https://").removeprefix("http://").split("/")[0]
        if value and value not in normalized:
            normalized.append(value)
        if len(normalized) >= 5:
            break
    return normalized


def _clamp_limit(limit: int) -> int:
    try:
        value = int(limit)
    except Exception:
        value = 5
    return max(1, min(value, 10))


def _normalize_searxng_results(raw_results: list[Any], limit: int) -> list[WebSearchResult]:
    results: list[WebSearchResult] = []
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        result = _result_from_mapping(
            item,
            title_key="title",
            url_key="url",
            snippet_keys=("content", "snippet"),
            source=item.get("engine") or item.get("engines"),
            published_at=item.get("publishedDate") or item.get("published_at"),
        )
        if result:
            results.append(result)
        if len(results) >= limit:
            break
    return results


def _normalize_brave_results(raw_results: list[Any], limit: int) -> list[WebSearchResult]:
    results: list[WebSearchResult] = []
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        result = _result_from_mapping(
            item,
            title_key="title",
            url_key="url",
            snippet_keys=("description", "snippet"),
            source=item.get("profile", {}).get("name") if isinstance(item.get("profile"), dict) else None,
            published_at=item.get("age"),
        )
        if result:
            results.append(result)
        if len(results) >= limit:
            break
    return results


def _result_from_mapping(
    item: dict[str, Any],
    *,
    title_key: str,
    url_key: str,
    snippet_keys: tuple[str, ...],
    source: Any,
    published_at: Any,
) -> WebSearchResult | None:
    title = str(item.get(title_key) or "").strip()
    url = str(item.get(url_key) or "").strip()
    snippet = ""
    for key in snippet_keys:
        snippet = str(item.get(key) or "").strip()
        if snippet:
            break
    if not title or not url:
        return None
    return WebSearchResult(
        title=title,
        url=url,
        snippet=snippet,
        source=_string_or_none(source),
        published_at=_string_or_none(published_at),
    )


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        value = ", ".join(str(item) for item in value if item)
    text = str(value).strip()
    return text or None
