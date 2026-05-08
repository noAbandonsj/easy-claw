from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from rich.table import Table

from easy_claw.cli_views import (
    _delete_checkpoint_thread,
    _find_session_by_prefix,
    _print_browser_details,
    _print_doctor,
    _print_mcp_details,
    _print_session_list,
    _print_session_status,
    _print_skill_sources,
    _write_conversation_markdown,
    console,
)
from easy_claw.config import AppConfig
from easy_claw.storage.db import initialize_product_db
from easy_claw.storage.repositories import SessionRepository


@dataclass(frozen=True)
class LoopControl:
    action: str
    value: str | None = None


@dataclass(frozen=True)
class SlashCommandContext:
    session_id: str
    config: AppConfig
    conversation: list[tuple[str, str]]
    token_usage: dict[str, int]


@dataclass(frozen=True)
class SlashCommand:
    name: str
    usage: str
    description: str
    group: str
    handler: Callable[[SlashCommandContext, str], LoopControl | None]
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class SlashCommandSpec:
    name: str
    usage: str
    description: str
    group: str
    aliases: list[str]


def get_slash_command_specs() -> list[SlashCommandSpec]:
    return [
        SlashCommandSpec(
            name=command.name,
            usage=command.usage,
            description=command.description,
            group=command.group,
            aliases=list(command.aliases),
        )
        for command in _SLASH_COMMANDS
    ]


def _dispatch_interactive_command(
    prompt: str,
    context: SlashCommandContext,
) -> tuple[bool, LoopControl | None]:
    raw = prompt.strip()
    lowered = raw.lower()
    if lowered in {"exit", "quit", ":q"}:
        return True, LoopControl("exit")
    if not raw.startswith("/"):
        return False, None

    command_token, _, args = raw.partition(" ")
    command = _SLASH_COMMANDS_BY_NAME.get(command_token.lower())
    if command is None:
        console.print(f"[yellow]未知命令：{command_token}[/]")
        console.print("[dim]输入 /help 查看可用命令。[/]")
        return True, None
    return True, command.handler(context, args.strip())


def _handle_help_command(context: SlashCommandContext, args: str) -> LoopControl | None:
    _print_help(args or None)
    return None


def _handle_exit_command(context: SlashCommandContext, args: str) -> LoopControl | None:
    return LoopControl("exit")


def _handle_clear_command(context: SlashCommandContext, args: str) -> LoopControl | None:
    return LoopControl("clear")


def _handle_workspace_command(context: SlashCommandContext, args: str) -> LoopControl | None:
    if not args:
        console.print(f"[dim]当前工作区：{context.config.default_workspace}[/]")
        console.print("[yellow]用法：/workspace <path>[/]")
        return None
    return LoopControl("workspace", args)


def _handle_model_command(context: SlashCommandContext, args: str) -> LoopControl | None:
    if not args:
        console.print(f"[dim]当前模型：{context.config.model or '未配置'}[/]")
        console.print("[yellow]用法：/model <name>[/]")
        return None
    return LoopControl("model", args)


def _handle_status_command(context: SlashCommandContext, args: str) -> LoopControl | None:
    _print_session_status(
        context.session_id,
        context.config,
        context.conversation,
        context.token_usage,
    )
    return None


def _handle_save_command(context: SlashCommandContext, args: str) -> LoopControl | None:
    if not args:
        console.print("[yellow]用法：/save <path>[/]")
        return None
    save_path = Path(args).expanduser().resolve()
    _write_conversation_markdown(
        context.conversation,
        save_path,
        context.session_id,
        context.config,
    )
    console.print(f"[dim]对话已保存到 {save_path}[/]")
    return None


def _handle_doctor_command(context: SlashCommandContext, args: str) -> LoopControl | None:
    _print_doctor(context.config, test_browser=False)
    return None


def _handle_skills_command(context: SlashCommandContext, args: str) -> LoopControl | None:
    _print_skill_sources(context.config)
    return None


def _handle_mcp_command(context: SlashCommandContext, args: str) -> LoopControl | None:
    _print_mcp_details(context.config)
    return None


def _handle_browser_command(context: SlashCommandContext, args: str) -> LoopControl | None:
    _print_browser_details(context.config)
    return None


def _handle_sessions_command(context: SlashCommandContext, args: str) -> LoopControl | None:
    _print_session_list(context.config)
    return None


def _handle_resume_command(context: SlashCommandContext, args: str) -> LoopControl | None:
    if not args:
        console.print("[yellow]用法：/resume <session-id>[/]")
        return None
    initialize_product_db(context.config.product_db_path)
    matched = _find_session_by_prefix(SessionRepository(context.config.product_db_path), args)
    if matched is None:
        console.print(f"没有找到匹配 [bold]{args}[/] 的会话。")
        return None
    return LoopControl("resume", matched.id)


def _handle_delete_session_command(
    context: SlashCommandContext,
    args: str,
) -> LoopControl | None:
    parts = args.split()
    force = any(part in {"--force", "-f"} for part in parts)
    session_ids = [part for part in parts if part not in {"--force", "-f"}]
    if len(session_ids) != 1:
        console.print("[yellow]用法：/delete-session <session-id> [--force][/]")
        return None

    initialize_product_db(context.config.product_db_path)
    repo = SessionRepository(context.config.product_db_path)
    matched = _find_session_by_prefix(repo, session_ids[0])
    if matched is None:
        console.print(f"没有找到匹配 [bold]{session_ids[0]}[/] 的会话。")
        return None
    if not force:
        if not console.is_terminal:
            console.print("[yellow]非交互式输入请使用 /delete-session <session-id> --force[/]")
            return None
        from typer import confirm

        if not confirm(f"确认删除会话 [bold]{matched.title}[/] ({matched.id[:8]})？"):
            return None

    repo.delete_session(matched.id)
    _delete_checkpoint_thread(matched.id, context.config.checkpoint_db_path)
    console.print(f"已删除会话 [bold]{matched.title}[/]。")
    return None


_SLASH_COMMANDS: tuple[SlashCommand, ...] = (
    SlashCommand(
        "/help",
        "/help [command]",
        "显示聊天内命令，或查看某个命令的用法",
        "帮助",
        _handle_help_command,
    ),
    SlashCommand(
        "/exit",
        "/exit",
        "退出助手；也可以输入 exit、quit 或 :q",
        "会话",
        _handle_exit_command,
        aliases=("exit", "quit", ":q", "/quit"),
    ),
    SlashCommand(
        "/clear",
        "/clear",
        "清空对话历史并开始新会话",
        "会话",
        _handle_clear_command,
    ),
    SlashCommand(
        "/status",
        "/status",
        "显示模型、工作区、Skill、MCP、浏览器和 token 用量",
        "会话",
        _handle_status_command,
    ),
    SlashCommand(
        "/save",
        "/save <path>",
        "把当前对话保存为 Markdown 文件",
        "会话",
        _handle_save_command,
    ),
    SlashCommand(
        "/workspace",
        "/workspace <path>",
        "切换后续任务使用的工作区",
        "配置",
        _handle_workspace_command,
    ),
    SlashCommand(
        "/model",
        "/model <name>",
        "切换后续请求使用的模型",
        "配置",
        _handle_model_command,
    ),
    SlashCommand(
        "/doctor",
        "/doctor",
        "查看本地配置、数据库、MCP 和浏览器诊断",
        "能力",
        _handle_doctor_command,
    ),
    SlashCommand(
        "/skills",
        "/skills",
        "查看本次会话自动收集的 skill 来源",
        "能力",
        _handle_skills_command,
    ),
    SlashCommand(
        "/mcp",
        "/mcp",
        "查看 MCP 模式、配置文件和服务数量",
        "能力",
        _handle_mcp_command,
    ),
    SlashCommand(
        "/browser",
        "/browser",
        "查看浏览器工具开关和 Playwright 安装状态",
        "能力",
        _handle_browser_command,
    ),
    SlashCommand(
        "/sessions",
        "/sessions",
        "列出历史聊天会话",
        "历史",
        _handle_sessions_command,
    ),
    SlashCommand(
        "/resume",
        "/resume <session-id>",
        "恢复历史会话，ID 输入前 8 位即可",
        "历史",
        _handle_resume_command,
    ),
    SlashCommand(
        "/delete-session",
        "/delete-session <session-id>",
        "删除聊天会话及其检查点",
        "历史",
        _handle_delete_session_command,
    ),
)
_SLASH_COMMANDS_BY_NAME = {
    alias: command
    for command in _SLASH_COMMANDS
    for alias in (command.name, *command.aliases)
}


def _normalize_help_command_name(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"exit", "quit", ":q"}:
        return normalized
    if normalized and not normalized.startswith("/"):
        return f"/{normalized}"
    return normalized


def _print_help(command_name: str | None = None) -> None:
    """打印交互式命令说明。"""
    if command_name:
        command = _SLASH_COMMANDS_BY_NAME.get(_normalize_help_command_name(command_name))
        if command is None:
            console.print(f"[yellow]未知命令：{command_name}[/]")
            console.print("[dim]输入 /help 查看所有聊天内命令。[/]")
            return
        aliases = ", ".join(command.aliases) if command.aliases else "-"
        table = Table(title=command.usage, title_style="bold")
        table.add_column("属性", style="bold cyan")
        table.add_column("值")
        table.add_row("类别", command.group)
        table.add_row("说明", command.description)
        table.add_row("别名", aliases)
        console.print(table)
        return

    table = Table(title="聊天内斜杠命令", title_style="bold")
    table.add_column("类别", style="bold magenta", no_wrap=True)
    table.add_column("命令", style="bold cyan", no_wrap=True)
    table.add_column("说明")
    for command in _SLASH_COMMANDS:
        table.add_row(command.group, command.usage, command.description)
    console.print(table)
    console.print("[dim]完整外部 CLI 帮助：uv run easy-claw --help[/]")
