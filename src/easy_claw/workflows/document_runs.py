from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from easy_claw.agent.runtime import AgentRequest, AgentRuntime, DeepAgentsRuntime
from easy_claw.config import AppConfig
from easy_claw.skills import discover_skill_sources
from easy_claw.storage.db import initialize_product_db
from easy_claw.storage.repositories import AuditRepository, MemoryRepository, SessionRepository
from easy_claw.tools.documents import DocumentContent, DocumentLoadResult, load_workspace_documents
from easy_claw.tools.reports import write_markdown_report


@dataclass(frozen=True)
class DocumentRunResult:
    session_id: str
    thread_id: str
    content: str
    output_path: str | None
    document_errors: list[dict[str, object]]
    outside_workspace_paths: list[str]
    load_result: DocumentLoadResult


class NoReadableDocumentsError(RuntimeError):
    def __init__(self, load_result: DocumentLoadResult) -> None:
        super().__init__("No readable documents found")
        self.load_result = load_result


def run_document_task(
    *,
    config: AppConfig,
    prompt: str,
    document_paths: Sequence[str],
    workspace_path: Path | None = None,
    output_path: str | Path | None = None,
    title: str = "Run",
    runtime: AgentRuntime | None = None,
) -> DocumentRunResult:
    if config.model is None:
        raise RuntimeError("EASY_CLAW_MODEL is required")

    active_workspace = workspace_path or config.default_workspace
    load_result = load_workspace_documents(active_workspace, document_paths)
    if not load_result.documents:
        raise NoReadableDocumentsError(load_result)

    initialize_product_db(config.product_db_path)
    audit_repo = AuditRepository(config.product_db_path)
    record_document_load_events(audit_repo, load_result)
    session = SessionRepository(config.product_db_path).create_session(
        workspace_path=str(active_workspace),
        model=config.model,
        title=title,
    )
    memories = [item.content for item in MemoryRepository(config.product_db_path).list_memory()]
    active_runtime = runtime or DeepAgentsRuntime()
    documents = load_result.documents
    result = active_runtime.run(
        AgentRequest(
            prompt=build_document_prompt(prompt, documents),
            thread_id=session.id,
            workspace_path=active_workspace,
            model=config.model,
            base_url=config.base_url,
            api_key=config.api_key,
            skill_sources=discover_skill_sources(config.cwd / "skills", active_workspace),
            memories=memories,
            checkpoint_db_path=config.checkpoint_db_path,
            approval_mode=config.approval_mode,
            execution_mode=config.execution_mode,
            browser_enabled=config.browser_enabled,
            browser_headless=config.browser_headless,
            max_model_calls=config.max_model_calls,
            max_tool_calls=config.max_tool_calls,
        )
    )
    audit_repo.record(
        event_type="agent_run",
        payload={"session_id": session.id, "document_count": len(documents)},
    )

    outside_workspace_paths = [
        document.relative_path for document in documents if document.outside_workspace
    ]
    written_output_path = None
    if output_path is not None:
        output = write_markdown_report(active_workspace, output_path, result.content)
        written_output_path = output.relative_path
        if output.outside_workspace:
            outside_workspace_paths.append(output.relative_path)
        audit_repo.record(
            event_type="report_written",
            payload={
                "path": output.relative_path,
                "outside_workspace": output.outside_workspace,
            },
        )

    return DocumentRunResult(
        session_id=session.id,
        thread_id=result.thread_id,
        content=result.content,
        output_path=written_output_path,
        document_errors=[error.__dict__ for error in load_result.errors],
        outside_workspace_paths=outside_workspace_paths,
        load_result=load_result,
    )


def build_document_prompt(prompt: str, documents: Sequence[DocumentContent]) -> str:
    sections = [prompt]
    for document in documents:
        sections.append(f"## 文件：{document.relative_path}\n\n{document.markdown}")
    return "\n\n".join(sections)


def record_document_load_events(
    audit_repo: AuditRepository,
    load_result: DocumentLoadResult,
) -> None:
    for error in load_result.errors:
        audit_repo.record(
            event_type="document_error",
            payload={
                "path": error.path,
                "message": error.message,
                "outside_workspace": error.outside_workspace,
            },
        )
    for document in load_result.documents:
        audit_repo.record(
            event_type="document_read",
            payload={
                "path": document.relative_path,
                "outside_workspace": document.outside_workspace,
            },
        )
        if document.converted:
            audit_repo.record(
                event_type="document_converted",
                payload={
                    "path": document.relative_path,
                    "outside_workspace": document.outside_workspace,
                },
            )
