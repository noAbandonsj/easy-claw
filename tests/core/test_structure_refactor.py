def test_cli_package_exports_existing_entrypoints():
    from easy_claw import cli as cli_package
    from easy_claw.cli import interactive, slash, views

    assert cli_package.app is not None
    assert cli_package.main is not None
    assert interactive._run_interactive_chat is not None
    assert slash.get_slash_command_specs is not None
    assert views._print_session_status is not None


def test_split_agent_modules_are_the_only_runtime_entrypoints():
    from easy_claw.agent import approvals, langchain_runtime, prompts, streaming

    assert langchain_runtime.AgentRequest is not None
    assert langchain_runtime.LangChainAgentRuntime is not None
    assert approvals.StaticApprovalReviewer is not None
    assert streaming.StreamEvent is not None
    assert prompts.build_system_prompt is not None


def test_api_app_uses_split_app_entrypoints():
    from easy_claw.api import app as api_app
    from easy_claw.api import websocket

    assert api_app.create_app is not None
    assert websocket.next_stream_event_or_none is not None


def test_legacy_compatibility_modules_are_removed():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]

    removed_paths = [
        root / "src" / "easy_claw" / "cli_interactive.py",
        root / "src" / "easy_claw" / "cli_slash.py",
        root / "src" / "easy_claw" / "cli_views.py",
        root / "src" / "easy_claw" / "agent" / "runtime.py",
        root / "src" / "easy_claw" / "api" / "main.py",
    ]

    assert [path for path in removed_paths if path.exists()] == []
