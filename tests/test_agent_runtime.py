from dataclasses import dataclass

from langgraph.types import Command

from easy_claw.agent.runtime import (
    AgentRequest,
    FakeAgentRuntime,
    StaticApprovalReviewer,
    _invoke_with_approval,
)


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


@dataclass
class FakeInterrupt:
    value: object


class FakeAgent:
    def __init__(self):
        self.inputs = []

    def invoke(self, input_value, config):
        self.inputs.append(input_value)
        if len(self.inputs) == 1:
            return {
                "__interrupt__": (
                    FakeInterrupt(
                        {
                            "action_requests": [
                                {
                                    "name": "write_file",
                                    "args": {"file_path": "report.md"},
                                    "description": "write report",
                                }
                            ],
                            "review_configs": [
                                {
                                    "action_name": "write_file",
                                    "allowed_decisions": ["approve", "reject"],
                                }
                            ],
                        }
                    ),
                )
            }
        return {"messages": [{"role": "assistant", "content": "done"}]}


def test_invoke_with_approval_resumes_after_interrupt():
    agent = FakeAgent()
    reviewer = StaticApprovalReviewer(approve=True)

    result = _invoke_with_approval(
        agent,
        {"messages": [{"role": "user", "content": "write report"}]},
        config={"configurable": {"thread_id": "thread-1"}},
        reviewer=reviewer,
    )

    assert result["messages"][-1]["content"] == "done"
    assert isinstance(agent.inputs[1], Command)
    assert agent.inputs[1].resume == {"decisions": [{"type": "approve"}]}
