import json
from io import StringIO

from rich.console import Console
from typer.testing import CliRunner

from easy_claw.agent.runtime import AgentResult, StreamEvent
from easy_claw.cli import app
from easy_claw.skills import SkillSource
from easy_claw.storage.repositories import AuditRepository
from easy_claw.tools.commands import CommandResult
from easy_claw.tools.search import SearchResult


def test_doctor_command_reports_ok(tmp_path, monkeypatch):
    monkeypatch.setenv("EASY_CLAW_DATA_DIR", str(tmp_path / "data"))
    runner = CliRunner()

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "easy-claw doctor" in result.stdout
    assert "MCP 启用状态:" in result.stdout
    assert "MCP 配置文件:" in result.stdout


def test_chat_dry_run_uses_fake_runtime():
    runner = CliRunner()

    result = runner.invoke(app, ["chat", "--dry-run", "hello"])

    assert result.exit_code == 0
    assert "easy-claw dry-run 测试：hello" in result.stdout


def test_chat_passes_resolved_skill_source_records(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EASY_CLAW_MODEL", "deepseek-v4-pro")
    source_root = tmp_path / ".easy-claw" / "skills"
    source_root.mkdir(parents=True)
    source = SkillSource(
        scope="project",
        label="project easy-claw",
        filesystem_path=source_root,
        backend_path="/.easy-claw/skills/",
        skill_count=1,
    )
    captured_requests = []

    class FakeRuntime:
        def run(self, request):
            captured_requests.append(request)
            return AgentResult(content="done", thread_id=request.thread_id)

    def fake_resolve_skill_sources(*, app_root, workspace_root, home_dir=None):
        assert app_root == tmp_path
        assert workspace_root == tmp_path
        return [source]

    monkeypatch.setattr("easy_claw.cli.DeepAgentsRuntime", FakeRuntime)
    monkeypatch.setattr("easy_claw.cli.resolve_skill_sources", fake_resolve_skill_sources)
    runner = CliRunner()

    result = runner.invoke(app, ["chat", "hello"])

    assert result.exit_code == 0
    assert captured_requests[0].skill_sources == ()
    assert captured_requests[0].skill_source_records == [source]


def test_chat_without_model_reports_configuration_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("EASY_CLAW_MODEL", raising=False)
    runner = CliRunner()

    result = runner.invoke(app, ["chat", "hello"])

    assert result.exit_code != 0
    assert "请先设置 EASY_CLAW_MODEL" in result.stdout


def test_chat_interactive_reuses_one_session_thread(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EASY_CLAW_MODEL", "deepseek-v4-pro")
    captured_requests = []

    class FakeRuntime:
        def run(self, request):
            captured_requests.append(request)
            return AgentResult(
                content=f"answer: {request.prompt}",
                thread_id=request.thread_id,
            )

    monkeypatch.setattr("easy_claw.cli.DeepAgentsRuntime", FakeRuntime)
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["chat", "--interactive"],
        input="hello\ncontinue\nexit\n",
    )

    assert result.exit_code == 0
    assert "answer: hello" in result.stdout
    assert "answer: continue" in result.stdout
    assert len(captured_requests) == 2
    assert captured_requests[0].thread_id == captured_requests[1].thread_id
    sessions = AuditRepository(tmp_path / "data" / "easy-claw.db").list_logs()
    assert [log.event_type for log in sessions].count("agent_run") == 2


def test_render_streaming_turn_prints_tokens_and_tool_panels(monkeypatch):
    output = StringIO()
    test_console = Console(file=output, force_terminal=False, color_system=None, width=100)
    monkeypatch.setattr("easy_claw.cli.console", test_console)

    from easy_claw.cli import _render_streaming_turn

    _render_streaming_turn(
        iter(
            [
                StreamEvent(type="token", content="hello "),
                StreamEvent(
                    type="tool_call_start",
                    tool_name="read_document",
                    tool_args={"path": "README.md"},
                ),
                StreamEvent(
                    type="tool_call_result",
                    tool_name="read_document",
                    tool_result="# Project",
                    content="# Project",
                ),
                StreamEvent(type="token", content="world"),
                StreamEvent(type="done", content="hello world"),
            ]
        )
    )

    rendered = output.getvalue()
    assert "hello " in rendered
    assert "world" in rendered
    assert "工具调用：read_document" in rendered
    assert "README.md" in rendered
    assert "工具结果：read_document" in rendered
    assert "# Project" in rendered


def test_chat_interactive_uses_stream_when_session_supports_it(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EASY_CLAW_MODEL", "deepseek-v4-pro")
    prompts = []

    class FakeStreamingSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            pass

        def run(self, prompt):
            raise AssertionError("interactive chat should prefer stream()")

        def stream(self, prompt):
            prompts.append(prompt)
            yield StreamEvent(type="token", content=f"stream: {prompt}")
            yield StreamEvent(type="done", content=f"stream: {prompt}", thread_id="thread-1")

    class FakeRuntime:
        def open_session(self, request):
            return FakeStreamingSession()

    monkeypatch.setattr("easy_claw.cli.DeepAgentsRuntime", FakeRuntime)
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["chat", "--interactive"],
        input="hello\nexit\n",
    )

    assert result.exit_code == 0
    assert "stream: hello" in result.stdout
    assert prompts == ["hello"]
    events = [
        log.event_type for log in AuditRepository(tmp_path / "data" / "easy-claw.db").list_logs()
    ]
    assert events.count("agent_run") == 1


def test_docs_summarize_command_is_removed():
    runner = CliRunner()

    result = runner.invoke(app, ["dev", "docs", "summarize", "README.md"])

    assert result.exit_code != 0


def test_top_level_developer_command_aliases_are_removed():
    runner = CliRunner()

    assert runner.invoke(app, ["tools", "search", "DeepSeek"]).exit_code != 0
    assert runner.invoke(app, ["skills", "list"]).exit_code != 0


def test_top_level_session_aliases_are_visible_in_help():
    runner = CliRunner()

    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "list-sessions" in result.stdout
    assert "resume-session" in result.stdout
    assert "delete-session" in result.stdout


def test_dev_tools_search_prints_results(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "easy_claw.cli.search_web",
        lambda query, **_: [
            SearchResult(
                title="DeepSeek Docs",
                url="https://api-docs.deepseek.com",
                snippet="Docs",
            )
        ],
        raising=False,
    )
    runner = CliRunner()

    result = runner.invoke(app, ["dev", "tools", "search", "DeepSeek"])

    assert result.exit_code == 0
    assert "DeepSeek Docs" in result.stdout
    assert "https://api-docs.deepseek.com" in result.stdout
    events = [
        log.event_type for log in AuditRepository(tmp_path / "data" / "easy-claw.db").list_logs()
    ]
    assert "web_search" in events


def test_dev_tools_run_records_command_output(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "easy_claw.cli.run_command",
        lambda command, cwd: CommandResult(
            command=command,
            cwd=cwd,
            exit_code=0,
            stdout="hello\n",
            stderr="",
            timed_out=False,
            truncated=False,
        ),
        raising=False,
    )
    runner = CliRunner()

    result = runner.invoke(app, ["dev", "tools", "run", "echo hello"])

    assert result.exit_code == 0
    assert "hello" in result.stdout
    events = [log for log in AuditRepository(tmp_path / "data" / "easy-claw.db").list_logs()]
    command_log = next(log for log in events if log.event_type == "command_run")
    payload = json.loads(command_log.payload_json)
    assert payload["command"] == "echo hello"
    assert payload["cwd"] == str(tmp_path)
    assert payload["exit_code"] == 0
    assert payload["timed_out"] is False
    assert payload["truncated"] is False


def test_dev_tools_python_prints_output(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "easy_claw.cli.run_python_code",
        lambda code, cwd: CommandResult(
            command=code,
            cwd=cwd,
            exit_code=0,
            stdout="2\n",
            stderr="",
            timed_out=False,
            truncated=False,
        ),
        raising=False,
    )
    runner = CliRunner()

    result = runner.invoke(app, ["dev", "tools", "python", "print(1 + 1)"])

    assert result.exit_code == 0
    assert "2" in result.stdout
    events = [
        log.event_type for log in AuditRepository(tmp_path / "data" / "easy-claw.db").list_logs()
    ]
    assert "python_run" in events


def test_dev_skills_list_all_sources_prints_resolved_sources(tmp_path, monkeypatch):
    source_root = tmp_path / ".easy-claw" / "skills"
    source_root.mkdir(parents=True)
    source = SkillSource(
        scope="project",
        label="project easy-claw",
        filesystem_path=source_root,
        backend_path="/.easy-claw/skills/",
        skill_count=1,
    )

    def fake_resolve_skill_sources(*, app_root, workspace_root, home_dir=None):
        return [source]

    monkeypatch.setattr("easy_claw.cli.resolve_skill_sources", fake_resolve_skill_sources)
    runner = CliRunner()

    result = runner.invoke(app, ["dev", "skills", "list", "--all-sources"])

    assert result.exit_code == 0
    assert "project easy-claw" in result.stdout
    assert "/.easy-claw/skills/" in result.stdout


def test_startup_banner_shows_mcp_status(tmp_path, monkeypatch):
    from easy_claw.cli import _count_mcp_servers, _mcp_status
    from easy_claw.config import AppConfig

    assert _count_mcp_servers("nonexistent.json") == 0

    valid = tmp_path / "servers.json"
    valid.write_text('{"_comment": "metadata", "srv1": {}, "srv2": {}}')
    assert _count_mcp_servers(str(valid)) == 2

    empty = tmp_path / "empty.json"
    empty.write_text("[]")
    assert _count_mcp_servers(str(empty)) == 0

    config = AppConfig(
        cwd=tmp_path,
        data_dir=tmp_path / "data",
        product_db_path=tmp_path / "data" / "easy-claw.db",
        checkpoint_db_path=tmp_path / "data" / "checkpoints.sqlite",
        default_workspace=tmp_path,
        model="test-model",
        base_url="https://api.example.com",
        api_key="sk-test",
        mcp_mode="auto",
        mcp_config_path=str(valid),
    )
    assert _mcp_status(config) == "auto（2 个服务）"
