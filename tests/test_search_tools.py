import pytest

from easy_claw.config import AppConfig
from easy_claw.tools.base import ToolExecutionError
from easy_claw.tools.search import (
    DdgsSearchBackend,
    TavilySearchBackend,
    _get_backend,
    search_web,
)

# ---------------------------------------------------------------------------
# 既有测试（适配 keyword-only max_results）
# ---------------------------------------------------------------------------


class FakeSearchBackend:
    def text(self, query, *, max_results):
        assert query == "DeepSeek API"
        assert max_results == 3
        return [{"title": "DeepSeek Docs", "href": "https://api-docs.deepseek.com", "body": "Docs"}]


def test_search_web_returns_normalized_results():
    results = search_web("DeepSeek API", max_results=3, backend=FakeSearchBackend())

    assert results[0].title == "DeepSeek Docs"
    assert results[0].url == "https://api-docs.deepseek.com"
    assert results[0].snippet == "Docs"


class FailingSearchBackend:
    def text(self, query, *, max_results):
        raise RuntimeError("network down")


def test_search_web_wraps_backend_errors():
    with pytest.raises(ToolExecutionError, match="搜索失败"):
        search_web("DeepSeek API", backend=FailingSearchBackend())


# ---------------------------------------------------------------------------
# DdgsSearchBackend
# ---------------------------------------------------------------------------


def test_ddgs_backend_calls_text_with_keyword_max_results(monkeypatch):
    captured = {}

    class FakeDDGS:
        def text(self, keywords, max_results=None):
            captured["keywords"] = keywords
            captured["max_results"] = max_results
            return [{"title": "R", "href": "https://r.com", "body": "b"}]

    monkeypatch.setattr("ddgs.DDGS", FakeDDGS)

    backend = DdgsSearchBackend()
    results = backend.text("test query", max_results=3)

    assert len(results) == 1
    assert results[0]["title"] == "R"
    assert captured["keywords"] == "test query"
    assert captured["max_results"] == 3


def test_ddgs_backend_caches_client(monkeypatch):
    create_count = 0

    class FakeDDGS:
        def __init__(self):
            nonlocal create_count
            create_count += 1

        def text(self, keywords, max_results=None):
            return [{"title": "x", "href": "https://x.com", "body": "x"}]

    monkeypatch.setattr("ddgs.DDGS", FakeDDGS)

    backend = DdgsSearchBackend()
    backend.text("q1", max_results=1)
    backend.text("q2", max_results=1)

    assert create_count == 1


# ---------------------------------------------------------------------------
# TavilySearchBackend
# ---------------------------------------------------------------------------


def test_tavily_backend_calls_search_and_normalizes(monkeypatch):
    captured = {}

    class FakeTavilyClient:
        def __init__(self, api_key):
            captured["api_key"] = api_key

        def search(self, query, max_results=None, include_raw_content=None):
            captured["query"] = query
            captured["max_results"] = max_results
            return {"results": [{"title": "T", "url": "https://t.com", "content": "body text"}]}

    monkeypatch.setattr("tavily.TavilyClient", FakeTavilyClient)

    backend = TavilySearchBackend(api_key="tvly-test")
    results = backend.text("test query", max_results=5)

    assert len(results) == 1
    assert results[0]["title"] == "T"
    assert results[0]["href"] == "https://t.com"
    assert results[0]["body"] == "body text"
    assert captured["api_key"] == "tvly-test"
    assert captured["query"] == "test query"
    assert captured["max_results"] == 5


# ---------------------------------------------------------------------------
# Factory: _get_backend
# ---------------------------------------------------------------------------


def _reset_cache():
    import easy_claw.tools.search as mod

    mod._cached_backend = None
    mod._cached_backend_mode = None


def _make_config(tmp_path, **kwargs):
    """Build AppConfig with required fields pre-filled."""
    defaults = dict(
        cwd=tmp_path,
        data_dir=tmp_path / "data",
        product_db_path=tmp_path / "data" / "db",
        checkpoint_db_path=tmp_path / "data" / "cp",
        default_workspace=tmp_path,
        model=None,
        base_url="https://api.deepseek.com",
        api_key=None,
    )
    return AppConfig(**{**defaults, **kwargs})


def test_factory_auto_with_tavily_key_returns_tavily(tmp_path):
    _reset_cache()
    config = _make_config(tmp_path, search_backend="auto", tavily_api_key="sk-test")
    backend = _get_backend(config)
    assert isinstance(backend, TavilySearchBackend)


def test_factory_auto_without_tavily_key_returns_ddgs(tmp_path):
    _reset_cache()
    config = _make_config(tmp_path, search_backend="auto", tavily_api_key=None)
    backend = _get_backend(config)
    assert isinstance(backend, DdgsSearchBackend)


def test_factory_explicit_tavily_without_key_raises(tmp_path):
    _reset_cache()
    config = _make_config(tmp_path, search_backend="tavily", tavily_api_key=None)
    with pytest.raises(ToolExecutionError, match="TAVILY_API_KEY"):
        _get_backend(config)


def test_factory_explicit_ddgs_ignores_tavily_key(tmp_path):
    _reset_cache()
    config = _make_config(tmp_path, search_backend="ddgs", tavily_api_key="sk-ignored")
    backend = _get_backend(config)
    assert isinstance(backend, DdgsSearchBackend)


def test_factory_caches_backend(tmp_path):
    _reset_cache()
    config = _make_config(tmp_path, search_backend="ddgs")
    b1 = _get_backend(config)
    b2 = _get_backend(config)
    assert b1 is b2


# ---------------------------------------------------------------------------
# search_web with config parameter
# ---------------------------------------------------------------------------


def test_search_web_with_config_uses_auto_backend(tmp_path, monkeypatch):
    _reset_cache()

    class FakeDDGS:
        def text(self, keywords, max_results=None):
            return [{"title": "DDG", "href": "https://d.com", "body": "snippet"}]

    monkeypatch.setattr("ddgs.DDGS", FakeDDGS)
    config = _make_config(tmp_path, search_backend="auto", tavily_api_key=None)
    results = search_web("test", max_results=3, config=config)
    assert len(results) == 1
    assert results[0].title == "DDG"
