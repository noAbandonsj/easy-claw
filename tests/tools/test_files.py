from __future__ import annotations

from easy_claw.agent.types import ToolBundle
from easy_claw.tools.files import FILE_MUTABLE_TOOLS, build_file_tool_bundle


def _tool_by_name(bundle: ToolBundle, name: str):
    return next(tool for tool in bundle.tools if tool.name == name)


class TestBuildFileToolBundle:
    def test_includes_all_eight_tools(self, tmp_path):
        bundle = build_file_tool_bundle(workspace_path=tmp_path)
        names = {tool.name for tool in bundle.tools}
        assert names == {
            "read_file",
            "write_file",
            "list_directory",
            "file_delete",
            "file_search",
            "copy_file",
            "move_file",
            "edit_file",
        }

    def test_interrupt_on_covers_mutable_operations(self, tmp_path):
        bundle = build_file_tool_bundle(workspace_path=tmp_path)
        for name in FILE_MUTABLE_TOOLS:
            assert bundle.interrupt_on.get(name) is True, f"{name} should be in interrupt_on"

    def test_read_only_tools_not_in_interrupt_on(self, tmp_path):
        bundle = build_file_tool_bundle(workspace_path=tmp_path)
        for name in ["read_file", "list_directory", "file_search"]:
            assert name not in bundle.interrupt_on


class TestEditFileTool:
    def test_replaces_single_match(self, tmp_path):
        file = tmp_path / "test.py"
        file.write_text("hello\nworld\n", encoding="utf-8")
        tool = _tool_by_name(build_file_tool_bundle(workspace_path=tmp_path), "edit_file")
        result = tool.invoke({
            "file_path": "test.py",
            "old_string": "hello",
            "new_string": "hi",
        })
        assert result == "File edited successfully: test.py"
        assert file.read_text(encoding="utf-8") == "hi\nworld\n"

    def test_reports_no_match(self, tmp_path):
        file = tmp_path / "test.py"
        file.write_text("hello\n", encoding="utf-8")
        tool = _tool_by_name(build_file_tool_bundle(workspace_path=tmp_path), "edit_file")
        result = tool.invoke({
            "file_path": "test.py",
            "old_string": "notfound",
            "new_string": "x",
        })
        assert "was not found" in result

    def test_reports_multiple_matches(self, tmp_path):
        file = tmp_path / "test.py"
        file.write_text("dup\ndup\n", encoding="utf-8")
        tool = _tool_by_name(build_file_tool_bundle(workspace_path=tmp_path), "edit_file")
        result = tool.invoke({
            "file_path": "test.py",
            "old_string": "dup",
            "new_string": "x",
        })
        assert "appears 2 times" in result

    def test_rejects_path_outside_root(self, tmp_path):
        bundle = build_file_tool_bundle(workspace_path=tmp_path)
        tool = _tool_by_name(bundle, "edit_file")
        result = tool.invoke({
            "file_path": "../outside.txt",
            "old_string": "a",
            "new_string": "b",
        })
        assert "Access denied" in result

    def test_reports_file_not_found(self, tmp_path):
        tool = _tool_by_name(build_file_tool_bundle(workspace_path=tmp_path), "edit_file")
        result = tool.invoke({
            "file_path": "nonexistent.txt",
            "old_string": "a",
            "new_string": "b",
        })
        assert "File not found" in result


class TestFileToolsRootDir:
    def test_read_file_rejects_escape(self, tmp_path):
        bundle = build_file_tool_bundle(workspace_path=tmp_path)
        tool = _tool_by_name(bundle, "read_file")
        result = tool.invoke({"file_path": "../secret.txt"})
        assert "Access denied" in result

    def test_write_file_rejects_escape(self, tmp_path):
        bundle = build_file_tool_bundle(workspace_path=tmp_path)
        tool = _tool_by_name(bundle, "write_file")
        result = tool.invoke({
            "file_path": "../secret.txt",
            "text": "bad",
        })
        assert "Access denied" in result

    def test_list_directory_works(self, tmp_path):
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        bundle = build_file_tool_bundle(workspace_path=tmp_path)
        tool = _tool_by_name(bundle, "list_directory")
        result = tool.invoke({"dir_path": "."})
        assert "a.txt" in result
        assert "b.txt" in result

    def test_file_delete_removes_file(self, tmp_path):
        file = tmp_path / "to_delete.txt"
        file.write_text("bye")
        bundle = build_file_tool_bundle(workspace_path=tmp_path)
        tool = _tool_by_name(bundle, "file_delete")
        result = tool.invoke({"file_path": "to_delete.txt"})
        assert "deleted successfully" in result
        assert not file.exists()
