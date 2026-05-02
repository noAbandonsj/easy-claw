# easy-claw 第一版 MVP 思路

> **历史文档**：本文档为 2026-05-01 的早期思路草稿，其中大部分技术选型（LangChain `create_agent`、`FileManagementToolkit`、`SQLModel`、开发者模式 Shell 等）已被 v0.2 实际实现取代。当前架构见 `docs/architecture.md`。

本文档保留原始内容以供参考，后续不再更新。

## 核心判断

easy-claw 第一版不应该放弃“本地 AI Agent 工作台”的方向，但需要把目标收紧到一个技术人员可以马上编码、马上跑通的 MVP。

第一版不是完整个人 AI 平台，也不是面向普通用户的零门槛产品。它更应该是一个 Windows 优先、技术人员优先、本地运行、复用成熟组件的 Agent 工作台骨架。

关键原则：

- **能跑优先**：先让用户在 Windows 本地通过 `uv` 和 `start.ps1` 跑起一个可用助手。
- **复用优先**：优先使用 LangChain、FastAPI、Typer、SQLite、MarkItDown 等现成组件。
- **技术人员优先**：允许用户理解 API key、命令行、工作区路径、开发者模式等概念。
- **本地优先**：默认本机运行，不做云平台、多用户系统或复杂 Gateway。
- **安全轻量化**：第一版只做开发者模式、基础风险提示和工具调用日志，完整审批、审计、沙箱后续增强。

## 第一版保留的产品思路

easy-claw 仍然可以被定位为“个人 AI Agent 工作台”，但第一版重点不是功能完整，而是跑通一条最短闭环：

1. 用户通过 CLI 或本地 API 输入任务。
2. 系统使用 LangChain Agent 调用模型和工具。
3. Agent 能读取工作区文件、总结文档、搜索资料、生成 Markdown 输出。
4. 会话、消息、工具调用和简单记忆写入 SQLite。
5. 技术用户可以显式开启开发者模式，让 Agent 使用 Shell 或 Python REPL。
6. Windows 用户可以通过 `start.ps1` 和 `uv` 启动项目。

这条路径跑通后，再逐步增强 Web UI、安全策略、MCP、LangGraph、长期记忆和桌面端。

## MVP 依赖分层

第一版应该区分“启动必须依赖”和“后续可接入组件”。不要因为某个组件听起来重要，就把它放进第一版核心路径。

| 层级 | 组件 | 第一版定位 |
| --- | --- | --- |
| 核心必需 | FastAPI | 本地 API 服务，承载会话、工具调用、后续 Web UI |
| 核心必需 | Typer + Rich | 技术人员 CLI 入口，适合 MVP 调试和日常使用 |
| 核心必需 | SQLite | 本地会话、消息、工具调用、简单记忆存储 |
| 核心必需 | LangChain `init_chat_model` | 第一版模型初始化入口，避免过早引入模型网关 |
| 核心必需 | LangChain `create_agent` | 第一版 Agent Runtime 的主体 |
| 核心必需 | FileManagementToolkit | 工作区内文件读取、列目录、写输出文件 |
| 核心必需 | MarkItDown | 把 PDF、Word、PPT、Excel、HTML 等转成 Markdown 给模型处理 |
| 核心必需 | Markdown Skills Loader | 加载可读、可版本化的工作流提示词 |
| 核心必需 | SQLite Memory | 保存用户偏好、项目摘要、任务结论 |
| 核心必需 | 搜索工具 | DuckDuckGo 默认免 key；Tavily 可作为有 key 的增强选择 |
| 谨慎保留 | ShellTool | 只在开发者模式启用，默认不开 |
| 谨慎保留 | Python REPL | 只在开发者模式启用，用于技术人员临时分析 |
| 后置增强 | LiteLLM | 需要模型网关、fallback、成本统计、多供应商统一代理时再引入 |
| 后置增强 | LangChain Document Loaders | MarkItDown 不够用，或需要格式特定 metadata 时再补 |
| 后置增强 | JSON Toolkit | 需要 Agent 逐步探索大型 JSON 时再接；普通配置文件先用 `json` 即可 |
| 后置增强 | MCP | 工具体系稳定后再接，不作为第一版核心依赖 |
| 后置增强 | LangGraph Runtime | 长任务恢复、人审中断、失败重试成熟后再显式引入 |
| 后置增强 | Mem0 / Honcho | SQLite Memory 不够用时再作为长期记忆 Provider |
| 后置增强 | Docker / WSL2 Sandbox | 安全增强阶段再做，不阻塞基础版本 |

## 工具用途说明

| 工具 | 用途 | 取舍说明 |
| --- | --- | --- |
| FastAPI | 提供本地 HTTP API、健康检查、会话接口、后续流式事件接口 | 比直接写脚本更利于后续 Web UI，但第一版 API 可以很薄 |
| Typer | 提供 `easy-claw chat`、`easy-claw doctor`、`easy-claw ingest` 等命令 | 技术人员优先时，CLI 比 Web UI 更快落地 |
| Rich | 美化 CLI 输出、表格、日志、状态提示 | 不是核心逻辑，但能显著提升开发者体验 |
| SQLite | 存储会话、消息、工具调用、记忆、配置 | 本地优先，部署简单，不需要 PostgreSQL |
| SQLModel | 定义表模型和 Repository | 可选；如果第一版想更轻，也可以先用 SQLAlchemy 或 sqlite3 |
| LangChain `init_chat_model` | 统一初始化聊天模型 | 第一版可替代 LiteLLM，降低依赖和概念复杂度 |
| LiteLLM | 多模型网关、统一 OpenAI-compatible API、fallback、成本追踪 | 很有价值，但不是跑通 MVP 的必需组件 |
| LangChain `create_agent` | 把模型和工具组合成可调用工具的 Agent | 第一版不自研 Agent 框架 |
| FileManagementToolkit | 提供文件读取、目录列表、写文件等工具 | 必须限制工作区根目录和可用工具，避免默认开放过多能力 |
| MarkItDown | 把多种文档格式转换为 Markdown | 适合个人文档助手的第一版输入管线 |
| LangChain Document Loaders | 更细粒度地读取特定文档格式并保留 metadata | 作为 MarkItDown 的补充，不必第一版全部接入 |
| JSON Toolkit | 让 Agent 逐步查询和分析大型 JSON | 对 OpenAPI、复杂配置有用；普通 JSON 文件先用基础解析即可 |
| DuckDuckGo Search | 默认联网搜索工具 | 免 API key，适合作为默认搜索能力 |
| Tavily Search | 面向 Agent/RAG 的搜索 API | 效果可能更稳定，但需要 API key，适合作为可选增强 |
| Markdown Skills Loader | 从 Markdown + frontmatter 加载任务流程 | 简单、可读、可版本化，不做复杂插件市场 |
| SQLite Memory | 简单保存用户偏好、项目摘要、任务结论 | 第一版足够；向量检索和用户建模后续再做 |
| ShellTool | 执行本机命令 | 高风险，只在开发者模式开启，并记录日志 |
| Python REPL | 执行临时 Python 代码 | 适合技术人员分析数据和文件，但必须默认关闭 |

## 建议的第一版能力边界

第一版可以做：

- 本地 FastAPI 服务。
- Typer CLI。
- SQLite 会话、消息、工具调用、简单记忆。
- LangChain `init_chat_model` + `create_agent`。
- 受限文件工具。
- MarkItDown 文档读取。
- DuckDuckGo 搜索，Tavily 可选。
- Markdown Skills 加载。
- 开发者模式 Shell / Python REPL。
- `start.ps1` + `uv` 启动方式。

第一版暂不做：

- 完整权限系统。
- 完整 Approval Policy。
- Docker / WSL2 沙箱。
- 桌面客户端。
- 多用户系统。
- 插件市场。
- 完整 MCP Server 管理。
- 显式 LangGraph 长任务恢复。
- Gmail / Calendar 深度集成。
- LiteLLM 网关模式。
- Mem0 / Honcho 长期记忆。

## 推荐工程切片

### Phase 0: 文档和工程骨架

- 明确 README 和 architecture 的 MVP 口径。
- 创建 `pyproject.toml`。
- 创建 `src/easy_claw/`。
- 创建 `scripts/start.ps1`。
- 确定基础配置格式和数据库位置。

### Phase 1: 最小可运行 Agent

- FastAPI `GET /health`。
- Typer CLI 入口。
- SQLite 初始化。
- LangChain `init_chat_model`。
- LangChain `create_agent`。
- 一个最小对话命令。
- 会话和消息落库。

### Phase 2: 本地文档助手

- 工作区路径配置。
- FileManagementToolkit 受限接入。
- MarkItDown 文档读取。
- Markdown 报告输出。
- 工具调用记录。

### Phase 3: 开发者工具增强

- Markdown Skills Loader。
- DuckDuckGo / Tavily 搜索。
- JSON 文件分析。
- 开发者模式 ShellTool。
- 开发者模式 Python REPL。

### Phase 4: 安全和可用性增强

- 基础风险标签。
- 高风险工具调用提示。
- 工具调用日志查看。
- 更清晰的工作区边界。
- 后续再考虑 Approval Policy 和 Docker 沙箱。

### Phase 5: 普通用户体验

- 轻量 Web UI。
- 更友好的配置向导。
- 桌面端或安装包。
- MCP Server 管理。
- LangGraph 长任务恢复。
- Mem0 / Honcho 长期记忆。

## README 后续修改口径

后续修改 README 时，可以采用这句话作为新的项目定位：

> easy-claw 是一个面向技术人员和个人开发者的 Windows 优先本地 AI Agent MVP 工作台。它不自研 Agent 框架，不重复造轮子，而是优先封装 LangChain、FastAPI、Typer、SQLite、MarkItDown 和相关工具，让用户能快速在 Windows 本地跑通一个可用的个人助手。

这句话保留了第一版“个人 AI Agent 工作台”的方向，但避免把项目写成过大的长期平台蓝图。
