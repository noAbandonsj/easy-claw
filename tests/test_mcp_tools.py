from pathlib import Path

import pytest

from easy_claw.tools.base import ToolExecutionError
from easy_claw.tools.mcp import _read_servers_config, build_mcp_tools


def test_default_example_config_contains_only_basic_memory_server():
    config = _read_servers_config(Path("mcp_servers.json.example"), auto_mode=False)

    assert set(config) == {"basic-memory"}
    assert config["basic-memory"]["transport"] == "stdio"
    assert config["basic-memory"]["args"] == [
        "basic-memory",
        "mcp",
        "--project",
        "easy-claw",
    ]


class TestBuildMcpToolsDisabled:
    def test_returns_empty_bundle_when_disabled(self):
        bundle = build_mcp_tools(enabled=False, config_path="nonexistent.json")
        assert bundle.tools == []
        assert bundle.cleanup == ()
        assert bundle.interrupt_on == {}

    def test_auto_returns_empty_bundle_when_config_file_is_missing(self, tmp_path):
        missing = str(tmp_path / "nonexistent.json")

        bundle = build_mcp_tools(enabled="auto", config_path=missing)

        assert bundle.tools == []
        assert bundle.cleanup == ()
        assert bundle.interrupt_on == {}


class TestBuildMcpToolsConfigErrors:
    def test_raises_when_config_file_not_found(self, tmp_path):
        missing = str(tmp_path / "nonexistent.json")
        with pytest.raises(ToolExecutionError, match="未找到 MCP 配置文件"):
            build_mcp_tools(enabled=True, config_path=missing)

    def test_raises_when_config_file_is_invalid_json(self, tmp_path):
        bad_json = tmp_path / "bad.json"
        bad_json.write_text("not json")
        with pytest.raises(ToolExecutionError, match="JSON 无效"):
            build_mcp_tools(enabled=True, config_path=str(bad_json))

    def test_raises_when_config_file_is_empty_object(self, tmp_path):
        empty = tmp_path / "empty.json"
        empty.write_text("{}")
        with pytest.raises(ToolExecutionError, match="非空 JSON 对象"):
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
        with pytest.raises(ToolExecutionError, match="非空 JSON 对象"):
            build_mcp_tools(enabled=True, config_path=str(config_file))

    def test_auto_warns_and_returns_empty_for_invalid_json(self, tmp_path):
        config_file = tmp_path / "bad.json"
        config_file.write_text("not json")

        with pytest.warns(RuntimeWarning, match="MCP auto 模式已关闭"):
            bundle = build_mcp_tools(enabled="auto", config_path=str(config_file))

        assert bundle.tools == []
        assert bundle.cleanup == ()
        assert bundle.interrupt_on == {}


class TestBuildMcpToolsSuccess:
    def test_ignores_metadata_keys_in_server_config(self, tmp_path, monkeypatch):
        config_file = tmp_path / "servers.json"
        config_file.write_text(
            '{"_comment": "copy and edit", "srv": {"command": "echo", '
            '"args": ["hi"], "transport": "stdio"}}'
        )

        class FakeClient:
            def __init__(self, config):
                assert config == {
                    "srv": {
                        "command": "echo",
                        "args": ["hi"],
                        "transport": "stdio",
                    }
                }

            async def get_tools(self):
                return []

        monkeypatch.setattr(
            "easy_claw.tools.mcp.MultiServerMCPClient",
            FakeClient,
            raising=False,
        )

        bundle = build_mcp_tools(enabled=True, config_path=str(config_file))

        assert bundle.tools == []

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

    def test_enabled_wraps_client_loading_errors(self, tmp_path, monkeypatch):
        config_file = tmp_path / "servers.json"
        config_file.write_text('{"srv": {"command": "echo", "args": ["hi"], "transport": "stdio"}}')

        class FakeClient:
            def __init__(self, config):
                pass

            async def get_tools(self):
                raise ValueError("server failed")

        monkeypatch.setattr(
            "easy_claw.tools.mcp.MultiServerMCPClient",
            FakeClient,
            raising=False,
        )

        with pytest.raises(ToolExecutionError, match="加载 MCP 工具失败"):
            build_mcp_tools(enabled=True, config_path=str(config_file))

    def test_auto_skips_failed_servers_and_keeps_working_tools(self, tmp_path, monkeypatch):
        config_file = tmp_path / "servers.json"
        config_file.write_text(
            '{"bad": {"command": "bad", "args": [], "transport": "stdio"}, '
            '"good": {"command": "good", "args": [], "transport": "stdio"}}'
        )

        class FakeTool:
            def __init__(self, name):
                self.name = name

        good_tool = FakeTool("good_tool")

        class FakeClient:
            def __init__(self, config):
                self.config = config

            async def get_tools(self, *, server_name=None):
                if server_name == "bad":
                    raise ValueError("bad failed")
                if server_name == "good":
                    return [good_tool]
                raise AssertionError("auto mode should load servers individually")

            async def close(self):
                pass

        monkeypatch.setattr(
            "easy_claw.tools.mcp.MultiServerMCPClient",
            FakeClient,
            raising=False,
        )

        with pytest.warns(RuntimeWarning, match="bad"):
            bundle = build_mcp_tools(enabled="auto", config_path=str(config_file))

        assert bundle.tools == [good_tool]
        assert bundle.interrupt_on == {"good_tool": True}
