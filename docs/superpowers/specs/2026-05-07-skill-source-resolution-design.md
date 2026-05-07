# Skill Source Resolution Design

## Goal

easy-claw should automatically discover complete DeepAgents-style skill directories from built-in, user-global, and project-local locations, then pass those source paths to DeepAgents without reimplementing skill execution.

## Scope

This change supports complete skill directories containing `SKILL.md` plus optional helper files. It does not copy skill files, inline skill bodies into prompts, install SkillHub packages, or load Codex system skills by default.

## Source Order

Sources are ordered from low to high priority so later sources can override earlier skills with the same name:

1. easy-claw built-in skills: `<easy-claw root>/skills`
2. user-global skills:
   - `%USERPROFILE%/.deepagents/skills`
   - `%USERPROFILE%/.deepagents/agent/skills`
   - `%USERPROFILE%/.agents/skills`
   - `%USERPROFILE%/.easy-claw/skills`
   - `%USERPROFILE%/.claude/skills`
3. workspace project skills:
   - `<workspace>/.deepagents/skills`
   - `<workspace>/.agents/skills`
   - `<workspace>/.easy-claw/skills`
   - `<workspace>/skills`

`%USERPROFILE%/.codex/skills` is intentionally excluded by default because it contains Codex runtime skills that may reference unavailable tools and conflicting workflows.

## Architecture

`easy_claw.skills` owns discovery. It returns structured source records with a label, filesystem path, priority group, skill count, and DeepAgents backend path. Existing callers that only need paths continue to receive a list of DeepAgents source strings.

Runtime loading uses the existing `LocalShellBackend` for the active workspace. When a discovered skill source lives outside that workspace, easy-claw mounts it into the agent backend with DeepAgents `CompositeBackend` and a read/write filesystem route rooted at the skill source directory. This lets DeepAgents read complete external skill directories, including helper files next to `SKILL.md`, without copying them into the project.

## Data Flow

CLI and API construct skill sources through the resolver using:

- `app_root`: easy-claw repository or package root
- `workspace_root`: current Agent workspace
- `home_dir`: current user's home directory

`DeepAgentsRuntime` receives `AgentRequest.skill_sources` and passes them directly to `create_deep_agent(skills=...)`.

## Error Handling

Missing directories are ignored. Directories without child `SKILL.md` files are ignored for runtime source paths but can be shown in detailed CLI diagnostics if needed later. Invalid frontmatter remains handled by existing `load_skill` fallback behavior.

## Testing

Tests cover project-local source discovery, source ordering, exclusion of Codex system skills, and CLI visibility for multiple source roots. Existing runtime tests continue to verify that `skill_sources` are passed through to DeepAgents.
