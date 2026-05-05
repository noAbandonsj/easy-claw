from __future__ import annotations

import asyncio
import threading
from collections.abc import Coroutine
from typing import Any


class ToolExecutionError(RuntimeError):
    """Raised when a local tool cannot complete the requested operation."""


class _BackgroundEventLoop:
    """A dedicated background thread with its own asyncio event loop.

    All async operations (browser launch, tool _arun, cleanup) run on the
    same loop/thread, avoiding ``asyncio.run()`` which crashes when called
    from inside an already-running loop (e.g. FastAPI).
    """

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._loop.run_forever,
            daemon=True,
            name="easy-claw-async-tools",
        )
        self._thread.start()

    def run_coroutine(self, coro: Coroutine[Any, Any, Any]) -> Any:
        """Submit *coro* to the background loop and block until it completes."""
        if self._loop.is_closed():
            raise RuntimeError("Background event loop is closed")
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result()

    def call_soon(self, callback: Any, *args: Any) -> None:
        """Schedule a callback on the background loop (fire-and-forget)."""
        self._loop.call_soon_threadsafe(callback, *args)

    def shutdown(self) -> None:
        """Stop the background loop and join the thread."""
        if self._loop.is_closed():
            return
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=10)
        self._loop.close()


_background_loop: _BackgroundEventLoop | None = None


def get_background_loop() -> _BackgroundEventLoop:
    """Return (creating on first call) the shared background event loop."""
    global _background_loop
    if _background_loop is None or _background_loop._loop.is_closed():
        _background_loop = _BackgroundEventLoop()
    return _background_loop
