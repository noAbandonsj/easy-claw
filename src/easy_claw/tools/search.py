from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from easy_claw.config import AppConfig
from easy_claw.tools.base import ToolExecutionError


class SearchBackend(Protocol):
    def text(self, query: str, *, max_results: int) -> list[dict[str, object]]:
        """返回指定查询的搜索结果。"""


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str


class DdgsSearchBackend:
    """通过 ddgs 使用免配置的 DuckDuckGo 搜索。"""

    def __init__(self) -> None:
        self._ddgs: object | None = None

    def text(self, query: str, *, max_results: int) -> list[dict[str, object]]:
        if self._ddgs is None:
            from ddgs import DDGS

            self._ddgs = DDGS()
        raw = self._ddgs.text(query, max_results=max_results)
        return [{"title": r["title"], "href": r["href"], "body": r["body"]} for r in raw]


class TavilySearchBackend:
    """通过 Tavily API 使用面向 AI 场景优化的搜索。"""

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
    """根据配置创建或返回缓存的搜索后端。"""
    global _cached_backend, _cached_backend_mode

    mode = config.search_backend
    cache_key = f"{mode}:{bool(config.tavily_api_key)}"
    if _cached_backend is not None and _cached_backend_mode == cache_key:
        return _cached_backend

    if mode == "tavily" or (mode == "auto" and config.tavily_api_key):
        if not config.tavily_api_key:
            raise ToolExecutionError("当 EASY_CLAW_SEARCH_BACKEND=tavily 时必须设置 TAVILY_API_KEY")
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
    """联网搜索并返回标准化结果。

    后端选择逻辑（未显式传入 backend 时）：
        如果传入 config，则使用 config.search_backend；否则读取当前配置。
        auto 模式：设置了 TAVILY_API_KEY 时使用 Tavily，否则使用 DDGS。
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
        raise ToolExecutionError(f"搜索失败 '{query}'：{exc}") from exc

    return [
        SearchResult(
            title=str(item.get("title", "")),
            url=str(item.get("href", "")),
            snippet=str(item.get("body", "")),
        )
        for item in raw_results
    ]
