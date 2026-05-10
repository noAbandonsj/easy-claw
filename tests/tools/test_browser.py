import pytest

from easy_claw.tools.base import ToolExecutionError
from easy_claw.tools.browser import build_browser_tools


def test_build_browser_tools_skips_browser_when_disabled():
    bundle = build_browser_tools(enabled=False, headless=False)

    assert bundle.tools == []
    assert bundle.cleanup == ()


def test_build_browser_tools_creates_langchain_playwright_tools(monkeypatch):
    captured = {}
    closed = []

    class FakeBrowser:
        async def close(self):
            closed.append("browser_closed")

    class FakePlaywright:
        async def stop(self):
            closed.append("pw_stopped")

    fake_browser = FakeBrowser()
    fake_pw = FakePlaywright()

    async def fake_launch(*, headless):
        captured["headless"] = headless
        return fake_pw, fake_browser

    class FakeTool:
        def __init__(self, name):
            self.name = name
            self._run = None
            self._arun = None

    fake_tools = [FakeTool("t1"), FakeTool("t2")]

    class FakeToolkit:
        @classmethod
        def from_browser(cls, *, async_browser, sync_browser=None):
            captured["async_browser"] = async_browser
            return cls()

        def get_tools(self):
            return fake_tools

    monkeypatch.setattr(
        "easy_claw.tools.browser._check_playwright_browsers",
        lambda *, headless: True,
    )
    monkeypatch.setattr(
        "easy_claw.tools.browser._async_launch_browser",
        fake_launch,
    )
    monkeypatch.setattr(
        "easy_claw.tools.browser.PlayWrightBrowserToolkit",
        FakeToolkit,
        raising=False,
    )

    bundle = build_browser_tools(enabled=True, headless=True)

    assert captured == {"headless": True, "async_browser": fake_browser}
    assert bundle.tools == fake_tools
    # _run is patched to a sync wrapper around _arun
    for tool in fake_tools:
        assert callable(tool._run)

    bundle.close()

    assert closed == ["browser_closed", "pw_stopped"]


def test_build_browser_tools_raises_when_playwright_not_installed(monkeypatch):
    async def fake_launch(*, headless):
        raise Exception("Executable doesn't exist\nplaywright install\n")

    monkeypatch.setattr(
        "easy_claw.tools.browser._async_launch_browser",
        fake_launch,
    )
    monkeypatch.setattr(
        "easy_claw.tools.browser._check_playwright_browsers",
        lambda *, headless: True,
    )
    monkeypatch.setattr(
        "easy_claw.tools.browser.PlayWrightBrowserToolkit",
        object(),
        raising=False,
    )

    with pytest.raises(ToolExecutionError, match="uv run playwright install chromium"):
        build_browser_tools(enabled=True, headless=False)


def test_build_browser_tools_raises_when_browser_check_fails(monkeypatch):
    monkeypatch.setattr(
        "easy_claw.tools.browser._check_playwright_browsers",
        lambda *, headless: False,
    )

    with pytest.raises(ToolExecutionError, match="uv run playwright install chromium"):
        build_browser_tools(enabled=True, headless=False)
