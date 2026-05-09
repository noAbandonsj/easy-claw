from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from easy_claw.agent.runtime import AgentRequest, AgentResult, StreamEvent


class AgentSession(Protocol):
    def run(self, prompt: str) -> AgentResult: ...

    def stream(self, prompt: str) -> Iterable[StreamEvent]: ...

    def close(self) -> None: ...


class AgentRuntime(Protocol):
    def run(self, request: AgentRequest) -> AgentResult: ...

    def open_session(self, request: AgentRequest) -> AgentSession: ...
