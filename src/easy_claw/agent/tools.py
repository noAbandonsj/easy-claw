from __future__ import annotations

from pathlib import Path

from langchain_core.tools import tool

from easy_claw.tools.commands import run_command as _run_command
from easy_claw.tools.documents import read_workspace_document as _read_workspace_document
from easy_claw.tools.python_runner import run_python_code as _run_python_code
from easy_claw.tools.reports import write_markdown_report as _write_markdown_report
from easy_claw.tools.search import search_web as _search_web


def build_agent_tools(*, workspace_path: Path, cwd: Path) -> list:
    """Return LangChain tools configured for the active workspace."""

    @tool
    def search_web(query: str) -> str:
        """Search the web using DuckDuckGo and return results as formatted text.

        Use this when you need up-to-date information that may not be in your
        training data, or when the user asks you to look something up online.
        Each result includes a title, URL, and snippet.
        """
        results = _search_web(query)
        if not results:
            return f"No results found for: {query}"
        lines = [f"Search results for: {query}"]
        for i, r in enumerate(results, 1):
            lines.append(f"\n{i}. {r.title}\n   URL: {r.url}\n   {r.snippet}")
        return "\n".join(lines)

    @tool
    def run_command(command: str) -> str:
        """Execute a PowerShell command on the local machine.

        WARNING: This runs real commands on the user's computer. The user will
        be asked to approve each invocation before it executes. Always explain
        what the command will do before calling this tool.

        Commands run in the project working directory. Output is captured and
        truncated at 20000 characters. Timeout is 60 seconds.
        """
        result = _run_command(command, cwd=cwd)
        parts: list[str] = []
        if result.timed_out:
            parts.append("[WARNING] Command timed out after 60 seconds.")
        if result.stdout:
            parts.append(result.stdout)
        if result.stderr:
            parts.append(f"[stderr]\n{result.stderr}")
        if result.truncated:
            parts.append("[WARNING] Output was truncated (exceeded 20000 characters).")
        if result.exit_code != 0 and not result.timed_out:
            parts.append(f"[exit code: {result.exit_code}]")
        return "\n".join(parts) if parts else "(no output)"

    @tool
    def run_python(code: str) -> str:
        """Execute a Python code snippet on the local machine.

        WARNING: This runs real Python code on the user's computer. The user
        will be asked to approve each invocation before it executes. Always
        explain what the code will do before calling this tool.

        The code is written to a temporary .py file and executed with the
        system Python interpreter. Output is captured and truncated at
        20000 characters. Timeout is 60 seconds.
        """
        result = _run_python_code(code, cwd=cwd)
        parts: list[str] = []
        if result.timed_out:
            parts.append("[WARNING] Python execution timed out after 60 seconds.")
        if result.stdout:
            parts.append(result.stdout)
        if result.stderr:
            parts.append(f"[stderr]\n{result.stderr}")
        if result.truncated:
            parts.append("[WARNING] Output was truncated (exceeded 20000 characters).")
        if result.exit_code != 0 and not result.timed_out:
            parts.append(f"[exit code: {result.exit_code}]")
        return "\n".join(parts) if parts else "(no output)"

    @tool
    def read_document(path: str) -> str:
        """Read a local document and return its content as markdown.

        Supports text files (.md, .txt, .py, .json, .yaml, .yml) and
        convertible formats (.pdf, .docx, .xlsx, .pptx, .csv, .html).
        Non-text formats are automatically converted to markdown.

        The path is relative to the workspace root. Use this to read
        project files, documentation, or any supported document the
        user wants you to analyze.
        """
        try:
            document = _read_workspace_document(workspace_path, path)
        except Exception as exc:
            return f"Failed to read document '{path}': {exc}"
        prefix = f"Document: {document.relative_path}"
        if document.converted:
            prefix += " (converted to markdown)"
        if document.outside_workspace:
            prefix += " [outside workspace]"
        return f"{prefix}\n\n{document.markdown}"

    @tool
    def write_report(path: str, content: str) -> str:
        """Write a markdown report to a file in the workspace.

        The path is relative to the workspace root. Parent directories are
        created automatically. Use this to save summaries, analysis results,
        or generated documentation for the user.

        The user will be asked to approve each file write before it executes.
        """
        try:
            output = _write_markdown_report(workspace_path, path, content)
        except Exception as exc:
            return f"Failed to write report '{path}': {exc}"
        location = output.relative_path
        if output.outside_workspace:
            location += " [outside workspace — user approved]"
        return f"Report written to: {location}"

    return [search_web, run_command, run_python, read_document, write_report]
