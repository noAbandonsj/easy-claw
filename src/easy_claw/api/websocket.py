from __future__ import annotations

from collections.abc import Iterator

from easy_claw.agent.streaming import StreamEvent


def event_to_dict(event: StreamEvent) -> dict[str, object]:
    msg: dict[str, object] = {"type": event.type}
    if event.content:
        msg["content"] = event.content
    if event.tool_name:
        msg["tool_name"] = event.tool_name
    if event.tool_args is not None:
        msg["tool_args"] = event.tool_args
    if event.tool_result is not None:
        msg["tool_result"] = event.tool_result
    if event.usage:
        msg["usage"] = event.usage
    return msg


def next_stream_event_or_none(stream_iter: Iterator[StreamEvent]) -> StreamEvent | None:
    try:
        return next(stream_iter)
    except StopIteration:
        return None
