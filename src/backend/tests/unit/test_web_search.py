from __future__ import annotations

import asyncio

import httpx
import pytest

import app.services.web_search as web_search
from app.config import settings


def _mock_client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=1.0)


def test_search_web_uses_searxng_json_results(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/search"
        assert request.url.params["format"] == "json"
        assert "site:example.com" in request.url.params["q"]
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "Result A",
                        "url": "https://example.com/a",
                        "content": "Snippet A",
                        "engine": "duckduckgo",
                        "publishedDate": "2026-05-09",
                    },
                    {"title": "Result B", "url": "https://example.com/b", "content": "Snippet B"},
                ]
            },
        )

    monkeypatch.setattr(settings, "web_search_provider", "searxng")
    monkeypatch.setattr(settings, "web_search_base_url", "https://search.local")
    monkeypatch.setattr(web_search, "_new_async_client", lambda: _mock_client(handler))

    results = asyncio.run(web_search.search_web("청개구리 최신 연구", limit=1, domains=["example.com"]))

    assert len(results) == 1
    assert results[0].title == "Result A"
    assert results[0].url == "https://example.com/a"
    assert results[0].snippet == "Snippet A"
    assert results[0].source == "duckduckgo"
    assert results[0].published_at == "2026-05-09"


def test_search_web_reports_missing_searxng_base_url(monkeypatch) -> None:
    monkeypatch.setattr(settings, "web_search_provider", "searxng")
    monkeypatch.setattr(settings, "web_search_base_url", "")

    with pytest.raises(web_search.WebSearchUnavailableError, match="WEB_SEARCH_BASE_URL"):
        asyncio.run(web_search.search_web("검색어"))


def test_search_web_converts_timeout(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("too slow")

    monkeypatch.setattr(settings, "web_search_provider", "searxng")
    monkeypatch.setattr(settings, "web_search_base_url", "https://search.local")
    monkeypatch.setattr(web_search, "_new_async_client", lambda: _mock_client(handler))

    with pytest.raises(web_search.WebSearchTimeoutError):
        asyncio.run(web_search.search_web("검색어"))


def test_search_web_reports_missing_brave_api_key(monkeypatch) -> None:
    monkeypatch.setattr(settings, "web_search_provider", "brave")
    monkeypatch.setattr(settings, "web_search_api_key", "")

    with pytest.raises(web_search.WebSearchUnavailableError, match="WEB_SEARCH_API_KEY"):
        asyncio.run(web_search.search_web("검색어"))
