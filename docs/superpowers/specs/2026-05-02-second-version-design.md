# easy-claw 第二版设计：本地文档助手与强工具可用性

日期：2026-05-02

## 决策

第二版聚焦可用性和工具能力开放，不把复杂安全体系作为主线。第一版已经具备 CLI、FastAPI、SQLite、Skills、DeepAgents Runtime 和 DeepSeek 模型接入；第二版要把这些骨架串成用户能直接使用的本地强工具助手。

第二版名称建议为：`v0.2 Local Document Agent + Power Tools`，中文口径是“本地文档助手与强工具可用性”。

## 目标

用户可以在 Windows 本地选择文档或目录，让 easy-claw 读取、转换、总结，并输出 Markdown 结果。用户也可以让 easy-claw 运行常用项目命令、执行 Python 片段、联网搜索资料，把这些工具结果交给 Agent 统一整理。这个能力需要同时能被 CLI 使用，也要为后续 Web UI 预留稳定 API。

## 范围

第二版包含：

- 工作区内文件选择和路径解析。
- 用户显式传入的本机路径读取，不把工作区做成硬沙箱。
- 读取文本、Markdown、代码和常见文档。
- 用 MarkItDown 把 PDF、Word、PowerPoint、Excel、HTML 等转换为 Markdown。
- DuckDuckGo 联网搜索。
- PowerShell / Shell 命令执行，适合运行 `pytest`、`ruff`、`git status`、项目脚本等常用本地任务。
- Python 片段或脚本执行，适合处理本地数据、表格和临时分析。
- 通过 CLI 运行文档总结任务。
- 可选把总结结果写入 Markdown 文件。
- 为后续 Web UI 提供一个简单的 run/chat API。
- 复用现有 Markdown Skills 和显式 Memory。
- 记录轻量活动日志，方便用户知道系统读了什么、搜了什么、执行了什么、写了什么。

第二版不包含：

- 完整 MCP Client Adapter。
- Web UI 聊天界面。
- Docker / WSL2 沙箱。
- 复杂审批流、权限系统或策略引擎。
- Mem0 / Honcho 长期记忆 Provider。
- 多用户系统或插件市场。

## 工具开放策略

第二版以工具可用性优先。设计上承认这是用户自己电脑上的本地个人助手，不把每个能力都包进严密权限模型。

- `EASY_CLAW_WORKSPACE` 是默认上下文，不是硬沙箱。
- 用户显式传入的绝对路径可以读取或作为输出路径。
- Shell / PowerShell 和 Python 工具可以在第二版进入工具集，默认设置超时和输出截断。
- 写文件、执行命令、搜索网络时给出清晰提示并记录活动日志，但不设计复杂审批流。
- 明显破坏性动作，例如批量删除、覆盖大量文件、格式化磁盘，不作为第二版内置工作流。
- 不实现强确认、沙箱隔离和细粒度权限管理。

这样做的原因是：当前项目还处于本地个人 MVP 阶段，优先级最高的是跑通“选资料 -> 调工具 -> Agent 整理 -> 输出结果”的闭环。过早做完整安全策略会拖慢工具可用性，安全增强应放到工具层稳定之后再做。

## 架构

第二版新增一个本地强工具层，但不做复杂插件系统：

```text
CLI / FastAPI
  -> Config
  -> Workspace path resolver
  -> Document tools
      -> Text reader
      -> MarkItDown converter
      -> Markdown report writer
  -> Power tools
      -> DuckDuckGo search
      -> Shell / PowerShell runner
      -> Python runner
  -> AgentRuntime
      -> DeepAgents
      -> DeepSeek ChatOpenAI
      -> Skills
      -> explicit memories
  -> SQLite product DB
      -> sessions
      -> memory_items
      -> audit_logs as activity logs
```

建议模块：

- `easy_claw.tools.base`：定义工具结果、工具配置、活动日志 payload、简单工具错误。
- `easy_claw.tools.documents`：读取本机文件，调用 MarkItDown 转换文档。
- `easy_claw.tools.reports`：把生成结果写成 Markdown 文件。
- `easy_claw.tools.search`：封装 DuckDuckGo 搜索。
- `easy_claw.tools.commands`：运行 PowerShell / Shell 命令，处理超时和输出截断。
- `easy_claw.tools.python_runner`：运行 Python 片段或脚本，处理超时和输出截断。
- `easy_claw.agent.runtime`：继续负责 Agent 调用，不直接承担文档转换细节。
- `easy_claw.cli`：新增 `docs summarize`、`tools search`、`tools run`、`tools python` 命令。
- `easy_claw.api.main`：新增简单 run/chat API。

## CLI 体验

推荐新增命令：

```powershell
uv run easy-claw docs summarize .\README.md
uv run easy-claw docs summarize .\docs --output .\data\reports\docs-summary.md
uv run easy-claw tools search "DeepSeek API tool calls"
uv run easy-claw tools run "pytest -q"
uv run easy-claw tools python ".\scripts\analyze_csv.py"
```

命令行为：

1. 读取配置和工作区。
2. 解析用户传入路径。相对路径默认按工作区解析，绝对路径按用户显式输入处理。
3. 对文件或目录收集可读文档。
4. 把非 Markdown 文档转换为 Markdown。
5. 把转换后的内容和 `summarize-docs` Skill 一起交给 Agent。
6. 在控制台输出总结。
7. 如果传入 `--output`，把结果写入指定 Markdown 文件。

## API 体验

推荐新增最小 API：

```text
POST /runs
```

请求体：

```json
{
  "prompt": "总结这些文档，列出关键决策和待办",
  "workspace_path": "D:/Pathon/Programs/easy-claw",
  "document_paths": ["README.md", "docs/architecture.md"],
  "output_path": "data/reports/summary.md"
}
```

响应体：

```json
{
  "session_id": "...",
  "thread_id": "...",
  "content": "...",
  "output_path": "data/reports/summary.md"
}
```

第二版先不做流式输出。后续 Web UI 可以先调用这个同步 API，等体验稳定后再引入 SSE 或 WebSocket。

## 数据和日志

现有 `audit_logs` 可以先作为活动日志使用，不扩展复杂审计语义。建议记录：

- `document_read`
- `document_converted`
- `web_search`
- `command_run`
- `python_run`
- `report_written`
- `agent_run`

payload 里保存路径、命令、搜索关键词、文档数量、输出路径、退出码和错误摘要即可。

## 错误处理

第二版错误信息要面向可用性：

- 路径不存在：说明路径和当前工作区。
- 路径不在工作区内：如果是用户显式传入的绝对路径，可以继续处理；如果是由 Agent 自己推断出来的路径，则要求用户明确提供。
- 文档转换失败：说明文件名，继续处理其他可读文件。
- 没有可读文档：明确告诉用户支持的输入类型。
- 命令超时：停止命令并返回已捕获输出。
- 命令输出过长：截断输出并提示截断长度。
- 模型或 API key 缺失：复用现有配置错误。

## 测试

测试重点：

- 相对路径按工作区解析，显式绝对路径可以处理。
- 文本文档读取。
- MarkItDown 转换入口可被替换成 fake converter 测试。
- 目录输入能收集多个文档。
- 搜索工具可用 fake backend 测试。
- 命令和 Python runner 覆盖超时、退出码、输出截断。
- CLI `docs summarize` 可以用 fake runtime 跑通，不发起真实模型调用。
- CLI `tools search`、`tools run`、`tools python` 可以在测试里用 fake runner 跑通。
- `POST /runs` 创建 session 并返回内容。
- `audit_logs` 能记录文档读取、搜索、命令执行和报告写入活动。
