from __future__ import annotations

from easy_claw.agent.types import ToolBundle
from easy_claw.tools.base import ToolExecutionError

try:
    from langchain_community.agent_toolkits import PlayWrightBrowserToolkit
    from langchain_community.tools.playwright.utils import create_sync_playwright_browser
except ImportError:  # pragma: no cover
    PlayWrightBrowserToolkit = None
    create_sync_playwright_browser = None


def _check_playwright_browsers(*, headless: bool) -> bool:
    """Return True if the needed Playwright Chromium browsers are installed."""
    import os as _os
    from pathlib import Path as _Path

    cache_dir = _os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if cache_dir:
        root = _Path(cache_dir)
    elif _os.name == "nt":
        root = _Path.home() / "AppData" / "Local" / "ms-playwright"
    else:
        root = _Path.home() / ".cache" / "ms-playwright"

    try:
        if headless:
            return any(root.glob("chromium_headless_shell-*"))
        return any(root.glob("chromium-*"))
    except OSError:
        return False


def build_browser_tools(*, enabled: bool, headless: bool) -> ToolBundle:
    if not enabled:
        return ToolBundle()

    if PlayWrightBrowserToolkit is None or create_sync_playwright_browser is None:
        raise ToolExecutionError(
            "Browser tools require langchain-community and playwright. "
            "Run: uv sync && uv run playwright install chromium"
        )

    if not _check_playwright_browsers(headless=headless):
        raise ToolExecutionError(
            "Playwright Chromium browser is not installed. "
            "Run: uv run playwright install chromium"
        )

    try:
        browser = create_sync_playwright_browser(headless=headless)
    except Exception as exc:
        msg = str(exc)
        if "Executable" in msg or "playwright install" in msg:
            raise ToolExecutionError(
                "Playwright Chromium browser is not installed. "
                "Run: uv run playwright install chromium"
            ) from exc
        raise ToolExecutionError(
            f"Failed to launch browser: {exc}"
        ) from exc

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
