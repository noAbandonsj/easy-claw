from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Annotated

import typer
import uvicorn
from rich.console import Console
from rich.table import Table

from easy_claw.agent.runtime import AgentRequest, AgentResult, DeepAgentsRuntime, FakeAgentRuntime
from easy_claw.config import load_config
from easy_claw.skills import discover_skill_sources, discover_skills
from easy_claw.storage.db import initialize_product_db
from easy_claw.storage.repositories import AuditRepository, MemoryRepository, SessionRepository
from easy_claw.tools.base import ToolExecutionError
from easy_claw.tools.commands import run_command
from easy_claw.tools.documents import DocumentLoadResult, load_workspace_documents
from easy_claw.tools.python_runner import run_python_code
from easy_claw.tools.search import search_web
from easy_claw.workflows.document_runs import NoReadableDocumentsError, run_document_task

console = Console()
DEFAULT_SKILLS_ROOT = Path("skills")
app = typer.Typer(help="easy-claw local AI agent workbench")
skills_app = typer.Typer(help="Manage Markdown skills")
memory_app = typer.Typer(help="Manage explicit product memory")
docs_app = typer.Typer(help="Work with local documents")
tools_app = typer.Typer(help="Run local power tools")
app.add_typer(skills_app, name="skills")
app.add_typer(memory_app, name="memory")
app.add_typer(docs_app, name="docs")
app.add_typer(tools_app, name="tools")


@app.command()
def doctor() -> None:
    """Print local environment diagnostics."""
    config = load_config()
    console.print("easy-claw doctor")
    console.print(f"data_dir: {config.data_dir}")
    console.print(f"product_db: {config.product_db_path}")
    console.print(f"checkpoint_db: {config.checkpoint_db_path}")
    console.print(f"workspace: {config.default_workspace}")
    console.print(f"model: {config.model or '<not configured>'}")


@app.command("init-db")
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


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8787, "--port"),
) -> None:
    """Start the local FastAPI service."""
    uvicorn.run("easy_claw.api.main:app", host=host, port=port)


@app.command()
def chat(
    prompt: Annotated[str | None, typer.Argument()] = None,
    dry_run: bool = typer.Option(False, "--dry-run"),
    interactive: bool = typer.Option(False, "--interactive", "-i"),
) -> None:
    """Run a chat request. Use --dry-run for deterministic smoke checks."""
    config = load_config()
    if interactive:
        _run_interactive_chat(dry_run=dry_run)
        return

    if prompt is None or prompt.strip() == "":
        console.print("Prompt is required unless --interactive is used.")
        raise typer.Exit(code=1)

    if dry_run:
        result = FakeAgentRuntime().run(
            AgentRequest(
                prompt=prompt,
                thread_id="dry-run",
                workspace_path=config.default_workspace,
                model=None,
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
            workspace_path=config.default_workspace,
            model=config.model,
            skill_sources=skill_sources,
            memories=memories,
            checkpoint_db_path=config.checkpoint_db_path,
        )
    )
    audit_repo.record(
        event_type="agent_run",
        payload={"session_id": session.id, "prompt_length": len(prompt)},
    )
    console.print(result.content)


@docs_app.command("summarize")
def summarize_docs(
    paths: Annotated[list[Path], typer.Argument(help="Files or directories to summarize")],
    output: Annotated[Path | None, typer.Option("--output")] = None,
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Summarize local documents."""
    config = load_config()

    if dry_run:
        load_result = load_workspace_documents(
            config.default_workspace,
            [str(path) for path in paths],
        )
        _print_document_load_notices(load_result)
        for document in load_result.documents:
            console.print(f"## {document.relative_path}")
            console.print(document.markdown)
        return

    if config.model is None:
        console.print("Set EASY_CLAW_MODEL before running docs summarize without --dry-run.")
        raise typer.Exit(code=1)

    try:
        result = run_document_task(
            config=config,
            prompt=_document_summary_instruction(),
            document_paths=[str(path) for path in paths],
            output_path=output,
            title="Summarize documents",
        )
    except NoReadableDocumentsError as exc:
        _print_document_load_notices(exc.load_result)
        console.print("No readable documents found.")
        raise typer.Exit(code=1) from None

    _print_document_load_notices(result.load_result)
    document_paths_outside_workspace = {
        document.relative_path
        for document in result.load_result.documents
        if document.outside_workspace
    }
    for path in result.outside_workspace_paths:
        if path not in document_paths_outside_workspace:
            console.print(f"outside workspace path: {path}")
    console.print(result.content)


def _document_summary_instruction() -> str:
    return "请总结下面这些本地文档，输出 Markdown，包含关键事实、决策、风险和建议下一步。"


def _run_interactive_chat(*, dry_run: bool) -> None:
    config = load_config()
    if not dry_run and config.model is None:
        console.print("Set EASY_CLAW_MODEL before running chat without --dry-run.")
        raise typer.Exit(code=1)

    if dry_run:
        runtime = FakeAgentRuntime()
        session_id = "dry-run"
        skill_sources = []
        memories = []
        audit_repo = None
    else:
        initialize_product_db(config.product_db_path)
        audit_repo = AuditRepository(config.product_db_path)
        session = SessionRepository(config.product_db_path).create_session(
            workspace_path=str(config.default_workspace),
            model=config.model,
            title="Interactive chat",
        )
        session_id = session.id
        skill_sources = discover_skill_sources(config.cwd / "skills", config.default_workspace)
        memories = [
            item.content for item in MemoryRepository(config.product_db_path).list_memory()
        ]
        runtime = DeepAgentsRuntime()

    console.print("Interactive chat started. Type exit or quit to leave.")
    base_request = AgentRequest(
        prompt="",
        thread_id=session_id,
        workspace_path=config.default_workspace,
        model=config.model if not dry_run else None,
        skill_sources=skill_sources,
        memories=memories,
        checkpoint_db_path=config.checkpoint_db_path if not dry_run else None,
    )
    if dry_run:
        _run_interactive_loop(
            run_turn=lambda prompt: runtime.run(
                AgentRequest(
                    prompt=prompt,
                    thread_id=session_id,
                    workspace_path=config.default_workspace,
                    model=None,
                )
            ),
            audit_repo=audit_repo,
            session_id=session_id,
        )
        return

    open_session = getattr(runtime, "open_session", None)
    if open_session is None:
        _run_interactive_loop(
            run_turn=lambda prompt: runtime.run(_agent_request_for_prompt(base_request, prompt)),
            audit_repo=audit_repo,
            session_id=session_id,
        )
        return

    with open_session(base_request) as agent_session:
        _run_interactive_loop(
            run_turn=agent_session.run,
            audit_repo=audit_repo,
            session_id=session_id,
        )


def _run_interactive_loop(
    *,
    run_turn: Callable[[str], AgentResult],
    audit_repo: AuditRepository | None,
    session_id: str,
) -> None:
    while True:
        try:
            prompt = input("easy-claw> ").strip()
        except EOFError:
            break
        if prompt.lower() in {"exit", "quit", ":q"}:
            break
        if prompt == "":
            continue

        result = run_turn(prompt)
        if audit_repo is not None:
            audit_repo.record(
                event_type="agent_run",
                payload={"session_id": session_id, "prompt_length": len(prompt)},
            )
        console.print(result.content)


def _agent_request_for_prompt(request: AgentRequest, prompt: str) -> AgentRequest:
    return AgentRequest(
        prompt=prompt,
        thread_id=request.thread_id,
        workspace_path=request.workspace_path,
        model=request.model,
        skill_sources=request.skill_sources,
        memories=request.memories,
        checkpoint_db_path=request.checkpoint_db_path,
    )


@tools_app.command("search")
def tool_search(query: str) -> None:
    """Search the web."""
    config = load_config()
    initialize_product_db(config.product_db_path)
    try:
        results = search_web(query)
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


def main() -> None:
    app()


def _print_document_load_notices(load_result: DocumentLoadResult) -> None:
    for document in load_result.documents:
        if document.outside_workspace:
            console.print(f"outside workspace document: {document.relative_path}")
    for error in load_result.errors:
        prefix = (
            "outside workspace document failed"
            if error.outside_workspace
            else "document failed"
        )
        console.print(f"{prefix}: {error.path} - {error.message}")
