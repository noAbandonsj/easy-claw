from easy_claw.agent.runtime import AgentRequest, FakeAgentRuntime


def test_fake_agent_runtime_returns_deterministic_result(tmp_path):
    runtime = FakeAgentRuntime()

    result = runtime.run(
        AgentRequest(
            prompt="hello",
            thread_id="thread-1",
            workspace_path=tmp_path,
            model=None,
            skills=[],
            memories=[],
        )
    )

    assert result.content == "easy-claw dry run: hello"
    assert result.thread_id == "thread-1"
