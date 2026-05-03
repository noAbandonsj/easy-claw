from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from easy_claw.config import AppConfig
from easy_claw.tools.base import ToolExecutionError


class SearchBackend(Protocol):
    def text(self, query: str, *, max_results: int) -> list[dict[str, object]]:
        """Return search results for a query."""


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str


class DdgsSearchBackend:
    """Zero-config DuckDuckGo search via ddgs."""

    def __init__(self) -> None:
        self._ddgs: object | None = None

    def text(self, query: str, *, max_results: int) -> list[dict[str, object]]:
        if self._ddgs is None:
            from ddgs import DDGS

            self._ddgs = DDGS()
        raw = self._ddgs.text(query, max_results=max_results)
        return [{"title": r["title"], "href": r["href"], "body": r["body"]} for r in raw]


class TavilySearchBackend:
    """AI-optimized search via Tavily API."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def text(self, query: str, *, max_results: int) -> list[dict[str, object]]:
        from tavily import TavilyClient

        response = TavilyClient(api_key=self._api_key).search(
            query, max_results=max_results, include_raw_content=False
        )
        return [
            {"title": r["title"], "href": r["url"], "body": r.get("content", "")}
            for r in response.get("results", [])
        ]


_cached_backend: SearchBackend | None = None
_cached_backend_mode: str | None = None


def _get_backend(config: AppConfig) -> SearchBackend:
    """Create or return cached search backend based on config."""
    global _cached_backend, _cached_backend_mode

    mode = config.search_backend
    cache_key = f"{mode}:{bool(config.tavily_api_key)}"
    if _cached_backend is not None and _cached_backend_mode == cache_key:
        return _cached_backend

    if mode == "tavily" or (mode == "auto" and config.tavily_api_key):
        if not config.tavily_api_key:
            raise ToolExecutionError(
                "TAVILY_API_KEY is required when EASY_CLAW_SEARCH_BACKEND=tavily"
            )
        _cached_backend = TavilySearchBackend(api_key=config.tavily_api_key)
    else:
        _cached_backend = DdgsSearchBackend()

    _cached_backend_mode = cache_key
    return _cached_backend


def search_web(
    query: str,
    *,
    max_results: int = 5,
    config: AppConfig | None = None,
    backend: SearchBackend | None = None,
) -> list[SearchResult]:
    """Search the web and return normalized results.

    Backend selection (when backend is None):
        Uses config.search_backend if config is provided, otherwise loads config.
        auto mode: Tavily if TAVILY_API_KEY is set, else DDGS.
    """
    if backend is not None:
        active_backend = backend
    elif config is not None:
        active_backend = _get_backend(config)
    else:
        from easy_claw.config import load_config

        active_backend = _get_backend(load_config())

    try:
        raw_results = active_backend.text(query, max_results=max_results)
    except Exception as exc:
        raise ToolExecutionError(f"Search failed for query '{query}': {exc}") from exc

    return [
        SearchResult(
            title=str(item.get("title", "")),
            url=str(item.get("href", "")),
            snippet=str(item.get("body", "")),
        )
        for item in raw_results
    ]
