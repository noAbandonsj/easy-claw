from easy_claw.agent.skill_tools import build_skill_summary, build_skill_tool_bundle
from easy_claw.skills import SkillSource


def _write_skill(source_root, name, description):
    skill_dir = source_root / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n# {name}\nBody",
        encoding="utf-8",
    )
    (skill_dir / "helper.py").write_text("print('helper')\n", encoding="utf-8")
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
    assert "easy-claw built-in" in result


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
    assert "helper.py" in result


def test_build_skill_summary_tells_agent_to_read_matching_skill(tmp_path):
    source_root = tmp_path / "skills" / "core"
    _write_skill(source_root, "summarize-docs", "Summarize documents.")
    source = SkillSource("builtin", "easy-claw built-in", source_root, "/skills/core/", 1)

    summary = build_skill_summary([source])

    assert "summarize-docs" in summary
    assert "read_skill" in summary
