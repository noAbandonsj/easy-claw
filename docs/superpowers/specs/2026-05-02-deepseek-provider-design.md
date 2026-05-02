# DeepSeek Provider 迁移设计

## 目标

删除第一版代码路径里的 Ollama 支持，把 DeepSeek 作为文档和运行时默认支持的模型 Provider。

## 范围

应用通过 DeepSeek 的 OpenAI-compatible chat completions endpoint 调用模型。文档默认模型是 `deepseek-v4-pro`，使用 `DEEPSEEK_API_KEY` 和 `https://api.deepseek.com`。

Ollama 示例和依赖需要删除。OpenAI 专属示例替换成 DeepSeek 示例。现有 session 存储继续保留通用的 `model` 字段，因为它保存的是用户选择的模型名，不是 Provider 实现。

## 架构

`DeepAgentsRuntime` 把配置里的模型名转换成 `langchain_openai.ChatOpenAI` 实例，并显式设置 DeepSeek 的 `base_url` 和 `api_key`。这样可以避开 DeepAgents 内置 `openai:*` profile 默认启用的 OpenAI Responses API 路径，改走 DeepSeek 兼容的 Chat Completions 路径。

`load_config` 继续负责读取 `.env`，并把 Provider 环境变量导出给下游库。当前不新增 Provider 注册表。

## 数据流

1. 用户设置 `EASY_CLAW_MODEL=deepseek-v4-pro`。
2. 用户设置 `DEEPSEEK_API_KEY`。
3. CLI/API 用模型字符串创建 `AgentRequest`。
4. `DeepAgentsRuntime` 构造 `ChatOpenAI(model=model, base_url="https://api.deepseek.com", api_key=...)`。
5. DeepAgents 接收已经构造好的 chat model 对象。

## 错误处理

缺少 `EASY_CLAW_MODEL` 时保留现有配置错误。缺少 `DEEPSEEK_API_KEY` 时，在创建 Agent 之前抛出清晰的运行时配置错误。

## 测试

测试覆盖 `.env` 导出 `DEEPSEEK_API_KEY`、默认示例使用 `deepseek-v4-pro`，以及在不发起真实模型请求的情况下构造 DeepSeek-compatible `ChatOpenAI` 对象。
