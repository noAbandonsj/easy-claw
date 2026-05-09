# LangChain Runtime Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the DeepAgents runtime dependency with LangChain `create_agent` while preserving easy-claw chat, streaming, MCP, checkpoint, approval, file, and skill behavior.

**Architecture:** Keep CLI, API, storage, MCP, and existing tool interfaces stable. Replace only the agent construction layer, then reintroduce DeepAgents-provided capabilities as easy-claw-owned LangChain tools and middleware.

**Tech Stack:** Python 3.11+, LangChain `create_agent`, LangChain middleware, LangGraph `SqliteSaver`, LangChain Core tools, langchain-mcp-adapters, pytest, ruff.

---

## Reference Design

Read `docs/superpowers/specs/2026-05-09-langchain-runtime-migration-design.md` before executing this plan.

Key migration facts:

- `create_agent` has no `skills` parameter.
- `create_agent` has no `backend` parameter.
- Approval moves to `HumanInTheLoopMiddleware`.
- DeepAgents file capabilities must become easy-claw file tools.
- easy-claw skills must become a skill summary plus `list_skills` and `read_skill` tools.

## File Structure

Create:

- `src/easy_claw/agent/protocols.py`: neutral `AgentRuntime` and `AgentSession` protocols.
- `src/easy_claw/agent/skill_tools.py`: LangChain tools for listing and reading easy-claw skills.
- `src/easy_claw/tools/files.py`: workspace-bound text file tools.
- `tests/test_skill_tools.py`: skill adapter tests.
- `tests/test_file_tools.py`: workspace file tool tests.

Modify:

- `src/easy_claw/agent/runtime.py`: replace `create_deep_agent` usage with `create_agent`, rename runtime/session, keep compatibility aliases.
- `src/easy_claw/agent/middleware.py`: add `HumanInTheLoopMiddleware`.
- `src/easy_claw/agent/toolset.py`: include file tools and remove DeepAgents filesystem policy names after replacement tools exist.
- `src/easy_claw/agent/types.py`: add optional skill source context only if needed by tool bundle construction.
- `src/easy_claw/skills.py`: add helper lookup APIs for highest-priority skill selection.
- `tests/test_agent_runtime.py`: update runtime construction assertions.
- `tests/test_agent_middleware.py`: test human-in-the-loop middleware insertion.
- `tests/test_agent_toolset.py`: test file tools and interrupt policy.
- `tests/test_skills.py`: test skill lookup precedence.
- `pyproject.toml`: remove `deepagents` only after all runtime tests pass.
- `README.md`, `docs/architecture.md`, `docs/skills.md`: update runtime wording after code passes.

Avoid changing:

- `src/easy_claw/api/main.py`, except import names if needed.
- `src/easy_claw/cli_interactive.py`, except import names if needed.
- `src/easy_claw/storage/*`.

### Task 1: Add Runtime Protocols

**Files:**
- Create: `src/easy_claw/agent/protocols.py`
- Modify: `src/easy_claw/agent/runtime.py`
- Test: `tests/test_agent_runtime.py`

- [ ] **Step 1: Create protocol tests**

Add this test to `tests/test_agent_runtime.py`:

```python
def test_langchain_runtime_is_available_as_agent_runtime_alias():
    from easy_claw.agent.protocols import AgentRuntime
    from easy_claw.agent.runtime import DeepAgentsRuntime, LangChainAgentRuntime

    runtime = LangChainAgentRuntime()

    assert isinstance(runtime, LangChainAgentRuntime)
    assert DeepAgentsRuntime is LangChainAgentRuntime
    assert hasattr(AgentRuntime, "__call__") is False
```

- [ ] **Step 2: Run the focused test and confirm it fails**

Run:

```powershell
uv run pytest tests/test_agent_runtime.py::test_langchain_runtime_is_available_as_agent_runtime_alias -q
```

Expected: FAIL because `easy_claw.agent.protocols` or `LangChainAgentRuntime` does not exist.

- [ ] **Step 3: Create `src/easy_claw/agent/protocols.py`**

Add:

```python
from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from easy_claw.agent.runtime import AgentRequest, AgentResult, StreamEvent


class AgentSession(Protocol):
    def run(self, prompt: str) -> AgentResult: ...

    def stream(self, prompt: str) -> Iterable[StreamEvent]: ...

    def close(self) -> None: ...


class AgentRuntime(Protocol):
    def run(self, request: AgentRequest) -> AgentResult: ...

    def open_session(self, request: AgentRequest) -> AgentSession: ...
```

- [ ] **Step 4: Rename classes with compatibility aliases**

In `src/easy_claw/agent/runtime.py`, rename:

```python
class DeepAgentsRuntime:
```

to:

```python
class LangChainAgentRuntime:
```

Rename:

```python
class DeepAgentSession:
```

to:

```python
class LangChainAgentSession:
```

Update method annotations inside the file to use `LangChainAgentSession`.

At the end of the session class definition, before helper functions, add:

```python
DeepAgentsRuntime = LangChainAgentRuntime
DeepAgentSession = LangChainAgentSession
```

- [ ] **Step 5: Run focused test**

Run:

```powershell
uv run pytest tests/test_agent_runtime.py::test_langchain_runtime_is_available_as_agent_runtime_alias -q
```

Expected: PASS.

- [ ] **Step 6: Run existing runtime tests**

Run:

```powershell
uv run pytest tests/test_agent_runtime.py -q
```

Expected: existing tests still pass through compatibility aliases.

### Task 2: Move Approval Into LangChain Middleware

**Files:**
- Modify: `src/easy_claw/agent/middleware.py`
- Modify: `src/easy_claw/agent/runtime.py`
- Test: `tests/test_agent_middleware.py`
- Test: `tests/test_agent_runtime.py`

- [ ] **Step 1: Add middleware tests**

Add to `tests/test_agent_middleware.py`:

```python
from langchain.agents.middleware import HumanInTheLoopMiddleware

from easy_claw.agent.middleware import build_agent_middleware


def test_build_agent_middleware_adds_human_in_the_loop_when_interrupts_enabled():
    middleware = build_agent_middleware(
        max_model_calls=None,
        max_tool_calls=None,
        interrupt_on={"run_command": True},
    )

    assert len(middleware) == 1
    assert isinstance(middleware[0], HumanInTheLoopMiddleware)
```

- [ ] **Step 2: Run the focused test and confirm it fails**

Run:

```powershell
uv run pytest tests/test_agent_middleware.py::test_build_agent_middleware_adds_human_in_the_loop_when_interrupts_enabled -q
```

Expected: FAIL because `build_agent_middleware` does not accept `interrupt_on`.

- [ ] **Step 3: Update middleware builder**

Change `src/easy_claw/agent/middleware.py` to:

```python
from __future__ import annotations

from langchain.agents.middleware import (
    HumanInTheLoopMiddleware,
    ModelCallLimitMiddleware,
    ToolCallLimitMiddleware,
)

from easy_claw.defaults import DEFAULT_MAX_MODEL_CALLS, DEFAULT_MAX_TOOL_CALLS


def build_agent_middleware(
    *,
    max_model_calls: int | None = DEFAULT_MAX_MODEL_CALLS,
    max_tool_calls: int | None = DEFAULT_MAX_TOOL_CALLS,
    interrupt_on: dict[str, object] | None = None,
) -> tuple[object, ...]:
    middleware: list[object] = []
    if max_model_calls is not None:
        middleware.append(ModelCallLimitMiddleware(run_limit=max_model_calls))
    if max_tool_calls is not None:
        middleware.append(ToolCallLimitMiddleware(run_limit=max_tool_calls))
    if interrupt_on:
        middleware.append(HumanInTheLoopMiddleware(interrupt_on=interrupt_on))
    return tuple(middleware)
```

- [ ] **Step 4: Pass interrupt policy from runtime to middleware**

In `src/easy_claw/agent/runtime.py`, update the call to `build_agent_middleware` so it includes:

```python
interrupt_on=interrupt_on,
```

Do not remove the direct `interrupt_on=interrupt_on` argument from `create_deep_agent` until Task 3 switches to `create_agent`.

- [ ] **Step 5: Run focused middleware tests**

Run:

```powershell
uv run pytest tests/test_agent_middleware.py -q
```

Expected: PASS.

### Task 3: Replace `create_deep_agent` With `create_agent`

**Files:**
- Modify: `src/easy_claw/agent/runtime.py`
- Test: `tests/test_agent_runtime.py`

- [ ] **Step 1: Update runtime test to patch LangChain**

In `tests/test_agent_runtime.py`, update tests that monkeypatch:

```python
monkeypatch.setattr("deepagents.create_deep_agent", fake_create_deep_agent)
```

to patch:

```python
monkeypatch.setattr("langchain.agents.create_agent", fake_create_agent)
```

Rename local fake function variables from `fake_create_deep_agent` to `fake_create_agent` where edited.

- [ ] **Step 2: Update assertions that are DeepAgents-specific**

Remove assertions that require:

```python
captured["skills"]
captured["backend"]
captured["backend_root_dir"]
captured["backend_virtual_mode"]
```

Replace them with assertions that:

```python
assert captured["model"] == "chat-model"
assert "middleware" in captured
assert "checkpointer" in captured
assert len(captured["tools"]) >= 4
```

Keep assertions for core tool names.

- [ ] **Step 3: Run focused runtime test and confirm it fails**

Run:

```powershell
uv run pytest tests/test_agent_runtime.py::test_deepagents_runtime_uses_native_skills_and_virtual_backend -q
```

Expected: FAIL because production code still imports `deepagents.create_deep_agent`.

- [ ] **Step 4: Replace agent construction**

In `src/easy_claw/agent/runtime.py`, replace:

```python
from deepagents import create_deep_agent
```

with:

```python
from langchain.agents import create_agent
```

Replace:

```python
agent = create_deep_agent(
    model=_build_chat_model(cfg.model, cfg.base_url, cfg.api_key),
    tools=tool_bundle.tools,
    system_prompt=system_prompt,
    skills=skill_sources or None,
    middleware=build_agent_middleware(
        max_model_calls=cfg.max_model_calls,
        max_tool_calls=cfg.max_tool_calls,
        interrupt_on=interrupt_on,
    ),
    backend=_build_agent_backend(workspace_path, request.skill_source_records),
    checkpointer=checkpointer,
    interrupt_on=interrupt_on,
)
```

with:

```python
agent = create_agent(
    model=_build_chat_model(cfg.model, cfg.base_url, cfg.api_key),
    tools=tool_bundle.tools,
    system_prompt=system_prompt,
    middleware=build_agent_middleware(
        max_model_calls=cfg.max_model_calls,
        max_tool_calls=cfg.max_tool_calls,
        interrupt_on=interrupt_on,
    ),
    checkpointer=checkpointer,
)
```

- [ ] **Step 5: Remove unused DeepAgents backend call**

Remove this call from agent construction:

```python
backend=_build_agent_backend(workspace_path, request.skill_source_records),
```

Keep `_build_agent_backend` temporarily until all tests and imports are updated. Delete it in Task 9.

- [ ] **Step 6: Run runtime tests**

Run:

```powershell
uv run pytest tests/test_agent_runtime.py -q
```

Expected: tests pass after DeepAgents-specific assertions are updated.

### Task 4: Add Workspace File Tools

**Files:**
- Create: `src/easy_claw/tools/files.py`
- Modify: `src/easy_claw/agent/toolset.py`
- Test: `tests/test_file_tools.py`
- Test: `tests/test_agent_toolset.py`

- [ ] **Step 1: Write file tool tests**

Create `tests/test_file_tools.py`:

```python
from easy_claw.tools.files import build_file_tool_bundle


def _tool_by_name(bundle, name):
    return next(tool for tool in bundle.tools if tool.name == name)


def test_read_text_file_reads_workspace_file(tmp_path):
    (tmp_path / "README.md").write_text("# Title\n", encoding="utf-8")
    bundle = build_file_tool_bundle(workspace_path=tmp_path)

    result = _tool_by_name(bundle, "read_text_file").invoke({"path": "README.md"})

    assert result == "# Title\n"


def test_write_text_file_rejects_workspace_escape(tmp_path):
    bundle = build_file_tool_bundle(workspace_path=tmp_path)

    result = _tool_by_name(bundle, "write_text_file").invoke(
        {"path": "../outside.txt", "content": "no"}
    )

    assert "工作区外" in result
    assert not (tmp_path.parent / "outside.txt").exists()


def test_edit_text_file_replaces_single_occurrence(tmp_path):
    target = tmp_path / "app.py"
    target.write_text("print('old')\n", encoding="utf-8")
    bundle = build_file_tool_bundle(workspace_path=tmp_path)

    result = _tool_by_name(bundle, "edit_text_file").invoke(
        {"path": "app.py", "old": "old", "new": "new"}
    )

    assert "已更新" in result
    assert target.read_text(encoding="utf-8") == "print('new')\n"


def test_edit_text_file_rejects_ambiguous_replacement(tmp_path):
    target = tmp_path / "app.py"
    target.write_text("x = 1\nx = 1\n", encoding="utf-8")
    bundle = build_file_tool_bundle(workspace_path=tmp_path)

    result = _tool_by_name(bundle, "edit_text_file").invoke(
        {"path": "app.py", "old": "x = 1", "new": "x = 2"}
    )

    assert "出现 2 次" in result
    assert target.read_text(encoding="utf-8") == "x = 1\nx = 1\n"
```

- [ ] **Step 2: Run file tool tests and confirm they fail**

Run:

```powershell
uv run pytest tests/test_file_tools.py -q
```

Expected: FAIL because `easy_claw.tools.files` does not exist.

- [ ] **Step 3: Implement `src/easy_claw/tools/files.py`**

Add:

```python
from __future__ import annotations

from pathlib import Path

from langchain_core.tools import tool

from easy_claw.agent.types import ToolBundle

FILE_INTERRUPT_ON = {
    "write_text_file": True,
    "edit_text_file": True,
}


def build_file_tool_bundle(*, workspace_path: Path) -> ToolBundle:
    return ToolBundle(
        tools=build_file_tools(workspace_path=workspace_path),
        interrupt_on=dict(FILE_INTERRUPT_ON),
    )


def build_file_tools(*, workspace_path: Path) -> list[object]:
    workspace = workspace_path.expanduser().resolve(strict=False)

    def resolve_workspace_path(path: str) -> tuple[Path | None, str | None]:
        raw = Path(path).expanduser()
        candidate = raw if raw.is_absolute() else workspace / raw
        resolved = candidate.resolve(strict=False)
        try:
            resolved.relative_to(workspace)
        except ValueError:
            return None, f"拒绝访问工作区外路径：{path}"
        return resolved, None

    @tool
    def list_files(pattern: str = "**/*") -> str:
        """列出当前工作区内匹配 pattern 的文件路径。"""
        matches = sorted(
            path.relative_to(workspace).as_posix()
            for path in workspace.glob(pattern)
            if path.is_file()
        )
        if not matches:
            return f"没有找到匹配文件：{pattern}"
        return "\n".join(matches[:500])

    @tool
    def read_text_file(path: str) -> str:
        """读取当前工作区内的 UTF-8 文本文件。"""
        resolved, error = resolve_workspace_path(path)
        if error:
            return error
        assert resolved is not None
        if not resolved.exists():
            return f"文件不存在：{path}"
        if not resolved.is_file():
            return f"不是文件：{path}"
        try:
            return resolved.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return f"文件不是 UTF-8 文本：{path}"

    @tool
    def write_text_file(path: str, content: str) -> str:
        """写入当前工作区内的 UTF-8 文本文件。会创建父目录。"""
        resolved, error = resolve_workspace_path(path)
        if error:
            return error
        assert resolved is not None
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
        return f"已写入：{resolved.relative_to(workspace).as_posix()}"

    @tool
    def edit_text_file(path: str, old: str, new: str) -> str:
        """在当前工作区内的文本文件中执行一次精确替换。"""
        resolved, error = resolve_workspace_path(path)
        if error:
            return error
        assert resolved is not None
        if not resolved.exists():
            return f"文件不存在：{path}"
        try:
            text = resolved.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return f"文件不是 UTF-8 文本：{path}"
        count = text.count(old)
        if count == 0:
            return f"未找到要替换的内容：{path}"
        if count > 1:
            return f"要替换的内容出现 {count} 次，请提供更精确的 old 文本。"
        resolved.write_text(text.replace(old, new, 1), encoding="utf-8")
        return f"已更新：{resolved.relative_to(workspace).as_posix()}"

    return [list_files, read_text_file, write_text_file, edit_text_file]
```

- [ ] **Step 4: Include file tools in toolset**

In `src/easy_claw/agent/toolset.py`, import:

```python
from easy_claw.tools.files import build_file_tool_bundle
```

Inside `build_easy_claw_tools`, after core tools:

```python
file_bundle = build_file_tool_bundle(workspace_path=context.workspace_path)
tools.extend(file_bundle.tools)
cleanup.extend(file_bundle.cleanup)
interrupt_on.update(file_bundle.interrupt_on)
```

- [ ] **Step 5: Update toolset tests**

In `tests/test_agent_toolset.py`, update expected core tool names to include:

```python
"list_files",
"read_text_file",
"write_text_file",
"edit_text_file",
```

Assert:

```python
assert bundle.interrupt_on["write_text_file"] is True
assert bundle.interrupt_on["edit_text_file"] is True
```

- [ ] **Step 6: Run file and toolset tests**

Run:

```powershell
uv run pytest tests/test_file_tools.py tests/test_agent_toolset.py -q
```

Expected: PASS.

### Task 5: Add Skill Tools

**Files:**
- Create: `src/easy_claw/agent/skill_tools.py`
- Modify: `src/easy_claw/skills.py`
- Modify: `src/easy_claw/agent/runtime.py`
- Test: `tests/test_skill_tools.py`
- Test: `tests/test_skills.py`

- [ ] **Step 1: Add skill lookup tests**

Create `tests/test_skill_tools.py`:

```python
from easy_claw.agent.skill_tools import build_skill_tool_bundle
from easy_claw.skills import SkillSource


def _write_skill(source_root, name, description):
    skill_dir = source_root / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n# {name}\nBody",
        encoding="utf-8",
    )
    return skill_dir


def _tool_by_name(bundle, name):
    return next(tool for tool in bundle.tools if tool.name == name)


def test_list_skills_returns_available_skill_summary(tmp_path):
    source_root = tmp_path / "skills" / "core"
    _write_skill(source_root, "analyze-project", "Analyze project.")
    source = SkillSource("builtin", "easy-claw built-in", source_root, "/skills/core/", 1)
    bundle = build_skill_tool_bundle(skill_source_records=[source])

    result = _tool_by_name(bundle, "list_skills").invoke({})

    assert "analyze-project" in result
    assert "Analyze project." in result


def test_read_skill_prefers_later_higher_priority_source(tmp_path):
    builtin = tmp_path / "builtin"
    project = tmp_path / "project"
    _write_skill(builtin, "review", "Builtin review.")
    _write_skill(project, "review", "Project review.")
    sources = [
        SkillSource("builtin", "easy-claw built-in", builtin, "/builtin/", 1),
        SkillSource("project", "project skills", project, "/skills/", 1),
    ]
    bundle = build_skill_tool_bundle(skill_source_records=sources)

    result = _tool_by_name(bundle, "read_skill").invoke({"name": "review"})

    assert "Project review." in result
    assert "Builtin review." not in result
```

- [ ] **Step 2: Run skill tool tests and confirm they fail**

Run:

```powershell
uv run pytest tests/test_skill_tools.py -q
```

Expected: FAIL because `easy_claw.agent.skill_tools` does not exist.

- [ ] **Step 3: Add skill lookup helper in `skills.py`**

Add:

```python
def discover_source_skills(source: SkillSource) -> list[Skill]:
    if not source.filesystem_path.exists():
        return []
    skills: list[Skill] = []
    for skill_file in sorted(source.filesystem_path.glob("*/SKILL.md")):
        if skill_file.is_file():
            skills.append(load_skill(skill_file))
    return skills
```

- [ ] **Step 4: Implement skill tools**

Create `src/easy_claw/agent/skill_tools.py`:

```python
from __future__ import annotations

from collections.abc import Sequence

from langchain_core.tools import tool

from easy_claw.agent.types import ToolBundle
from easy_claw.skills import Skill, SkillSource, discover_source_skills


def build_skill_tool_bundle(*, skill_source_records: Sequence[SkillSource]) -> ToolBundle:
    skills_by_name = _skills_by_name(skill_source_records)

    @tool
    def list_skills() -> str:
        """列出当前会话可用的 easy-claw skills。"""
        if not skills_by_name:
            return "当前没有发现 easy-claw skills。"
        lines = ["可用 easy-claw skills:"]
        for name, skill in sorted(skills_by_name.items()):
            description = skill.description or "无描述"
            lines.append(f"- {name}: {description} ({skill.path})")
        return "\n".join(lines)

    @tool
    def read_skill(name: str) -> str:
        """读取一个 easy-claw skill 的完整 SKILL.md 内容。"""
        skill = skills_by_name.get(name.strip())
        if skill is None:
            available = ", ".join(sorted(skills_by_name)) or "无"
            return f"未找到 skill：{name}。可用：{available}"
        helper_files = _helper_files(skill)
        helper_text = "\n".join(helper_files) if helper_files else "无"
        return (
            f"Skill: {skill.name}\n"
            f"Description: {skill.description or '无描述'}\n"
            f"Path: {skill.path}\n"
            f"Helper files:\n{helper_text}\n\n"
            f"{skill.body}"
        )

    return ToolBundle(tools=[list_skills, read_skill])


def build_skill_summary(skill_source_records: Sequence[SkillSource]) -> str:
    skills_by_name = _skills_by_name(skill_source_records)
    if not skills_by_name:
        return "当前没有发现 easy-claw skills。"
    lines = ["可用 easy-claw skills 摘要:"]
    for name, skill in sorted(skills_by_name.items()):
        description = skill.description or "无描述"
        lines.append(f"- {name}: {description}")
    lines.append("如果任务匹配某个 skill，请先调用 read_skill 读取完整说明。")
    return "\n".join(lines)


def _skills_by_name(skill_source_records: Sequence[SkillSource]) -> dict[str, Skill]:
    skills: dict[str, Skill] = {}
    for source in skill_source_records:
        for skill in discover_source_skills(source):
            skills[skill.name] = skill
    return skills


def _helper_files(skill: Skill) -> list[str]:
    skill_dir = skill.path.parent
    return sorted(
        path.relative_to(skill_dir).as_posix()
        for path in skill_dir.rglob("*")
        if path.is_file() and path.name != "SKILL.md"
    )
```

- [ ] **Step 5: Add skill tools to runtime tools**

In `src/easy_claw/agent/runtime.py`, import:

```python
from easy_claw.agent.skill_tools import build_skill_summary, build_skill_tool_bundle
```

After `tool_bundle = build_easy_claw_tools(...)`, add:

```python
skill_tool_bundle = build_skill_tool_bundle(
    skill_source_records=request.skill_source_records,
)
tools = [*tool_bundle.tools, *skill_tool_bundle.tools]
```

Pass `tools=tools` into `create_agent`.

- [ ] **Step 6: Add skill summary to system prompt**

Change:

```python
system_prompt = _build_system_prompt()
```

to:

```python
system_prompt = _build_system_prompt(
    skill_summary=build_skill_summary(request.skill_source_records),
)
```

Update `_build_system_prompt` signature:

```python
def _build_system_prompt(*, skill_summary: str = "") -> str:
```

Append `skill_summary` to the prompt parts when non-empty.

- [ ] **Step 7: Run skill tests**

Run:

```powershell
uv run pytest tests/test_skill_tools.py tests/test_skills.py -q
```

Expected: PASS.

### Task 6: Remove DeepAgents Backend Helpers

**Files:**
- Modify: `src/easy_claw/agent/runtime.py`
- Test: `tests/test_agent_runtime.py`

- [ ] **Step 1: Delete unused helpers**

Remove these from `src/easy_claw/agent/runtime.py` if no production code uses them:

```python
def _request_skill_source_paths(request: AgentRequest) -> list[str]: ...
def _build_agent_backend(...): ...
def _is_under_workspace(...): ...
```

- [ ] **Step 2: Delete imports made unused by helper removal**

Remove unused imports from `runtime.py`, including:

```python
Mapping
```

only if no longer used. Keep `Mapping` if `_build_interrupt_on` still needs it.

- [ ] **Step 3: Run runtime tests**

Run:

```powershell
uv run pytest tests/test_agent_runtime.py -q
```

Expected: PASS.

### Task 7: Update Tool Interrupt Policy Names

**Files:**
- Modify: `src/easy_claw/agent/toolset.py`
- Test: `tests/test_agent_toolset.py`

- [ ] **Step 1: Rename DeepAgents-specific constant**

Change:

```python
DEEPAGENTS_FILESYSTEM_INTERRUPT_ON = {
    "edit_file": True,
    "execute": True,
    "write_file": True,
}
```

to:

```python
BASE_RISKY_TOOL_INTERRUPT_ON = {}
```

The new file tools contribute `write_text_file` and `edit_text_file` through `build_file_tool_bundle`.

- [ ] **Step 2: Update toolset construction**

Change:

```python
interrupt_on = dict(DEEPAGENTS_FILESYSTEM_INTERRUPT_ON)
```

to:

```python
interrupt_on = dict(BASE_RISKY_TOOL_INTERRUPT_ON)
```

- [ ] **Step 3: Update tests**

In `tests/test_agent_toolset.py`, remove expected keys:

```python
"edit_file"
"execute"
"write_file"
```

Keep expected keys:

```python
"run_command"
"run_python"
"write_text_file"
"edit_text_file"
```

- [ ] **Step 4: Run toolset tests**

Run:

```powershell
uv run pytest tests/test_agent_toolset.py -q
```

Expected: PASS.

### Task 8: Update Runtime Tests and Names

**Files:**
- Modify: `tests/test_agent_runtime.py`
- Modify: `src/easy_claw/api/main.py`
- Modify: `src/easy_claw/cli.py`
- Modify: `src/easy_claw/cli_interactive.py`

- [ ] **Step 1: Update imports in tests**

In `tests/test_agent_runtime.py`, prefer:

```python
from easy_claw.agent.runtime import LangChainAgentRuntime, LangChainAgentSession
```

Keep one compatibility test for:

```python
DeepAgentsRuntime is LangChainAgentRuntime
DeepAgentSession is LangChainAgentSession
```

- [ ] **Step 2: Update production imports**

In API and CLI modules, change imports from:

```python
DeepAgentsRuntime
```

to:

```python
LangChainAgentRuntime
```

Then change construction:

```python
runtime = LangChainAgentRuntime(...)
```

- [ ] **Step 3: Run CLI/API focused tests**

Run:

```powershell
uv run pytest tests/test_api.py tests/test_cli.py -q
```

Expected: PASS.

### Task 9: Remove DeepAgents Dependency

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`

- [ ] **Step 1: Confirm no production imports remain**

Run:

```powershell
Get-ChildItem -Recurse -File src,tests -Include *.py | Select-String -Pattern 'deepagents','DeepAgents','DeepAgent'
```

Expected: only temporary compatibility aliases and tests should remain. If production code still imports `deepagents`, remove that import before continuing.

- [ ] **Step 2: Remove dependency**

In `pyproject.toml`, delete:

```toml
"deepagents>=0.4.0",
```

- [ ] **Step 3: Sync lockfile**

Run:

```powershell
uv sync
```

Expected: succeeds and updates `uv.lock`.

- [ ] **Step 4: Verify package tree**

Run:

```powershell
uv tree --depth 1
```

Expected: `deepagents` is not listed as a direct dependency.

### Task 10: Update Documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/skills.md`

- [ ] **Step 1: Update README capability wording**

Replace DeepAgents-specific runtime wording with:

```text
LangChain / LangGraph 运行时封装。
easy-claw Markdown skill 加载和项目级 skill 自动发现。
```

- [ ] **Step 2: Update Skills section**

Replace:

```text
easy-claw 使用 DeepAgents 原生 skill 机制。
```

with:

```text
easy-claw 使用自有 Markdown skill 机制，并通过 LangChain tools 在运行时按需读取 skill。
```

- [ ] **Step 3: Update architecture runtime section**

Describe the new flow:

```text
LangChainAgentRuntime 通过 langchain.agents.create_agent 创建 Agent，传入 easy-claw 工具、skill 工具、LangChain middleware 和 LangGraph SqliteSaver。
```

- [ ] **Step 4: Run docs grep**

Run:

```powershell
Get-ChildItem -Recurse -File README.md,docs -Include *.md | Select-String -Pattern 'DeepAgents','deepagents'
```

Expected: remaining mentions only document historical migration context or supported legacy skill paths such as `.deepagents\skills`.

### Task 11: Full Verification

**Files:**
- All modified files

- [ ] **Step 1: Run full tests**

Run:

```powershell
uv run pytest
```

Expected: all non-skipped tests pass.

- [ ] **Step 2: Run lint**

Run:

```powershell
uv run ruff check .
```

Expected:

```text
All checks passed!
```

- [ ] **Step 3: Run doctor**

Run:

```powershell
uv run easy-claw doctor
```

Expected: command exits successfully and prints config, database, MCP, and browser diagnostics.

- [ ] **Step 4: Run skill listing smoke**

Run:

```powershell
uv run easy-claw dev skills list --all-sources
```

Expected: TSV output includes built-in skill sources when present.

- [ ] **Step 5: Run single-shot chat smoke if API credentials are configured**

Run:

```powershell
uv run easy-claw chat "总结 README.md 的主要内容"
```

Expected: agent returns a Chinese summary and can use file-reading tools. If credentials are not configured, expected failure mentions `EASY_CLAW_MODEL` or `EASY_CLAW_API_KEY`.

## Rollback Checklist

If migration breaks core chat behavior:

- [ ] Restore `deepagents>=0.4.0` in `pyproject.toml`.
- [ ] Restore the last known `create_deep_agent` block in `src/easy_claw/agent/runtime.py`.
- [ ] Keep `src/easy_claw/tools/files.py` only if it remains isolated and tests pass.
- [ ] Keep `src/easy_claw/agent/skill_tools.py` only if it remains isolated and tests pass.
- [ ] Run `uv sync`.
- [ ] Run `uv run pytest`.
- [ ] Run `uv run ruff check .`.

## Completion Criteria

- [ ] `pyproject.toml` has no `deepagents` dependency.
- [ ] `uv.lock` no longer resolves `deepagents`.
- [ ] Production code uses `langchain.agents.create_agent`.
- [ ] File tools replace DeepAgents built-in file operations.
- [ ] Skill tools replace DeepAgents native `skills` loading.
- [ ] HITL approval uses `HumanInTheLoopMiddleware`.
- [ ] `uv run pytest` passes.
- [ ] `uv run ruff check .` passes.
- [ ] README and architecture docs describe LangChain runtime accurately.

