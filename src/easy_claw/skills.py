from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    path: Path
    body: str


@dataclass(frozen=True)
class SkillSource:
    scope: str
    label: str
    filesystem_path: Path
    backend_path: str
    skill_count: int


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


def discover_source_skills(source: SkillSource) -> list[Skill]:
    """Return direct child ``SKILL.md`` skills from a resolved skill source."""
    if not source.filesystem_path.exists():
        return []
    skill_paths = sorted(
        path
        for path in source.filesystem_path.glob("*/SKILL.md")
        if path.is_file()
    )
    return [load_skill(path) for path in skill_paths]


def discover_skill_sources(skills_root: Path, workspace_root: Path) -> list[str]:
    """返回可按虚拟路径引用的技能源目录路径。"""
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


def resolve_skill_sources(
    *,
    app_root: Path,
    workspace_root: Path,
    home_dir: Path | None = None,
) -> list[SkillSource]:
    """Resolve complete easy-claw skill source directories.

    The returned sources are ordered from low to high priority. Each source path
    is a directory that contains one or more child skill directories with
    ``SKILL.md`` files; helper files next to ``SKILL.md`` remain available to the
    easy-claw skill tools.
    """
    app = app_root.expanduser().resolve(strict=False)
    workspace = workspace_root.expanduser().resolve(strict=False)
    home = (home_dir or Path.home()).expanduser().resolve(strict=False)

    candidates = [
        ("builtin", "easy-claw built-in", app / "skills"),
        ("user", "user skills (legacy deepagents)", home / ".deepagents" / "skills"),
        ("user", "user agent skills (legacy deepagents)", home / ".deepagents" / "agent" / "skills"),
        ("user", "user agents", home / ".agents" / "skills"),
        ("user", "user easy-claw", home / ".easy-claw" / "skills"),
        ("user", "user claude", home / ".claude" / "skills"),
        ("project", "project skills (legacy deepagents)", workspace / ".deepagents" / "skills"),
        ("project", "project agents", workspace / ".agents" / "skills"),
        ("project", "project easy-claw", workspace / ".easy-claw" / "skills"),
        ("project", "project skills", workspace / "skills"),
    ]

    sources: list[SkillSource] = []
    seen_paths: set[Path] = set()
    for scope, label, root in candidates:
        resolved_root = root.expanduser().resolve(strict=False)
        if resolved_root in seen_paths:
            continue
        source_dirs = _discover_source_dirs(resolved_root)
        if not source_dirs:
            continue
        for source_dir in source_dirs:
            resolved_source = source_dir.resolve(strict=False)
            if resolved_source in seen_paths:
                continue
            seen_paths.add(resolved_source)
            sources.append(
                SkillSource(
                    scope=scope,
                    label=label,
                    filesystem_path=resolved_source,
                    backend_path=_backend_source_path(resolved_source, workspace),
                    skill_count=_count_direct_skill_dirs(resolved_source),
                )
            )
    return sources


def _discover_source_dirs(skills_root: Path) -> list[Path]:
    if not skills_root.exists():
        return []
    source_dirs: set[Path] = set()
    for skill_path in skills_root.rglob("SKILL.md"):
        if skill_path.is_file():
            source_dirs.add(skill_path.parent.parent.resolve(strict=False))
    return sorted(source_dirs)


def _count_direct_skill_dirs(source_dir: Path) -> int:
    if not source_dir.exists():
        return 0
    return sum(1 for child in source_dir.iterdir() if (child / "SKILL.md").is_file())


def _backend_source_path(source_dir: Path, workspace_root: Path) -> str:
    try:
        relative = source_dir.relative_to(workspace_root)
        source = "/" + relative.as_posix().strip("/")
    except ValueError:
        source = "/easy-claw/skill-sources/" + _source_path_slug(source_dir)
    if not source.endswith("/"):
        source += "/"
    return source


def _source_path_slug(path: Path) -> str:
    raw = path.as_posix().strip("/").replace(":", "")
    parts = [part for part in raw.split("/") if part]
    slug = "-".join(parts[-4:]) if parts else "skills"
    return slug
