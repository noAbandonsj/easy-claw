from __future__ import annotations

from pathlib import Path

import typer
import uvicorn
from rich.console import Console
from rich.table import Table

from easy_claw.config import load_config
from easy_claw.skills import discover_skills
from easy_claw.storage.db import initialize_product_db
from easy_claw.storage.repositories import MemoryRepository


console = Console()
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
def list_skills(skills_root: Path = typer.Option(Path("skills"), "--skills-root")) -> None:
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
    if dry_run:
        console.print(f"easy-claw dry run: {prompt}")
        return

    raise typer.BadParameter("chat requires agent runtime wiring; use --dry-run for smoke checks")


def main() -> None:
    app()
