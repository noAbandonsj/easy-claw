from __future__ import annotations

from langchain.agents.middleware import ModelCallLimitMiddleware, ToolCallLimitMiddleware

from easy_claw.defaults import DEFAULT_MAX_MODEL_CALLS, DEFAULT_MAX_TOOL_CALLS


def build_agent_middleware(
    *,
    max_model_calls: int | None = DEFAULT_MAX_MODEL_CALLS,
    max_tool_calls: int | None = DEFAULT_MAX_TOOL_CALLS,
) -> tuple[object, ...]:
    middleware: list[object] = []
    if max_model_calls is not None:
        middleware.append(ModelCallLimitMiddleware(run_limit=max_model_calls))
    if max_tool_calls is not None:
        middleware.append(ToolCallLimitMiddleware(run_limit=max_tool_calls))
    return tuple(middleware)
