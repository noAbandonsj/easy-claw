from __future__ import annotations

from easy_claw.agent.types import ToolBundle, ToolContext
from easy_claw.tools.browser import build_browser_tools
from easy_claw.tools.core import build_core_tool_bundle
from easy_claw.tools.files import build_file_tool_bundle
from easy_claw.tools.mcp import build_mcp_tools

BASE_RISKY_TOOL_INTERRUPT_ON: dict[str, object] = {}


def build_easy_claw_tools(context: ToolContext) -> ToolBundle:
    core_bundle = build_core_tool_bundle(workspace_path=context.workspace_path, cwd=context.cwd)
    tools = list(core_bundle.tools)
    cleanup = []
    interrupt_on = dict(BASE_RISKY_TOOL_INTERRUPT_ON)
    interrupt_on.update(core_bundle.interrupt_on)

    file_bundle = build_file_tool_bundle(workspace_path=context.workspace_path)
    tools.extend(file_bundle.tools)
    interrupt_on.update(file_bundle.interrupt_on)

    browser_bundle = build_browser_tools(
        enabled=context.browser_enabled,
        headless=context.browser_headless,
    )
    tools.extend(browser_bundle.tools)
    cleanup.extend(browser_bundle.cleanup)
    interrupt_on.update(browser_bundle.interrupt_on)

    mcp_bundle = build_mcp_tools(
        enabled=context.mcp_mode if context.mcp_mode is not None else context.mcp_enabled,
        config_path=context.mcp_config_path,
    )
    tools.extend(mcp_bundle.tools)
    cleanup.extend(mcp_bundle.cleanup)
    interrupt_on.update(mcp_bundle.interrupt_on)

    return ToolBundle(tools=tools, cleanup=tuple(cleanup), interrupt_on=interrupt_on)
