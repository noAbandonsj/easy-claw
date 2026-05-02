from easy_claw.tools.documents import (
    collect_document_paths,
    convert_workspace_document,
    load_workspace_documents,
    read_workspace_text,
)


def test_read_workspace_text_reads_text_file(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "README.md").write_text("# Hello", encoding="utf-8")

    result = read_workspace_text(workspace, "README.md")

    assert result.relative_path == "README.md"
    assert result.markdown == "# Hello"


def test_collect_document_paths_expands_directory(tmp_path):
    workspace = tmp_path / "workspace"
    docs = workspace / "docs"
    docs.mkdir(parents=True)
    (docs / "a.md").write_text("A", encoding="utf-8")
    (docs / "b.txt").write_text("B", encoding="utf-8")
    (docs / "c.docx").write_bytes(b"fake")

    paths = collect_document_paths(workspace, ["docs"])

    assert [path.as_posix() for path in paths] == [
        "docs/a.md",
        "docs/b.txt",
        "docs/c.docx",
    ]


class FakeConverter:
    def convert(self, path):
        class Result:
            text_content = "# Converted"

        return Result()


def test_convert_workspace_document_uses_converter(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "report.docx").write_bytes(b"fake")

    result = convert_workspace_document(
        workspace,
        "report.docx",
        converter=FakeConverter(),
    )

    assert result.relative_path == "report.docx"
    assert result.markdown == "# Converted"
    assert result.converted is True


def test_load_workspace_documents_converts_non_text_documents(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "README.md").write_text("# Text", encoding="utf-8")
    (workspace / "report.docx").write_bytes(b"fake")

    result = load_workspace_documents(
        workspace,
        ["README.md", "report.docx"],
        converter=FakeConverter(),
    )

    assert [document.relative_path for document in result.documents] == [
        "README.md",
        "report.docx",
    ]
    assert result.documents[0].converted is False
    assert result.documents[1].converted is True
    assert result.errors == []


def test_load_workspace_documents_continues_after_unreadable_file(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "README.md").write_text("# Text", encoding="utf-8")
    (workspace / "bad.txt").write_bytes(b"\xff\xfe\xff")

    result = load_workspace_documents(workspace, ["README.md", "bad.txt"])

    assert [document.relative_path for document in result.documents] == ["README.md"]
    assert len(result.errors) == 1
    assert result.errors[0].path == "bad.txt"


def test_load_workspace_documents_marks_paths_outside_workspace(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("# Outside", encoding="utf-8")

    result = load_workspace_documents(workspace, [str(outside)])

    assert result.documents[0].outside_workspace is True
    assert result.documents[0].relative_path == outside.resolve().as_posix()
