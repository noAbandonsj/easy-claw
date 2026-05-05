import pytest

from easy_claw.tools.base import ToolExecutionError
from easy_claw.tools.mcp import build_mcp_tools


class TestBuildMcpToolsDisabled:
    def test_returns_empty_bundle_when_disabled(self):
        bundle = build_mcp_tools(enabled=False, config_path="nonexistent.json")
        assert bundle.tools == []
        assert bundle.cleanup == ()
        assert bundle.interrupt_on == {}


class TestBuildMcpToolsConfigErrors:
    def test_raises_when_config_file_not_found(self, tmp_path):
        missing = str(tmp_path / "nonexistent.json")
        with pytest.raises(ToolExecutionError, match="MCP config file not found"):
            build_mcp_tools(enabled=True, config_path=missing)

    def test_raises_when_config_file_is_invalid_json(self, tmp_path):
        bad_json = tmp_path / "bad.json"
        bad_json.write_text("not json")
        with pytest.raises(ToolExecutionError, match="Invalid JSON"):
            build_mcp_tools(enabled=True, config_path=str(bad_json))

    def test_raises_when_config_file_is_empty_object(self, tmp_path):
        empty = tmp_path / "empty.json"
        empty.write_text("{}")
        with pytest.raises(ToolExecutionError, match="non-empty JSON object"):
            build_mcp_tools(enabled=True, config_path=str(empty))

    def test_raises_when_dependency_not_installed(self, tmp_path, monkeypatch):
        config_file = tmp_path / "servers.json"
        config_file.write_text('{"srv": {"command": "echo", "args": ["hi"], "transport": "stdio"}}')
        monkeypatch.setattr("easy_claw.tools.mcp.MultiServerMCPClient", None)
        with pytest.raises(ToolExecutionError, match="langchain-mcp-adapters"):
            build_mcp_tools(enabled=True, config_path=str(config_file))

    def test_raises_when_config_is_array_not_object(self, tmp_path):
        config_file = tmp_path / "array.json"
        config_file.write_text("[1, 2, 3]")
        with pytest.raises(ToolExecutionError, match="non-empty JSON object"):
            build_mcp_tools(enabled=True, config_path=str(config_file))


class TestBuildMcpToolsSuccess:
    def test_creates_client_and_returns_tools_and_cleanup(self, tmp_path, monkeypatch):
        config_file = tmp_path / "servers.json"
        config_file.write_text('{"srv": {"command": "echo", "args": ["hi"], "transport": "stdio"}}')

        closed = []

        class FakeTool:
            def __init__(self, name):
                self.name = name

        fake_tools = [FakeTool("mcp_srv_tool1"), FakeTool("mcp_srv_tool2")]

        class FakeClient:
            def __init__(self, config):
                self.config = config

            async def get_tools(self):
                return fake_tools

            async def close(self):
                closed.append("mcp_closed")

        monkeypatch.setattr(
            "easy_claw.tools.mcp.MultiServerMCPClient",
            FakeClient,
            raising=False,
        )

        bundle = build_mcp_tools(enabled=True, config_path=str(config_file))

        assert bundle.tools == fake_tools
        assert bundle.interrupt_on == {
            "mcp_srv_tool1": True,
            "mcp_srv_tool2": True,
        }
        assert len(bundle.cleanup) == 1

        bundle.close()
        assert closed == ["mcp_closed"]

    def test_cleanup_handles_client_without_close_method(self, tmp_path, monkeypatch):
        config_file = tmp_path / "servers.json"
        config_file.write_text('{"srv": {"command": "echo", "args": ["hi"], "transport": "stdio"}}')

        class FakeTool:
            def __init__(self, name):
                self.name = name

        class FakeClientNoClose:
            def __init__(self, config):
                pass

            async def get_tools(self):
                return [FakeTool("t1")]

        monkeypatch.setattr(
            "easy_claw.tools.mcp.MultiServerMCPClient",
            FakeClientNoClose,
            raising=False,
        )

        bundle = build_mcp_tools(enabled=True, config_path=str(config_file))
        # Should not raise
        bundle.close()
