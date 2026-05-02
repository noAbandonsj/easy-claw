from __future__ import annotations

from collections.abc import Sequence
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


@dataclass(frozen=True)
class DocumentLoadError:
    path: str
    message: str
    outside_workspace: bool = False


@dataclass(frozen=True)
class DocumentLoadResult:
    documents: list[DocumentContent]
    errors: list[DocumentLoadError]


def collect_document_paths(workspace_root: Path, requested_paths: Sequence[str]) -> list[Path]:
    root = normalize_path(workspace_root)
    collected: list[Path] = []
    for requested_path in requested_paths:
        resolved = _resolve_user_path(root, requested_path)
        if resolved.is_dir():
            collected.extend(
                _relative_to_root(path, root)
                for path in sorted(resolved.rglob("*"))
                if path.is_file() and path.suffix.lower() in SUPPORTED_DOCUMENT_SUFFIXES
            )
        elif resolved.is_file() and resolved.suffix.lower() in SUPPORTED_DOCUMENT_SUFFIXES:
            collected.append(_relative_to_root(resolved, root))
    return collected


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


def load_workspace_documents(
    workspace_root: Path,
    requested_paths: Sequence[str],
    *,
    converter: object | None = None,
) -> DocumentLoadResult:
    root = normalize_path(workspace_root)
    documents: list[DocumentContent] = []
    errors: list[DocumentLoadError] = []
    for requested_path in requested_paths:
        resolved = _resolve_user_path(root, requested_path)
        if not resolved.exists():
            errors.append(
                DocumentLoadError(
                    path=_relative_to_root(resolved, root).as_posix(),
                    message="File not found",
                    outside_workspace=_is_outside_workspace(resolved, root),
                )
            )
            continue

        paths = collect_document_paths(root, [requested_path])
        if not paths and resolved.is_file():
            errors.append(
                DocumentLoadError(
                    path=_relative_to_root(resolved, root).as_posix(),
                    message=f"Unsupported document type: {resolved.suffix}",
                    outside_workspace=_is_outside_workspace(resolved, root),
                )
            )
            continue

        for path in paths:
            try:
                documents.append(
                    read_workspace_document(root, path.as_posix(), converter=converter)
                )
            except Exception as exc:
                resolved_path = _resolve_user_path(root, path)
                errors.append(
                    DocumentLoadError(
                        path=_relative_to_root(resolved_path, root).as_posix(),
                        message=str(exc),
                        outside_workspace=_is_outside_workspace(resolved_path, root),
                    )
                )
    return DocumentLoadResult(documents=documents, errors=errors)


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
