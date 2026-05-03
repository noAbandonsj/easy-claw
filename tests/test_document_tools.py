from easy_claw.tools.documents import (
    convert_workspace_document,
    read_workspace_document,
    read_workspace_text,
)


def test_read_workspace_text_reads_text_file(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "README.md").write_text("# Hello", encoding="utf-8")

    result = read_workspace_text(workspace, "README.md")

    assert result.relative_path == "README.md"
    assert result.markdown == "# Hello"


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


def test_read_workspace_document_dispatches_by_suffix(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "README.md").write_text("# Text", encoding="utf-8")
    (workspace / "report.docx").write_bytes(b"fake")

    text = read_workspace_document(workspace, "README.md")
    converted = read_workspace_document(workspace, "report.docx", converter=FakeConverter())

    assert text.markdown == "# Text"
    assert text.converted is False
    assert converted.markdown == "# Converted"
    assert converted.converted is True


def test_read_workspace_document_marks_paths_outside_workspace(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("# Outside", encoding="utf-8")

    result = read_workspace_document(workspace, str(outside))

    assert result.outside_workspace is True
    assert result.relative_path == outside.resolve().as_posix()
