"""Real Playwright smoke test — requires ``uv run playwright install chromium``."""

import os

import pytest

playwright_installed = os.environ.get("EASY_CLAW_SMOKE_BROWSER", "").lower() in (
    "1",
    "true",
    "yes",
)

pytestmark = pytest.mark.skipif(
    not playwright_installed,
    reason="Set EASY_CLAW_SMOKE_BROWSER=1 to run real Playwright tests",
)


def test_browser_launch_navigate_extract():
    """Launch a headless browser, navigate, and extract page text."""
    from easy_claw.tools.browser import _async_launch_browser, get_background_loop

    loop = get_background_loop()
    pw, browser = loop.run_coroutine(_async_launch_browser(headless=True))

    try:
        page = loop.run_coroutine(browser.new_page())
        loop.run_coroutine(page.goto("data:text/html,<h1>Hello easy-claw</h1>"))
        title = loop.run_coroutine(page.title())
        text = loop.run_coroutine(page.inner_text("h1"))

        assert "Hello easy-claw" in text

        loop.run_coroutine(page.close())
    finally:
        loop.run_coroutine(browser.close())
        loop.run_coroutine(pw.stop())


def test_build_browser_tools_real():
    """Build the full browser tool bundle against a real Playwright instance."""
    from easy_claw.tools.browser import build_browser_tools

    bundle = build_browser_tools(enabled=True, headless=True)
    assert len(bundle.tools) > 0, "Expected at least one Playwright tool"
    assert len(bundle.cleanup) == 1

    # Cleanup should not raise
    for cb in bundle.cleanup:
        cb()
