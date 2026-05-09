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

    names = {tool.name for tool in bundle.tools}
    assert names == {
        "search_web",
        "run_command",
        "run_python",
        "read_document",
        "read_file",
        "write_file",
        "list_directory",
        "file_delete",
        "file_search",
        "copy_file",
        "move_file",
        "edit_file",
    }
    assert bundle.interrupt_on["run_command"] is True
    assert bundle.interrupt_on["run_python"] is True
    assert bundle.interrupt_on["write_file"] is True
    assert bundle.interrupt_on["file_delete"] is True
    assert bundle.interrupt_on["edit_file"] is True
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
            {
                "tools": [browser_tool],
                "cleanup": (lambda: closed.append("browser"),),
                "interrupt_on": {"browser_navigate": True},
            },
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
    assert bundle.interrupt_on["browser_navigate"] is True
    assert len(bundle.cleanup) == 1

    bundle.close()

    assert closed == ["browser"]


def test_build_easy_claw_tools_adds_mcp_tools_and_cleanup(tmp_path, monkeypatch):
    closed = []
    mcp_tool = object()

    def fake_build_mcp_tools(*, enabled, config_path):
        assert enabled is True
        assert config_path == "mcp_servers.json"
        return type(
            "FakeToolBundle",
            (),
            {
                "tools": [mcp_tool],
                "cleanup": (lambda: closed.append("mcp"),),
                "interrupt_on": {"mcp_external_tool": True},
            },
        )()

    monkeypatch.setattr("easy_claw.agent.toolset.build_mcp_tools", fake_build_mcp_tools)

    bundle = build_easy_claw_tools(
        ToolContext(
            workspace_path=tmp_path,
            cwd=tmp_path,
            browser_enabled=False,
            browser_headless=False,
            mcp_enabled=True,
            mcp_config_path="mcp_servers.json",
        )
    )

    assert mcp_tool in bundle.tools
    assert bundle.interrupt_on["mcp_external_tool"] is True
    assert len(bundle.cleanup) == 1

    bundle.close()

    assert closed == ["mcp"]


def test_build_easy_claw_tools_passes_mcp_auto_mode(tmp_path, monkeypatch):
    def fake_build_mcp_tools(*, enabled, config_path):
        assert enabled == "auto"
        assert config_path == "mcp_servers.json"
        return type(
            "FakeToolBundle",
            (),
            {
                "tools": [],
                "cleanup": (),
                "interrupt_on": {},
            },
        )()

    monkeypatch.setattr("easy_claw.agent.toolset.build_mcp_tools", fake_build_mcp_tools)

    build_easy_claw_tools(
        ToolContext(
            workspace_path=tmp_path,
            cwd=tmp_path,
            browser_enabled=False,
            browser_headless=False,
            mcp_mode="auto",
            mcp_config_path="mcp_servers.json",
        )
    )
