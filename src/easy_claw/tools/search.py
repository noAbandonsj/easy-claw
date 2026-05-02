from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from easy_claw.tools.base import ToolExecutionError


class SearchBackend(Protocol):
    def text(self, query: str, max_results: int) -> list[dict[str, object]]:
        """Return search results for a query."""


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str


def search_web(
    query: str,
    *,
    max_results: int = 5,
    backend: SearchBackend | None = None,
) -> list[SearchResult]:
    active_backend = backend or _create_duckduckgo_backend()
    try:
        raw_results = active_backend.text(query, max_results)
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


def _create_duckduckgo_backend() -> SearchBackend:
    from duckduckgo_search import DDGS

    return DDGS()
