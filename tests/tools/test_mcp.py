from pathlib import Path

import pytest
from langchain_core.tools import StructuredTool, ToolException

from easy_claw.tools.base import ToolExecutionError
from easy_claw.tools.mcp import _read_servers_config, build_mcp_tools


def test_default_example_config_contains_default_mcp_servers(monkeypatch):
    monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", "ghp_test")
    monkeypatch.setenv("AMAP_MAPS_API_KEY", "amap_test")

    config = _read_servers_config(Path("mcp_servers.json.example"), auto_mode=False)

    assert set(config) == {"basic-memory", "git", "github", "amap-maps"}
    assert config["basic-memory"]["transport"] == "stdio"
    assert config["basic-memory"]["args"] == [
        "basic-memory",
        "mcp",
        "--project",
        "easy-claw",
    ]
    assert config["git"]["transport"] == "stdio"
    assert config["git"]["args"] == [
        "mcp-server-git",
        "--repository",
        ".",
    ]
    assert config["github"]["transport"] == "http"
    assert config["github"]["url"] == "https://api.githubcopilot.com/mcp/"
    assert config["github"]["headers"]["Authorization"] == "Bearer ghp_test"
    assert config["amap-maps"]["transport"] == "stdio"
    assert config["amap-maps"]["args"] == ["-y", "@amap/amap-maps-mcp-server"]
    assert config["amap-maps"]["env"]["AMAP_MAPS_API_KEY"] == "amap_test"


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

    def test_auto_skips_server_when_required_environment_variable_is_missing(
        self,
        tmp_path,
        monkeypatch,
    ):
        monkeypatch.delenv("TOKEN", raising=False)
        config_file = tmp_path / "servers.json"
        config_file.write_text(
            '{"plain": {"command": "echo", "args": ["ok"], "transport": "stdio"}, '
            '"secret": {"command": "echo", "args": ["${TOKEN}"], "transport": "stdio"}}'
        )

        with pytest.warns(RuntimeWarning, match="缺少环境变量 TOKEN"):
            config = _read_servers_config(config_file, auto_mode=True)

        assert set(config) == {"plain"}

    def test_enabled_raises_when_required_environment_variable_is_missing(
        self,
        tmp_path,
        monkeypatch,
    ):
        monkeypatch.delenv("TOKEN", raising=False)
        config_file = tmp_path / "servers.json"
        config_file.write_text(
            '{"secret": {"command": "echo", "args": ["${TOKEN}"], "transport": "stdio"}}'
        )

        with pytest.raises(ToolExecutionError, match="缺少环境变量 TOKEN"):
            _read_servers_config(config_file, auto_mode=False)


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

            async def get_tools(self, server_name=None):
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

            async def get_tools(self, server_name=None):
                return fake_tools

            async def close(self):
                closed.append("mcp_closed")

        monkeypatch.setattr(
            "easy_claw.tools.mcp.MultiServerMCPClient",
            FakeClient,
            raising=False,
        )

        bundle = build_mcp_tools(enabled=True, config_path=str(config_file))

        assert [t.name for t in bundle.tools] == [
            "mcp__srv__mcp_srv_tool1",
            "mcp__srv__mcp_srv_tool2",
        ]
        assert bundle.interrupt_on == {
            "mcp__srv__mcp_srv_tool1": True,
            "mcp__srv__mcp_srv_tool2": True,
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

            async def get_tools(self, server_name=None):
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

            async def get_tools(self, server_name=None):
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

        assert [t.name for t in bundle.tools] == ["mcp__good__good_tool"]
        assert bundle.interrupt_on == {"mcp__good__good_tool": True}

    def test_wraps_async_only_mcp_tools_for_sync_agent_invocation(self, tmp_path, monkeypatch):
        config_file = tmp_path / "servers.json"
        config_file.write_text('{"amap": {"command": "npx", "args": [], "transport": "stdio"}}')

        async def lookup(city: str) -> str:
            return f"{city} ok"

        async_only_tool = StructuredTool.from_function(
            coroutine=lookup,
            name="maps_weather",
            description="天气查询",
        )

        class FakeClient:
            def __init__(self, config):
                pass

            async def get_tools(self, server_name=None):
                return [async_only_tool]

            async def close(self):
                pass

        monkeypatch.setattr(
            "easy_claw.tools.mcp.MultiServerMCPClient",
            FakeClient,
            raising=False,
        )

        bundle = build_mcp_tools(enabled=True, config_path=str(config_file))

        assert bundle.tools[0].name == "mcp__amap__maps_weather"
        assert bundle.tools[0].invoke({"city": "上海"}) == "上海 ok"

    def test_mcp_tool_exception_returns_tool_result_instead_of_raising(
        self,
        tmp_path,
        monkeypatch,
    ):
        config_file = tmp_path / "servers.json"
        config_file.write_text('{"srv": {"command": "npx", "args": [], "transport": "stdio"}}')

        async def fail_lookup(city: str) -> str:
            """查询天气。"""
            raise ToolException("远端 MCP 服务拒绝调用")

        failing_tool = StructuredTool.from_function(
            coroutine=fail_lookup,
            name="maps_weather",
            description="天气查询",
        )

        class FakeClient:
            def __init__(self, config):
                pass

            async def get_tools(self, server_name=None):
                return [failing_tool]

            async def close(self):
                pass

        monkeypatch.setattr(
            "easy_claw.tools.mcp.MultiServerMCPClient",
            FakeClient,
            raising=False,
        )

        bundle = build_mcp_tools(enabled=True, config_path=str(config_file))

        assert "远端 MCP 服务拒绝调用" in bundle.tools[0].invoke({"city": "上海"})

    def test_mcp_runtime_exception_returns_tool_result_instead_of_raising(
        self,
        tmp_path,
        monkeypatch,
    ):
        config_file = tmp_path / "servers.json"
        config_file.write_text('{"srv": {"command": "npx", "args": [], "transport": "stdio"}}')

        async def fail_lookup(city: str) -> str:
            """查询天气。"""
            raise RuntimeError("connection closed")

        failing_tool = StructuredTool.from_function(
            coroutine=fail_lookup,
            name="maps_weather",
            description="天气查询",
        )

        class FakeClient:
            def __init__(self, config):
                pass

            async def get_tools(self, server_name=None):
                return [failing_tool]

            async def close(self):
                pass

        monkeypatch.setattr(
            "easy_claw.tools.mcp.MultiServerMCPClient",
            FakeClient,
            raising=False,
        )

        bundle = build_mcp_tools(enabled=True, config_path=str(config_file))

        result = bundle.tools[0].invoke({"city": "上海"})

        assert "MCP 工具 'mcp__srv__maps_weather' 调用失败" in result
        assert "connection closed" in result
