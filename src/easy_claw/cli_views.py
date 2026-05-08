from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from easy_claw import __version__ as _easy_claw_version
from easy_claw.config import AppConfig
from easy_claw.skills import SkillSource, resolve_skill_sources
from easy_claw.storage.db import initialize_product_db
from easy_claw.storage.repositories import SessionRecord, SessionRepository

console = Console()


def _print_doctor(config: AppConfig, *, test_browser: bool) -> None:
    """打印本地环境诊断信息。"""
    console.print("easy-claw doctor")
    console.print(f"数据目录: {config.data_dir}")
    console.print(f"业务数据库: {config.product_db_path}")
    console.print(f"检查点数据库: {config.checkpoint_db_path}")
    console.print(f"工作区: {config.default_workspace}")
    console.print(f"模型: {config.model or '<未配置>'}")
    console.print(f"模型服务地址: {config.base_url}")
    console.print(f"审批模式: {config.approval_mode}")
    console.print(f"执行模式: {config.execution_mode}")
    console.print(f"浏览器工具: {config.browser_enabled}")
    console.print(f"浏览器无头模式: {config.browser_headless}")
    console.print(f"MCP 启用状态: {_mcp_status(config)}")
    console.print(f"MCP 模式: {config.mcp_mode}")
    console.print(f"MCP 配置文件: {config.mcp_config_path}")
    console.print(f"模型调用上限: {config.max_model_calls}")
    console.print(f"工具调用上限: {config.max_tool_calls}")
    api_key_display = "***" + config.api_key[-4:] if config.api_key else "<未配置>"
    console.print(f"密钥: {api_key_display}")

    console.print()
    console.print("[bold]浏览器诊断[/]")
    try:
        from easy_claw.tools.browser import _check_playwright_browsers
    except ImportError:
        console.print("[yellow]未安装 playwright 包[/]")
        return

    chromium_installed = _check_playwright_browsers(headless=False)
    headless_installed = _check_playwright_browsers(headless=True)
    console.print(f"Chromium（有界面）: {'已安装' if chromium_installed else '[red]未安装[/]'}")
    console.print(f"Chromium（无头）: {'已安装' if headless_installed else '[red]未安装[/]'}")

    if not chromium_installed and not headless_installed:
        console.print("[dim]请运行：uv run playwright install chromium[/]")
        return

    if not test_browser:
        console.print("[dim]聊天内 /doctor 跳过实时浏览器启动测试。[/]")
        console.print("[dim]需要完整浏览器启动测试时运行：uv run easy-claw doctor[/]")
        return

    if config.browser_enabled:
        console.print("[dim]正在测试浏览器启动和页面访问...[/]")
        try:
            from easy_claw.tools.browser import build_browser_tools

            bundle = build_browser_tools(enabled=True, headless=True)
            console.print(f"[green]浏览器已启动[/] — 已加载 {len(bundle.tools)} 个工具")
            for cb in bundle.cleanup:
                cb()
            console.print("[green]浏览器已正常关闭[/]")
        except Exception as exc:
            console.print(f"[red]浏览器测试失败：{exc}[/]")


def _find_session_by_prefix(repo: SessionRepository, prefix: str) -> SessionRecord | None:
    sessions = repo.list_sessions()
    matches = [s for s in sessions if s.id.startswith(prefix)]
    if len(matches) == 1:
        return matches[0]
    return repo.get_session(prefix)


def _delete_checkpoint_thread(thread_id: str, checkpoint_db_path: Path) -> None:
    """使用 LangGraph 公开接口删除指定线程的所有检查点。"""
    from langgraph.checkpoint.sqlite import SqliteSaver

    if not checkpoint_db_path.exists():
        return
    try:
        with SqliteSaver.from_conn_string(str(checkpoint_db_path)) as saver:
            saver.delete_thread(thread_id)
    except Exception:
        console.print(f"[yellow]警告：[/]会话已删除，但未能清理 {checkpoint_db_path} 中的检查点")


def _resolve_skill_source_records(config: AppConfig) -> list[SkillSource]:
    return resolve_skill_sources(app_root=config.cwd, workspace_root=config.default_workspace)


def _write_conversation_markdown(
    conversation: list[tuple[str, str]],
    path: Path,
    session_id: str,
    config: AppConfig,
) -> None:
    lines: list[str] = []
    lines.append("# easy-claw 对话记录")
    lines.append("")
    lines.append(f"- **会话：** `{session_id}`")
    lines.append(f"- **模型：** {config.model}")
    lines.append(f"- **工作区：** {config.default_workspace}")
    lines.append(f"- **导出时间：** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append("---")
    lines.append("")

    for i, (user_msg, assistant_msg) in enumerate(conversation, 1):
        lines.append(f"### 第 {i} 轮")
        lines.append("")
        lines.append("**用户：**")
        lines.append("")
        lines.append(f"{user_msg}")
        lines.append("")
        lines.append("**easy-claw:**")
        lines.append("")
        lines.append(f"{assistant_msg}")
        lines.append("")
        lines.append("---")
        lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _print_session_list(config: AppConfig) -> None:
    initialize_product_db(config.product_db_path)
    repo = SessionRepository(config.product_db_path)
    sessions = repo.list_sessions()
    if not sessions:
        console.print("[dim]没有找到会话。[/]")
        return
    table = Table("ID", "标题", "模型", "更新时间")
    for s in sessions:
        table.add_row(s.id[:8], s.title[:60], s.model or "-", s.updated_at[:19])
    console.print(table)


def _print_skill_sources(config: AppConfig) -> None:
    sources = _resolve_skill_source_records(config)
    if not sources:
        console.print("[dim]没有找到 skill 来源。[/]")
        return
    console.print("[bold]Skill 来源[/]")
    for source in sources:
        console.print(f"[bold cyan]{source.label}[/]")
        console.print(f"  范围: {source.scope}")
        console.print(f"  skill 数量: {source.skill_count}")
        console.print(f"  后端路径: {source.backend_path}")
        console.print(f"  本地路径: {source.filesystem_path}")


def _print_mcp_details(config: AppConfig) -> None:
    table = Table(title="MCP", title_style="bold")
    table.add_column("属性", style="bold cyan")
    table.add_column("值")
    table.add_row("模式", config.mcp_mode)
    table.add_row("启用状态", _mcp_status(config))
    table.add_row("配置文件", config.mcp_config_path)
    table.add_row("服务数量", str(_count_mcp_servers(config.mcp_config_path)))
    console.print(table)


def _print_browser_details(config: AppConfig) -> None:
    table = Table(title="浏览器工具", title_style="bold")
    table.add_column("属性", style="bold cyan")
    table.add_column("值")
    table.add_row("启用", "是" if config.browser_enabled else "否")
    table.add_row("无头模式", "是" if config.browser_headless else "否")
    try:
        from easy_claw.tools.browser import _check_playwright_browsers
    except ImportError:
        table.add_row("Playwright", "未安装")
    else:
        table.add_row(
            "Chromium（有界面）",
            "已安装" if _check_playwright_browsers(headless=False) else "未安装",
        )
        table.add_row(
            "Chromium（无头）",
            "已安装" if _check_playwright_browsers(headless=True) else "未安装",
        )
    console.print(table)


def _format_limit(value: int | None) -> str:
    return "无限制" if value is None else f"{value:,}"


def _skill_source_summary(config: AppConfig) -> str:
    try:
        sources = _resolve_skill_source_records(config)
    except Exception as exc:
        return f"无法解析：{exc}"
    skill_count = sum(source.skill_count for source in sources)
    return f"{len(sources)} 个来源，{skill_count} 个 skill"


def _print_session_status(
    session_id: str,
    config: AppConfig,
    conversation: list[tuple[str, str]],
    token_usage: dict[str, int] | None = None,
) -> None:
    table = Table(title=f"会话 {session_id[:8]}", title_style="bold")
    table.add_column("属性", style="bold cyan")
    table.add_column("值")
    table.add_row("模型", config.model or "未配置")
    table.add_row("工作区", str(config.default_workspace))
    table.add_row("审批模式", config.approval_mode)
    table.add_row("浏览器", "已启用" if config.browser_enabled else "已关闭")
    table.add_row("MCP", _mcp_status(config))
    table.add_row("Skill 来源", _skill_source_summary(config))
    table.add_row("模型调用上限", _format_limit(config.max_model_calls))
    table.add_row("工具调用上限", _format_limit(config.max_tool_calls))
    table.add_row("轮次", str(len(conversation)))
    if token_usage:
        table.add_row("输入 token", f"{token_usage.get('input', 0):,}")
        table.add_row("输出 token", f"{token_usage.get('output', 0):,}")
        table.add_row("总 token", f"{token_usage.get('total', 0):,}")
    table.add_row("检查点", str(config.checkpoint_db_path))
    console.print(table)


def _count_mcp_servers(config_path: str) -> int:
    try:
        data = json.loads(Path(config_path).read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return sum(
                1
                for name, server_config in data.items()
                if not name.startswith("_") and isinstance(server_config, dict)
            )
    except Exception:
        pass
    return 0


def _mcp_status(config: AppConfig) -> str:
    mode = getattr(config, "mcp_mode", "enabled" if config.mcp_enabled else "disabled")
    if mode == "auto":
        count = _count_mcp_servers(config.mcp_config_path)
        return f"auto（{count} 个服务）" if count else "auto"
    if mode == "enabled" or config.mcp_enabled:
        count = _count_mcp_servers(config.mcp_config_path)
        return f"已启用（{count} 个服务）" if count else "已启用"
    return "已关闭"


def _render_startup_banner(config: AppConfig) -> None:
    """渲染启动横幅，展示当前配置。"""
    approval_color = {"permissive": "green", "balanced": "yellow", "strict": "red"}
    color = approval_color.get(config.approval_mode, "white")

    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="bold cyan", justify="right")
    grid.add_column(style="white")
    grid.add_row("模型:", config.model or "未配置")
    grid.add_row("工作区:", str(config.default_workspace))
    grid.add_row(
        "审批:",
        f"[{color}]{config.approval_mode}[/]",
    )
    grid.add_row("浏览器:", "已启用" if config.browser_enabled else "已关闭")
    grid.add_row("MCP 工具:", _mcp_status(config))

    banner = Panel(
        grid,
        title=f"[bold]easy-claw v{_easy_claw_version}[/]",
        title_align="left",
        border_style="cyan",
    )
    console.print(banner)
    console.print("[dim]输入 /help 查看命令；输入 :q、exit 或 quit 退出；空行会跳过。[/]")
    console.print()
