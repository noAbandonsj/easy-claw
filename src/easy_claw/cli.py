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
from easy_claw.storage.repositories import AuditRepository, MemoryRepository, SessionRecord, SessionRepository
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
sessions_app = typer.Typer(help="Manage chat sessions")
app.add_typer(sessions_app, name="sessions", rich_help_panel="Management")
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


@sessions_app.command("list")
def list_sessions() -> None:
    """List past chat sessions."""
    config = load_config()
    initialize_product_db(config.product_db_path)
    repo = SessionRepository(config.product_db_path)
    sessions = repo.list_sessions()
    if not sessions:
        console.print("[dim]No sessions found.[/]")
        return
    table = Table("ID", "Title", "Model", "Updated")
    for s in sessions:
        table.add_row(s.id[:8], s.title[:60], s.model or "-", s.updated_at[:19])
    console.print(table)


@sessions_app.command("resume")
def resume_session(
    session_id: Annotated[str, typer.Argument(help="Session ID (first 8 chars are enough)")],
    model: Annotated[str | None, typer.Option("--model", help="Override the model.")] = None,
) -> None:
    """Resume an existing chat session."""
    config = load_config()
    if model is not None:
        config = dataclasses.replace(config, model=model)
    initialize_product_db(config.product_db_path)
    repo = SessionRepository(config.product_db_path)

    # Match by prefix
    matched = _find_session_by_prefix(repo, session_id)
    if matched is None:
        console.print(f"No session found matching [bold]{session_id}[/].")
        raise typer.Exit(code=1)

    _run_interactive_chat(dry_run=False, config=config, resume_thread_id=matched.id)


@sessions_app.command("delete")
def delete_session(
    session_id: Annotated[str, typer.Argument(help="Session ID (first 8 chars are enough)")],
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation."),
) -> None:
    """Delete a chat session and its checkpoints."""
    config = load_config()
    initialize_product_db(config.product_db_path)
    repo = SessionRepository(config.product_db_path)

    matched = _find_session_by_prefix(repo, session_id)
    if matched is None:
        console.print(f"No session found matching [bold]{session_id}[/].")
        raise typer.Exit(code=1)

    if not force:
        from typer import confirm

        if not confirm(
            f"Delete session [bold]{matched.title}[/] ({matched.id[:8]})?"
        ):
            raise typer.Exit()

    repo.delete_session(matched.id)
    _delete_checkpoint_thread(matched.id, config.checkpoint_db_path)
    console.print(f"Deleted session [bold]{matched.title}[/].")


def _find_session_by_prefix(repo: SessionRepository, prefix: str) -> SessionRecord | None:
    sessions = repo.list_sessions()
    matches = [s for s in sessions if s.id.startswith(prefix)]
    if len(matches) == 1:
        return matches[0]
    # Fall back to exact match
    return repo.get_session(prefix)


def _delete_checkpoint_thread(thread_id: str, checkpoint_db_path: Path) -> None:
    """Delete all checkpoints for a thread using langgraph's public API."""
    from langgraph.checkpoint.sqlite import SqliteSaver

    if not checkpoint_db_path.exists():
        return
    try:
        with SqliteSaver.from_conn_string(str(checkpoint_db_path)) as saver:
            saver.delete_thread(thread_id)
    except Exception:
        console.print(
            f"[yellow]Warning:[/] deleted session but failed to clean up "
            f"checkpoints in {checkpoint_db_path}"
        )


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


def _run_interactive_chat(
    *,
    dry_run: bool,
    config: "AppConfig",  # noqa: F821
    resume_thread_id: str | None = None,
) -> None:
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
            session_config=None,
        )
        return

    initialize_product_db(config.product_db_path)
    audit_repo = AuditRepository(config.product_db_path)
    skill_sources = discover_skill_sources(config.cwd / "skills", config.default_workspace)
    memories = [item.content for item in MemoryRepository(config.product_db_path).list_memory()]
    runtime = DeepAgentsRuntime()
    conversation: list[tuple[str, str]] = []
    token_usage: dict[str, int] = {}

    _render_startup_banner(config)

    # First iteration: use resume_thread_id if given, otherwise create new session
    thread_id: str | None = resume_thread_id
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
            new_path = Path(restart[len("/workspace "):]).resolve()
            if not new_path.is_dir():
                console.print(f"[yellow]Not a directory: {new_path}[/]")
                continue
            config = dataclasses.replace(config, default_workspace=new_path)
            # Keep thread_id and conversation across workspace switches
            console.print(f"[dim]Workspace changed to {new_path}[/]")
        else:
            thread_id = None  # /clear: create a new session next iteration
            conversation.clear()
            token_usage.clear()
            console.print("[dim]Conversation cleared. Starting fresh.[/]")


def _run_interactive_loop(
    *,
    run_turn: Callable[[str], AgentResult],
    audit_repo: AuditRepository | None,
    session_id: str,
    stream_turn: Callable[[str], Iterable[StreamEvent]] | None = None,
    supports_clear: bool = False,
    session_config: "AppConfig | None" = None,  # noqa: F821
    conversation: list[tuple[str, str]] | None = None,
    token_usage: dict[str, int] | None = None,
) -> str | None:
    """Run the REPL loop.

    Returns:
        None if the user quit.
        \"clear\" if the caller should restart with a fresh session.
        \"/workspace <path>\" if the caller should switch workspace.
    """
    if conversation is None:
        conversation = []
    if token_usage is None:
        token_usage = {}

    while True:
        try:
            console.print(Rule(style="pink"))
            console.print("  [bold cyan]>[/] ", end="")
            prompt = input().strip()
            console.print(Rule(style="pink"))
        except EOFError:
            console.print()
            break
        if prompt.lower() in {"exit", "quit", ":q"}:
            break
        if prompt == "":
            continue
        if prompt.lower() == "/clear":
            if supports_clear:
                return "clear"
            console.print("[dim]History clearing is not supported in dry-run mode.[/]")
            continue
        if prompt.lower().startswith("/workspace"):
            if not supports_clear:
                console.print("[dim]Workspace switching is not supported in dry-run mode.[/]")
                continue
            parts = prompt.split(maxsplit=1)
            if len(parts) < 2 or not parts[1].strip():
                console.print("[yellow]Usage: /workspace <path>[/]")
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
                console.print("[yellow]Usage: /save <path>[/]")
                continue
            save_path = Path(parts[1].strip()).expanduser().resolve()
            _write_conversation_markdown(conversation, save_path, session_id, session_config)
            console.print(f"[dim]Conversation saved to {save_path}[/]")
            continue

        if stream_turn is not None:
            response, usage = _render_streaming_turn(stream_turn(prompt))
        else:
            with console.status("[dim]Thinking...[/]"):
                result = run_turn(prompt)
            response = result.content
            usage = result.usage
            console.print(response)
            console.print(Rule(style="dim"))

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


def _render_streaming_turn(events: Iterable[StreamEvent]) -> tuple[str, dict[str, int] | None]:
    """Render a streaming turn. Returns (response_text, usage)."""
    tokens: list[str] = []
    usage: dict[str, int] | None = None
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
            tokens.append(event.content)
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
            usage = event.usage
    console.print(Rule(style="dim"))
    return "".join(tokens), usage


def _print_stream_separator(printed_token: bool) -> None:
    if printed_token:
        console.print()


def _write_conversation_markdown(
    conversation: list[tuple[str, str]],
    path: Path,
    session_id: str,
    config: "AppConfig | None",  # noqa: F821
) -> None:
    from datetime import datetime

    lines: list[str] = []
    lines.append(f"# easy-claw Conversation")
    lines.append(f"")
    lines.append(f"- **Session:** `{session_id}`")
    lines.append(f"- **Model:** {config.model if config else 'N/A'}")
    lines.append(f"- **Workspace:** {config.default_workspace if config else 'N/A'}")
    lines.append(f"- **Exported:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"")

    for i, (user_msg, assistant_msg) in enumerate(conversation, 1):
        lines.append(f"### Turn {i}")
        lines.append(f"")
        lines.append(f"**You:**")
        lines.append(f"")
        lines.append(f"{user_msg}")
        lines.append(f"")
        lines.append(f"**easy-claw:**")
        lines.append(f"")
        lines.append(f"{assistant_msg}")
        lines.append(f"")
        lines.append(f"---")
        lines.append(f"")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _print_help() -> None:
    """Print available slash commands in the interactive REPL."""
    table = Table(title="Available Commands", title_style="bold")
    table.add_column("Command", style="bold cyan")
    table.add_column("Description")
    table.add_row("/help", "Show this help message")
    table.add_row("/clear", "Clear conversation history and start a new session")
    table.add_row("/workspace <path>", "Switch the working directory")
    table.add_row("/save <path>", "Save the conversation to a Markdown file")
    table.add_row("/status", "Show current session details and token usage")
    table.add_row("exit, quit, :q", "Exit the assistant")
    console.print(table)


def _print_session_status(
    session_id: str,
    config: "AppConfig | None",  # noqa: F821
    conversation: list[tuple[str, str]],
    token_usage: dict[str, int] | None = None,
) -> None:
    cfg = config
    table = Table(title=f"Session {session_id[:8]}", title_style="bold")
    table.add_column("Property", style="bold cyan")
    table.add_column("Value")
    table.add_row("Model", cfg.model if cfg else "N/A")
    table.add_row("Workspace", str(cfg.default_workspace) if cfg else "N/A")
    table.add_row("Approval mode", cfg.approval_mode if cfg else "N/A")
    table.add_row("Turns", str(len(conversation)))
    if token_usage:
        table.add_row("Tokens in", f"{token_usage.get('input', 0):,}")
        table.add_row("Tokens out", f"{token_usage.get('output', 0):,}")
        table.add_row("Tokens total", f"{token_usage.get('total', 0):,}")
    table.add_row("Checkpoints", str(cfg.checkpoint_db_path) if cfg else "N/A")
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
    console.print("[dim]Type /help to see all commands. :q/exit/quit to leave, empty to skip.[/]")
    console.print()


def main() -> None:
    app()
