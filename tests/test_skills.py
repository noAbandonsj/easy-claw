from easy_claw.skills import discover_skills


def test_discover_skills_reads_deep_agents_style_skill(tmp_path):
    skill_dir = tmp_path / "skills" / "core" / "analyze-project"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: analyze-project\ndescription: Analyze a local project.\n---\n# Skill\nRead files.",
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
