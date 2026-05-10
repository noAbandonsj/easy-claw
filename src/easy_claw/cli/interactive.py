from __future__ import annotations

import dataclasses
import json
from collections.abc import Callable, Iterable
from math import ceil
from pathlib import Path

import typer
from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import BufferControl, HSplit, Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.processors import BeforeInput
from prompt_toolkit.styles import Style
from prompt_toolkit.utils import get_cwidth
from rich.markup import escape
from rich.panel import Panel
from rich.rule import Rule

from easy_claw.agent.langchain_runtime import AgentRequest, AgentResult, LangChainAgentRuntime
from easy_claw.agent.streaming import StreamEvent
from easy_claw.cli.slash import (
    LoopControl,
    SlashCommandContext,
    _dispatch_interactive_command,
    get_slash_command_specs,
)
from easy_claw.cli.views import (
    _render_startup_banner,
    _resolve_skill_source_records,
    console,
)
from easy_claw.config import AppConfig
from easy_claw.storage.db import initialize_product_db
from easy_claw.storage.repositories import AuditRepository, SessionRepository

STREAM_PANEL_VALUE_LIMIT = 200
PROMPT_RULE_STYLE = "light_pink1"
PROMPT_TOOLKIT_COLOR = "#ffafaf"

_pt_style: Style | None = None


def _get_pt_style() -> Style:
    global _pt_style
    if _pt_style is None:
        _pt_style = Style.from_dict(
            {
                "prompt": f"{PROMPT_TOOLKIT_COLOR} bold",
                "rule": PROMPT_TOOLKIT_COLOR,
            }
        )
    return _pt_style


def _run_interactive_chat(
    *,
    config: AppConfig,
    resume_thread_id: str | None = None,
) -> None:
    if config.model is None:
        console.print("请先设置 EASY_CLAW_MODEL，再运行聊天。")
        raise typer.Exit(code=1)

    initialize_product_db(config.product_db_path)
    audit_repo = AuditRepository(config.product_db_path)
    runtime = LangChainAgentRuntime()
    conversation: list[tuple[str, str]] = []
    token_usage: dict[str, int] = {}

    _render_startup_banner(config)

    thread_id: str | None = resume_thread_id
    open_session = getattr(runtime, "open_session", None)

    while True:
        if thread_id is None:
            session = SessionRepository(config.product_db_path).create_session(
                workspace_path=str(config.default_workspace),
                model=config.model,
                title="交互式聊天",
            )
            thread_id = session.id

        base_request = AgentRequest(
            prompt="",
            thread_id=thread_id,
            config=config,
            skill_source_records=_resolve_skill_source_records(config),
        )

        agent_session_cm = None
        agent_session = None

        if open_session is None:
            def run_turn(prompt: str, request: AgentRequest = base_request) -> AgentResult:
                return runtime.run(_agent_request_for_prompt(request, prompt))

            stream_turn = None
        else:
            def ensure_agent_session(request: AgentRequest = base_request):
                nonlocal agent_session_cm, agent_session
                if agent_session is None:
                    agent_session_cm = open_session(request)
                    agent_session = agent_session_cm.__enter__()
                return agent_session

            def run_turn(prompt: str) -> AgentResult:
                return ensure_agent_session().run(prompt)

            def stream_turn(prompt: str) -> Iterable[StreamEvent]:
                return ensure_agent_session().stream(prompt)

        try:
            control = _run_interactive_loop(
                run_turn=run_turn,
                stream_turn=stream_turn,
                audit_repo=audit_repo,
                session_id=thread_id,
                session_config=config,
                conversation=conversation,
                token_usage=token_usage,
            )
        finally:
            if agent_session_cm is not None:
                agent_session_cm.__exit__(None, None, None)

        if control.action == "exit":
            break
        if control.action == "workspace":
            new_path = Path(control.value or "").expanduser().resolve()
            if not new_path.is_dir():
                console.print(f"[yellow]不是目录：{new_path}[/]")
                continue
            config = dataclasses.replace(config, default_workspace=new_path)
            console.print(f"[dim]工作区已切换到 {new_path}[/]")
            continue
        if control.action == "model":
            model_name = (control.value or "").strip()
            if not model_name:
                console.print("[yellow]用法：/model <name>[/]")
                continue
            config = dataclasses.replace(config, model=model_name)
            console.print(f"[dim]模型已切换到 {model_name}[/]")
            continue
        if control.action == "resume":
            matched = SessionRepository(config.product_db_path).get_session(control.value or "")
            if matched is None:
                console.print(f"[yellow]会话不存在：{control.value}[/]")
                continue
            thread_id = matched.id
            workspace_path = Path(matched.workspace_path).expanduser()
            if workspace_path.is_dir():
                config = dataclasses.replace(
                    config,
                    default_workspace=workspace_path.resolve(),
                    model=matched.model or config.model,
                )
            elif matched.model:
                config = dataclasses.replace(config, model=matched.model)
            conversation.clear()
            token_usage.clear()
            console.print(f"[dim]已恢复会话 {matched.id[:8]}：{matched.title}[/]")
            continue
        if control.action == "clear":
            thread_id = None
            conversation.clear()
            token_usage.clear()
            console.print("[dim]对话历史已清空，已开始新会话。[/]")
            continue


def _run_interactive_loop(
    *,
    run_turn: Callable[[str], AgentResult],
    audit_repo: AuditRepository | None,
    session_id: str,
    session_config: AppConfig,
    stream_turn: Callable[[str], Iterable[StreamEvent]] | None = None,
    conversation: list[tuple[str, str]] | None = None,
    token_usage: dict[str, int] | None = None,
) -> LoopControl:
    """运行交互式循环。"""
    if conversation is None:
        conversation = []
    if token_usage is None:
        token_usage = {}

    while True:
        try:
            prompt = _read_interactive_prompt()
        except EOFError:
            console.print()
            return LoopControl("exit")
        if not prompt:
            continue

        command_handled, control = _dispatch_interactive_command(
            prompt,
            SlashCommandContext(
                session_id=session_id,
                config=session_config,
                conversation=conversation,
                token_usage=token_usage,
            ),
        )
        if command_handled:
            if control is not None:
                return control
            continue

        if stream_turn is not None:
            response, usage = _render_streaming_turn(stream_turn(prompt))
        else:
            with console.status("[dim]正在思考...[/]"):
                result = run_turn(prompt)
            response = result.content
            usage = result.usage
            console.print(response)

        conversation.append((prompt, response))
        if usage:
            for key in ("input", "output", "total"):
                token_usage[key] = token_usage.get(key, 0) + usage.get(key, 0)

        if audit_repo is not None:
            audit_repo.record(
                event_type="agent_run",
                payload={"session_id": session_id, "prompt_length": len(prompt)},
            )


def _read_interactive_prompt() -> str:
    if console.is_terminal:
        rule = "\u2500" * console.width
        try:
            prompt = _run_prompt_toolkit_frame(rule)
        except KeyboardInterrupt:
            console.print()
            return ""
        except EOFError:
            raise
        except Exception:
            # prompt_toolkit needs a real Windows console (not pty/bash/xterm).
            # Fall back to original 3-line frame + input().
            console.print(Rule(style=PROMPT_RULE_STYLE))
            console.print(f"[bold {PROMPT_RULE_STYLE}]>[/] ")
            console.print(Rule(style=PROMPT_RULE_STYLE))
            console.file.write("\033[2A\033[2C")
            console.file.flush()
            prompt = input()
            _clear_prompt_frame()
        stripped = prompt.strip()
        if stripped:
            console.print(f"[bold {PROMPT_TOOLKIT_COLOR}]>[/] {escape(stripped)}")
        return stripped
    return input("> ").strip()


def _run_prompt_toolkit_frame(rule: str) -> str:
    app, _buffer = _build_prompt_frame_app(rule, width=console.width)
    return app.run()


def _build_slash_completer() -> WordCompleter:
    specs = get_slash_command_specs()
    words: list[str] = []
    meta: dict[str, str] = {}
    for spec in specs:
        words.append(spec.name)
        meta[spec.name] = spec.description
        for alias in spec.aliases:
            words.append(alias)
            meta[alias] = f"{spec.name} — {spec.description}"
    return WordCompleter(words, ignore_case=True, sentence=True, meta_dict=meta)


def _build_prompt_frame_app(
    rule: str,
    *,
    width: int,
    output=None,
) -> tuple[Application[str], Buffer]:
    buffer = Buffer(multiline=True, completer=_build_slash_completer())
    key_bindings = KeyBindings()

    @key_bindings.add("enter")
    def _accept(event) -> None:
        event.app.exit(result=buffer.text)

    @key_bindings.add("c-c")
    def _interrupt(event) -> None:
        event.app.exit(exception=KeyboardInterrupt)

    @key_bindings.add("c-d")
    def _eof(event) -> None:
        event.app.exit(exception=EOFError)

    @key_bindings.add("tab")
    def _complete(event) -> None:
        _advance_or_start_completion(event.current_buffer)

    buffer_control = BufferControl(
        buffer=buffer,
        input_processors=[BeforeInput([("class:prompt", "> ")])],
    )
    buffer_window = Window(
        buffer_control,
        height=lambda: _prompt_buffer_height(buffer, width),
        wrap_lines=True,
    )
    root = HSplit(
        [
            Window(FormattedTextControl([("class:rule", rule)]), height=1),
            buffer_window,
            Window(FormattedTextControl([("class:rule", rule)]), height=1),
        ]
    )
    app: Application[str] = Application(
        layout=Layout(root, focused_element=buffer_control),
        key_bindings=key_bindings,
        style=_get_pt_style(),
        erase_when_done=True,
        full_screen=False,
        output=output,
    )
    return app, buffer


def _advance_or_start_completion(buffer: Buffer) -> None:
    if buffer.complete_state:
        buffer.complete_next()
        return
    buffer.start_completion(select_first=True)


def _prompt_buffer_height(buffer: Buffer, width: int) -> Dimension:
    usable_width = max(1, width)
    rows = 0
    for index, line in enumerate(buffer.document.lines):
        prompt_width = 2 if index == 0 else 0
        line_width = prompt_width + get_cwidth(line)
        rows += max(1, ceil(line_width / usable_width))
    return Dimension.exact(max(1, rows))


def _clear_prompt_frame() -> None:
    console.file.write("\r\033[2K\033[1A\r\033[2K\033[1A\r\033[2K")
    console.file.flush()


def _agent_request_for_prompt(request: AgentRequest, prompt: str) -> AgentRequest:
    return dataclasses.replace(request, prompt=prompt)


def _render_streaming_turn(events: Iterable[StreamEvent]) -> tuple[str, dict[str, int] | None]:
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


def _print_stream_separator(printed_token: bool) -> None:
    if printed_token:
        console.print()


def _format_stream_value(value: object) -> str:
    if value is None:
        text = ""
    elif isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, ensure_ascii=False, indent=2, default=str)
        except TypeError:
            text = str(value)
    if len(text) <= STREAM_PANEL_VALUE_LIMIT:
        return text
    return text[:STREAM_PANEL_VALUE_LIMIT] + "\n\\[已截断]"
