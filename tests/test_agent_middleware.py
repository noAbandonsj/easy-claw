from langchain.agents.middleware import (
    HumanInTheLoopMiddleware,
    ModelCallLimitMiddleware,
    ToolCallLimitMiddleware,
)

from easy_claw.agent.middleware import build_agent_middleware


def test_build_agent_middleware_uses_default_call_limits():
    middleware = build_agent_middleware()

    assert len(middleware) == 2
    assert isinstance(middleware[0], ModelCallLimitMiddleware)
    assert middleware[0].run_limit == 40
    assert isinstance(middleware[1], ToolCallLimitMiddleware)
    assert middleware[1].run_limit == 100


def test_build_agent_middleware_can_disable_limits():
    assert build_agent_middleware(max_model_calls=None, max_tool_calls=None) == ()


def test_build_agent_middleware_adds_human_in_the_loop_when_interrupts_enabled():
    middleware = build_agent_middleware(
        max_model_calls=None,
        max_tool_calls=None,
        interrupt_on={"run_command": True},
    )

    assert len(middleware) == 1
    assert isinstance(middleware[0], HumanInTheLoopMiddleware)
