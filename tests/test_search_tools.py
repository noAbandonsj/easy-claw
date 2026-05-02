import pytest

from easy_claw.tools.base import ToolExecutionError
from easy_claw.tools.search import search_web


class FakeSearchBackend:
    def text(self, query, max_results):
        assert query == "DeepSeek API"
        assert max_results == 3
        return [
            {
                "title": "DeepSeek Docs",
                "href": "https://api-docs.deepseek.com",
                "body": "Docs",
            }
        ]


def test_search_web_returns_normalized_results():
    results = search_web("DeepSeek API", max_results=3, backend=FakeSearchBackend())

    assert results[0].title == "DeepSeek Docs"
    assert results[0].url == "https://api-docs.deepseek.com"
    assert results[0].snippet == "Docs"


class FailingSearchBackend:
    def text(self, query, max_results):
        raise RuntimeError("network down")


def test_search_web_wraps_backend_errors():
    with pytest.raises(ToolExecutionError, match="Search failed"):
        search_web("DeepSeek API", backend=FailingSearchBackend())
