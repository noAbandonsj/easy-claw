from __future__ import annotations

from pathlib import Path

from langchain_core.tools import tool

from easy_claw.agent.types import ToolBundle
from easy_claw.tools.commands import CommandResult
from easy_claw.tools.commands import run_command as _run_command
from easy_claw.tools.documents import read_workspace_document as _read_workspace_document
from easy_claw.tools.python_runner import run_python_code as _run_python_code
from easy_claw.tools.search import search_web as _search_web

CORE_INTERRUPT_ON = {
    "run_command": True,
    "run_python": True,
}


def _format_command_result(result: CommandResult, *, label: str) -> str:
    parts: list[str] = []
    if result.timed_out:
        parts.append(f"[警告] {label} 已超过 60 秒超时。")
    if result.stdout:
        parts.append(result.stdout)
    if result.stderr:
        parts.append(f"[stderr]\n{result.stderr}")
    if result.truncated:
        parts.append("[警告] 输出已截断（超过 20000 个字符）。")
    if result.exit_code != 0 and not result.timed_out:
        parts.append(f"[退出码：{result.exit_code}]")
    return "\n".join(parts) if parts else "（无输出）"


def build_core_tool_bundle(*, workspace_path: Path, cwd: Path) -> ToolBundle:
    return ToolBundle(
        tools=build_core_tools(workspace_path=workspace_path, cwd=cwd),
        interrupt_on=dict(CORE_INTERRUPT_ON),
    )


def build_core_tools(*, workspace_path: Path, cwd: Path) -> list[object]:
    """返回已绑定当前工作区的 LangChain 工具。"""

    @tool
    def search_web(query: str) -> str:
        """使用搜索后端联网搜索，并返回格式化文本。

        当用户需要最新信息，或明确要求联网查询时使用。
        每条结果包含标题、网址和摘要。
        """
        results = _search_web(query)
        if not results:
            return f"没有找到结果：{query}"
        lines = [f"搜索结果：{query}"]
        for i, r in enumerate(results, 1):
            lines.append(f"\n{i}. {r.title}\n   URL: {r.url}\n   {r.snippet}")
        return "\n".join(lines)

    @tool
    def run_command(command: str) -> str:
        """在当前工作区执行 PowerShell 命令。

        常用于运行测试、检查代码风格、查看 Git 状态、列文件和执行本地构建。
        这是本地执行器，不是沙箱。输出最多保留 20000 个字符，超时时间为 60 秒。
        """
        return _format_command_result(_run_command(command, cwd=cwd), label="命令")

    @tool
    def run_python(code: str) -> str:
        """在当前工作区执行 Python 代码片段。

        常用于临时分析、数据处理和项目检查。
        代码会写入临时 .py 文件，并由系统 Python 解释器执行。
        输出最多保留 20000 个字符，超时时间为 60 秒。
        """
        return _format_command_result(_run_python_code(code, cwd=cwd), label="Python 执行")

    @tool
    def read_document(path: str) -> str:
        """读取本地文档，并以 Markdown 文本返回内容。

        支持文本文件（.md、.txt、.py、.json、.yaml、.yml）和可转换格式
        （.pdf、.docx、.xlsx、.pptx、.csv、.html）。
        非文本格式会自动转换为 Markdown。

        路径相对于工作区根目录。适合读取项目文件、说明文档或用户要求分析的文档。
        """
        try:
            document = _read_workspace_document(workspace_path, path)
        except Exception as exc:
            return f"读取文档失败 '{path}'：{exc}"
        prefix = f"文档：{document.relative_path}"
        if document.converted:
            prefix += "（已转换为 Markdown）"
        if document.outside_workspace:
            prefix += " [工作区外]"
        return f"{prefix}\n\n{document.markdown}"

    return [search_web, run_command, run_python, read_document]
