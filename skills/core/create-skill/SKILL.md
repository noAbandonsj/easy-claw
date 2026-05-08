---
name: create-skill
description: 创建、改写或检查 easy-claw/DeepAgents 技能。适用于用户想把自己的流程沉淀成 skill、从外部导入 skill、修复 SKILL.md、选择技能安装目录，或让 easy-claw 生成可复用的技能目录。
---

# Create Skill

## 工作流

1. 先确认用户的目标：这个技能要解决什么任务、用户会怎样触发它、输入来自哪里、输出应该是什么格式。
2. 选择安装位置：
   - 项目专属技能放在当前工作区的 `.easy-claw/skills/<skill-name>/`。
   - 跨项目复用技能放在 `%USERPROFILE%\.easy-claw\skills\<skill-name>\`。
   - 只有在维护 easy-claw 本体且用户明确要求内置时，才放到仓库的 `skills/core/<skill-name>/`。
3. 使用小写字母、数字和连字符生成技能名，保持简短明确，例如 `summarize-meetings`。
4. 创建目录式技能，而不是只创建零散 Markdown 文件：

```text
<skill-name>/
  SKILL.md
  references/   # 可选
  scripts/      # 可选
  assets/       # 可选
```

只在确实需要时创建 `references/`、`scripts/` 或 `assets/`；不要添加 README、安装指南、变更日志等额外说明文件。

## 编写 SKILL.md

`SKILL.md` 必须包含 YAML frontmatter：

```markdown
---
name: <skill-name>
description: <这个技能做什么，以及哪些用户请求应该触发它>
---
```

`description` 是触发技能的主要依据，要写清楚“做什么”和“什么时候使用”。正文只保留执行步骤、判断规则和必要约束。

正文写法：

- 使用命令式步骤，避免长篇背景说明。
- 把详细参考资料放进 `references/`，并在 `SKILL.md` 中说明何时读取。
- 把稳定、容易写错、需要重复执行的逻辑放进 `scripts/`。
- 把模板、图片、示例文件等输出素材放进 `assets/`。
- 如果技能依赖特定工具、API、环境变量或 MCP 服务，在正文中写清楚前置条件。

## 导入外部技能

导入外部 skill 时先检查：

1. 是否有 `SKILL.md`，frontmatter 是否包含 `name` 和 `description`。
2. 是否引用了 easy-claw 没有的专用工具、命令、路径或 UI 元数据。
3. 是否有辅助脚本、模板或参考资料；保留整个目录，不要只复制 `SKILL.md`。
4. 是否需要把 Codex、Claude 或其它客户端专属说明改写成 easy-claw/DeepAgents 可执行的通用流程。

如果外部 skill 含有 `agents/openai.yaml` 等客户端元数据，可以保留，但不要依赖它完成 easy-claw 的触发逻辑；触发逻辑必须写在 `SKILL.md` 的 `description` 中。

## 验证

创建或改写后：

1. 重新读取目标 `SKILL.md`，检查名称、触发描述和步骤是否一致。
2. 确认目录位于 easy-claw 会自动收集的路径。
3. 运行 `uv run easy-claw dev skills list --all-sources` 或在聊天中执行 `/skills`，确认来源和数量符合预期。
4. 对包含脚本的技能，至少运行一次代表性脚本或静态检查。
