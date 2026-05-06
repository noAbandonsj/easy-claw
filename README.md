# easy-claw

easy-claw 是一个 Windows 优先的本地 AI 助手。你可以在终端里用自然语言让它总结文档、分析项目、搜索资料、运行测试、读取文件和执行常见开发任务。

它不是复杂平台，也不要求你理解容器、集群或插件系统。配置好模型后，运行启动脚本就能进入对话。

---

## 快速开始

### 1. 准备环境

请先安装：

- Python 3.11 或更高版本
- Git
- [uv](https://docs.astral.sh/uv/)

进入项目目录：

```powershell
cd D:\Pathon\Programs\easy-claw
```

### 2. 配置模型

复制配置模板：

```powershell
Copy-Item .env.example .env
```

编辑 `.env`，至少填写模型名称和密钥：

```env
EASY_CLAW_MODEL=deepseek-v4-pro
EASY_CLAW_API_KEY=你的密钥
```

如果你使用的模型服务不是 DeepSeek，还需要设置兼容 OpenAI API 的地址：

```env
EASY_CLAW_BASE_URL=https://你的模型服务地址/v1
```

### 3. 一键启动

推荐新手直接运行启动脚本：

```powershell
.\scripts\start.ps1
```

脚本会自动完成三件事：

1. 同步 Python 依赖。
2. 初始化本地 SQLite 数据库。
3. 启动交互式聊天。

看到输入提示符后，就可以开始输入自然语言任务：

```text
> 帮我总结 README.md 的主要内容
> 分析这个项目的代码结构
> 运行 pytest 看看有没有失败的测试
```

输入 `exit`、`quit` 或 `:q` 可以退出。

### 4. 检查环境

如果启动前想检查配置，可以运行：

```powershell
.\scripts\doctor.ps1
```

也可以直接运行 CLI 诊断：

```powershell
uv run easy-claw doctor
```

---

## 常用命令

| 命令 | 说明 |
|---|---|
| `.\scripts\start.ps1` | 同步依赖、初始化数据库并启动聊天 |
| `.\scripts\start.ps1 -Mcp` | 一键配置默认 MCP，并启动聊天 |
| `.\scripts\setup-mcp.ps1` | 只配置默认 MCP，不启动聊天 |
| `.\scripts\doctor.ps1` | 检查 uv、Git、项目配置和浏览器状态 |
| `uv run easy-claw chat --interactive` | 手动启动交互式聊天 |
| `uv run easy-claw chat --dry-run "你好"` | 不调用模型，只测试命令链路 |
| `uv run easy-claw init-db` | 初始化本地数据库 |
| `uv run easy-claw doctor` | 打印当前环境诊断信息 |

开发者调试命令：

| 命令 | 说明 |
|---|---|
| `uv run easy-claw dev tools search "关键词"` | 调试联网搜索工具 |
| `uv run easy-claw dev tools run "pytest -q"` | 调试本地命令执行工具 |
| `uv run easy-claw dev tools python "print('hello')"` | 调试 Python 片段执行工具 |
| `uv run easy-claw dev skills list` | 查看可用技能 |

---

## API 服务

普通聊天不需要启动 API 服务。只有开发 Web 界面或做外部集成时才需要：

```powershell
.\scripts\start.ps1 -ApiServer
```

启动后可访问：

| 地址 | 说明 |
|---|---|
| `http://127.0.0.1:8787/` | 本地 Web 聊天页面 |
| `http://127.0.0.1:8787/health` | 健康检查 |
| `http://127.0.0.1:8787/docs` | 接口文档 |
| `http://127.0.0.1:8787/sessions` | 会话列表 |

注意：`/docs` 是接口文档，不是聊天界面。聊天页面在根路径 `/`，底层通过 `/ws/chat` 建立 WebSocket 连接。

---

## 默认配置

默认配置偏向个人本地助手的易用性：

```env
EASY_CLAW_APPROVAL_MODE=permissive
EASY_CLAW_EXECUTION_MODE=local
EASY_CLAW_MCP_ENABLED=auto
EASY_CLAW_BROWSER_ENABLED=false
EASY_CLAW_MAX_MODEL_CALLS=40
EASY_CLAW_MAX_TOOL_CALLS=100
```

含义：

- `permissive`：优先保证可用性，本地命令、Python 片段和文件写入默认不弹出确认。
- `local`：在当前 Windows 本机执行工具。
- `auto`：如果存在 `mcp_servers.json`，自动尝试加载 MCP 工具；配置缺失或某个服务失败时不会阻断启动。
- 浏览器工具默认关闭，需要时手动开启。

如果你希望更谨慎，可以设置：

```env
EASY_CLAW_APPROVAL_MODE=balanced
```

`balanced` / `strict` 会对命令执行、Python 执行和文件写入启用人工确认。

---

## MCP 工具

MCP 默认是 `auto` 模式，但仓库只提供示例配置，不直接启用本机 MCP 服务。这样新手即使没有安装额外工具，也能稳定启动。

如果需要 MCP 工具，推荐用启动脚本一键配置：

```powershell
.\scripts\start.ps1 -Mcp
```

这会自动完成：

1. 创建项目内 Basic Memory 目录 `data\basic-memory`。
2. 注册 Basic Memory 项目 `easy-claw`，指向这个目录。
3. 把 Git MCP 指向当前项目仓库。
4. 如果 `.env` 或系统环境变量里有 `GITHUB_PERSONAL_ACCESS_TOKEN`，启用 GitHub MCP。
5. 如果 `.env` 或系统环境变量里有 `AMAP_MAPS_API_KEY` 且本机有 `npx`，启用高德地图 MCP。
6. 生成或合并本机配置 `mcp_servers.json`，已有自定义服务会保留。
7. 启动交互式聊天。

如果只想配置 MCP、不启动聊天，可以运行：

```powershell
.\scripts\setup-mcp.ps1
```

默认 MCP 说明：

| 服务 | 默认行为 | 额外要求 |
|---|---|---|
| `basic-memory` | 一键脚本自动启用 | `uvx` |
| `git` | 一键脚本自动启用，并指向当前项目 | `uvx` |
| `github` | 配置 `GITHUB_PERSONAL_ACCESS_TOKEN` 后启用 | GitHub 个人访问令牌 |
| `amap-maps` | 配置 `AMAP_MAPS_API_KEY` 且本机有 `npx` 后启用 | Node.js / npx、高德地图密钥 |

`mcp_servers.json.example` 包含以上 4 个服务示例。示例中的 `${GITHUB_PERSONAL_ACCESS_TOKEN}` 和 `${AMAP_MAPS_API_KEY}` 会在启动时从环境变量或 `.env` 读取；`auto` 模式下缺少变量的服务会被跳过，不会阻断启动。

之前示例里曾包含 `filesystem`，现在不作为默认项，因为 easy-claw 和 DeepAgents 已经有文件读取、写入和命令执行能力；再默认启用 filesystem MCP 会重复能力，还会额外引入 Node / npx 依赖。

如果你确实需要 MCP filesystem，可以自行把它加入本机 `mcp_servers.json`。

---

## 浏览器工具

浏览器工具默认关闭。首次使用前先安装浏览器内核：

```powershell
uv run playwright install chromium
```

然后在 `.env` 中开启：

```env
EASY_CLAW_BROWSER_ENABLED=true
EASY_CLAW_BROWSER_HEADLESS=false
```

开启后，Agent 可以在对话中打开网页、点击链接和提取页面内容。`headless=false` 时，Windows 用户可以看到浏览器窗口。

---

## 当前能力范围

当前版本包含：

- Typer 命令行入口。
- 交互式聊天和单次请求。
- DeepAgents / LangChain / LangGraph 运行时封装。
- 本地工具：文档读取、MarkItDown 转换、联网搜索、PowerShell 命令执行、Python 片段执行。
- FastAPI 服务、WebSocket 聊天接口和本地 Web 页面。
- SQLite 会话存储和审计日志。
- Markdown 技能加载。
- LangGraph 中断审批机制。
- Playwright 浏览器工具接入。
- MCP 工具接入，默认包含 Basic Memory、Git，配置密钥后可启用 GitHub 和高德地图。

当前限制：

- 只面向单用户本地运行。
- 默认没有 Docker / WSL2 沙箱。
- Web 端审批流还比较基础。
- 长期记忆目前主要通过 MCP 的 basic-memory 接入，尚未集成 Mem0 或 Honcho 这类独立记忆服务。
- 暂无桌面客户端和安装包。

---

## 项目结构

```text
easy-claw/
  pyproject.toml
  uv.lock
  README.md
  .env.example
  mcp_servers.json.example
  docs/
    architecture.md
    mvp-first-version-thinking.md
  scripts/
    start.ps1
    doctor.ps1
    setup-mcp.ps1
  src/
    easy_claw/
      cli.py
      config.py
      api/
      agent/
      storage/
      tools/
  skills/
    core/
    user/
  tests/
```

本地运行生成的数据默认放在 `data/`，该目录不会提交到仓库。

---

## 开发命令

```powershell
uv sync
uv run pytest
uv run ruff check .
uv run ruff format .
```

详细架构见 [docs/architecture.md](docs/architecture.md)。

---

## 路线图

| 阶段 | 内容 | 状态 |
|---|---|---|
| 0 | 工程蓝图、MVP 范围、架构设计 | 完成 |
| 1 | FastAPI、SQLite、配置加载、基础 CLI | 完成 |
| 2 | 本地文档助手、强工具可用性、交互式对话 | 完成 |
| 3 | CLI 流式输出和工具调用显示 | 完成 |
| 4 | MCP 工具接入 | 完成 |
| 5 | basic-memory 记忆接入 | 完成 |
| 6 | 沙箱增强 | 计划中 |
| 7 | 长任务恢复 | 计划中 |
| 8 | 桌面端和打包 | 计划中 |

---

## 参考资料

- [LangChain 文档](https://docs.langchain.com/oss/python/langchain/agents)
- [LangGraph 文档](https://docs.langchain.com/oss/python/langgraph/overview)
- [MCP 文档](https://modelcontextprotocol.io/docs/concepts/tools)
- [uv 文档](https://docs.astral.sh/uv/)
