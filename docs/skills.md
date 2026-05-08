# easy-claw Skills

easy-claw 使用 DeepAgents 原生 skill 机制。一个 skill 是一个目录，目录中必须包含 `SKILL.md`，也可以包含辅助脚本、模板、参考资料等文件。easy-claw 会收集整个 skill 目录，而不是只读取 `SKILL.md`。

## 目录格式

推荐格式：

```text
my-skill/
  SKILL.md
  helper.py
  references/
    notes.md
```

`SKILL.md` 至少包含 `name` 和 `description`：

```markdown
---
name: analyze-django-project
description: 分析 Django 项目的结构、配置、路由、模型和测试风险。
---

# Analyze Django Project

1. 先读取 pyproject.toml、manage.py 和 settings.py。
2. 检查 apps、urls、models、migrations 和 tests。
3. 输出架构、启动命令、测试命令、风险和建议。
```

DeepAgents 启动时只读取 skill 的名称和描述；当用户任务匹配某个 skill 时，Agent 再读取完整 `SKILL.md` 和旁边的辅助文件。

## 内置技能

easy-claw 当前内置这些技能：

- `analyze-project`：分析本地项目结构，并总结架构、命令和风险。
- `summarize-docs`：将选中的本地文档总结为简洁的 Markdown 报告。
- `create-skill`：创建、改写或检查 easy-claw/DeepAgents 技能。

如果你想把自己的流程沉淀成技能，可以直接在聊天里说：

```text
帮我创建一个用于总结会议纪要的技能
把这个流程沉淀成 skill
检查这个外部 skill 能不能导入 easy-claw
```

`create-skill` 会帮助选择项目目录或用户全局目录，生成标准 `SKILL.md` 结构，并提醒你用 `/skills` 或 `uv run easy-claw dev skills list --all-sources` 验证加载结果。

## 自动收集路径

easy-claw 会按低优先级到高优先级收集以下路径。后面的来源可以覆盖前面同名 skill。

内置来源：

```text
<easy-claw 项目根>\skills
```

用户全局来源：

```text
%USERPROFILE%\.deepagents\skills
%USERPROFILE%\.deepagents\agent\skills
%USERPROFILE%\.agents\skills
%USERPROFILE%\.easy-claw\skills
%USERPROFILE%\.claude\skills
```

当前工作区项目来源：

```text
<workspace>\.deepagents\skills
<workspace>\.agents\skills
<workspace>\.easy-claw\skills
<workspace>\skills
```

`%USERPROFILE%\.codex\skills` 不会默认收集，因为其中通常包含 Codex 运行时专用 skill，可能引用 easy-claw 不具备的工具或流程。

## 查看已加载来源

运行：

```powershell
uv run easy-claw dev skills list --all-sources
```

输出包含：

- `scope`：来源范围，`builtin`、`user` 或 `project`
- `label`：来源名称
- `skill_count`：该来源下直接包含的 skill 数量
- `backend_path`：传给 DeepAgents 的虚拟路径
- `filesystem_path`：本机实际路径

如果只想查看指定目录内的 Markdown skill：

```powershell
uv run easy-claw dev skills list --skills-root skills
```

## 安装外部 skill

如果外部 skill 已经是 `SKILL.md` 目录格式，可以直接复制整个目录到任一自动收集路径。例如：

```text
%USERPROFILE%\.easy-claw\skills\my-skill\SKILL.md
```

或者放到某个项目内：

```text
<workspace>\.easy-claw\skills\my-skill\SKILL.md
```

放到项目内的 skill 只在该工作区生效，适合保存项目专属流程。放到用户全局目录的 skill 会在所有 easy-claw 工作区中可用。

## 注意事项

- skill 是行为说明和参考资料，不是安全沙箱。
- skill 辅助脚本只有在 Agent 调用工具读取或执行时才会产生效果。
- 如果一个 skill 依赖特定工具，最好在 `SKILL.md` 中写清楚前置条件。
- 同名 skill 会被更高优先级来源覆盖。
