from __future__ import annotations

import json
import os
import re
import warnings
from pathlib import Path

from easy_claw.agent.types import ToolBundle
from easy_claw.tools.base import ToolExecutionError, get_background_loop

try:
    from langchain_mcp_adapters.client import MultiServerMCPClient
except ImportError:  # pragma: no cover
    MultiServerMCPClient = None

_ENV_REF_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def build_mcp_tools(*, enabled: bool | str, config_path: str) -> ToolBundle:
    """从 JSON 配置文件构建 MCP 工具。

    关闭时返回空 ToolBundle。启用时读取服务配置，连接 MCP 服务，
    并返回发现到的工具和清理回调。
    """
    mode = _mcp_mode(enabled)
    if mode == "disabled":
        return ToolBundle()

    if MultiServerMCPClient is None:
        if mode == "auto":
            _warn_auto_disabled("未安装 langchain-mcp-adapters")
            return ToolBundle()
        raise ToolExecutionError("MCP 工具需要 langchain-mcp-adapters。请运行：uv sync")

    config_file = Path(config_path)
    if not config_file.exists():
        if mode == "auto":
            return ToolBundle()
        raise ToolExecutionError(
            f"未找到 MCP 配置文件：{config_file}。"
            "请创建 mcp_servers.json，或设置 EASY_CLAW_MCP_CONFIG。"
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
            _warn_auto_disabled(f"无法从 {config_file} 加载工具：{exc}")
            return ToolBundle()
        raise ToolExecutionError(f"从 '{config_file}' 加载 MCP 工具失败：{exc}") from exc

    for server_name, error in errors.items():
        warnings.warn(
            f"MCP auto 模式已跳过服务 '{server_name}'：{error}",
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
            _warn_auto_disabled(f"{config_file} 中的 JSON 无效：{exc}")
            return {}
        raise ToolExecutionError(f"MCP 配置文件 '{config_file}' 中的 JSON 无效：{exc}") from exc

    if not isinstance(raw_config, dict) or not raw_config:
        if auto_mode:
            _warn_auto_disabled(f"{config_file} 没有包含任何服务配置")
            return {}
        raise ToolExecutionError(
            f"MCP 配置文件 '{config_file}' 必须是非空 JSON 对象，并以服务名映射到服务配置。"
        )

    servers_config: dict[str, dict] = {}
    for name, server_config in raw_config.items():
        if name.startswith("_"):
            continue
        if not isinstance(server_config, dict):
            if auto_mode:
                warnings.warn(
                    f"MCP auto 模式已跳过服务 '{name}'：配置必须是对象",
                    RuntimeWarning,
                    stacklevel=2,
                )
                continue
            raise ToolExecutionError(
                f"MCP 配置文件 '{config_file}' 中的服务 '{name}' 必须是 JSON 对象。"
            )

        missing_env: set[str] = set()
        expanded_config = _expand_env_refs(server_config, missing_env)
        if missing_env:
            env_names = ", ".join(sorted(missing_env))
            if auto_mode:
                warnings.warn(
                    f"MCP auto 模式已跳过服务 '{name}'：缺少环境变量 {env_names}",
                    RuntimeWarning,
                    stacklevel=2,
                )
                continue
            raise ToolExecutionError(
                f"MCP 配置文件 '{config_file}' 中的服务 '{name}' 缺少环境变量 {env_names}。"
            )

        servers_config[name] = expanded_config

    if not servers_config:
        if auto_mode:
            _warn_auto_disabled(f"{config_file} 没有包含任何服务配置")
            return {}
        raise ToolExecutionError(
            f"MCP 配置文件 '{config_file}' 必须是非空 JSON 对象，并以服务名映射到服务配置。"
        )

    return servers_config


def _expand_env_refs(value, missing_env: set[str]):
    if isinstance(value, str):
        return _ENV_REF_PATTERN.sub(lambda match: _replace_env_ref(match, missing_env), value)

    if isinstance(value, list):
        return [_expand_env_refs(item, missing_env) for item in value]

    if isinstance(value, dict):
        return {key: _expand_env_refs(item, missing_env) for key, item in value.items()}

    return value


def _replace_env_ref(match: re.Match[str], missing_env: set[str]) -> str:
    name = match.group(1)
    value = os.environ.get(name)
    if value is None or value == "":
        missing_env.add(name)
        return match.group(0)
    return value


def _warn_auto_disabled(reason: str) -> None:
    warnings.warn(
        f"MCP auto 模式已关闭：{reason}",
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
