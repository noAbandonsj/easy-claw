# CLI 流式打断功能 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** CLI 终端聊天中按 Esc 键打断 agent 流式输出，保留已生成内容并返回输入提示符。

**Architecture:** `threading.Event` 作为取消信号，后台线程用 `msvcrt` 监听 Esc 键，`_stream_with_approval()` 在每次迭代时检查信号，检测到取消时 yield `interrupted` 事件，CLI 渲染循环处理该事件后退出流式循环。

**Tech Stack:** Python `threading`, `msvcrt` (标准库), LangGraph streaming

---

### Task 1: streaming.py — _stream_with_approval 支持 cancel_event

**Files:**
- Modify: `src/easy_claw/agent/streaming.py:56-117`
- Test: `tests/agent/test_runtime.py` (追加测试)

- [ ] **Step 1: 编写 _stream_with_approval 取消测试**

在 `tests/agent/test_runtime.py` 末尾追加：

```python
import threading


class FakeStreamingCancelAgent:
    """模拟一个可以在迭代中被取消的流式 agent。"""

    def __init__(self):
        self.inputs = []

    def stream(self, input_value, config, stream_mode, version=None):
        self.inputs.append(input_value)
        yield FakeStreamMessage("hello ")
        yield FakeStreamMessage("world")


def test_stream_with_approval_yields_interrupted_when_cancel_event_set():
    from easy_claw.agent.streaming import _stream_with_approval

    agent = FakeStreamingCancelAgent()
    cancel_event = threading.Event()
    cancel_event.set()  # 预先设置，模拟立即取消

    events = list(
        _stream_with_approval(
            agent,
            {"messages": [{"role": "user", "content": "hello"}]},
            config={"configurable": {"thread_id": "thread-1"}},
            reviewer=StaticApprovalReviewer(approve=True),
            thread_id="thread-1",
            cancel_event=cancel_event,
        )
    )

    # while 循环顶部检查到 cancel_event 已设置，直接 break
    # 不会进入 for 循环迭代，所以 events 只包含 done
    assert events == [
        StreamEvent(type="done", content="", thread_id="thread-1"),
    ]


def test_stream_with_approval_works_normally_without_cancel_event():
    from easy_claw.agent.streaming import _stream_with_approval

    agent = FakeStreamingCancelAgent()

    events = list(
        _stream_with_approval(
            agent,
            {"messages": [{"role": "user", "content": "hello"}]},
            config={"configurable": {"thread_id": "thread-1"}},
            reviewer=StaticApprovalReviewer(approve=True),
            thread_id="thread-1",
        )
    )

    assert events == [
        StreamEvent(type="token", content="hello ", thread_id="thread-1"),
        StreamEvent(type="token", content="world", thread_id="thread-1"),
        StreamEvent(type="done", content="hello world", thread_id="thread-1"),
    ]


class FakeMidStreamCancelAgent:
    """先产出一些 token，然后可以被取消。"""

    def __init__(self):
        self.cancel_checkpoint = None

    def stream(self, input_value, config, stream_mode, version=None):
        yield FakeStreamMessage("first ")
        # 返回 control 给调用者，让它有机会 set cancel_event
        yield FakeStreamMessage("second")


def test_stream_with_approval_cancel_during_stream_preserves_partial_content():
    from easy_claw.agent.streaming import _stream_with_approval

    agent = FakeMidStreamCancelAgent()
    cancel_event = threading.Event()
    events_collected = []

    # 手动模拟 _stream_with_approval 的循环：
    # 创建一个在第一次 yield 后设置 cancel_event 的包装迭代器
    stream_iter = _stream_with_approval(
        agent,
        {"messages": [{"role": "user", "content": "hello"}]},
        config={"configurable": {"thread_id": "thread-1"}},
        reviewer=StaticApprovalReviewer(approve=True),
        thread_id="thread-1",
        cancel_event=cancel_event,
    )

    # 取第一个事件，然后设置取消信号
    first = next(stream_iter)
    events_collected.append(first)
    cancel_event.set()
    # 取剩余事件
    for event in stream_iter:
        events_collected.append(event)

    # 应该看到 interrupted 事件，保留部分内容
    types = [e.type for e in events_collected]
    assert "interrupted" in types
    # done 事件中的 content 是已累积的部分内容
    assert events_collected[-1].type == "done"
```

- [ ] **Step 2: 运行测试确认失败**

```powershell
uv run pytest tests/agent/test_runtime.py::test_stream_with_approval_yields_interrupted_when_cancel_event_set -v
```

预期：`TypeError: _stream_with_approval() got an unexpected keyword argument 'cancel_event'`

- [ ] **Step 3: 修改 _stream_with_approval 签名和逻辑**

在 `src/easy_claw/agent/streaming.py` 顶部添加 `import threading`，修改 `_stream_with_approval`：

```python
import threading

# ... 在 _stream_with_approval 函数中：

def _stream_with_approval(
    agent: Any,
    input_value: object,
    *,
    config: dict[str, object],
    reviewer: ApprovalReviewer,
    thread_id: str,
    cancel_event: threading.Event | None = None,
) -> Iterable[StreamEvent]:
    from langgraph.types import Command

    content = ""
    usage: dict[str, int] | None = None
    next_input = input_value

    while True:
        if cancel_event and cancel_event.is_set():
            break
        interrupted = False
        try:
            for stream_item in agent.stream(
                next_input,
                config,
                stream_mode=["messages", "updates"],
                version="v2",
            ):
                if cancel_event and cancel_event.is_set():
                    yield StreamEvent(type="interrupted", thread_id=thread_id)
                    break

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

        if interrupted:
            continue
        break

    yield StreamEvent(type="done", content=content, thread_id=thread_id, usage=usage)
```

关键是三处新增：
1. 参数 `cancel_event: threading.Event | None = None`
2. while 循环顶部 `if cancel_event and cancel_event.is_set(): break`
3. for 循环内部 `if cancel_event and cancel_event.is_set(): yield StreamEvent(type="interrupted", ...); break`

- [ ] **Step 4: 运行测试确认通过**

```powershell
uv run pytest tests/agent/test_runtime.py::test_stream_with_approval_yields_interrupted_when_cancel_event_set tests/agent/test_runtime.py::test_stream_with_approval_works_normally_without_cancel_event tests/agent/test_runtime.py::test_stream_with_approval_cancel_during_stream_preserves_partial_content -v
```

- [ ] **Step 5: 运行全部已有测试确认无回归**

```powershell
uv run pytest tests/agent/test_runtime.py -v
```

- [ ] **Step 6: 提交**

```bash
git add src/easy_claw/agent/streaming.py tests/agent/test_runtime.py
git commit -m "feat: add cancel_event support to _stream_with_approval"
```

---

### Task 2: langchain_runtime.py — Session.stream 透传 cancel_event

**Files:**
- Modify: `src/easy_claw/agent/langchain_runtime.py:181-188`
- Test: `tests/agent/test_runtime.py` (追加测试)

- [ ] **Step 1: 编写 Session.stream 取消透传测试**

在 `tests/agent/test_runtime.py` 末尾追加：

```python
def test_session_stream_passes_cancel_event_to_underlying_function(monkeypatch):
    captured_cancel = {}

    def fake_stream_with_approval(agent, input_value, *, config, reviewer, thread_id,
                                  cancel_event=None):
        captured_cancel["event"] = cancel_event
        yield StreamEvent(type="token", content="ok", thread_id=thread_id)
        yield StreamEvent(type="done", content="ok", thread_id=thread_id)

    monkeypatch.setattr(
        "easy_claw.agent.langchain_runtime._stream_with_approval",
        fake_stream_with_approval,
    )

    cancel_event = threading.Event()
    session = LangChainAgentSession(
        agent=FakeStreamingAgent(),
        thread_id="thread-1",
        reviewer=StaticApprovalReviewer(approve=True),
        exit_stack=ExitStack(),
    )

    list(session.stream("hello", cancel_event=cancel_event))

    assert captured_cancel["event"] is cancel_event


def test_session_stream_works_without_cancel_event(monkeypatch):
    captured_cancel = {}

    def fake_stream_with_approval(agent, input_value, *, config, reviewer, thread_id,
                                  cancel_event=None):
        captured_cancel["event"] = cancel_event
        yield StreamEvent(type="token", content="ok", thread_id=thread_id)
        yield StreamEvent(type="done", content="ok", thread_id=thread_id)

    monkeypatch.setattr(
        "easy_claw.agent.langchain_runtime._stream_with_approval",
        fake_stream_with_approval,
    )

    session = LangChainAgentSession(
        agent=FakeStreamingAgent(),
        thread_id="thread-1",
        reviewer=StaticApprovalReviewer(approve=True),
        exit_stack=ExitStack(),
    )

    list(session.stream("hello"))

    assert captured_cancel["event"] is None
```

- [ ] **Step 2: 运行测试确认失败**

```powershell
uv run pytest tests/agent/test_runtime.py::test_session_stream_passes_cancel_event_to_underlying_function -v
```

预期：`TypeError: LangChainAgentSession.stream() got an unexpected keyword argument 'cancel_event'`

- [ ] **Step 3: 修改 LangChainAgentSession.stream**

在 `src/easy_claw/agent/langchain_runtime.py` 中修改 `stream` 方法：

```python
def stream(self, prompt: str, cancel_event: Any = None) -> Iterable[StreamEvent]:
    return _stream_with_approval(
        self._agent,
        {"messages": [{"role": "user", "content": prompt}]},
        config={"configurable": {"thread_id": self._thread_id}},
        reviewer=self._reviewer,
        thread_id=self._thread_id,
        cancel_event=cancel_event,
    )
```

文件顶部添加 `import threading`（如果尚未导入）。

- [ ] **Step 4: 运行测试确认通过**

```powershell
uv run pytest tests/agent/test_runtime.py::test_session_stream_passes_cancel_event_to_underlying_function tests/agent/test_runtime.py::test_session_stream_works_without_cancel_event -v
```

- [ ] **Step 5: 运行全部已有测试确认无回归**

```powershell
uv run pytest tests/agent/test_runtime.py -v
```

- [ ] **Step 6: 提交**

```bash
git add src/easy_claw/agent/langchain_runtime.py tests/agent/test_runtime.py
git commit -m "feat: pass cancel_event through LangChainAgentSession.stream"
```

---

### Task 3: cli/interactive.py — 按键监听与渲染循环改动

**Files:**
- Modify: `src/easy_claw/cli/interactive.py:360-418`
- Test: `tests/cli/test_interactive_stream.py` (新建)

- [ ] **Step 1: 编写按键监听函数测试**

新建 `tests/cli/test_interactive_stream.py`：

```python
import threading
import time

from easy_claw.agent.streaming import StreamEvent


def test_watch_esc_key_detects_escape_and_sets_cancel_event():
    """用 mock msvcrt 测试按键监听函数。"""
    from unittest import mock

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
    from unittest import mock

    cancel_event = threading.Event()
    stopped = threading.Event()

    # 提前设置 stopped，模拟主线程已结束
    stopped.set()

    def fake_kbhit():
        raise AssertionError("should not be called when stopped")

    with mock.patch('msvcrt.kbhit', fake_kbhit):
        from easy_claw.cli.interactive import _watch_esc_key
        _watch_esc_key(cancel_event, stopped)

    assert not cancel_event.is_set()


def test_render_streaming_turn_handles_interrupted_event(monkeypatch):
    """_render_streaming_turn 收到 interrupted 事件后正确退出。"""
    from io import StringIO

    from rich.console import Console

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
    from io import StringIO

    from rich.console import Console

    output = StringIO()
    test_console = Console(
        file=output, force_terminal=False, color_system=None, width=100
    )
    monkeypatch.setattr("easy_claw.cli.interactive.console", test_console)

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
    assert "已打断" in output.getvalue()
    assert usage is None
```

- [ ] **Step 2: 运行测试确认失败**

```powershell
uv run pytest tests/cli/test_interactive_stream.py -v
```

预期：import error（`_watch_esc_key` 不存在）或 assertion error

- [ ] **Step 3: 添加 _watch_esc_key 函数和修改 _render_streaming_turn**

在 `src/easy_claw/cli/interactive.py` 顶部添加 `import threading`。

在文件中（`_render_streaming_turn` 函数之前）添加：

```python
def _watch_esc_key(cancel_event: threading.Event, stopped: threading.Event) -> None:
    import msvcrt

    while not stopped.is_set():
        try:
            if msvcrt.kbhit():
                ch = msvcrt.getch()
                if ch == b'\x1b':
                    cancel_event.set()
                    break
        except Exception:
            break
```

修改 `_render_streaming_turn` 函数签名和实现：

```python
def _render_streaming_turn(
    events: Iterable[StreamEvent],
) -> tuple[str, dict[str, int] | None]:
    """渲染一次流式回复，返回回复文本和用量。"""
    tokens: list[str] = []
    usage: dict[str, int] | None = None
    printed_token = False
    spinner = console.status("[dim]正在思考...[/]")
    spinner.start()
    spinner_running = True
    try:
        for event in events:
            if spinner_running:
                spinner.stop()
                spinner_running = False
            if event.type == "token":
                console.print(event.content, end="")
                tokens.append(event.content)
                printed_token = True
            elif event.type == "tool_call_start":
                _print_stream_separator(printed_token)
                console.print(
                    Panel(
                        _format_stream_value(event.tool_args),
                        title=f"工具调用：{event.tool_name or '未知工具'}",
                        border_style="blue",
                    )
                )
                printed_token = False
            elif event.type == "tool_call_result":
                _print_stream_separator(printed_token)
                console.print(
                    Panel(
                        _format_stream_value(event.content or event.tool_result),
                        title=f"工具结果：{event.tool_name or '未知工具'}",
                        border_style="green",
                    )
                )
                printed_token = False
            elif event.type == "approval_required":
                _print_stream_separator(printed_token)
                console.print("[yellow]工具执行需要确认[/]")
                printed_token = False
            elif event.type == "interrupted":
                _print_stream_separator(printed_token)
                console.print("[yellow]已打断[/]")
                printed_token = False
            elif event.type == "error":
                _print_stream_separator(printed_token)
                if event.content:
                    console.print(f"[red]{escape(event.content)}[/]")
                    tokens.append(event.content)
                printed_token = False
            elif event.type == "done":
                if spinner_running:
                    spinner.stop()
                    spinner_running = False
                if printed_token:
                    console.print()
                printed_token = False
                usage = event.usage
    finally:
        if spinner_running:
            spinner.stop()
    return "".join(tokens), usage
```

修改 `_run_interactive_loop` 中 `stream_turn` 的类型和调用方式。找到 `stream_turn` 的定义位置（`_run_interactive_chat` 函数中），将：

```python
def stream_turn(prompt: str) -> Iterable[StreamEvent]:
    return ensure_agent_session().stream(prompt)
```

改为：

```python
def stream_turn(prompt: str, cancel_event=None) -> Iterable[StreamEvent]:
    return ensure_agent_session().stream(prompt, cancel_event=cancel_event)
```

修改 `_render_streaming_turn` 的调用（在 `_run_interactive_loop` 中约第 217 行），将：

```python
response, usage = _render_streaming_turn(stream_turn(prompt))
```

改为：

```python
cancel_event = threading.Event()
stopped = threading.Event()
listener = threading.Thread(
    target=_watch_esc_key,
    args=(cancel_event, stopped),
    daemon=True,
)
listener.start()
try:
    response, usage = _render_streaming_turn(
        stream_turn(prompt, cancel_event=cancel_event)
    )
finally:
    stopped.set()
```

- [ ] **Step 4: 运行测试确认通过**

```powershell
uv run pytest tests/cli/test_interactive_stream.py -v
```

- [ ] **Step 5: 运行全部已有测试确认无回归**

```powershell
uv run pytest tests/cli/ -v
uv run pytest tests/agent/ -v
```

- [ ] **Step 6: 提交**

```bash
git add src/easy_claw/cli/interactive.py tests/cli/test_interactive_stream.py
git commit -m "feat: add Esc key interrupt to CLI streaming"
```

---

### Task 4: 最终验证

**Files:** 无新文件

- [ ] **Step 1: 运行完整测试套件**

```powershell
uv run pytest -v
```

- [ ] **Step 2: 运行 ruff 检查**

```powershell
uv run ruff check .
```

- [ ] **Step 3: 手动验证（可选）**

启动 CLI 交互式聊天，输入一个会生成较长回复的 prompt，在输出过程中按 Esc，确认：
- 输出停止
- 显示 "已打断"
- 回到输入提示符
- 可以继续输入新消息

```powershell
uv run easy-claw chat --interactive
```
