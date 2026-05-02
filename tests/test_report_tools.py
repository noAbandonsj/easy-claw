from easy_claw.tools.reports import write_markdown_report


def test_write_markdown_report_writes_inside_workspace(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    output = write_markdown_report(workspace, "reports/summary.md", "# Summary")

    assert output.relative_path == "reports/summary.md"
    assert output.outside_workspace is False
    assert (workspace / "reports" / "summary.md").read_text(encoding="utf-8") == "# Summary"


def test_write_markdown_report_marks_absolute_path_outside_workspace(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside" / "summary.md"

    output = write_markdown_report(workspace, outside, "# Summary")

    assert output.relative_path == outside.resolve().as_posix()
    assert output.outside_workspace is True
    assert outside.read_text(encoding="utf-8") == "# Summary"
