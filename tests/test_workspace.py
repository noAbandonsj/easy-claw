from pathlib import Path

import pytest

from easy_claw.workspace import WorkspaceBoundaryError, resolve_workspace_path


def test_resolve_workspace_path_allows_child_path(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "docs" / "README.md"

    resolved = resolve_workspace_path(workspace, Path("docs") / "README.md")

    assert resolved == target.resolve()


def test_resolve_workspace_path_rejects_parent_escape(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with pytest.raises(WorkspaceBoundaryError):
        resolve_workspace_path(workspace, Path("..") / "outside.txt")
