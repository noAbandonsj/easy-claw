# CLI 和聊天内命令

easy-claw 的主入口是聊天界面：

```powershell
uv run easy-claw
```

进入聊天后，日常操作优先使用 `/` 命令。外部 CLI 仍然保留，主要用于脚本、诊断和开发调试。

## Slash 命令

输入 `/help` 查看完整命令列表，输入 `/help <command>` 查看某个命令的说明。

| 命令 | 说明 |
|---|---|
| `/help [command]` | 显示聊天内命令，或查看某个命令的用法 |
| `/exit` | 退出助手；也可以输入 `exit`、`quit` 或 `:q` |
| `/clear` | 清空对话历史并开始新会话 |
| `/status` | 显示模型、工作区、Skill、MCP、浏览器和 token 用量 |
| `/save <path>` | 把当前对话保存为 Markdown 文件 |
| `/workspace <path>` | 切换后续任务使用的工作区 |
| `/model <name>` | 切换后续请求使用的模型 |
| `/doctor` | 查看本地配置、数据库、MCP 和浏览器诊断 |
| `/skills` | 查看本次会话自动收集的 skill 来源 |
| `/mcp` | 查看 MCP 模式、配置文件和服务数量 |
| `/browser` | 查看浏览器工具开关和 Playwright 安装状态 |
| `/sessions` | 列出历史聊天会话 |
| `/resume <session-id>` | 恢复历史会话，ID 输入前 8 位即可 |
| `/delete-session <session-id>` | 删除聊天会话及其检查点 |

`/delete-session` 在真实终端里会要求确认。如果通过管道或非交互输入执行，需要写成：

```text
/delete-session <session-id> --force
```

## 推荐流程

常规聊天：

```powershell
uv run easy-claw
```

查看当前能力：

```text
/status
/skills
/mcp
/browser
```

切换上下文：

```text
/workspace D:\Pathon\Programs\some-project
/model deepseek-v4-pro
```

管理历史：

```text
/sessions
/resume 1234abcd
/clear
```

## 外部 CLI

外部 CLI 适合初始化、脚本和开发调试。完整列表可以运行：

```powershell
uv run easy-claw --help
```

常用命令：

| 命令 | 说明 |
|---|---|
| `uv run easy-claw` | 进入聊天界面 |
| `uv run easy-claw chat --dry-run "你好"` | 不调用模型，只测试命令链路 |
| `uv run easy-claw doctor` | 打印完整环境诊断信息 |
| `uv run easy-claw init-db` | 初始化本地 SQLite 数据库 |
| `uv run easy-claw serve` | 启动本地 API 和 Web 页面 |
| `uv run easy-claw dev skills list --all-sources` | 以 TSV 查看自动收集的 skill 来源 |
| `uv run easy-claw dev tools search "关键词"` | 调试联网搜索工具 |
| `uv run easy-claw dev tools run "pytest -q"` | 调试本地命令执行工具 |
| `uv run easy-claw dev tools python "print('hello')"` | 调试 Python 片段执行工具 |

历史会话也保留外部 CLI，便于脚本使用：

| 命令 | 说明 |
|---|---|
| `uv run easy-claw list-sessions` | 列出历史聊天会话 |
| `uv run easy-claw resume-session <session-id>` | 恢复已有聊天会话 |
| `uv run easy-claw delete-session <session-id>` | 删除聊天会话及其检查点 |

同样的分组写法也可用：

```powershell
uv run easy-claw sessions list
uv run easy-claw sessions resume <session-id>
uv run easy-claw sessions delete <session-id>
```

