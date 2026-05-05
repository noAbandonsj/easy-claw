from easy_claw.tools.commands import run_command


def test_run_command_captures_output(tmp_path):
    result = run_command("python -c \"print('hello')\"", cwd=tmp_path, timeout_seconds=5)

    assert result.exit_code == 0
    assert result.stdout.strip() == "hello"


def test_run_command_truncates_long_output(tmp_path):
    result = run_command(
        "python -c \"print('x' * 100)\"",
        cwd=tmp_path,
        timeout_seconds=5,
        max_output_chars=10,
    )

    assert result.truncated is True
    assert len(result.stdout) <= 10


def test_run_command_marks_timeout(tmp_path):
    result = run_command(
        'python -c "import time; time.sleep(2)"',
        cwd=tmp_path,
        timeout_seconds=1,
    )

    assert result.timed_out is True
    assert result.exit_code == 124
