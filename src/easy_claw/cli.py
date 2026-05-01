from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
import uvicorn
from rich.console import Console
from rich.table import Table

from easy_claw.agent.runtime import AgentRequest, DeepAgentsRuntime, FakeAgentRuntime
from easy_claw.config import load_config
from easy_claw.skills import discover_skills
from easy_claw.storage.db import initialize_product_db
from easy_claw.storage.repositories import MemoryRepository, SessionRepository

console = Console()
DEFAULT_SKILLS_ROOT = Path("skills")
app = typer.Typer(help="easy-claw local AI agent workbench")
skills_app = typer.Typer(help="Manage Markdown skills")
memory_app = typer.Typer(help="Manage explicit product memory")
app.add_typer(skills_app, name="skills")
app.add_typer(memory_app, name="memory")


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
    console.print(f"developer_mode: {config.developer_mode}")


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
    prompt: str,
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Run a chat request. Use --dry-run for deterministic smoke checks."""
    config = load_config()
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
    session = SessionRepository(config.product_db_path).create_session(
        workspace_path=str(config.default_workspace),
        model=config.model,
        title=prompt[:60] or "Chat",
    )
    skills = discover_skills(config.cwd / "skills")
    memories = [item.content for item in MemoryRepository(config.product_db_path).list_memory()]
    result = DeepAgentsRuntime().run(
        AgentRequest(
            prompt=prompt,
            thread_id=session.id,
            workspace_path=config.default_workspace,
            model=config.model,
            skills=skills,
            memories=memories,
            checkpoint_db_path=config.checkpoint_db_path,
            developer_mode=config.developer_mode,
        )
    )
    console.print(result.content)


def main() -> None:
    app()
