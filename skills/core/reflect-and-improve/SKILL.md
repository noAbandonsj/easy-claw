---
name: reflect-and-improve
description: 复盘 easy-claw 的执行过程，并在用户明确要求记住、沉淀、改进流程、总结经验、更新 skill 或以后都按某种方式处理时，提炼可复用规则并建议写入记忆或创建/修改 easy-claw 技能。
---

# Reflect And Improve

## 使用边界

这个技能是 Self-Improving Agent 思路的 easy-claw 改写版。它用于按需复盘和沉淀经验，不是后台自动 hooks、heartbeat 或自我修改系统。

只在用户明确表达以下意图时使用：

- “记住这个规则”
- “以后遇到这种情况都这样做”
- “把这次经验沉淀下来”
- “复盘一下刚才哪里可以改进”
- “把这个流程变成 skill”
- “更新/改进某个 skill”

不要在每轮对话后自动运行。不要在没有用户确认时修改技能文件、长期记忆或项目文档。

## 复盘流程

1. 先确认要复盘的对象：一次任务、一个错误、一条用户纠正、一个重复流程，或一个已有 skill。
2. 提取事实：发生了什么、用户纠正了什么、最终采用了什么做法。
3. 提取经验：哪些判断、步骤、命令、路径或格式以后可以复用。
4. 判断沉淀位置：
   - 临时提醒：直接在当前回答中说明即可。
   - 跨会话偏好：如果 Basic Memory MCP 可用，建议写入记忆。
   - 项目专属流程：建议写入当前工作区 `.easy-claw/skills/<skill-name>/SKILL.md`。
   - 通用工作流：建议用 `create-skill` 创建或修改用户全局 `%USERPROFILE%\.easy-claw\skills\<skill-name>\SKILL.md`。
   - easy-claw 本体流程：只有在维护 easy-claw 且用户明确要求内置时，才建议修改 `skills/core/`。
5. 给出最小改动建议：说明要新增或修改哪条规则、放在哪里、为什么值得长期保留。
6. 在写入任何文件或记忆前，先征求用户确认，除非用户已经明确要求执行。

## 沉淀格式

把经验写成具体、可执行的规则，而不是泛泛总结。

优先格式：

```markdown
- 当 <触发条件> 时，先 <关键步骤>，再 <验证方式>。
```

示例：

```markdown
- 当用户要求新增 easy-claw 内置 skill 时，先为内置列表添加失败测试，再创建 `skills/core/<name>/SKILL.md`，最后更新 README、docs/skills.md 并运行 ruff、pytest 和 skills list。
```

如果经验已经稳定、重复出现，并且能被清楚触发，建议升级为 skill。创建或改写 skill 时使用 `create-skill` 的流程。

## 更新已有技能

修改已有 skill 前：

1. 读取目标 `SKILL.md`。
2. 判断新经验是否属于该 skill 的职责范围。
3. 保持正文简洁；只添加必要步骤、边界或验证要求。
4. 避免添加 README、安装指南、变更日志等旁路文档。
5. 修改后运行 `uv run easy-claw dev skills list --all-sources` 或在聊天中执行 `/skills` 验证来源仍可加载。

## 输出要求

复盘输出应包含：

- 事实：刚才发生了什么。
- 可复用经验：以后要怎么做。
- 建议沉淀位置：记忆、项目 skill、用户全局 skill 或内置 skill。
- 下一步：是否需要创建或更新 skill。

如果用户只是要求复盘，不要直接写文件。如果用户要求执行沉淀，则按确认后的目标路径修改。
