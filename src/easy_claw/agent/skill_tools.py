from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from langchain_core.tools import tool

from easy_claw.agent.types import ToolBundle
from easy_claw.skills import Skill, SkillSource, discover_source_skills


@dataclass(frozen=True)
class _SkillEntry:
    skill: Skill
    source: SkillSource


def build_skill_tool_bundle(*, skill_source_records: Sequence[SkillSource]) -> ToolBundle:
    skills_by_name = _skills_by_name(skill_source_records)

    @tool
    def list_skills() -> str:
        """列出当前会话可用的 easy-claw skills。"""
        if not skills_by_name:
            return "当前没有发现 easy-claw skills。"
        lines = ["可用 easy-claw skills:"]
        for name, entry in sorted(skills_by_name.items()):
            description = entry.skill.description or "无描述"
            lines.append(f"- {name}: {description} [{entry.source.label}] {entry.skill.path}")
        return "\n".join(lines)

    @tool
    def read_skill(name: str) -> str:
        """读取一个 easy-claw skill 的完整 SKILL.md 内容。"""
        entry = skills_by_name.get(name.strip())
        if entry is None:
            available = ", ".join(sorted(skills_by_name)) or "无"
            return f"未找到 skill：{name}。可用：{available}"
        skill = entry.skill
        helper_files = _helper_files(skill)
        helper_text = "\n".join(helper_files) if helper_files else "无"
        return (
            f"Skill: {skill.name}\n"
            f"Description: {skill.description or '无描述'}\n"
            f"Source: {entry.source.label}\n"
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
    for name, entry in sorted(skills_by_name.items()):
        description = entry.skill.description or "无描述"
        lines.append(f"- {name}: {description}")
    lines.append("如果任务匹配某个 skill，请先调用 read_skill 读取完整说明。")
    return "\n".join(lines)


def _skills_by_name(skill_source_records: Sequence[SkillSource]) -> dict[str, _SkillEntry]:
    skills: dict[str, _SkillEntry] = {}
    for source in skill_source_records:
        for skill in discover_source_skills(source):
            skills[skill.name] = _SkillEntry(skill=skill, source=source)
    return skills


def _helper_files(skill: Skill) -> list[str]:
    skill_dir = skill.path.parent
    return sorted(
        path.relative_to(skill_dir).as_posix()
        for path in skill_dir.rglob("*")
        if path.is_file() and path.name != "SKILL.md"
    )
