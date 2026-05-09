from __future__ import annotations

from pathlib import Path

from langchain_community.agent_toolkits.file_management.toolkit import FileManagementToolkit
from langchain_core.tools import tool

from easy_claw.agent.types import ToolBundle

FILE_READ_ONLY_TOOLS = {"read_file", "list_directory", "file_search"}
FILE_MUTABLE_TOOLS = {"write_file", "file_delete", "copy_file", "move_file", "edit_file"}


def build_file_tool_bundle(*, workspace_path: Path) -> ToolBundle:
    root_dir = str(workspace_path)

    toolkit = FileManagementToolkit(
        root_dir=root_dir,
        selected_tools=[
            "read_file",
            "write_file",
            "list_directory",
            "file_delete",
            "file_search",
            "copy_file",
            "move_file",
        ],
    )
    tools = list(toolkit.get_tools())
    tools.append(_build_edit_file_tool(root_dir=root_dir))

    interrupt_on: dict[str, object] = {}
    for name in FILE_MUTABLE_TOOLS:
        interrupt_on[name] = True

    return ToolBundle(tools=tools, interrupt_on=interrupt_on)


def _build_edit_file_tool(*, root_dir: str):
    root = Path(root_dir).resolve()

    @tool
    def edit_file(file_path: str, old_string: str, new_string: str) -> str:
        """Edit a file by exact string replacement.

        Finds and replaces old_string with new_string in the target file.
        The old_string must appear exactly once in the file. If it appears
        zero or multiple times, the edit is rejected and you must provide
        a larger string with more surrounding context to make it unique.
        """
        full_path = (root / file_path).resolve()
        if not full_path.is_relative_to(root):
            return f"Error: Access denied to {file_path}. Path is outside the workspace."

        if not full_path.exists():
            return f"Error: File not found: {file_path}"

        try:
            content = full_path.read_text(encoding="utf-8")
        except Exception as exc:
            return f"Error: Cannot read {file_path}: {exc}"

        count = content.count(old_string)
        if count == 0:
            return f"Error: The string to replace was not found in {file_path}."
        if count > 1:
            return (
                f"Error: The string to replace appears {count} times in {file_path}. "
                "Please provide a larger string with more surrounding context to make it unique."
            )

        new_content = content.replace(old_string, new_string, 1)
        try:
            full_path.write_text(new_content, encoding="utf-8")
        except Exception as exc:
            return f"Error: Cannot write {file_path}: {exc}"

        return f"File edited successfully: {file_path}"

    return edit_file
