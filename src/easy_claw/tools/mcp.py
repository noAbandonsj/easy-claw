from __future__ import annotations

import json
import warnings
from pathlib import Path

from easy_claw.agent.types import ToolBundle
from easy_claw.tools.base import ToolExecutionError, get_background_loop

try:
    from langchain_mcp_adapters.client import MultiServerMCPClient
except ImportError:  # pragma: no cover
    MultiServerMCPClient = None


def build_mcp_tools(*, enabled: bool | str, config_path: str) -> ToolBundle:
    """Build MCP tools from a JSON configuration file.

    Returns an empty ToolBundle when disabled. When enabled, reads the
    server config JSON, connects to all configured MCP servers, and
    returns the discovered tools plus a cleanup callback.
    """
    mode = _mcp_mode(enabled)
    if mode == "disabled":
        return ToolBundle()

    if MultiServerMCPClient is None:
        if mode == "auto":
            _warn_auto_disabled("langchain-mcp-adapters is not installed")
            return ToolBundle()
        raise ToolExecutionError("MCP tools require langchain-mcp-adapters. Run: uv sync")

    config_file = Path(config_path)
    if not config_file.exists():
        if mode == "auto":
            return ToolBundle()
        raise ToolExecutionError(
            f"MCP config file not found: {config_file}. "
            "Create an mcp_servers.json file or set EASY_CLAW_MCP_CONFIG."
        )

    servers_config = _read_servers_config(config_file, auto_mode=mode == "auto")
    if not servers_config:
        return ToolBundle()

    loop = get_background_loop()
    try:
        client, tools, errors = loop.run_coroutine(
            _async_init_mcp(
                servers_config,
                tolerate_errors=mode == "auto",
            )
        )
    except Exception as exc:
        if mode == "auto":
            _warn_auto_disabled(f"failed to load tools from {config_file}: {exc}")
            return ToolBundle()
        raise ToolExecutionError(f"Failed to load MCP tools from '{config_file}': {exc}") from exc

    for server_name, error in errors.items():
        warnings.warn(
            f"MCP auto mode skipped server '{server_name}': {error}",
            RuntimeWarning,
            stacklevel=2,
        )

    if not tools:
        return ToolBundle()

    interrupt_on = {tool.name: True for tool in tools}

    return ToolBundle(
        tools=list(tools),
        cleanup=(_make_mcp_cleanup(loop, client),),
        interrupt_on=interrupt_on,
    )


def _mcp_mode(enabled: bool | str) -> str:
    if isinstance(enabled, bool):
        return "enabled" if enabled else "disabled"
    normalized = enabled.strip().lower()
    if normalized == "auto":
        return "auto"
    if normalized in {"1", "true", "yes", "y", "on", "enabled"}:
        return "enabled"
    return "disabled"


def _read_servers_config(config_file: Path, *, auto_mode: bool) -> dict[str, dict]:
    try:
        raw_config = json.loads(config_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        if auto_mode:
            _warn_auto_disabled(f"invalid JSON in {config_file}: {exc}")
            return {}
        raise ToolExecutionError(f"Invalid JSON in MCP config file '{config_file}': {exc}") from exc

    if not isinstance(raw_config, dict) or not raw_config:
        if auto_mode:
            _warn_auto_disabled(f"{config_file} does not contain any server configs")
            return {}
        raise ToolExecutionError(
            f"MCP config file '{config_file}' must contain a non-empty "
            "JSON object mapping server names to server configs."
        )

    servers_config: dict[str, dict] = {}
    for name, server_config in raw_config.items():
        if name.startswith("_"):
            continue
        if not isinstance(server_config, dict):
            if auto_mode:
                warnings.warn(
                    f"MCP auto mode skipped server '{name}': config must be an object",
                    RuntimeWarning,
                    stacklevel=2,
                )
                continue
            raise ToolExecutionError(
                f"MCP server '{name}' in '{config_file}' must be a JSON object."
            )
        servers_config[name] = server_config

    if not servers_config:
        if auto_mode:
            _warn_auto_disabled(f"{config_file} does not contain any server configs")
            return {}
        raise ToolExecutionError(
            f"MCP config file '{config_file}' must contain a non-empty "
            "JSON object mapping server names to server configs."
        )

    return servers_config


def _warn_auto_disabled(reason: str) -> None:
    warnings.warn(
        f"MCP auto mode disabled: {reason}",
        RuntimeWarning,
        stacklevel=2,
    )


async def _async_init_mcp(
    servers_config: dict,
    *,
    tolerate_errors: bool = False,
) -> tuple[object, list[object], dict[str, str]]:
    client = MultiServerMCPClient(servers_config)
    if not tolerate_errors:
        tools = await client.get_tools()
        return client, tools, {}

    tools = []
    errors = {}
    for server_name in servers_config:
        try:
            tools.extend(await client.get_tools(server_name=server_name))
        except Exception as exc:  # pragma: no cover - concrete errors depend on MCP servers
            errors[server_name] = str(exc)
    return client, tools, errors


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
