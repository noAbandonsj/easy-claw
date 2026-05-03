from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from easy_claw.tools.base import ToolExecutionError
from easy_claw.workspace import normalize_path

TEXT_DOCUMENT_SUFFIXES = {".md", ".txt", ".py", ".json", ".yaml", ".yml"}
CONVERTIBLE_DOCUMENT_SUFFIXES = {
    ".csv",
    ".doc",
    ".docx",
    ".htm",
    ".html",
    ".pdf",
    ".ppt",
    ".pptx",
    ".xls",
    ".xlsx",
}
SUPPORTED_DOCUMENT_SUFFIXES = TEXT_DOCUMENT_SUFFIXES | CONVERTIBLE_DOCUMENT_SUFFIXES


@dataclass(frozen=True)
class DocumentContent:
    relative_path: str
    markdown: str
    converted: bool = False
    outside_workspace: bool = False


def read_workspace_text(workspace_root: Path, requested_path: str) -> DocumentContent:
    root = normalize_path(workspace_root)
    resolved = _resolve_user_path(root, requested_path)
    return DocumentContent(
        relative_path=_relative_to_root(resolved, root).as_posix(),
        markdown=resolved.read_text(encoding="utf-8"),
        converted=False,
        outside_workspace=_is_outside_workspace(resolved, root),
    )


def convert_workspace_document(
    workspace_root: Path,
    requested_path: str,
    *,
    converter: object | None = None,
) -> DocumentContent:
    root = normalize_path(workspace_root)
    resolved = _resolve_user_path(root, requested_path)
    active_converter = converter or _create_markitdown_converter()
    result = active_converter.convert(resolved)
    return DocumentContent(
        relative_path=_relative_to_root(resolved, root).as_posix(),
        markdown=str(getattr(result, "text_content", "")),
        converted=True,
        outside_workspace=_is_outside_workspace(resolved, root),
    )


def read_workspace_document(
    workspace_root: Path,
    requested_path: str,
    *,
    converter: object | None = None,
) -> DocumentContent:
    suffix = Path(requested_path).suffix.lower()
    if suffix in TEXT_DOCUMENT_SUFFIXES:
        return read_workspace_text(workspace_root, requested_path)
    if suffix in CONVERTIBLE_DOCUMENT_SUFFIXES:
        return convert_workspace_document(
            workspace_root,
            requested_path,
            converter=converter,
        )
    raise ToolExecutionError(f"Unsupported document type: {requested_path}")


def _resolve_user_path(workspace_root: Path, requested_path: str | Path) -> Path:
    path = Path(requested_path)
    if not path.is_absolute():
        path = workspace_root / path
    return normalize_path(path)


def _relative_to_root(path: Path, root: Path) -> Path:
    try:
        return path.relative_to(root)
    except ValueError:
        return path


def _is_outside_workspace(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return True
    return False


def _create_markitdown_converter() -> object:
    from markitdown import MarkItDown

    return MarkItDown()
