from __future__ import annotations

import dataclasses
import json
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Annotated

import typer
import uvicorn
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from easy_claw import __version__ as _easy_claw_version
from easy_claw.agent.runtime import (
    AgentRequest,
    AgentResult,
    DeepAgentsRuntime,
    FakeAgentRuntime,
    StreamEvent,
)
from easy_claw.config import AppConfig, load_config
from easy_claw.skills import SkillSource, discover_skills, resolve_skill_sources
from easy_claw.storage.db import initialize_product_db
from easy_claw.storage.repositories import AuditRepository, SessionRecord, SessionRepository
from easy_claw.tools.base import ToolExecutionError
from easy_claw.tools.commands import run_command
from easy_claw.tools.python_runner import run_python_code
from easy_claw.tools.search import search_web

console = Console()
DEFAULT_SKILLS_ROOT = Path("skills")
STREAM_PANEL_VALUE_LIMIT = 1200
app = typer.Typer(
    help="easy-claw - Windows 优先的本地 AI 助手",
    invoke_without_command=True,
    no_args_is_help=False,
)
dev_app = typer.Typer(help="开发者调试命令")
skills_app = typer.Typer(help="管理 Markdown 技能")
tools_app = typer.Typer(help="运行本地工具")
sessions_app = typer.Typer(help="管理聊天会话")
app.add_typer(sessions_app, name="sessions", rich_help_panel="管理")
app.add_typer(dev_app, name="dev", rich_help_panel="开发")
dev_app.add_typer(skills_app, name="skills")
dev_app.add_typer(tools_app, name="tools")


@dataclasses.dataclass(frozen=True)
class LoopControl:
    action: str
    value: str | None = None


@dataclasses.dataclass(frozen=True)
class SlashCommandContext:
    session_id: str
    config: AppConfig | None
    conversation: list[tuple[str, str]]
    token_usage: dict[str, int]
    supports_clear: bool


@dataclasses.dataclass(frozen=True)
class SlashCommand:
    name: str
    usage: str
    description: str
    group: str
    handler: Callable[[SlashCommandContext, str], LoopControl | None]
    aliases: tuple[str, ...] = ()


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"easy-claw v{_easy_claw_version}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def _main_callback(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="显示版本并退出。",
    ),
) -> None:
    if ctx.invoked_subcommand is not None:
        return
    _run_interactive_chat(dry_run=False, config=load_config())


@app.command(rich_help_panel="管理")
def doctor() -> None:
    """打印本地环境诊断信息。"""
    _print_doctor(load_config(), test_browser=True)


def _print_doctor(config: AppConfig, *, test_browser: bool) -> None:
    """打印本地环境诊断信息。"""
    console.print("easy-claw doctor")
    console.print(f"数据目录: {config.data_dir}")
    console.print(f"业务数据库: {config.product_db_path}")
    console.print(f"检查点数据库: {config.checkpoint_db_path}")
    console.print(f"工作区: {config.default_workspace}")
    console.print(f"模型: {config.model or '<未配置>'}")
    console.print(f"模型服务地址: {config.base_url}")
    console.print(f"审批模式: {config.approval_mode}")
    console.print(f"执行模式: {config.execution_mode}")
    console.print(f"浏览器工具: {config.browser_enabled}")
    console.print(f"浏览器无头模式: {config.browser_headless}")
    console.print(f"MCP 启用状态: {_mcp_status(config)}")
    console.print(f"MCP 模式: {config.mcp_mode}")
    console.print(f"MCP 配置文件: {config.mcp_config_path}")
    console.print(f"模型调用上限: {config.max_model_calls}")
    console.print(f"工具调用上限: {config.max_tool_calls}")
    api_key_display = "***" + config.api_key[-4:] if config.api_key else "<未配置>"
    console.print(f"密钥: {api_key_display}")

    # 浏览器诊断
    console.print()
    console.print("[bold]浏览器诊断[/]")
    try:
        from easy_claw.tools.browser import _check_playwright_browsers
    except ImportError:
        console.print("[yellow]未安装 playwright 包[/]")
        return

    chromium_installed = _check_playwright_browsers(headless=False)
    headless_installed = _check_playwright_browsers(headless=True)
    console.print(f"Chromium（有界面）: {'已安装' if chromium_installed else '[red]未安装[/]'}")
    console.print(f"Chromium（无头）: {'已安装' if headless_installed else '[red]未安装[/]'}")

    if not chromium_installed and not headless_installed:
        console.print("[dim]请运行：uv run playwright install chromium[/]")
        return

    if not test_browser:
        console.print("[dim]聊天内 /doctor 跳过实时浏览器启动测试。[/]")
        console.print("[dim]需要完整浏览器启动测试时运行：uv run easy-claw doctor[/]")
        return

    # 浏览器实时检查：启动、加载页面、提取文本、关闭。
    if config.browser_enabled:
        console.print("[dim]正在测试浏览器启动和页面访问...[/]")
        try:
            from easy_claw.tools.browser import build_browser_tools

            bundle = build_browser_tools(enabled=True, headless=True)
            console.print(f"[green]浏览器已启动[/] — 已加载 {len(bundle.tools)} 个工具")
            for cb in bundle.cleanup:
                cb()
            console.print("[green]浏览器已正常关闭[/]")
        except Exception as exc:
            console.print(f"[red]浏览器测试失败：{exc}[/]")


@app.command("init-db", rich_help_panel="管理")
def init_db() -> None:
    """初始化本地存储。"""
    config = load_config()
    initialize_product_db(config.product_db_path)
    console.print(f"已初始化 {config.product_db_path}")


@app.command("list-sessions", rich_help_panel="管理")
@sessions_app.command("list")
def list_sessions() -> None:
    """列出历史聊天会话。"""
    _print_session_list(load_config())


@app.command("resume-session", rich_help_panel="管理")
@sessions_app.command("resume")
def resume_session(
    session_id: Annotated[str, typer.Argument(help="会话 ID，输入前 8 位即可")],
    model: Annotated[str | None, typer.Option("--model", help="覆盖模型名称。")] = None,
) -> None:
    """恢复已有聊天会话。"""
    config = load_config()
    if model is not None:
        config = dataclasses.replace(config, model=model)
    initialize_product_db(config.product_db_path)
    repo = SessionRepository(config.product_db_path)

    # 按前缀匹配会话。
    matched = _find_session_by_prefix(repo, session_id)
    if matched is None:
        console.print(f"没有找到匹配 [bold]{session_id}[/] 的会话。")
        raise typer.Exit(code=1)

    _run_interactive_chat(dry_run=False, config=config, resume_thread_id=matched.id)


@app.command("delete-session", rich_help_panel="管理")
@sessions_app.command("delete")
def delete_session(
    session_id: Annotated[str, typer.Argument(help="会话 ID，输入前 8 位即可")],
    force: bool = typer.Option(False, "--force", "-f", help="跳过确认。"),
) -> None:
    """删除聊天会话及其检查点。"""
    config = load_config()
    initialize_product_db(config.product_db_path)
    repo = SessionRepository(config.product_db_path)

    matched = _find_session_by_prefix(repo, session_id)
    if matched is None:
        console.print(f"没有找到匹配 [bold]{session_id}[/] 的会话。")
        raise typer.Exit(code=1)

    if not force:
        from typer import confirm

        if not confirm(f"确认删除会话 [bold]{matched.title}[/] ({matched.id[:8]})？"):
            raise typer.Exit()

    repo.delete_session(matched.id)
    _delete_checkpoint_thread(matched.id, config.checkpoint_db_path)
    console.print(f"已删除会话 [bold]{matched.title}[/]。")


def _find_session_by_prefix(repo: SessionRepository, prefix: str) -> SessionRecord | None:
    sessions = repo.list_sessions()
    matches = [s for s in sessions if s.id.startswith(prefix)]
    if len(matches) == 1:
        return matches[0]
    # 前缀不唯一时回退为精确匹配。
    return repo.get_session(prefix)


def _delete_checkpoint_thread(thread_id: str, checkpoint_db_path: Path) -> None:
    """使用 LangGraph 公开接口删除指定线程的所有检查点。"""
    from langgraph.checkpoint.sqlite import SqliteSaver

    if not checkpoint_db_path.exists():
        return
    try:
        with SqliteSaver.from_conn_string(str(checkpoint_db_path)) as saver:
            saver.delete_thread(thread_id)
    except Exception:
        console.print(f"[yellow]警告：[/]会话已删除，但未能清理 {checkpoint_db_path} 中的检查点")


@skills_app.command("list")
def list_skills(
    skills_root: Annotated[Path, typer.Option("--skills-root")] = DEFAULT_SKILLS_ROOT,
    all_sources: Annotated[
        bool,
        typer.Option("--all-sources", help="显示当前会话会自动收集的所有 skill 来源。"),
    ] = False,
    workspace: Annotated[
        Path | None,
        typer.Option("--workspace", help="用于解析项目级 skill 的工作区。"),
    ] = None,
) -> None:
    """列出可用 Markdown 技能。"""
    if all_sources:
        config = load_config()
        workspace_root = workspace or config.default_workspace
        sources = resolve_skill_sources(app_root=config.cwd, workspace_root=workspace_root)
        console.out("scope\tlabel\tskill_count\tbackend_path\tfilesystem_path")
        for source in sources:
            console.out(
                "\t".join(
                    [
                        source.scope,
                        source.label,
                        str(source.skill_count),
                        source.backend_path,
                        str(source.filesystem_path),
                    ]
                )
            )
        return

    skills = discover_skills(skills_root)
    table = Table("名称", "说明", "路径")
    for skill in skills:
        table.add_row(skill.name, skill.description, str(skill.path))
    console.print(table)


@app.command(rich_help_panel="管理")
def serve(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8787, "--port"),
) -> None:
    """启动本地 API 服务（开发者向）。"""
    uvicorn.run("easy_claw.api.main:app", host=host, port=port)


@app.command(rich_help_panel="主命令")
def chat(
    prompt: Annotated[str | None, typer.Argument()] = None,
    dry_run: bool = typer.Option(False, "--dry-run"),
    interactive: bool = typer.Option(False, "--interactive", "-i"),
    model: Annotated[
        str | None,
        typer.Option("--model", help="覆盖模型名称，例如 deepseek-chat。"),
    ] = None,
) -> None:
    """启动 AI 助手；不传参数时建议使用交互模式。"""
    config = load_config()
    if model is not None:
        config = dataclasses.replace(config, model=model)

    if interactive:
        _run_interactive_chat(dry_run=dry_run, config=config)
        return

    if prompt is None or prompt.strip() == "":
        console.print("请提供提示词，或使用 --interactive 启动交互模式。")
        raise typer.Exit(code=1)

    if dry_run:
        result = FakeAgentRuntime().run(
            AgentRequest(
                prompt=prompt,
                thread_id="dry-run",
                config=None,
            )
        )
        console.print(result.content)
        return

    if config.model is None:
        console.print("请先设置 EASY_CLAW_MODEL，再运行非 dry-run 聊天。")
        raise typer.Exit(code=1)

    initialize_product_db(config.product_db_path)
    audit_repo = AuditRepository(config.product_db_path)
    session = SessionRepository(config.product_db_path).create_session(
        workspace_path=str(config.default_workspace),
        model=config.model,
        title=prompt[:60] or "聊天",
    )
    skill_source_records = _resolve_skill_source_records(config)
    result = DeepAgentsRuntime().run(
        AgentRequest(
            prompt=prompt,
            thread_id=session.id,
            config=config,
            skill_source_records=skill_source_records,
        )
    )
    audit_repo.record(
        event_type="agent_run",
        payload={"session_id": session.id, "prompt_length": len(prompt)},
    )
    console.print(result.content)


def _run_interactive_chat(
    *,
    dry_run: bool,
    config: AppConfig,  # noqa: F821
    resume_thread_id: str | None = None,
) -> None:
    if not dry_run and config.model is None:
        console.print("请先设置 EASY_CLAW_MODEL，再运行非 dry-run 聊天。")
        raise typer.Exit(code=1)

    if dry_run:
        runtime = FakeAgentRuntime()
        session_id = "dry-run"
        audit_repo = None

        _render_startup_banner(config)
        _run_interactive_loop(
            run_turn=lambda prompt: runtime.run(
                AgentRequest(
                    prompt=prompt,
                    thread_id=session_id,
                    config=None,
                )
            ),
            audit_repo=audit_repo,
            session_id=session_id,
            supports_clear=False,
            session_config=config,
        )
        return

    initialize_product_db(config.product_db_path)
    audit_repo = AuditRepository(config.product_db_path)
    runtime = DeepAgentsRuntime()
    conversation: list[tuple[str, str]] = []
    token_usage: dict[str, int] = {}

    _render_startup_banner(config)

    # 首轮使用传入的会话 ID；没有传入时创建新会话。
    thread_id: str | None = resume_thread_id
    open_session = getattr(runtime, "open_session", None)

    while True:
        if thread_id is None:
            session = SessionRepository(config.product_db_path).create_session(
                workspace_path=str(config.default_workspace),
                model=config.model,
                title="交互式聊天",
            )
            thread_id = session.id

        base_request = AgentRequest(
            prompt="",
            thread_id=thread_id,
            config=config,
            skill_source_records=_resolve_skill_source_records(config),
        )

        if open_session is None:
            control = _run_interactive_loop(
                run_turn=lambda prompt, req=base_request: runtime.run(
                    _agent_request_for_prompt(req, prompt)
                ),
                audit_repo=audit_repo,
                session_id=thread_id,
                supports_clear=True,
                session_config=config,
                conversation=conversation,
                token_usage=token_usage,
            )
        else:
            with open_session(base_request) as agent_session:
                stream_turn = getattr(agent_session, "stream", None)
                control = _run_interactive_loop(
                    run_turn=agent_session.run,
                    stream_turn=stream_turn,
                    audit_repo=audit_repo,
                    session_id=thread_id,
                    supports_clear=True,
                    session_config=config,
                    conversation=conversation,
                    token_usage=token_usage,
                )

        if control.action == "exit":
            break
        if control.action == "workspace":
            new_path = Path(control.value or "").expanduser().resolve()
            if not new_path.is_dir():
                console.print(f"[yellow]不是目录：{new_path}[/]")
                continue
            config = dataclasses.replace(config, default_workspace=new_path)
            # 切换工作区时保留会话 ID 和对话历史。
            console.print(f"[dim]工作区已切换到 {new_path}[/]")
            continue
        if control.action == "model":
            model_name = (control.value or "").strip()
            if not model_name:
                console.print("[yellow]用法：/model <name>[/]")
                continue
            config = dataclasses.replace(config, model=model_name)
            console.print(f"[dim]模型已切换到 {model_name}[/]")
            continue
        if control.action == "resume":
            matched = SessionRepository(config.product_db_path).get_session(control.value or "")
            if matched is None:
                console.print(f"[yellow]会话不存在：{control.value}[/]")
                continue
            thread_id = matched.id
            workspace_path = Path(matched.workspace_path).expanduser()
            if workspace_path.is_dir():
                config = dataclasses.replace(
                    config,
                    default_workspace=workspace_path.resolve(),
                    model=matched.model or config.model,
                )
            elif matched.model:
                config = dataclasses.replace(config, model=matched.model)
            conversation.clear()
            token_usage.clear()
            console.print(f"[dim]已恢复会话 {matched.id[:8]}：{matched.title}[/]")
            continue
        if control.action == "clear":
            thread_id = None  # /clear：下一轮创建新会话。
            conversation.clear()
            token_usage.clear()
            console.print("[dim]对话历史已清空，已开始新会话。[/]")
            continue


def _run_interactive_loop(
    *,
    run_turn: Callable[[str], AgentResult],
    audit_repo: AuditRepository | None,
    session_id: str,
    stream_turn: Callable[[str], Iterable[StreamEvent]] | None = None,
    supports_clear: bool = False,
    session_config: AppConfig | None = None,  # noqa: F821
    conversation: list[tuple[str, str]] | None = None,
    token_usage: dict[str, int] | None = None,
) -> LoopControl:
    """运行交互式循环。

    返回值：
        LoopControl 表示用户退出或请求调用方调整会话状态。
    """
    if conversation is None:
        conversation = []
    if token_usage is None:
        token_usage = {}

    while True:
        try:
            prompt = _read_interactive_prompt()
        except EOFError:
            console.print()
            return LoopControl("exit")
        if not prompt:
            continue

        command_handled, control = _dispatch_interactive_command(
            prompt,
            SlashCommandContext(
                session_id=session_id,
                config=session_config,
                conversation=conversation,
                token_usage=token_usage,
                supports_clear=supports_clear,
            ),
        )
        if command_handled:
            if control is not None:
                return control
            continue

        if stream_turn is not None:
            response, usage = _render_streaming_turn(stream_turn(prompt))
        else:
            with console.status("[dim]正在思考...[/]"):
                result = run_turn(prompt)
            response = result.content
            usage = result.usage
            console.print(response)

        conversation.append((prompt, response))
        if usage:
            for key in ("input", "output", "total"):
                token_usage[key] = token_usage.get(key, 0) + usage.get(key, 0)

        if audit_repo is not None:
            audit_repo.record(
                event_type="agent_run",
                payload={"session_id": session_id, "prompt_length": len(prompt)},
            )

    return LoopControl("exit")


def _agent_request_for_prompt(request: AgentRequest, prompt: str) -> AgentRequest:
    return dataclasses.replace(request, prompt=prompt)


def _resolve_skill_source_records(config: AppConfig) -> list[SkillSource]:
    return resolve_skill_sources(app_root=config.cwd, workspace_root=config.default_workspace)


@tools_app.command("search")
def tool_search(query: str) -> None:
    """联网搜索。"""
    config = load_config()
    initialize_product_db(config.product_db_path)
    try:
        results = search_web(query, config=config)
    except ToolExecutionError as exc:
        AuditRepository(config.product_db_path).record(
            event_type="web_search_failed",
            payload={"query": query, "error": str(exc)},
        )
        console.print(str(exc))
        raise typer.Exit(code=1) from exc
    AuditRepository(config.product_db_path).record(
        event_type="web_search",
        payload={"query": query, "result_count": len(results)},
    )
    table = Table("标题", "URL", "摘要")
    for result in results:
        table.add_row(result.title, result.url, result.snippet)
    console.print(table)


@tools_app.command("run")
def tool_run(command: str) -> None:
    """执行本地 shell 命令。"""
    config = load_config()
    initialize_product_db(config.product_db_path)
    result = run_command(command, cwd=config.cwd)
    AuditRepository(config.product_db_path).record(
        event_type="command_run",
        payload={
            "command": command,
            "cwd": str(result.cwd),
            "exit_code": result.exit_code,
            "timed_out": result.timed_out,
            "truncated": result.truncated,
            "timeout_seconds": 60,
        },
    )
    if result.stdout:
        console.print(result.stdout)
    if result.stderr:
        console.print(result.stderr)
    if result.exit_code != 0:
        raise typer.Exit(code=result.exit_code)


@tools_app.command("python")
def tool_python(code: str) -> None:
    """执行本地 Python 片段。"""
    config = load_config()
    initialize_product_db(config.product_db_path)
    result = run_python_code(code, cwd=config.cwd)
    AuditRepository(config.product_db_path).record(
        event_type="python_run",
        payload={
            "cwd": str(result.cwd),
            "exit_code": result.exit_code,
            "timed_out": result.timed_out,
            "truncated": result.truncated,
            "timeout_seconds": 60,
        },
    )
    if result.stdout:
        console.print(result.stdout)
    if result.stderr:
        console.print(result.stderr)
    if result.exit_code != 0:
        raise typer.Exit(code=result.exit_code)


def _render_streaming_turn(events: Iterable[StreamEvent]) -> tuple[str, dict[str, int] | None]:
    """渲染一次流式回复，返回回复文本和用量。"""
    tokens: list[str] = []
    usage: dict[str, int] | None = None
    printed_token = False
    spinner = console.status("[dim]正在思考...[/]")
    spinner.start()
    spinner_running = True
    try:
        for event in events:
            if spinner_running:
                spinner.stop()
                spinner_running = False
            if event.type == "token":
                console.print(event.content, end="")
                tokens.append(event.content)
                printed_token = True
            elif event.type == "tool_call_start":
                _print_stream_separator(printed_token)
                console.print(
                    Panel(
                        _format_stream_value(event.tool_args),
                        title=f"工具调用：{event.tool_name or '未知工具'}",
                        border_style="blue",
                    )
                )
                printed_token = False
            elif event.type == "tool_call_result":
                _print_stream_separator(printed_token)
                console.print(
                    Panel(
                        _format_stream_value(event.content or event.tool_result),
                        title=f"工具结果：{event.tool_name or '未知工具'}",
                        border_style="green",
                    )
                )
                printed_token = False
            elif event.type == "approval_required":
                _print_stream_separator(printed_token)
                console.print("[yellow]工具执行需要确认[/]")
                printed_token = False
            elif event.type == "done":
                if spinner_running:
                    spinner.stop()
                    spinner_running = False
                if printed_token:
                    console.print()
                printed_token = False
                usage = event.usage
    finally:
        if spinner_running:
            spinner.stop()
    return "".join(tokens), usage


def _print_stream_separator(printed_token: bool) -> None:
    if printed_token:
        console.print()


def _write_conversation_markdown(
    conversation: list[tuple[str, str]],
    path: Path,
    session_id: str,
    config: AppConfig | None,  # noqa: F821
) -> None:
    from datetime import datetime

    lines: list[str] = []
    lines.append("# easy-claw 对话记录")
    lines.append("")
    lines.append(f"- **会话：** `{session_id}`")
    lines.append(f"- **模型：** {config.model if config else '未配置'}")
    lines.append(f"- **工作区：** {config.default_workspace if config else '未配置'}")
    lines.append(f"- **导出时间：** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append("---")
    lines.append("")

    for i, (user_msg, assistant_msg) in enumerate(conversation, 1):
        lines.append(f"### 第 {i} 轮")
        lines.append("")
        lines.append("**用户：**")
        lines.append("")
        lines.append(f"{user_msg}")
        lines.append("")
        lines.append("**easy-claw:**")
        lines.append("")
        lines.append(f"{assistant_msg}")
        lines.append("")
        lines.append("---")
        lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _read_interactive_prompt() -> str:
    if console.is_terminal:
        return console.input("[bold hot_pink]>[/] ").strip()
    return input("> ").strip()


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
    if not context.supports_clear:
        console.print("[dim]dry-run 模式不支持清空历史。[/]")
        return None
    return LoopControl("clear")


def _handle_workspace_command(context: SlashCommandContext, args: str) -> LoopControl | None:
    if not context.supports_clear:
        console.print("[dim]dry-run 模式不支持切换工作区。[/]")
        return None
    if not args:
        if context.config is not None:
            console.print(f"[dim]当前工作区：{context.config.default_workspace}[/]")
        console.print("[yellow]用法：/workspace <path>[/]")
        return None
    return LoopControl("workspace", args)


def _handle_model_command(context: SlashCommandContext, args: str) -> LoopControl | None:
    if not args:
        current = context.config.model if context.config else None
        console.print(f"[dim]当前模型：{current or '未配置'}[/]")
        console.print("[yellow]用法：/model <name>[/]")
        return None
    if not context.supports_clear:
        console.print("[dim]dry-run 模式不需要切换模型。[/]")
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
    if context.config is None:
        console.print("[dim]当前模式没有可用配置。[/]")
        return None
    _print_doctor(context.config, test_browser=False)
    return None


def _handle_skills_command(context: SlashCommandContext, args: str) -> LoopControl | None:
    if context.config is None:
        console.print("[dim]当前模式没有可用配置。[/]")
        return None
    _print_skill_sources(context.config)
    return None


def _handle_mcp_command(context: SlashCommandContext, args: str) -> LoopControl | None:
    if context.config is None:
        console.print("[dim]当前模式没有可用配置。[/]")
        return None
    _print_mcp_details(context.config)
    return None


def _handle_browser_command(context: SlashCommandContext, args: str) -> LoopControl | None:
    if context.config is None:
        console.print("[dim]当前模式没有可用配置。[/]")
        return None
    _print_browser_details(context.config)
    return None


def _handle_sessions_command(context: SlashCommandContext, args: str) -> LoopControl | None:
    if context.config is None:
        console.print("[dim]当前模式没有可用配置。[/]")
        return None
    _print_session_list(context.config)
    return None


def _handle_resume_command(context: SlashCommandContext, args: str) -> LoopControl | None:
    if context.config is None or not context.supports_clear:
        console.print("[dim]当前模式不支持恢复会话。[/]")
        return None
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
    if context.config is None or not context.supports_clear:
        console.print("[dim]当前模式不支持删除会话。[/]")
        return None
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


def _print_session_list(config: AppConfig) -> None:
    initialize_product_db(config.product_db_path)
    repo = SessionRepository(config.product_db_path)
    sessions = repo.list_sessions()
    if not sessions:
        console.print("[dim]没有找到会话。[/]")
        return
    table = Table("ID", "标题", "模型", "更新时间")
    for s in sessions:
        table.add_row(s.id[:8], s.title[:60], s.model or "-", s.updated_at[:19])
    console.print(table)


def _print_skill_sources(config: AppConfig) -> None:
    sources = _resolve_skill_source_records(config)
    if not sources:
        console.print("[dim]没有找到 skill 来源。[/]")
        return
    console.print("[bold]Skill 来源[/]")
    for source in sources:
        console.print(f"[bold cyan]{source.label}[/]")
        console.print(f"  范围: {source.scope}")
        console.print(f"  skill 数量: {source.skill_count}")
        console.print(f"  后端路径: {source.backend_path}")
        console.print(f"  本地路径: {source.filesystem_path}")


def _print_mcp_details(config: AppConfig) -> None:
    table = Table(title="MCP", title_style="bold")
    table.add_column("属性", style="bold cyan")
    table.add_column("值")
    table.add_row("模式", config.mcp_mode)
    table.add_row("启用状态", _mcp_status(config))
    table.add_row("配置文件", config.mcp_config_path)
    table.add_row("服务数量", str(_count_mcp_servers(config.mcp_config_path)))
    console.print(table)


def _print_browser_details(config: AppConfig) -> None:
    table = Table(title="浏览器工具", title_style="bold")
    table.add_column("属性", style="bold cyan")
    table.add_column("值")
    table.add_row("启用", "是" if config.browser_enabled else "否")
    table.add_row("无头模式", "是" if config.browser_headless else "否")
    try:
        from easy_claw.tools.browser import _check_playwright_browsers
    except ImportError:
        table.add_row("Playwright", "未安装")
    else:
        table.add_row(
            "Chromium（有界面）",
            "已安装" if _check_playwright_browsers(headless=False) else "未安装",
        )
        table.add_row(
            "Chromium（无头）",
            "已安装" if _check_playwright_browsers(headless=True) else "未安装",
        )
    console.print(table)


def _format_limit(value: int | None) -> str:
    return "无限制" if value is None else f"{value:,}"


def _skill_source_summary(config: AppConfig) -> str:
    try:
        sources = _resolve_skill_source_records(config)
    except Exception as exc:
        return f"无法解析：{exc}"
    skill_count = sum(source.skill_count for source in sources)
    return f"{len(sources)} 个来源，{skill_count} 个 skill"


def _print_session_status(
    session_id: str,
    config: AppConfig | None,  # noqa: F821
    conversation: list[tuple[str, str]],
    token_usage: dict[str, int] | None = None,
) -> None:
    cfg = config
    table = Table(title=f"会话 {session_id[:8]}", title_style="bold")
    table.add_column("属性", style="bold cyan")
    table.add_column("值")
    table.add_row("模型", cfg.model if cfg else "未配置")
    table.add_row("工作区", str(cfg.default_workspace) if cfg else "未配置")
    table.add_row("审批模式", cfg.approval_mode if cfg else "未配置")
    table.add_row("浏览器", "已启用" if cfg and cfg.browser_enabled else "已关闭")
    table.add_row("MCP", _mcp_status(cfg) if cfg else "未配置")
    table.add_row("Skill 来源", _skill_source_summary(cfg) if cfg else "未配置")
    table.add_row("模型调用上限", _format_limit(cfg.max_model_calls) if cfg else "未配置")
    table.add_row("工具调用上限", _format_limit(cfg.max_tool_calls) if cfg else "未配置")
    table.add_row("轮次", str(len(conversation)))
    if token_usage:
        table.add_row("输入 token", f"{token_usage.get('input', 0):,}")
        table.add_row("输出 token", f"{token_usage.get('output', 0):,}")
        table.add_row("总 token", f"{token_usage.get('total', 0):,}")
    table.add_row("检查点", str(cfg.checkpoint_db_path) if cfg else "未配置")
    console.print(table)


def _format_stream_value(value: object) -> str:
    if value is None:
        text = ""
    elif isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, ensure_ascii=False, indent=2, default=str)
        except TypeError:
            text = str(value)
    if len(text) <= STREAM_PANEL_VALUE_LIMIT:
        return text
    return text[:STREAM_PANEL_VALUE_LIMIT] + "\n\\[已截断]"


def _count_mcp_servers(config_path: str) -> int:
    try:
        data = json.loads(Path(config_path).read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return sum(
                1
                for name, server_config in data.items()
                if not name.startswith("_") and isinstance(server_config, dict)
            )
    except Exception:
        pass
    return 0


def _mcp_status(config: AppConfig) -> str:
    mode = getattr(config, "mcp_mode", "enabled" if config.mcp_enabled else "disabled")
    if mode == "auto":
        count = _count_mcp_servers(config.mcp_config_path)
        return f"auto（{count} 个服务）" if count else "auto"
    if mode == "enabled" or config.mcp_enabled:
        count = _count_mcp_servers(config.mcp_config_path)
        return f"已启用（{count} 个服务）" if count else "已启用"
    return "已关闭"


def _render_startup_banner(config: AppConfig) -> None:  # noqa: F821
    """渲染启动横幅，展示当前配置。"""
    approval_color = {"permissive": "green", "balanced": "yellow", "strict": "red"}
    color = approval_color.get(config.approval_mode, "white")

    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="bold cyan", justify="right")
    grid.add_column(style="white")
    grid.add_row("模型:", config.model or "[dim]dry-run[/]")
    grid.add_row("工作区:", str(config.default_workspace))
    grid.add_row(
        "审批:",
        f"[{color}]{config.approval_mode}[/]",
    )
    grid.add_row("浏览器:", "已启用" if config.browser_enabled else "已关闭")
    grid.add_row("MCP 工具:", _mcp_status(config))

    banner = Panel(
        grid,
        title=f"[bold]easy-claw v{_easy_claw_version}[/]",
        title_align="left",
        border_style="cyan",
    )
    console.print(banner)
    console.print("[dim]输入 /help 查看命令；输入 :q、exit 或 quit 退出；空行会跳过。[/]")
    console.print()


def main() -> None:
    app()
