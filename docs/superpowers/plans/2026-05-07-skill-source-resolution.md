# Skill Source Resolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add automatic discovery for built-in, user-global, Claude-compatible, and project-local DeepAgents skill source directories.

**Architecture:** Keep DeepAgents as the skill execution system. Add a focused resolver in `easy_claw.skills`, update CLI/API call sites to use it, and expose source diagnostics through `dev skills list`.

**Tech Stack:** Python 3.11, Typer, pytest, DeepAgents `create_deep_agent(skills=...)`.

---

### Task 1: Resolver Tests

**Files:**
- Modify: `tests/test_skills.py`

- [ ] **Step 1: Write failing tests**

Add tests that create built-in, home, and workspace skill directories and assert source ordering, Codex exclusion, and DeepAgents path conversion for workspace-visible sources.

- [ ] **Step 2: Run tests and verify failure**

Run: `uv run pytest tests/test_skills.py -q`

Expected: tests fail because the resolver does not exist.

### Task 2: Resolver Implementation

**Files:**
- Modify: `src/easy_claw/skills.py`

- [ ] **Step 1: Implement source records**

Add a `SkillSource` dataclass and `resolve_skill_sources(...)` function.

- [ ] **Step 2: Preserve existing API**

Update `discover_skill_sources(...)` to delegate to the resolver while preserving current return type.

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/test_skills.py -q`

Expected: all skill tests pass.

### Task 3: CLI/API Integration

**Files:**
- Modify: `src/easy_claw/cli.py`
- Modify: `src/easy_claw/api/main.py`
- Modify: `tests/test_cli.py`
- Modify: `tests/test_api.py`

- [ ] **Step 1: Write failing CLI/API tests**

Add tests proving callers use the resolver and that `dev skills list` can display source labels.

- [ ] **Step 2: Implement caller changes**

Replace direct `discover_skill_sources(config.cwd / "skills", workspace)` calls with the new resolver.

- [ ] **Step 3: Run focused tests**

Run: `uv run pytest tests/test_skills.py tests/test_cli.py tests/test_api.py -q`

Expected: focused tests pass.

### Task 4: Full Verification

**Files:**
- No additional source files.

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest -q`

Expected: full suite passes with existing browser smoke skips.

- [ ] **Step 2: Run lint**

Run: `uv run ruff check .`

Expected: all checks pass.
