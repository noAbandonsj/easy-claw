# easy-claw 第二版实施计划

> **给 agentic worker 的要求：** 实施本计划时必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans`，并按复选框逐步跟踪。

**目标：** 把第一版的 Agent 骨架扩展成可用的本地强工具助手，支持读取文档、转换 Markdown、联网搜索、运行项目命令、执行 Python 片段、调用 Agent 总结，并通过 CLI/API 输出报告。

**架构：** 新增 `tools` 模块承接文件读取、文档转换、搜索、命令执行、Python 执行和报告写入；CLI/API 负责收集用户输入并调用工具层；`DeepAgentsRuntime` 继续负责模型和 Agent 执行。第二版把工作区作为默认上下文而不是硬沙箱，不实现完整审批、安全策略或沙箱。

**技术栈：** Python 3.11+、Typer、FastAPI、SQLite、MarkItDown、DuckDuckGo Search、DeepAgents、LangChain、DeepSeek、pytest、ruff、uv。

---

## 文件结构

- 创建 `src/easy_claw/tools/__init__.py`：工具模块包入口。
- 创建 `src/easy_claw/tools/base.py`：工具结果、工具配置、工具错误和活动日志 payload。
- 创建 `src/easy_claw/tools/documents.py`：工作区内文件收集、文本读取、MarkItDown 转换。
- 创建 `src/easy_claw/tools/reports.py`：Markdown 报告写入。
- 创建 `src/easy_claw/tools/search.py`：DuckDuckGo 搜索封装。
- 创建 `src/easy_claw/tools/commands.py`：PowerShell / Shell 命令执行，带超时和输出截断。
- 创建 `src/easy_claw/tools/python_runner.py`：Python 片段或脚本执行，带超时和输出截断。
- 修改 `src/easy_claw/cli.py`：新增 `docs summarize` 命令。
- 修改 `src/easy_claw/cli.py`：新增 `tools search`、`tools run`、`tools python` 命令。
- 修改 `src/easy_claw/api/main.py`：新增 `POST /runs`。
- 修改 `src/easy_claw/storage/repositories.py`：给活动日志增加列表查询，方便测试和后续 UI。
- 创建 `tests/test_document_tools.py`：文档工具测试。
- 创建 `tests/test_report_tools.py`：报告写入测试。
- 创建 `tests/test_search_tools.py`：搜索工具测试。
- 创建 `tests/test_command_tools.py`：命令工具测试。
- 创建 `tests/test_python_runner.py`：Python runner 测试。
- 修改 `tests/test_cli.py`：覆盖 `docs summarize`。
- 修改 `tests/test_api.py`：覆盖 `POST /runs`。
- 修改 `README.md`：补充第二版使用方式。

## 任务 1：文档工具基础

**文件：**
- 创建：`src/easy_claw/tools/__init__.py`
- 创建：`src/easy_claw/tools/base.py`
- 创建：`src/easy_claw/tools/documents.py`
- 创建：`tests/test_document_tools.py`

- [ ] **步骤 1：先写失败测试**

```python
from easy_claw.tools.documents import collect_document_paths, read_workspace_text


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

    paths = collect_document_paths(workspace, ["docs"])

    assert [path.as_posix() for path in paths] == ["docs/a.md", "docs/b.txt"]
```

- [ ] **步骤 2：确认红灯**

运行：`uv run pytest tests/test_document_tools.py -q`

预期：因为 `easy_claw.tools.documents` 不存在而失败。

- [ ] **步骤 3：实现最小工具代码**

实现：

- `DocumentContent(relative_path: str, markdown: str)`
- `collect_document_paths(workspace_root: Path, requested_paths: Sequence[str]) -> list[Path]`
- `read_workspace_text(workspace_root: Path, requested_path: str) -> DocumentContent`

相对路径按工作区解析；用户显式传入的绝对路径允许读取。目录收集先支持 `.md`、`.txt`、`.py`、`.json`、`.yaml`、`.yml`。

- [ ] **步骤 4：确认绿灯**

运行：`uv run pytest tests/test_document_tools.py -q`

预期：文档工具测试通过。

## 任务 2：MarkItDown 转换入口

**文件：**
- 修改：`src/easy_claw/tools/documents.py`
- 修改：`tests/test_document_tools.py`

- [ ] **步骤 1：先写失败测试**

```python
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
```

- [ ] **步骤 2：确认红灯**

运行：`uv run pytest tests/test_document_tools.py -q`

预期：因为 `convert_workspace_document` 不存在而失败。

- [ ] **步骤 3：实现转换入口**

实现 `convert_workspace_document(workspace_root, requested_path, converter=None)`。如果 `converter` 为空，懒加载 `from markitdown import MarkItDown` 并调用 `MarkItDown().convert(path)`。

- [ ] **步骤 4：确认绿灯**

运行：`uv run pytest tests/test_document_tools.py -q`

预期：转换入口测试通过。

## 任务 3：报告写入工具

**文件：**
- 创建：`src/easy_claw/tools/reports.py`
- 创建：`tests/test_report_tools.py`

- [ ] **步骤 1：先写失败测试**

```python
from easy_claw.tools.reports import write_markdown_report


def test_write_markdown_report_writes_inside_workspace(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    output = write_markdown_report(workspace, "reports/summary.md", "# Summary")

    assert output.relative_path == "reports/summary.md"
    assert (workspace / "reports" / "summary.md").read_text(encoding="utf-8") == "# Summary"
```

- [ ] **步骤 2：确认红灯**

运行：`uv run pytest tests/test_report_tools.py -q`

预期：因为 `easy_claw.tools.reports` 不存在而失败。

- [ ] **步骤 3：实现报告写入**

实现 `write_markdown_report(workspace_root, output_path, content)`，复用 `resolve_workspace_path`，自动创建父目录，返回包含 `relative_path` 的结果对象。

- [ ] **步骤 4：确认绿灯**

运行：`uv run pytest tests/test_report_tools.py -q`

预期：报告工具测试通过。

## 任务 4：搜索工具

**文件：**
- 创建：`src/easy_claw/tools/search.py`
- 创建：`tests/test_search_tools.py`

- [ ] **步骤 1：先写失败测试**

```python
from easy_claw.tools.search import search_web


class FakeSearchBackend:
    def text(self, query, max_results):
        assert query == "DeepSeek API"
        assert max_results == 3
        return [
            {"title": "DeepSeek Docs", "href": "https://api-docs.deepseek.com", "body": "Docs"}
        ]


def test_search_web_returns_normalized_results():
    results = search_web("DeepSeek API", max_results=3, backend=FakeSearchBackend())

    assert results[0].title == "DeepSeek Docs"
    assert results[0].url == "https://api-docs.deepseek.com"
    assert results[0].snippet == "Docs"
```

- [ ] **步骤 2：确认红灯**

运行：`uv run pytest tests/test_search_tools.py -q`

预期：因为 `easy_claw.tools.search` 不存在而失败。

- [ ] **步骤 3：实现搜索封装**

实现 `SearchResult(title: str, url: str, snippet: str)` 和 `search_web(query, max_results=5, backend=None)`。默认 backend 懒加载 `duckduckgo_search.DDGS()`。

- [ ] **步骤 4：确认绿灯**

运行：`uv run pytest tests/test_search_tools.py -q`

预期：搜索工具测试通过。

## 任务 5：命令执行工具

**文件：**
- 创建：`src/easy_claw/tools/commands.py`
- 创建：`tests/test_command_tools.py`

- [ ] **步骤 1：先写失败测试**

```python
from easy_claw.tools.commands import run_command


def test_run_command_captures_output(tmp_path):
    result = run_command("python -c \"print('hello')\"", cwd=tmp_path, timeout_seconds=5)

    assert result.exit_code == 0
    assert result.stdout.strip() == "hello"


def test_run_command_truncates_long_output(tmp_path):
    result = run_command(
        "python -c \"print('x' * 100)\"",
        cwd=tmp_path,
        timeout_seconds=5,
        max_output_chars=10,
    )

    assert result.truncated is True
    assert len(result.stdout) <= 10
```

- [ ] **步骤 2：确认红灯**

运行：`uv run pytest tests/test_command_tools.py -q`

预期：因为 `easy_claw.tools.commands` 不存在而失败。

- [ ] **步骤 3：实现命令执行**

实现 `CommandResult(command, cwd, exit_code, stdout, stderr, timed_out, truncated)` 和 `run_command(command, cwd, timeout_seconds=60, max_output_chars=20000)`。Windows 下用 PowerShell 执行字符串命令，设置超时，截断 stdout/stderr。

- [ ] **步骤 4：确认绿灯**

运行：`uv run pytest tests/test_command_tools.py -q`

预期：命令工具测试通过。

## 任务 6：Python Runner

**文件：**
- 创建：`src/easy_claw/tools/python_runner.py`
- 创建：`tests/test_python_runner.py`

- [ ] **步骤 1：先写失败测试**

```python
from easy_claw.tools.python_runner import run_python_code


def test_run_python_code_captures_output(tmp_path):
    result = run_python_code("print(1 + 1)", cwd=tmp_path, timeout_seconds=5)

    assert result.exit_code == 0
    assert result.stdout.strip() == "2"
```

- [ ] **步骤 2：确认红灯**

运行：`uv run pytest tests/test_python_runner.py -q`

预期：因为 `easy_claw.tools.python_runner` 不存在而失败。

- [ ] **步骤 3：实现 Python 执行**

实现 `run_python_code(code, cwd, timeout_seconds=60, max_output_chars=20000)`。内部复用命令执行工具，把代码通过临时 `.py` 文件运行，运行结束后删除临时文件。

- [ ] **步骤 4：确认绿灯**

运行：`uv run pytest tests/test_python_runner.py -q`

预期：Python runner 测试通过。

## 任务 7：CLI 文档总结命令

**文件：**
- 修改：`src/easy_claw/cli.py`
- 修改：`tests/test_cli.py`

- [ ] **步骤 1：先写失败测试**

```python
def test_docs_summarize_dry_run_reads_document(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "README.md").write_text("# Project", encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(app, ["docs", "summarize", "--dry-run", "README.md"])

    assert result.exit_code == 0
    assert "README.md" in result.stdout
    assert "# Project" in result.stdout
```

- [ ] **步骤 2：确认红灯**

运行：`uv run pytest tests/test_cli.py::test_docs_summarize_dry_run_reads_document -q`

预期：因为 `docs summarize` 命令不存在而失败。

- [ ] **步骤 3：实现 dry-run 命令**

新增 `docs_app = typer.Typer(...)`，注册为 `app.add_typer(docs_app, name="docs")`。实现 `summarize(paths: list[Path], output: Path | None = None, dry_run: bool = False)`。dry-run 只输出收集到的文档内容，不调用模型。

- [ ] **步骤 4：确认绿灯**

运行：`uv run pytest tests/test_cli.py::test_docs_summarize_dry_run_reads_document -q`

预期：CLI dry-run 测试通过。

## 任务 8：真实 CLI 总结流程

**文件：**
- 修改：`src/easy_claw/cli.py`
- 修改：`tests/test_cli.py`

- [ ] **步骤 1：先写失败测试**

```python
def test_docs_summarize_requires_model_without_dry_run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("EASY_CLAW_MODEL", raising=False)
    (tmp_path / "README.md").write_text("# Project", encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(app, ["docs", "summarize", "README.md"])

    assert result.exit_code != 0
    assert "Set EASY_CLAW_MODEL" in result.stdout
```

- [ ] **步骤 2：确认红灯**

运行：`uv run pytest tests/test_cli.py::test_docs_summarize_requires_model_without_dry_run -q`

预期：命令不存在或没有配置检查而失败。

- [ ] **步骤 3：实现真实流程**

真实流程复用现有 `DeepAgentsRuntime`：读取文档内容，拼出包含文件名和 Markdown 内容的 prompt，加载 `summarize-docs` skill 和 memory，创建 session，然后调用 runtime。若设置 `--output`，将结果写入报告。

- [ ] **步骤 4：确认绿灯**

运行：`uv run pytest tests/test_cli.py -q`

预期：CLI 测试通过。

## 任务 9：API Run 入口

**文件：**
- 修改：`src/easy_claw/api/main.py`
- 修改：`tests/test_api.py`

- [ ] **步骤 1：先写失败测试**

```python
def test_create_run_requires_prompt_and_documents(tmp_path):
    config = AppConfig(
        cwd=tmp_path,
        data_dir=tmp_path / "data",
        product_db_path=tmp_path / "data" / "easy-claw.db",
        checkpoint_db_path=tmp_path / "data" / "checkpoints.sqlite",
        default_workspace=tmp_path,
        model=None,
        developer_mode=False,
    )
    client = TestClient(create_app(config))

    response = client.post("/runs", json={"prompt": "总结", "document_paths": []})

    assert response.status_code == 400
```

- [ ] **步骤 2：确认红灯**

运行：`uv run pytest tests/test_api.py -q`

预期：因为 `/runs` 不存在而失败。

- [ ] **步骤 3：实现最小 `/runs`**

新增 `CreateRunRequest`，字段包括 `prompt`、`workspace_path`、`document_paths`、`output_path`。第二版先同步返回结果，不做流式。

- [ ] **步骤 4：确认绿灯**

运行：`uv run pytest tests/test_api.py -q`

预期：API 测试通过。

## 任务 10：活动日志

**文件：**
- 修改：`src/easy_claw/storage/repositories.py`
- 修改：`src/easy_claw/cli.py`
- 修改：`src/easy_claw/api/main.py`
- 修改：`tests/test_storage.py`

- [ ] **步骤 1：先写失败测试**

```python
def test_audit_repository_lists_records(tmp_path):
    db_path = tmp_path / "easy-claw.db"
    initialize_product_db(db_path)
    repo = AuditRepository(db_path)

    repo.record(event_type="document_read", payload={"path": "README.md"})

    assert repo.list_logs()[0].event_type == "document_read"
```

- [ ] **步骤 2：确认红灯**

运行：`uv run pytest tests/test_storage.py::test_audit_repository_lists_records -q`

预期：因为 `list_logs` 不存在而失败。

- [ ] **步骤 3：实现活动日志查询并接入 CLI/API**

实现 `AuditRepository.list_logs()`。CLI/API 在读取文档、转换文档、写报告、发起 Agent run 时调用 `record()`。这里的日志只做可见性记录，不做复杂安全审计。

- [ ] **步骤 4：确认绿灯**

运行：`uv run pytest tests/test_storage.py tests/test_cli.py tests/test_api.py -q`

预期：相关测试通过。

## 任务 11：CLI 强工具命令、文档和验证

**文件：**
- 修改：`README.md`
- 修改：`docs/architecture.md`

- [ ] **步骤 1：更新使用说明**

README 增加：

```powershell
uv run easy-claw docs summarize README.md
uv run easy-claw docs summarize docs --output data/reports/docs-summary.md
uv run easy-claw tools search "DeepSeek API tool calls"
uv run easy-claw tools run "pytest -q"
uv run easy-claw tools python "print('hello from easy-claw')"
```

- [ ] **步骤 2：新增 CLI 强工具命令**

在 `src/easy_claw/cli.py` 中新增：

- `tools search <query>`
- `tools run <command>`
- `tools python <code>`

这些命令直接调用对应工具层，输出结果并记录活动日志。

- [ ] **步骤 3：运行全量测试**

运行：`uv run pytest -q`

预期：全部测试通过。

- [ ] **步骤 4：运行 lint**

运行：`uv run ruff check .`

预期：无 lint 错误。
