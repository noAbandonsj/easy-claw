from __future__ import annotations

from easy_claw.agent.types import ToolBundle, ToolContext
from easy_claw.tools.browser import build_browser_tools
from easy_claw.tools.core import build_core_tools


def build_easy_claw_tools(context: ToolContext) -> ToolBundle:
    tools = build_core_tools(workspace_path=context.workspace_path, cwd=context.cwd)
    cleanup = []

    browser_bundle = build_browser_tools(
        enabled=context.browser_enabled,
        headless=context.browser_headless,
    )
    tools.extend(browser_bundle.tools)
    cleanup.extend(browser_bundle.cleanup)

    return ToolBundle(tools=tools, cleanup=tuple(cleanup))
