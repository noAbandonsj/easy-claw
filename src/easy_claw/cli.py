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
from easy_claw.config import load_config
from easy_claw.skills import discover_skill_sources, discover_skills
from easy_claw.storage.db import initialize_product_db
from easy_claw.storage.repositories import AuditRepository, MemoryRepository, SessionRepository
from easy_claw.tools.base import ToolExecutionError
from easy_claw.tools.commands import run_command
from easy_claw.tools.python_runner import run_python_code
from easy_claw.tools.search import search_web

console = Console()
DEFAULT_SKILLS_ROOT = Path("skills")
STREAM_PANEL_VALUE_LIMIT = 1200
app = typer.Typer(help="easy-claw - your personal AI assistant for Windows")
dev_app = typer.Typer(help="Developer and debugging commands")
skills_app = typer.Typer(help="Manage Markdown skills")
memory_app = typer.Typer(help="Manage explicit product memory")
tools_app = typer.Typer(help="Run local power tools")
app.add_typer(dev_app, name="dev", rich_help_panel="Development")
dev_app.add_typer(skills_app, name="skills")
dev_app.add_typer(memory_app, name="memory")
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
        help="Show version and exit.",
    ),
) -> None:
    pass


@app.command(rich_help_panel="Management")
def doctor() -> None:
    """Print local environment diagnostics."""
    config = load_config()
    console.print("easy-claw doctor")
    console.print(f"data_dir: {config.data_dir}")
    console.print(f"product_db: {config.product_db_path}")
    console.print(f"checkpoint_db: {config.checkpoint_db_path}")
    console.print(f"workspace: {config.default_workspace}")
    console.print(f"model: {config.model or '<not configured>'}")
    console.print(f"base_url: {config.base_url}")
    console.print(f"approval_mode: {config.approval_mode}")
    console.print(f"execution_mode: {config.execution_mode}")
    console.print(f"browser_enabled: {config.browser_enabled}")
    console.print(f"browser_headless: {config.browser_headless}")
    console.print(f"mcp_enabled: {config.mcp_enabled}")
    console.print(f"mcp_config_path: {config.mcp_config_path}")
    console.print(f"max_model_calls: {config.max_model_calls}")
    console.print(f"max_tool_calls: {config.max_tool_calls}")
    api_key_display = "***" + config.api_key[-4:] if config.api_key else "<not configured>"
    console.print(f"api_key: {api_key_display}")


@app.command("init-db", rich_help_panel="Management")
def init_db() -> None:
    """Initialize local product storage."""
    config = load_config()
    initialize_product_db(config.product_db_path)
    console.print(f"initialized {config.product_db_path}")


@skills_app.command("list")
def list_skills(
    skills_root: Annotated[Path, typer.Option("--skills-root")] = DEFAULT_SKILLS_ROOT,
) -> None:
    """List available Markdown skills."""
    skills = discover_skills(skills_root)
    table = Table("Name", "Description", "Path")
    for skill in skills:
        table.add_row(skill.name, skill.description, str(skill.path))
    console.print(table)


@memory_app.command("list")
def list_memory() -> None:
    """List explicit product memory items."""
    config = load_config()
    initialize_product_db(config.product_db_path)
    table = Table("Scope", "Key", "Content", "Source")
    for item in MemoryRepository(config.product_db_path).list_memory():
        table.add_row(item.scope, item.key, item.content, item.source)
    console.print(table)


@app.command(rich_help_panel="Management")
def serve(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8787, "--port"),
) -> None:
    """Start the local API service (developers only)."""
    uvicorn.run("easy_claw.api.main:app", host=host, port=port)


@app.command(rich_help_panel="Primary")
def chat(
    prompt: Annotated[str | None, typer.Argument()] = None,
    dry_run: bool = typer.Option(False, "--dry-run"),
    interactive: bool = typer.Option(False, "--interactive", "-i"),
    model: Annotated[str | None, typer.Option("--model", help="Override the model (e.g. deepseek-chat).")] = None,
) -> None:
    """Start the interactive AI assistant (run without args for interactive mode)."""
    config = load_config()
    if model is not None:
        config = dataclasses.replace(config, model=model)

    if interactive:
        _run_interactive_chat(dry_run=dry_run, config=config)
        return

    if prompt is None or prompt.strip() == "":
        console.print("Prompt is required unless --interactive is used.")
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
        console.print("Set EASY_CLAW_MODEL before running chat without --dry-run.")
        raise typer.Exit(code=1)

    initialize_product_db(config.product_db_path)
    audit_repo = AuditRepository(config.product_db_path)
    session = SessionRepository(config.product_db_path).create_session(
        workspace_path=str(config.default_workspace),
        model=config.model,
        title=prompt[:60] or "Chat",
    )
    skill_sources = discover_skill_sources(config.cwd / "skills", config.default_workspace)
    memories = [item.content for item in MemoryRepository(config.product_db_path).list_memory()]
    result = DeepAgentsRuntime().run(
        AgentRequest(
            prompt=prompt,
            thread_id=session.id,
            config=config,
            skill_sources=skill_sources,
            memories=memories,
        )
    )
    audit_repo.record(
        event_type="agent_run",
        payload={"session_id": session.id, "prompt_length": len(prompt)},
    )
    console.print(result.content)


def _run_interactive_chat(*, dry_run: bool, config: "AppConfig") -> None:  # noqa: F821
    if not dry_run and config.model is None:
        console.print("Set EASY_CLAW_MODEL before running chat without --dry-run.")
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
        )
        return

    initialize_product_db(config.product_db_path)
    audit_repo = AuditRepository(config.product_db_path)
    skill_sources = discover_skill_sources(config.cwd / "skills", config.default_workspace)
    memories = [item.content for item in MemoryRepository(config.product_db_path).list_memory()]
    runtime = DeepAgentsRuntime()

    _render_startup_banner(config)

    thread_id: str | None = None
    open_session = getattr(runtime, "open_session", None)

    while True:
        if thread_id is None:
            session = SessionRepository(config.product_db_path).create_session(
                workspace_path=str(config.default_workspace),
                model=config.model,
                title="Interactive chat",
            )
            thread_id = session.id

        base_request = AgentRequest(
            prompt="",
            thread_id=thread_id,
            config=config,
            skill_sources=skill_sources,
            memories=memories,
        )

        if open_session is None:
            restart = _run_interactive_loop(
                run_turn=lambda prompt: runtime.run(
                    _agent_request_for_prompt(base_request, prompt)
                ),
                audit_repo=audit_repo,
                session_id=thread_id,
                supports_clear=True,
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
                )

        if not restart:
            break
        thread_id = None
        console.print("[dim]Conversation cleared. Starting fresh.[/]")


def _run_interactive_loop(
    *,
    run_turn: Callable[[str], AgentResult],
    audit_repo: AuditRepository | None,
    session_id: str,
    stream_turn: Callable[[str], Iterable[StreamEvent]] | None = None,
    supports_clear: bool = False,
) -> bool:
    """Run the REPL loop. Returns True if the caller should restart with a fresh session."""
    while True:
        try:
            console.print("  [bold cyan]easy-claw>[/] ", end="")
            prompt = input().strip()
        except EOFError:
            console.print()
            break
        if prompt.lower() in {"exit", "quit", ":q"}:
            break
        if prompt == "":
            continue
        if prompt.lower() == "/clear":
            if supports_clear:
                return True
            console.print("[dim]History clearing is not supported in dry-run mode.[/]")
            continue

        if stream_turn is not None:
            _render_streaming_turn(stream_turn(prompt))
        else:
            with console.status("[dim]Thinking...[/]"):
                result = run_turn(prompt)
            console.print(result.content)
            console.print(Rule(style="dim"))

        if audit_repo is not None:
            audit_repo.record(
                event_type="agent_run",
                payload={"session_id": session_id, "prompt_length": len(prompt)},
            )

    return False


def _agent_request_for_prompt(request: AgentRequest, prompt: str) -> AgentRequest:
    return dataclasses.replace(request, prompt=prompt)


@tools_app.command("search")
def tool_search(query: str) -> None:
    """Search the web."""
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
    table = Table("Title", "URL", "Snippet")
    for result in results:
        table.add_row(result.title, result.url, result.snippet)
    console.print(table)


@tools_app.command("run")
def tool_run(command: str) -> None:
    """Run a local shell command."""
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
    """Run a local Python snippet."""
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


def _render_streaming_turn(events: Iterable[StreamEvent]) -> None:
    printed_token = False
    spinner = console.status("[dim]Thinking...[/]")
    spinner.start()
    spinner_running = True
    for event in events:
        if spinner_running:
            spinner.stop()
            spinner_running = False
        if event.type == "token":
            console.print(event.content, end="")
            printed_token = True
        elif event.type == "tool_call_start":
            _print_stream_separator(printed_token)
            console.print(
                Panel(
                    _format_stream_value(event.tool_args),
                    title=f"Tool call: {event.tool_name or 'unknown'}",
                    border_style="blue",
                )
            )
            printed_token = False
        elif event.type == "tool_call_result":
            _print_stream_separator(printed_token)
            console.print(
                Panel(
                    _format_stream_value(event.content or event.tool_result),
                    title=f"Tool result: {event.tool_name or 'unknown'}",
                    border_style="green",
                )
            )
            printed_token = False
        elif event.type == "approval_required":
            _print_stream_separator(printed_token)
            console.print("[yellow]Tool execution requires approval[/]")
            printed_token = False
        elif event.type == "done":
            if spinner_running:
                spinner.stop()
                spinner_running = False
            if printed_token:
                console.print()
            printed_token = False
    console.print(Rule(style="dim"))


def _print_stream_separator(printed_token: bool) -> None:
    if printed_token:
        console.print()


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
    return text[:STREAM_PANEL_VALUE_LIMIT] + "\n[truncated]"


def _count_mcp_servers(config_path: str) -> int:
    try:
        import json
        data = json.loads(Path(config_path).read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return len(data)
    except Exception:
        pass
    return 0


def _render_startup_banner(config: "AppConfig") -> None:  # noqa: F821
    """Render a startup banner showing current configuration."""
    approval_color = {"permissive": "green", "balanced": "yellow", "strict": "red"}
    color = approval_color.get(config.approval_mode, "white")

    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="bold cyan", justify="right")
    grid.add_column(style="white")
    grid.add_row("Model:", config.model or "[dim]dry-run[/]")
    grid.add_row("Workspace:", str(config.default_workspace))
    grid.add_row(
        "Approval:",
        f"[{color}]{config.approval_mode}[/]",
    )
    grid.add_row("Browser:", "enabled" if config.browser_enabled else "disabled")
    mcp_status = "disabled"
    if config.mcp_enabled:
        count = _count_mcp_servers(config.mcp_config_path)
        mcp_status = f"enabled ({count} servers)" if count else "enabled"
    grid.add_row("MCP tools:", mcp_status)

    banner = Panel(
        grid,
        title=f"[bold]easy-claw v{_easy_claw_version}[/]",
        title_align="left",
        border_style="cyan",
    )
    console.print(banner)
    console.print("[dim]Type :q, exit or quit to leave. /clear to reset conversation. Empty line to skip.[/]")
    console.print()


def main() -> None:
    app()
