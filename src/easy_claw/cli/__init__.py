from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Annotated

import typer
import uvicorn
from rich.table import Table

from easy_claw import __version__ as _easy_claw_version
from easy_claw.agent.langchain_runtime import AgentRequest, LangChainAgentRuntime
from easy_claw.cli.interactive import _run_interactive_chat
from easy_claw.cli.views import (
    _delete_checkpoint_thread,
    _find_session_by_prefix,
    _print_doctor,
    _print_session_list,
    _resolve_skill_source_records,
    console,
)
from easy_claw.config import load_config
from easy_claw.skills import discover_skills, resolve_skill_sources
from easy_claw.storage.db import initialize_product_db
from easy_claw.storage.repositories import AuditRepository, SessionRepository
from easy_claw.tools.base import ToolExecutionError
from easy_claw.tools.commands import run_command
from easy_claw.tools.python_runner import run_python_code
from easy_claw.tools.search import search_web

DEFAULT_SKILLS_ROOT = Path("skills")

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
    _run_interactive_chat(config=load_config())


@app.command(rich_help_panel="管理")
def doctor() -> None:
    """打印本地环境诊断信息。"""
    _print_doctor(load_config(), test_browser=True)


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

    matched = _find_session_by_prefix(repo, session_id)
    if matched is None:
        console.print(f"没有找到匹配 [bold]{session_id}[/] 的会话。")
        raise typer.Exit(code=1)

    _run_interactive_chat(config=config, resume_thread_id=matched.id)


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
    uvicorn.run("easy_claw.api.app:app", host=host, port=port)


@app.command(rich_help_panel="主命令")
def chat(
    prompt: Annotated[str | None, typer.Argument()] = None,
    interactive: bool = typer.Option(False, "--interactive", "-i"),
    model: Annotated[
        str | None,
        typer.Option("--model", help="覆盖模型名称，例如 deepseek-chat。"),
    ] = None,
) -> None:
    """启动 AI 助手；不传参数时进入交互模式。"""
    config = load_config()
    if model is not None:
        config = dataclasses.replace(config, model=model)

    if interactive or prompt is None or prompt.strip() == "":
        _run_interactive_chat(config=config)
        return

    if config.model is None:
        console.print("请先设置 EASY_CLAW_MODEL，再运行聊天。")
        raise typer.Exit(code=1)

    initialize_product_db(config.product_db_path)
    audit_repo = AuditRepository(config.product_db_path)
    session = SessionRepository(config.product_db_path).create_session(
        workspace_path=str(config.default_workspace),
        model=config.model,
        title=prompt[:60] or "聊天",
    )
    skill_source_records = _resolve_skill_source_records(config)
    result = LangChainAgentRuntime().run(
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
    _print_agent_content(result.content)


def _print_agent_content(content: str) -> None:
    encoding = getattr(console.file, "encoding", None) or "utf-8"
    safe_content = content.encode(encoding, errors="replace").decode(encoding, errors="replace")
    console.print(safe_content)


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


def main() -> None:
    app()
