from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from easy_claw.skills import Skill


@dataclass(frozen=True)
class AgentRequest:
    prompt: str
    thread_id: str
    workspace_path: Path
    model: str | None
    skills: Sequence[Skill] = field(default_factory=tuple)
    memories: Sequence[str] = field(default_factory=tuple)
    checkpoint_db_path: Path | None = None
    developer_mode: bool = False


@dataclass(frozen=True)
class AgentResult:
    content: str
    thread_id: str


class AgentRuntime(Protocol):
    def run(self, request: AgentRequest) -> AgentResult:
        """Run one agent turn."""


class FakeAgentRuntime:
    def run(self, request: AgentRequest) -> AgentResult:
        return AgentResult(
            content=f"easy-claw dry run: {request.prompt}",
            thread_id=request.thread_id,
        )


class DeepAgentsRuntime:
    def run(self, request: AgentRequest) -> AgentResult:
        if request.model is None:
            raise RuntimeError("Set EASY_CLAW_MODEL before running chat without --dry-run.")
        if request.checkpoint_db_path is None:
            raise RuntimeError("checkpoint_db_path is required for DeepAgentsRuntime.")

        request.checkpoint_db_path.parent.mkdir(parents=True, exist_ok=True)
        system_prompt = _build_system_prompt(request.skills, request.memories)

        from deepagents import create_deep_agent
        from deepagents.backends import FilesystemBackend
        from langgraph.checkpoint.sqlite import SqliteSaver

        interrupt_on = {
            "edit_file": True,
            "write_file": True,
            "execute": True,
        }

        with SqliteSaver.from_conn_string(str(request.checkpoint_db_path)) as checkpointer:
            agent = create_deep_agent(
                model=request.model,
                system_prompt=system_prompt,
                backend=FilesystemBackend(root_dir=request.workspace_path),
                checkpointer=checkpointer,
                interrupt_on=interrupt_on,
            )
            result = agent.invoke(
                {"messages": [{"role": "user", "content": request.prompt}]},
                config={"configurable": {"thread_id": request.thread_id}},
            )

        return AgentResult(
            content=_extract_last_message_content(result), thread_id=request.thread_id
        )


def _build_system_prompt(skills: Sequence[Skill], memories: Sequence[str]) -> str:
    sections = [
        "You are easy-claw, a Windows-first local personal AI workbench.",
        "Operate only inside the selected workspace unless the user explicitly approves otherwise.",
        "Do not execute commands or write files without human approval.",
    ]
    if skills:
        sections.append(
            "Available Markdown skills:\n" + "\n\n".join(_format_skill(skill) for skill in skills)
        )
    if memories:
        sections.append(
            "Explicit product memories:\n" + "\n".join(f"- {memory}" for memory in memories)
        )
    return "\n\n".join(sections)


def _format_skill(skill: Skill) -> str:
    description = f": {skill.description}" if skill.description else ""
    return f"## {skill.name}{description}\n{skill.body}"


def _extract_last_message_content(result: object) -> str:
    if not isinstance(result, dict):
        return str(result)

    messages = result.get("messages")
    if not messages:
        return str(result)

    last_message = messages[-1]
    content = getattr(last_message, "content", None)
    if content is None and isinstance(last_message, dict):
        content = last_message.get("content")
    return str(content or "")
