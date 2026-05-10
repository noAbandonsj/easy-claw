from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from easy_claw.agent.approvals import ApprovalReviewer, _read_field


@dataclass(frozen=True)
class StreamEvent:
    type: str
    content: str = ""
    tool_name: str | None = None
    tool_args: object | None = None
    tool_result: object | None = None
    thread_id: str | None = None
    usage: dict[str, int] | None = None


def _extract_last_message_info(result: object) -> tuple[str, dict[str, int] | None]:
    """从 agent 调用结果中提取回复内容和用量。"""
    if not isinstance(result, dict):
        return str(result), None

    messages = result.get("messages")
    if not messages:
        return str(result), None

    last_message = messages[-1]
    content = getattr(last_message, "content", None)
    if content is None and isinstance(last_message, dict):
        content = last_message.get("content")

    usage = _usage_from_message(last_message)
    return str(content or ""), usage


def _invoke_with_approval(
    agent: Any,
    input_value: object,
    *,
    config: dict[str, object],
    reviewer: ApprovalReviewer,
) -> object:
    from langgraph.types import Command

    result = agent.invoke(input_value, config)
    while interrupts := _extract_interrupts(result):
        decisions = reviewer.review(interrupts)
        result = agent.invoke(Command(resume={"decisions": decisions}), config)
    return result


def _stream_with_approval(
    agent: Any,
    input_value: object,
    *,
    config: dict[str, object],
    reviewer: ApprovalReviewer,
    thread_id: str,
) -> Iterable[StreamEvent]:
    from langgraph.types import Command

    content = ""
    usage: dict[str, int] | None = None
    next_input = input_value

    while True:
        interrupted = False
        try:
            for stream_item in agent.stream(
                next_input,
                config,
                stream_mode=["messages", "updates"],
                version="v2",
            ):
                mode, payload = _stream_item_payload(stream_item)

                interrupts = _extract_interrupts(payload)
                if interrupts:
                    yield StreamEvent(type="approval_required", thread_id=thread_id)
                    decisions = reviewer.review(interrupts)
                    next_input = Command(resume={"decisions": decisions})
                    interrupted = True
                    break

                if mode == "updates":
                    msg = _last_completed_message(payload)
                    msg_usage = _usage_from_message(msg)
                    if msg_usage is not None:
                        usage = msg_usage
                    # tool_result already emitted via "messages" mode
                else:
                    msg = _message_from_stream_item(stream_item)
                    msg_usage = _usage_from_message(msg)
                    if msg_usage is not None:
                        usage = msg_usage
                    for event in _events_from_message(msg, thread_id=thread_id):
                        if event.type == "token":
                            content += event.content
                        yield event
        except Exception as exc:
            error_content = _format_agent_runtime_error(exc)
            yield StreamEvent(type="error", content=error_content, thread_id=thread_id)
            if content:
                content = f"{content}\n{error_content}"
            else:
                content = error_content
            yield StreamEvent(type="done", content=content, thread_id=thread_id, usage=usage)
            return

        if not interrupted:
            break

    yield StreamEvent(type="done", content=content, thread_id=thread_id, usage=usage)


def _format_agent_runtime_error(exc: Exception) -> str:
    message = str(exc).strip() or exc.__class__.__name__
    return f"Agent 执行失败：{message}"


def _events_from_message(message: object, *, thread_id: str) -> list[StreamEvent]:
    if message is None:
        return []
    events: list[StreamEvent] = []
    events.extend(_tool_call_events_from_message(message, thread_id=thread_id))

    tool_result = _tool_result_event_from_message(message, thread_id=thread_id)
    if tool_result is not None:
        events.append(tool_result)
        return events

    content = _text_from_message(message)
    if content:
        events.append(StreamEvent(type="token", content=content, thread_id=thread_id))
    return events


def _message_from_stream_item(stream_item: object) -> object:
    mode, payload = _stream_item_payload(stream_item)
    if mode == "updates":
        return None
    if isinstance(payload, tuple):
        return payload[0]
    return payload


def _stream_item_payload(stream_item: object) -> tuple[str | None, object]:
    if isinstance(stream_item, dict) and "type" in stream_item:
        return stream_item["type"], stream_item["data"]
    if (
        isinstance(stream_item, tuple)
        and len(stream_item) == 2
        and isinstance(stream_item[0], str)
    ):
        return stream_item[0], stream_item[1]
    return None, stream_item


def _last_completed_message(payload: object) -> object | None:
    if not isinstance(payload, dict):
        return None
    for source in ("model", "tools"):
        update = payload.get(source)
        if isinstance(update, dict):
            messages = update.get("messages")
            if messages:
                return messages[-1]
    return None


def _usage_from_message(message: object) -> dict[str, int] | None:
    usage_metadata = _read_field(message, "usage_metadata")
    usage = _normalize_usage_metadata(usage_metadata)
    if usage is not None:
        return usage

    response_metadata = _read_field(message, "response_metadata")
    if isinstance(response_metadata, dict):
        usage = _normalize_usage_metadata(response_metadata.get("token_usage"))
        if usage is not None:
            return usage
        return _normalize_usage_metadata(response_metadata.get("usage"))
    return None


def _normalize_usage_metadata(value: object) -> dict[str, int] | None:
    if not isinstance(value, dict):
        return None

    input_tokens = _first_int(value, "input_tokens", "prompt_tokens", "input")
    output_tokens = _first_int(value, "output_tokens", "completion_tokens", "output")
    total_tokens = _first_int(value, "total_tokens", "total")
    if input_tokens is None and output_tokens is None and total_tokens is None:
        return None

    input_count = input_tokens or 0
    output_count = output_tokens or 0
    return {
        "input": input_count,
        "output": output_count,
        "total": total_tokens if total_tokens is not None else input_count + output_count,
    }


def _first_int(value: dict[str, object], *keys: str) -> int | None:
    for key in keys:
        raw = value.get(key)
        if isinstance(raw, int):
            return raw
    return None


def _text_from_message(message: object) -> str:
    content = _read_field(message, "content")
    if content is None:
        return ""
    return str(content)


def _tool_call_events_from_message(message: object, *, thread_id: str) -> list[StreamEvent]:
    tool_calls = _read_field(message, "tool_calls") or []
    additional_kwargs = _read_field(message, "additional_kwargs") or {}
    if isinstance(additional_kwargs, dict):
        tool_calls = tool_calls or additional_kwargs.get("tool_calls") or []

    events: list[StreamEvent] = []
    for raw_call in tool_calls:
        name, args = _parse_tool_call(raw_call)
        if name:
            events.append(
                StreamEvent(
                    type="tool_call_start",
                    tool_name=name,
                    tool_args=args,
                    thread_id=thread_id,
                )
            )
    return events


def _tool_result_event_from_message(
    message: object,
    *,
    thread_id: str,
) -> StreamEvent | None:
    role = _read_field(message, "role")
    message_type = _read_field(message, "type")
    tool_call_id = _read_field(message, "tool_call_id")
    if role != "tool" and message_type != "tool" and tool_call_id is None:
        return None

    content = _text_from_message(message)
    name = _read_field(message, "name") or _read_field(message, "tool_name") or "工具"
    return StreamEvent(
        type="tool_call_result",
        content=content,
        tool_name=str(name),
        tool_result=content,
        thread_id=thread_id,
    )


def _parse_tool_call(raw_call: object) -> tuple[str | None, object | None]:
    if isinstance(raw_call, dict):
        name = raw_call.get("name")
        args = raw_call.get("args")
        function = raw_call.get("function")
        if isinstance(function, dict):
            name = name or function.get("name")
            args = args if args is not None else function.get("arguments")
        return str(name) if name else None, _parse_tool_args(args)

    name = _read_field(raw_call, "name")
    args = _read_field(raw_call, "args")
    return str(name) if name else None, _parse_tool_args(args)


def _parse_tool_args(args: object) -> object | None:
    if not isinstance(args, str):
        return args
    try:
        return json.loads(args)
    except json.JSONDecodeError:
        return args


def _extract_interrupts(result: object) -> tuple[object, ...]:
    if not isinstance(result, dict):
        return ()
    interrupts = result.get("__interrupt__")
    if not interrupts:
        return ()
    return tuple(interrupts)
