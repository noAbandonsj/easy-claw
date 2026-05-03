from __future__ import annotations

from easy_claw.agent.types import ToolBundle

try:
    from langchain_community.agent_toolkits import PlayWrightBrowserToolkit
    from langchain_community.tools.playwright.utils import create_sync_playwright_browser
except ImportError:  # pragma: no cover - exercised through runtime error path
    PlayWrightBrowserToolkit = None
    create_sync_playwright_browser = None


def build_browser_tools(*, enabled: bool, headless: bool) -> ToolBundle:
    if not enabled:
        return ToolBundle()
    if PlayWrightBrowserToolkit is None or create_sync_playwright_browser is None:
        raise RuntimeError(
            "Browser tools require langchain-community and playwright. "
            "Install dependencies and run `uv run playwright install chromium`."
        )

    browser = create_sync_playwright_browser(headless=headless)
    toolkit = PlayWrightBrowserToolkit.from_browser(sync_browser=browser)
    return ToolBundle(
        tools=list(toolkit.get_tools()),
        cleanup=(_close_browser_callback(browser),),
    )


def _close_browser_callback(browser: object):
    def close_browser() -> None:
        close = getattr(browser, "close", None)
        if callable(close):
            close()

    return close_browser
