from __future__ import annotations

from langchain.agents.middleware import (
    HumanInTheLoopMiddleware,
    ModelCallLimitMiddleware,
    SummarizationMiddleware,
    TodoListMiddleware,
    ToolCallLimitMiddleware,
)

from easy_claw.defaults import DEFAULT_MAX_MODEL_CALLS, DEFAULT_MAX_TOOL_CALLS


def build_agent_middleware(
    *,
    max_model_calls: int | None = DEFAULT_MAX_MODEL_CALLS,
    max_tool_calls: int | None = DEFAULT_MAX_TOOL_CALLS,
    interrupt_on: dict[str, object] | None = None,
    summarization_model: object | None = None,
) -> tuple[object, ...]:
    middleware: list[object] = []
    if max_model_calls is not None:
        middleware.append(ModelCallLimitMiddleware(run_limit=max_model_calls))
    if max_tool_calls is not None:
        middleware.append(ToolCallLimitMiddleware(run_limit=max_tool_calls))
    middleware.append(TodoListMiddleware())
    if interrupt_on:
        middleware.append(HumanInTheLoopMiddleware(interrupt_on=interrupt_on))
    if summarization_model is not None:
        middleware.append(
            SummarizationMiddleware(
                model=summarization_model,
                trigger=("tokens", 640000),
                keep=("messages", 10),
            )
        )
    return tuple(middleware)
