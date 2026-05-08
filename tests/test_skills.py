from pathlib import Path

from easy_claw.skills import discover_skill_sources, discover_skills, resolve_skill_sources

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _write_skill(source_root, name, description="Test skill."):
    skill_dir = source_root / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n# Skill\n",
        encoding="utf-8",
    )
    (skill_dir / "helper.py").write_text("print('helper')\n", encoding="utf-8")
    return skill_dir


def test_builtin_skills_include_create_skill():
    skills = discover_skills(PROJECT_ROOT / "skills")

    create_skill = next(skill for skill in skills if skill.name == "create-skill")

    assert "创建" in create_skill.description
    assert "SKILL.md" in create_skill.body


def test_discover_skills_reads_deep_agents_style_skill(tmp_path):
    skill_dir = tmp_path / "skills" / "core" / "analyze-project"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: analyze-project\n"
        "description: Analyze a local project.\n"
        "---\n"
        "# Skill\n"
        "Read files.",
        encoding="utf-8",
    )

    skills = discover_skills(tmp_path / "skills")

    assert [skill.name for skill in skills] == ["analyze-project"]
    assert skills[0].description == "Analyze a local project."
    assert "Read files." in skills[0].body


def test_discover_skills_reads_flat_markdown_skill(tmp_path):
    skill_root = tmp_path / "skills" / "core"
    skill_root.mkdir(parents=True)
    (skill_root / "summarize-docs.md").write_text(
        "---\nname: summarize-docs\ndescription: Summarize docs.\n---\n# Skill\nSummarize.",
        encoding="utf-8",
    )

    skills = discover_skills(tmp_path / "skills")

    assert skills[0].name == "summarize-docs"


def test_discover_skill_sources_returns_deepagents_source_dirs(tmp_path):
    skill_dir = tmp_path / "skills" / "core" / "analyze-project"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: analyze-project\ndescription: Analyze.\n---\n# Skill",
        encoding="utf-8",
    )

    sources = discover_skill_sources(tmp_path / "skills", tmp_path)

    assert sources == ["/skills/core/"]


def test_resolve_skill_sources_collects_common_paths_in_priority_order(tmp_path):
    app_root = tmp_path / "app"
    workspace = tmp_path / "workspace"
    home = tmp_path / "home"

    builtin_source = app_root / "skills" / "core"
    user_source = home / ".easy-claw" / "skills"
    claude_source = home / ".claude" / "skills"
    project_source = workspace / ".deepagents" / "skills"
    project_alias_source = workspace / ".easy-claw" / "skills"

    _write_skill(builtin_source, "analyze-project")
    _write_skill(user_source, "weekly-review")
    _write_skill(claude_source, "systematic-debugging")
    _write_skill(project_source, "project-review")
    _write_skill(project_alias_source, "project-alias")

    sources = resolve_skill_sources(
        app_root=app_root,
        workspace_root=workspace,
        home_dir=home,
    )

    assert [(source.scope, source.label, source.filesystem_path) for source in sources] == [
        ("builtin", "easy-claw built-in", builtin_source.resolve()),
        ("user", "user easy-claw", user_source.resolve()),
        ("user", "user claude", claude_source.resolve()),
        ("project", "project deepagents", project_source.resolve()),
        ("project", "project easy-claw", project_alias_source.resolve()),
    ]
    assert [source.skill_count for source in sources] == [1, 1, 1, 1, 1]
    assert sources[0].backend_path.startswith("/easy-claw/skill-sources/")
    assert sources[1].backend_path.startswith("/easy-claw/skill-sources/")
    assert sources[2].backend_path.startswith("/easy-claw/skill-sources/")
    assert sources[3].backend_path == "/.deepagents/skills/"
    assert sources[4].backend_path == "/.easy-claw/skills/"
    assert all(source.backend_path.endswith("/") for source in sources)


def test_resolve_skill_sources_excludes_codex_system_skills_by_default(tmp_path):
    app_root = tmp_path / "app"
    workspace = tmp_path / "workspace"
    home = tmp_path / "home"

    _write_skill(home / ".codex" / "skills" / ".system", "codex-only")
    _write_skill(home / ".agents" / "skills", "agent-compatible")

    sources = resolve_skill_sources(
        app_root=app_root,
        workspace_root=workspace,
        home_dir=home,
    )

    assert [source.label for source in sources] == ["user agents"]
    assert sources[0].filesystem_path == (home / ".agents" / "skills").resolve()


def test_resolve_skill_sources_deduplicates_same_physical_source(tmp_path):
    app_root = tmp_path / "project"
    workspace = app_root
    home = tmp_path / "home"
    source = app_root / "skills" / "core"
    _write_skill(source, "analyze-project")

    sources = resolve_skill_sources(
        app_root=app_root,
        workspace_root=workspace,
        home_dir=home,
    )

    assert len(sources) == 1
    assert sources[0].label == "easy-claw built-in"
    assert sources[0].filesystem_path == source.resolve()


def test_resolve_skill_sources_ignores_markdown_helpers_inside_skill_dirs(tmp_path):
    app_root = tmp_path / "app"
    workspace = tmp_path / "workspace"
    home = tmp_path / "home"
    skill_dir = _write_skill(app_root / "skills" / "core", "analyze-project")
    references_dir = skill_dir / "references"
    references_dir.mkdir()
    (references_dir / "notes.md").write_text("# Notes\n", encoding="utf-8")

    sources = resolve_skill_sources(
        app_root=app_root,
        workspace_root=workspace,
        home_dir=home,
    )

    assert len(sources) == 1
    assert sources[0].filesystem_path == (app_root / "skills" / "core").resolve()
