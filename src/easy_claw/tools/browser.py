from __future__ import annotations

from playwright.async_api import async_playwright

from easy_claw.agent.types import ToolBundle
from easy_claw.tools.base import ToolExecutionError, get_background_loop

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
    browser = await pw.chromium.launch(headless=headless)
    return pw, browser


def _patch_tool_sync_run(tool, loop):
    """Patch a browser tool's _run to delegate to _arun via the background loop.

    All async Playwright calls now execute on the same dedicated event-loop
    thread, eliminating greenlet cross-thread errors and asyncio.run() crashes.
    """
    async_run = tool._arun

    def sync_run(*args, **kwargs):
        return loop.run_coroutine(async_run(*args, **kwargs))

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

    loop = get_background_loop()

    try:
        pw, async_browser = loop.run_coroutine(
            _async_launch_browser(headless=headless)
        )
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
        _patch_tool_sync_run(tool, loop)

    return ToolBundle(
        tools=tools,
        cleanup=(_close_browser_callback(loop, pw, async_browser),),
    )


def _close_browser_callback(loop, pw, browser):
    def close_browser() -> None:
        async def _close():
            await browser.close()
            await pw.stop()

        try:
            loop.run_coroutine(_close())
        except (RuntimeError, OSError):
            pass

    return close_browser
