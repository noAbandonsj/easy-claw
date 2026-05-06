from __future__ import annotations

import dataclasses
import json
import sys
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Annotated

import typer
import uvicorn
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
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
from easy_claw.skills import discover_skill_sources, discover_skills
from easy_claw.storage.db import initialize_product_db
from easy_claw.storage.repositories import AuditRepository, SessionRecord, SessionRepository
from easy_claw.tools.base import ToolExecutionError
from easy_claw.tools.commands import run_command
from easy_claw.tools.python_runner import run_python_code
from easy_claw.tools.search import search_web

console = Console()
DEFAULT_SKILLS_ROOT = Path("skills")
STREAM_PANEL_VALUE_LIMIT = 1200
app = typer.Typer(help="easy-claw - Windows 优先的本地 AI 助手")
dev_app = typer.Typer(help="开发者调试命令")
skills_app = typer.Typer(help="管理 Markdown 技能")
tools_app = typer.Typer(help="运行本地工具")
sessions_app = typer.Typer(help="管理聊天会话")
app.add_typer(sessions_app, name="sessions", rich_help_panel="管理")
app.add_typer(dev_app, name="dev", rich_help_panel="开发")
dev_app.add_typer(skills_app, name="skills")
dev_app.add_typer(tools_app, name="tools")


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"easy-claw v{_easy_claw_version}")
        raise typer.Exit()


@app.callback()
def _main_callback(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="显示版本并退出。",
    ),
) -> None:
    pass


@app.command(rich_help_panel="管理")
def doctor() -> None:
    """打印本地环境诊断信息。"""
    config = load_config()
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


@sessions_app.command("list")
def list_sessions() -> None:
    """列出历史聊天会话。"""
    config = load_config()
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
) -> None:
    """列出可用 Markdown 技能。"""
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
    skill_sources = discover_skill_sources(config.cwd / "skills", config.default_workspace)
    result = DeepAgentsRuntime().run(
        AgentRequest(
            prompt=prompt,
            thread_id=session.id,
            config=config,
            skill_sources=skill_sources,
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
            session_config=None,
        )
        return

    initialize_product_db(config.product_db_path)
    audit_repo = AuditRepository(config.product_db_path)
    skill_sources = discover_skill_sources(config.cwd / "skills", config.default_workspace)
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
            skill_sources=skill_sources,
        )

        if open_session is None:
            restart = _run_interactive_loop(
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
                restart = _run_interactive_loop(
                    run_turn=agent_session.run,
                    stream_turn=stream_turn,
                    audit_repo=audit_repo,
                    session_id=thread_id,
                    supports_clear=True,
                    session_config=config,
                    conversation=conversation,
                    token_usage=token_usage,
                )

        if not restart:
            break
        if restart.startswith("/workspace "):
            new_path = Path(restart[len("/workspace ") :]).resolve()
            if not new_path.is_dir():
                console.print(f"[yellow]不是目录：{new_path}[/]")
                continue
            config = dataclasses.replace(config, default_workspace=new_path)
            # 切换工作区时保留会话 ID 和对话历史。
            console.print(f"[dim]工作区已切换到 {new_path}[/]")
        else:
            thread_id = None  # /clear：下一轮创建新会话。
            conversation.clear()
            token_usage.clear()
            console.print("[dim]对话历史已清空，已开始新会话。[/]")


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
) -> str | None:
    """运行交互式循环。

    返回值：
        None 表示用户退出。
        \"clear\" 表示调用方应重新创建会话。
        \"/workspace <path>\" 表示调用方应切换工作区。
    """
    if conversation is None:
        conversation = []
    if token_usage is None:
        token_usage = {}

    while True:
        try:
            console.print(Rule(style="hot_pink"))
            console.print("[bold hot_pink]>[/] ", end="")
            sys.stdout.write("\n")
            console.print(Rule(style="hot_pink"))
            sys.stdout.write("\033[2A\033[2C\033[38;5;205m")
            sys.stdout.flush()
            prompt = input().strip()
            sys.stdout.write("\033[0m\n")
            sys.stdout.flush()
        except EOFError:
            console.print()
            break
        if not prompt:
            continue
        if prompt.lower() in {"exit", "quit", ":q"}:
            break
        if prompt.lower() == "/clear":
            if supports_clear:
                return "clear"
            console.print("[dim]dry-run 模式不支持清空历史。[/]")
            continue
        if prompt.lower().startswith("/workspace"):
            if not supports_clear:
                console.print("[dim]dry-run 模式不支持切换工作区。[/]")
                continue
            parts = prompt.split(maxsplit=1)
            if len(parts) < 2 or not parts[1].strip():
                console.print("[yellow]用法：/workspace <路径>[/]")
                continue
            return f"/workspace {parts[1].strip()}"
        if prompt.lower() == "/status":
            _print_session_status(session_id, session_config, conversation, token_usage)
            continue
        if prompt.lower() == "/help":
            _print_help()
            continue
        if prompt.lower().startswith("/save"):
            parts = prompt.split(maxsplit=1)
            if len(parts) < 2 or not parts[1].strip():
                console.print("[yellow]用法：/save <路径>[/]")
                continue
            save_path = Path(parts[1].strip()).expanduser().resolve()
            _write_conversation_markdown(conversation, save_path, session_id, session_config)
            console.print(f"[dim]对话已保存到 {save_path}[/]")
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

    return None


def _agent_request_for_prompt(request: AgentRequest, prompt: str) -> AgentRequest:
    return dataclasses.replace(request, prompt=prompt)


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


def _print_help() -> None:
    """打印交互式命令说明。"""
    table = Table(title="可用命令", title_style="bold")
    table.add_column("命令", style="bold cyan")
    table.add_column("说明")
    table.add_row("/help", "显示帮助")
    table.add_row("/clear", "清空对话历史并开始新会话")
    table.add_row("/workspace <路径>", "切换工作区")
    table.add_row("/save <路径>", "把对话保存为 Markdown 文件")
    table.add_row("/status", "显示当前会话和 token 用量")
    table.add_row("exit, quit, :q", "退出助手")
    console.print(table)


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
