from __future__ import annotations

import json
from pathlib import Path

from easy_claw.agent.types import ToolBundle
from easy_claw.tools.base import ToolExecutionError, get_background_loop

try:
    from langchain_mcp_adapters.client import MultiServerMCPClient
except ImportError:  # pragma: no cover
    MultiServerMCPClient = None


def build_mcp_tools(*, enabled: bool, config_path: str) -> ToolBundle:
    """Build MCP tools from a JSON configuration file.

    Returns an empty ToolBundle when disabled. When enabled, reads the
    server config JSON, connects to all configured MCP servers, and
    returns the discovered tools plus a cleanup callback.
    """
    if not enabled:
        return ToolBundle()

    if MultiServerMCPClient is None:
        raise ToolExecutionError("MCP tools require langchain-mcp-adapters. Run: uv sync")

    config_file = Path(config_path)
    if not config_file.exists():
        raise ToolExecutionError(
            f"MCP config file not found: {config_file}. "
            "Create an mcp_servers.json file or set EASY_CLAW_MCP_CONFIG."
        )

    try:
        servers_config = json.loads(config_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ToolExecutionError(f"Invalid JSON in MCP config file '{config_file}': {exc}") from exc

    if not isinstance(servers_config, dict) or not servers_config:
        raise ToolExecutionError(
            f"MCP config file '{config_file}' must contain a non-empty "
            "JSON object mapping server names to server configs."
        )

    loop = get_background_loop()
    client, tools = loop.run_coroutine(_async_init_mcp(servers_config))

    interrupt_on = {tool.name: True for tool in tools}

    return ToolBundle(
        tools=list(tools),
        cleanup=(_make_mcp_cleanup(loop, client),),
        interrupt_on=interrupt_on,
    )


async def _async_init_mcp(servers_config: dict) -> tuple[object, list[object]]:
    client = MultiServerMCPClient(servers_config)
    tools = await client.get_tools()
    return client, tools


def _make_mcp_cleanup(loop, client: object):
    def cleanup() -> None:
        async def _close() -> None:
            close = getattr(client, "close", None)
            if callable(close):
                await close()

        try:
            loop.run_coroutine(_close())
        except (RuntimeError, OSError):
            pass

    return cleanup
