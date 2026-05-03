# easy-claw

easy-claw 是一个 Windows 个人 AI 助手——在终端里用自然语言完成总结文档、分析项目、搜索资料、运行测试等日常任务。

它不是复杂 AI 平台，也不要求你懂 Docker 或 Kubernetes。一句 `uv run easy-claw chat --interactive` 就能开始对话。

> 不重复造轮子，只做成熟框架的组合、封装和易用化部署。

---

## 快速开始

### 1. 准备环境

- Python 3.11+
- Git
- [uv](https://docs.astral.sh/uv/)

```powershell
cd D:\Pathon\Programs\easy-claw
uv sync
```

### 2. 配置模型

复制环境变量模板：

```powershell
Copy-Item .env.example .env
```

编辑 `.env`，至少填入模型和 API Key：

```env
EASY_CLAW_MODEL=deepseek-v4-pro
EASY_CLAW_API_KEY=你的 API Key
```

也可以直接在当前 PowerShell 会话设置环境变量（优先级高于 `.env`）：

```powershell
$env:EASY_CLAW_MODEL = "deepseek-v4-pro"
$env:EASY_CLAW_API_KEY = "你的 API Key"
```

### 3. 启动

```powershell
uv run easy-claw chat --interactive
```

看到 `easy-claw>` 提示符就说明成功了。输入自然语言开始使用，输入 `exit` 退出。

```text
easy-claw> 帮我总结 README.md 的主要内容
easy-claw> 这个项目用了哪些 Python 依赖
easy-claw> 运行 pytest 看看有没有失败的测试
```

如果想先验证配置是否正确：

```powershell
uv run easy-claw doctor
```

---

## 典型使用场景

进入交互式对话后，你可以直接用自然语言完成以下任务：

| 场景 | 示例 |
|---|---|
| 总结文档 | "帮我总结 docs/architecture.md，输出关键设计决策" |
| 分析项目 | "分析这个项目的代码结构，解释各模块的职责" |
| 搜索资料 | "搜索 DeepSeek API 最新的 function calling 文档" |
| 运行测试 | "运行 pytest 并告诉我哪些测试失败了" |
| 生成报告 | "把刚才的分析结果写入 reports/analysis.md" |
| 代码片段 | "用 Python 读取 data/config.json 并打印所有 key" |
| 命令执行 | "列出当前目录下所有 Python 文件" |

如果只是想调试底层文档读取能力但不调用模型，可以使用开发者入口：

```powershell
uv run easy-claw dev docs summarize README.md --dry-run
```

如果用 `--dry-run` 测试对话：

```powershell
uv run easy-claw chat --dry-run "你好"
```

---

## CLI 命令参考

所有命令分组如下：

### Primary — 主命令

| 命令 | 说明 |
|---|---|
| `chat --interactive` | 启动交互式 AI 助手（推荐） |
| `chat "prompt"` | 单次对话 |
| `chat --dry-run "prompt"` | 不调用模型，测试对话链路 |

### Management — 管理命令

| 命令 | 说明 |
|---|---|
| `doctor` | 打印当前环境诊断信息 |
| `init-db` | 初始化本地 SQLite 数据库 |
| `serve` | 启动 FastAPI 服务（开发者向） |

### Dev — 开发者调试命令

这些命令只用于调试底层能力。普通用户不需要记忆这些入口；在交互式 `chat` 里用自然语言同样可以完成这些操作。

#### `docs summarize` — 文档总结

```powershell
uv run easy-claw dev docs summarize README.md
uv run easy-claw dev docs summarize docs --output reports/summary.md
```

#### `tools search` — 联网搜索

```powershell
uv run easy-claw dev tools search "DeepSeek API function calling"
```

#### `tools run` — 执行命令

```powershell
uv run easy-claw dev tools run "pytest -q"
```

#### `tools python` — 执行 Python 片段

```powershell
uv run easy-claw dev tools python "print('hello from easy-claw')"
```

#### `skills list` — 查看技能

```powershell
uv run easy-claw dev skills list
```

#### `memory list` — 查看记忆

```powershell
uv run easy-claw dev memory list
```

旧的 `docs`、`tools`、`skills`、`memory` 顶层入口暂时保留为隐藏兼容命令，但不再作为普通用户主线。

---

## API 模式（开发者向）

`serve` 命令启动一个本地 FastAPI 服务，主要用于开发和集成：

```powershell
uv run easy-claw serve
# 或通过脚本启动：
.\scripts\start.ps1
```

启动后：

| 路径 | 内容 |
|---|---|
| `http://127.0.0.1:8787/` | API 状态说明（不再是 404） |
| `http://127.0.0.1:8787/health` | 健康检查 |
| `http://127.0.0.1:8787/docs` | Swagger 接口文档 |
| `http://127.0.0.1:8787/sessions` | 会话列表 |

**重要**：`/docs` 是 Swagger 接口文档，不是聊天界面。当前 **没有 Web UI**。如果你只是想使用 AI 助手，请用 `uv run easy-claw chat --interactive`，不需要启动 `serve`。

API 模式适用于：
- 开发 Web UI 时作为后端
- 集成到其他自动化流程
- 调试和测试 API 端点

---

## 当前限制

v0.3 已实现可用的终端交互式助手和交互式流式输出，但以下能力尚未完成：

- **没有 Web UI**：交互式对话只在终端中进行，`serve` 启动后没有聊天界面
- **单用户本地运行**：没有多用户、多租户支持
- **工具执行无沙箱**：默认 `EASY_CLAW_APPROVAL_MODE=permissive`，优先保证可用性；本地命令、Python 和报告写入会直接运行并记录审计日志
- **暂无 MCP Server 接入**：工具集为内置实现，尚未对接外部 MCP Server
- **暂无长期记忆 Provider**：记忆存储在本地 SQLite，未接入 Mem0 或 Honcho
- **流式范围有限**：`chat --interactive` 支持流式输出和工具调用显示；`docs summarize`、API `/runs` 和 Web UI 尚未实现流式输出

---

## 执行与审批模式

默认配置偏向个人助手的可用性：

```env
EASY_CLAW_APPROVAL_MODE=permissive
EASY_CLAW_EXECUTION_MODE=local
```

`permissive` 模式下，Agent 在对话中可以直接调用本地工具执行常规任务，例如运行 `pytest`、读取文件、执行临时 Python 片段和写 Markdown 报告。命令仍然有工作目录、超时、输出截断和审计日志，但不会默认弹出人工确认。

如果你希望恢复更谨慎的行为，可以设置：

```env
EASY_CLAW_APPROVAL_MODE=balanced
```

`balanced` / `strict` 会对命令执行、Python 执行和文件写入启用人工确认。

---

## 设计原则

- **Windows first**：安装、启动和脚本优先为 Windows 用户设计。
- **Local first**：默认本机运行，SQLite 存储，无需云服务。
- **uv managed**：依赖管理、虚拟环境和命令入口统一由 `uv` 处理。
- **Reuse first**：Agent 编排复用 LangChain/LangGraph，不自行实现编排引擎。
- **Usability first**：默认优先可用性，让 Agent 能主动读文件、运行测试、执行 Python 和写报告；需要更谨慎时可切换审批模式。

---

## 当前版本范围（v0.2）

已包含：

- Typer CLI 入口，交互式对话和单次请求模式
- `deepagents` SDK 封装的 Agent Runtime（LangChain + LangGraph）
- 本地工具：文档读取/MarkItDown 转换、DuckDuckGo 搜索、PowerShell 命令执行、Python 片段运行
- FastAPI 服务（`/health`、`/sessions`、`/runs`）
- SQLite 本地存储（sessions、memory_items、audit_logs）
- Markdown Skills 加载和注入
- 执行确认层：LangGraph interrupt + 控制台人工确认
- `FilesystemBackend(virtual_mode=True)` 工作区边界保护

暂不包含：

- Web UI 聊天界面
- MCP Client Adapter
- Docker / WSL2 沙箱
- Mem0 / Honcho 长期记忆
- LangGraph 长任务恢复、API / Web 流式输出
- 多用户权限和桌面客户端

---

## 目录结构

```text
easy-claw/
  pyproject.toml
  uv.lock
  README.md
  .env.example
  docs/
    architecture.md
  scripts/
    start.ps1
  src/
    easy_claw/
      cli.py
      config.py
      skills.py
      workspace.py
      api/
        main.py
      agent/
        runtime.py
      storage/
        db.py
        repositories.py
      tools/
        commands.py
        documents.py
        python_runner.py
        reports.py
        search.py
      workflows/
        document_runs.py
  skills/
    core/
    user/
  tests/
  data/
    easy-claw.db
    checkpoints.sqlite
```

---

## 开发

```powershell
uv sync
uv run easy-claw
uv run pytest
uv run ruff check .
uv run ruff format .
```

详细架构设计见 [docs/architecture.md](docs/architecture.md)。

---

## 路线图

| Phase | 内容 | 状态 |
|---|---|---|
| 0 | 工程蓝图、MVP 范围、架构设计 | 完成 |
| 1 | FastAPI + SQLite + 配置加载 + 基础 CLI | 完成 |
| 2 | 本地文档助手 + 强工具可用性 + 交互式对话 | 完成 |
| 3 | CLI 流式输出与工具调用显示 | 完成 |
| 4 | MCP 工具接入 | 计划中 |
| 5 | 长期记忆（Mem0 / Honcho） | 计划中 |
| 6 | 沙箱款增强（Docker Desktop + WSL2） | 计划中 |
| 7 | LangGraph 长任务与 API / Web 流式输出 | 计划中 |
| 8 | 桌面端和打包 | 计划中 |

---

## 参考资料

- [LangChain Agents](https://docs.langchain.com/oss/python/langchain/agents)
- [LangGraph Overview](https://docs.langchain.com/oss/python/langgraph/overview)
- [MCP Tools](https://modelcontextprotocol.io/docs/concepts/tools)
- [Mem0 Overview](https://docs.mem0.ai/platform/overview)
- [uv Documentation](https://docs.astral.sh/uv/)
