# CLI 流式打断功能设计

## 需求

CLI 终端聊天中，用户在 agent 流式输出期间按 Esc 键可打断当前生成，保留已输出内容，返回输入提示符。

- 范围：仅 CLI（`cli/interactive.py`），Web 端不改
- 触发：Esc 键
- 行为：停止生成，保留已输出的文本和工具结果

## 数据流

```
用户按 Esc
    │
    ▼
后台监听线程 (msvcrt) ──► cancel_event.set()
    │
    ▼
_stream_with_approval() 循环检测到 cancel_event.is_set()
    │
    ▼
yield StreamEvent(type="interrupted")
    │
    ▼
_render_streaming_turn() 收到 interrupted 事件
    │
    ▼
打印 "[黄色]已打断[/]" 并退出循环，保留已累积的 tokens
    │
    ▼
_run_interactive_loop() 继续，返回输入提示符
```

## 改动文件

### 1. `agent/streaming.py`

`_stream_with_approval()` 增加 `cancel_event: threading.Event | None = None` 参数：

- while 循环顶部检查 `cancel_event.is_set()`，为真则 break
- for 循环内部每次迭代后检查，为真则 yield `StreamEvent(type="interrupted")` 并 return
- `interrupted` 事件不需要额外字段，用现有 `StreamEvent` dataclass 的 `type` 即可

`_invoke_with_approval()`（非流式）不改。

### 2. `agent/langchain_runtime.py`

`LangChainAgentSession.stream()` 增加 `cancel_event: threading.Event | None = None` 参数，透传给 `_stream_with_approval()`。

### 3. `cli/interactive.py`

**按键监听函数**（新增）：

```python
def _watch_esc_key(cancel_event: threading.Event, stopped: threading.Event):
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

**`_render_streaming_turn()` 改动**：

- 创建 `cancel_event = threading.Event()` 和 `stopped = threading.Event()`
- 启动 daemon 线程执行 `_watch_esc_key(cancel_event, stopped)`
- 调用 `stream_turn(prompt, cancel_event=cancel_event)`
- 事件循环新增处理 `"interrupted"` 类型：打印黄色提示，break
- finally 中 `stopped.set()` 确保监听线程退出

**`stream_turn` 签名扩展**：从 `Callable[[str], Iterable[StreamEvent]]` 扩展为接受 `cancel_event` 关键字参数。

## 关键技术点

- `msvcrt` 是 Python 标准库，Windows 原生，无需额外依赖
- daemon 线程 + stopped 事件确保线程不会泄漏
- 取消检查放在 stream 循环内部：for 循环每次迭代后检查，开销极低
- Esc 键值为 `\x1b`（一个字节，`msvcrt.getch()` 返回 `b'\x1b'`）

## 测试要点

- 打断后已有 token 文本保留在对话中
- 打断后返回输入提示符，可继续聊天
- 没有流式输出时按 Esc 不影响程序
- 监听线程在流式结束后正常退出
