import threading
from io import StringIO
from unittest import mock

from rich.console import Console

from easy_claw.agent.streaming import StreamEvent


def test_watch_esc_key_detects_escape_and_sets_cancel_event():
    """用 mock msvcrt 测试按键监听函数。"""
    cancel_event = threading.Event()
    stopped = threading.Event()

    kbhit_results = [True]
    getch_results = [b'\x1b']

    def fake_kbhit():
        return kbhit_results.pop(0) if kbhit_results else False

    def fake_getch():
        return getch_results.pop(0) if getch_results else b'\x00'

    with mock.patch('msvcrt.kbhit', fake_kbhit), \
         mock.patch('msvcrt.getch', fake_getch):
        from easy_claw.cli.interactive import _watch_esc_key
        _watch_esc_key(cancel_event, stopped)

    assert cancel_event.is_set()


def test_watch_esc_key_exits_when_stopped():
    """stopped 事件设置后监听线程退出。"""
    cancel_event = threading.Event()
    stopped = threading.Event()
    stopped.set()

    def fake_kbhit():
        raise AssertionError("should not be called when stopped")

    with mock.patch('msvcrt.kbhit', fake_kbhit):
        from easy_claw.cli.interactive import _watch_esc_key
        _watch_esc_key(cancel_event, stopped)

    assert not cancel_event.is_set()


def test_watch_esc_key_does_not_read_input_while_paused():
    """审批输入期间暂停 Esc 监听，避免后台线程吞掉 yes/no 按键。"""
    cancel_event = threading.Event()
    paused = threading.Event()
    paused.set()

    class FakeStopped:
        def __init__(self):
            self.calls = 0

        def wait(self, timeout):
            self.calls += 1
            return self.calls > 1

    def fake_kbhit():
        raise AssertionError("should not read console input while paused")

    with mock.patch('msvcrt.kbhit', fake_kbhit):
        from easy_claw.cli.interactive import _watch_esc_key
        _watch_esc_key(cancel_event, FakeStopped(), paused)

    assert not cancel_event.is_set()


def test_render_streaming_turn_handles_interrupted_event(monkeypatch):
    """_render_streaming_turn 收到 interrupted 事件后打印提示。"""
    output = StringIO()
    test_console = Console(
        file=output, force_terminal=False, color_system=None, width=100
    )
    monkeypatch.setattr("easy_claw.cli.interactive.console", test_console)

    from easy_claw.cli.interactive import _render_streaming_turn

    response, usage = _render_streaming_turn(
        iter(
            [
                StreamEvent(type="token", content="hello "),
                StreamEvent(type="interrupted", thread_id="thread-1"),
                StreamEvent(type="done", content="hello ", thread_id="thread-1"),
            ]
        )
    )

    rendered = output.getvalue()
    assert "hello " in rendered
    assert "已打断" in rendered
    assert response == "hello "
    assert usage is None


def test_render_streaming_turn_returns_partial_content_on_interrupted():
    """interrupted 事件后 _render_streaming_turn 返回已累积的 tokens。"""
    from easy_claw.cli.interactive import _render_streaming_turn

    response, usage = _render_streaming_turn(
        iter(
            [
                StreamEvent(type="token", content="part1 "),
                StreamEvent(type="token", content="part2 "),
                StreamEvent(type="interrupted", thread_id="thread-1"),
                StreamEvent(type="done", content="part1 part2 ", thread_id="thread-1"),
            ]
        )
    )

    assert response == "part1 part2 "
    assert usage is None
