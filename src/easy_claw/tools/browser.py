from __future__ import annotations

import asyncio

from playwright.async_api import async_playwright

from easy_claw.agent.types import ToolBundle
from easy_claw.tools.base import ToolExecutionError

try:
    from langchain_community.agent_toolkits import PlayWrightBrowserToolkit
except ImportError:  # pragma: no cover
    PlayWrightBrowserToolkit = None


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


async def _async_launch_browser(*, headless: bool):
    pw = await async_playwright().start()
    return await pw.chromium.launch(headless=headless)


def _patch_tool_sync_run(tool):
    """Patch a browser tool's _run to delegate to _arun via asyncio.run().

    Avoids greenlet cross-thread errors that occur when the sync Playwright
    browser (which uses greenlets) is invoked from a different thread than
    the one that created it.
    """
    async_run = tool._arun

    def sync_run(*args, **kwargs):
        return asyncio.run(async_run(*args, **kwargs))

    tool._run = sync_run


def build_browser_tools(*, enabled: bool, headless: bool) -> ToolBundle:
    if not enabled:
        return ToolBundle()

    if PlayWrightBrowserToolkit is None:
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
        async_browser = asyncio.run(_async_launch_browser(headless=headless))
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

    toolkit = PlayWrightBrowserToolkit.from_browser(async_browser=async_browser)
    tools = list(toolkit.get_tools())

    for tool in tools:
        _patch_tool_sync_run(tool)

    return ToolBundle(
        tools=tools,
        cleanup=(_close_browser_callback(async_browser),),
    )


def _close_browser_callback(browser):
    def close_browser() -> None:
        async def _close():
            await browser.close()

        try:
            asyncio.run(_close())
        except RuntimeError:
            pass

    return close_browser
