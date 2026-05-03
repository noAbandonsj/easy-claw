from easy_claw.agent.toolset import ToolContext, build_easy_claw_tools


def test_build_easy_claw_tools_returns_core_tools_without_browser(tmp_path):
    bundle = build_easy_claw_tools(
        ToolContext(
            workspace_path=tmp_path,
            cwd=tmp_path,
            browser_enabled=False,
            browser_headless=False,
        )
    )

    assert [tool.name for tool in bundle.tools] == [
        "search_web",
        "run_command",
        "run_python",
        "read_document",
        "write_report",
    ]
    assert bundle.cleanup == ()


def test_build_easy_claw_tools_adds_browser_tools_and_cleanup(tmp_path, monkeypatch):
    closed = []
    browser_tool = object()

    def fake_build_browser_tools(*, enabled, headless):
        assert enabled is True
        assert headless is True
        return type(
            "FakeToolBundle",
            (),
            {"tools": [browser_tool], "cleanup": (lambda: closed.append("browser"),)},
        )()

    monkeypatch.setattr("easy_claw.agent.toolset.build_browser_tools", fake_build_browser_tools)

    bundle = build_easy_claw_tools(
        ToolContext(
            workspace_path=tmp_path,
            cwd=tmp_path,
            browser_enabled=True,
            browser_headless=True,
        )
    )

    assert browser_tool in bundle.tools
    assert len(bundle.cleanup) == 1

    bundle.close()

    assert closed == ["browser"]
