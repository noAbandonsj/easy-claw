from easy_claw.agent import approvals


def test_yes_no_selection_defaults_to_yes_on_enter():
    output: list[str] = []
    keys = iter(["enter"])
    selector = getattr(approvals, "_read_yes_no_selection", None)
    assert selector is not None

    result = selector(
        "允许执行？",
        default=True,
        read_key=lambda: next(keys),
        write=output.append,
    )

    assert result is True
    assert "[Yes]" in "".join(output)


def test_yes_no_selection_can_choose_no_before_enter():
    output: list[str] = []
    keys = iter(["right", "enter"])
    selector = getattr(approvals, "_read_yes_no_selection", None)
    assert selector is not None

    result = selector(
        "允许执行？",
        default=True,
        read_key=lambda: next(keys),
        write=output.append,
    )

    assert result is False
    assert "[No]" in "".join(output)


def test_console_approval_reviewer_uses_yes_no_selection(monkeypatch):
    prompts = []

    def fake_selection(prompt: str, *, default: bool = True) -> bool:
        prompts.append((prompt, default))
        return True

    monkeypatch.setattr(
        "easy_claw.agent.approvals._read_yes_no_selection",
        fake_selection,
    )

    decisions = approvals.ConsoleApprovalReviewer().review(
        [
            {
                "action_requests": [
                    {
                        "name": "run_command",
                        "args": {"command": "pytest -q"},
                        "description": "run tests",
                    }
                ]
            }
        ]
    )

    assert decisions == [{"type": "approve"}]
    assert prompts == [("允许执行？", True)]
