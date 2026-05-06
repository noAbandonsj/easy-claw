from __future__ import annotations

import asyncio
import threading
from collections.abc import Coroutine
from typing import Any


class ToolExecutionError(RuntimeError):
    """本地工具无法完成请求时抛出。"""


class _BackgroundEventLoop:
    """带独立 asyncio 事件循环的后台线程。

    浏览器启动、工具 _arun 和清理等异步操作都在同一个循环和线程中执行，
    避免在 FastAPI 等已运行事件循环内调用 ``asyncio.run()`` 导致崩溃。
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
        """把协程提交到后台循环，并阻塞等待完成。"""
        if self._loop.is_closed():
            raise RuntimeError("后台事件循环已关闭")
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result()

    def call_soon(self, callback: Any, *args: Any) -> None:
        """在后台循环上调度回调，不等待结果。"""
        self._loop.call_soon_threadsafe(callback, *args)

    def shutdown(self) -> None:
        """停止后台事件循环并等待线程退出。"""
        if self._loop.is_closed():
            return
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=10)
        self._loop.close()


_background_loop: _BackgroundEventLoop | None = None


def get_background_loop() -> _BackgroundEventLoop:
    """返回共享后台事件循环，首次调用时创建。"""
    global _background_loop
    if _background_loop is None or _background_loop._loop.is_closed():
        _background_loop = _BackgroundEventLoop()
    return _background_loop
