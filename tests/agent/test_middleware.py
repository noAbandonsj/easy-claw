from langchain.agents.middleware import (
    FilesystemFileSearchMiddleware,
    HumanInTheLoopMiddleware,
    ModelCallLimitMiddleware,
    TodoListMiddleware,
    ToolCallLimitMiddleware,
)

from easy_claw.agent.middleware import build_agent_middleware


def test_build_agent_middleware_uses_default_call_limits():
    middleware = build_agent_middleware()

    assert len(middleware) == 3
    assert isinstance(middleware[0], ModelCallLimitMiddleware)
    assert middleware[0].run_limit == 80
    assert isinstance(middleware[1], ToolCallLimitMiddleware)
    assert middleware[1].run_limit == 200
    assert isinstance(middleware[2], TodoListMiddleware)


def test_build_agent_middleware_can_disable_limits():
    middleware = build_agent_middleware(max_model_calls=None, max_tool_calls=None)
    assert len(middleware) == 1
    assert isinstance(middleware[0], TodoListMiddleware)


def test_build_agent_middleware_adds_human_in_the_loop_when_interrupts_enabled():
    middleware = build_agent_middleware(
        max_model_calls=None,
        max_tool_calls=None,
        interrupt_on={"run_command": True},
    )

    assert len(middleware) == 2
    assert isinstance(middleware[0], TodoListMiddleware)
    assert isinstance(middleware[1], HumanInTheLoopMiddleware)


def test_build_agent_middleware_adds_filesystem_search_when_workspace_provided():
    middleware = build_agent_middleware(
        max_model_calls=None,
        max_tool_calls=None,
        workspace_path="/tmp/test",
    )

    assert len(middleware) == 2
    assert isinstance(middleware[0], FilesystemFileSearchMiddleware)
    assert isinstance(middleware[1], TodoListMiddleware)
