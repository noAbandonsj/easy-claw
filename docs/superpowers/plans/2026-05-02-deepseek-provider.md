# DeepSeek Provider 迁移实施计划

> **给 agentic worker 的要求：** 实施本计划时必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans`，并按复选框逐步跟踪。

**目标：** 删除第一版 OpenAI/Ollama 配置口径，把 DeepSeek 作为当前支持的模型 Provider。

**架构：** 应用层继续把模型配置保存为简单字符串。`DeepAgentsRuntime` 内部显式构造 DeepSeek-compatible `ChatOpenAI` 对象，再把该对象交给 DeepAgents。

**技术栈：** Python 3.11+、DeepAgents、LangChain、`langchain-openai`、pytest、uv。

---

### 任务 1：配置测试

**文件：**
- 修改：`tests/test_config.py`

- [ ] **步骤 1：先写失败测试**

```python
def test_load_config_reads_env_overrides(tmp_path, monkeypatch):
    data_dir = tmp_path / "custom-data"
    workspace = tmp_path / "workspace"
    monkeypatch.setenv("EASY_CLAW_DATA_DIR", str(data_dir))
    monkeypatch.setenv("EASY_CLAW_WORKSPACE", str(workspace))
    monkeypatch.setenv("EASY_CLAW_MODEL", "deepseek-v4-pro")
    monkeypatch.setenv("EASY_CLAW_DEVELOPER_MODE", "true")

    config = load_config(cwd=tmp_path)

    assert config.data_dir == data_dir
    assert config.default_workspace == workspace
    assert config.model == "deepseek-v4-pro"
    assert config.developer_mode is True


def test_load_config_exports_deepseek_dotenv_values_for_provider_libraries(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    (tmp_path / ".env").write_text(
        "DEEPSEEK_API_KEY=from-dotenv",
        encoding="utf-8",
    )

    load_config(cwd=tmp_path)

    assert os.environ["DEEPSEEK_API_KEY"] == "from-dotenv"
```

- [ ] **步骤 2：确认红灯**

运行：`uv run pytest tests/test_config.py -q`

预期：测试失败，因为当前断言或示例仍使用旧的 OpenAI 配置。

- [ ] **步骤 3：实现最小改动**

如果测试只需要更新示例值，则不改生产配置代码。现有 `.env` 导出逻辑已经能处理任意 Provider key。

- [ ] **步骤 4：确认绿灯**

运行：`uv run pytest tests/test_config.py -q`

预期：配置测试全部通过。

### 任务 2：运行时模型构造

**文件：**
- 修改：`src/easy_claw/agent/runtime.py`
- 修改：`tests/test_agent_runtime.py`

- [ ] **步骤 1：先写失败测试**

```python
def test_build_deepseek_chat_model_requires_api_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
        _build_deepseek_chat_model("deepseek-v4-pro")


def test_build_deepseek_chat_model_uses_deepseek_endpoint(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    model = _build_deepseek_chat_model("deepseek-v4-pro")

    assert model.model_name == "deepseek-v4-pro"
    assert str(model.openai_api_base).rstrip("/") == "https://api.deepseek.com"
```

- [ ] **步骤 2：确认红灯**

运行：`uv run pytest tests/test_agent_runtime.py -q`

预期：因为 `_build_deepseek_chat_model` 尚不存在而导入失败。

- [ ] **步骤 3：实现 DeepSeek 模型构造**

```python
DEEPSEEK_BASE_URL = "https://api.deepseek.com"


def _build_deepseek_chat_model(model: str):
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("Set DEEPSEEK_API_KEY before running chat without --dry-run.")
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=DEEPSEEK_BASE_URL,
    )
```

把 `DeepAgentsRuntime.run` 里传给 `create_deep_agent` 的 `model=request.model` 改成 `model=_build_deepseek_chat_model(request.model)`。

- [ ] **步骤 4：确认绿灯**

运行：`uv run pytest tests/test_agent_runtime.py -q`

预期：运行时测试全部通过。

### 任务 3：依赖和文档

**文件：**
- 修改：`pyproject.toml`
- 修改：`uv.lock`
- 修改：`.env.example`
- 修改：`README.md`

- [ ] **步骤 1：删除 Ollama 依赖**

从 `pyproject.toml` 删除 `langchain-ollama>=1.0.0`。

- [ ] **步骤 2：刷新锁文件**

运行：`uv lock`

预期：`uv.lock` 不再把 `langchain-ollama` 作为直接依赖。

- [ ] **步骤 3：更新文档示例**

把 OpenAI/Ollama 启动示例替换成：

```env
EASY_CLAW_MODEL=deepseek-v4-pro
DEEPSEEK_API_KEY=你的 API Key
```

- [ ] **步骤 4：检查残留引用**

搜索 `ollama`、`OPENAI_API_KEY`、`openai:gpt`。

预期：活跃启动说明不再指向已删除的 Provider。

### 任务 4：完整验证

**文件：**
- 无新增文件。

- [ ] **步骤 1：运行聚焦测试**

运行：`uv run pytest tests/test_config.py tests/test_agent_runtime.py -q`

预期：聚焦测试全部通过。

- [ ] **步骤 2：运行全量测试**

运行：`uv run pytest -q`

预期：所有测试通过。

- [ ] **步骤 3：运行 lint**

运行：`uv run ruff check .`

预期：无 lint 错误。
