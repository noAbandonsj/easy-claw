from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    path: Path
    body: str


def _split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---"):
        return {}, text

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text

    metadata: dict[str, str] = {}
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return metadata, "\n".join(lines[index + 1 :]).strip()
        if ":" in line:
            key, value = line.split(":", 1)
            metadata[key.strip()] = value.strip().strip('"').strip("'")

    return {}, text


def load_skill(path: Path) -> Skill:
    text = path.read_text(encoding="utf-8")
    metadata, body = _split_frontmatter(text)
    default_name = path.parent.name if path.name.lower() == "skill.md" else path.stem
    return Skill(
        name=metadata.get("name", default_name),
        description=metadata.get("description", ""),
        path=path,
        body=body,
    )


def discover_skills(skills_root: Path) -> list[Skill]:
    if not skills_root.exists():
        return []

    skill_paths = sorted(
        path for path in skills_root.rglob("*.md") if path.is_file() and path.name != ".gitkeep"
    )
    return [load_skill(path) for path in skill_paths]


def discover_skill_sources(skills_root: Path, workspace_root: Path) -> list[str]:
    """返回 DeepAgents 可读取的技能源目录路径。"""
    workspace = workspace_root.resolve()
    source_dirs: set[Path] = set()
    for skill in discover_skills(skills_root):
        if skill.path.name.lower() == "skill.md":
            source_dirs.add(skill.path.parent.parent.resolve())
        else:
            source_dirs.add(skill.path.parent.resolve())

    sources: list[str] = []
    for source_dir in sorted(source_dirs):
        try:
            relative = source_dir.relative_to(workspace)
        except ValueError:
            continue
        source = "/" + relative.as_posix().strip("/")
        if not source.endswith("/"):
            source += "/"
        sources.append(source)
    return sources
