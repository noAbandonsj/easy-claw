from easy_claw.tools.python_runner import run_python_code


def test_run_python_code_captures_output(tmp_path):
    result = run_python_code("print(1 + 1)", cwd=tmp_path, timeout_seconds=5)

    assert result.exit_code == 0
    assert result.stdout.strip() == "2"


def test_run_python_code_removes_temporary_script(tmp_path):
    result = run_python_code("print('done')", cwd=tmp_path, timeout_seconds=5)

    assert result.exit_code == 0
    assert list(tmp_path.glob(".easy_claw_*.py")) == []


def test_run_python_code_reports_script_errors(tmp_path):
    result = run_python_code("raise SystemExit(7)", cwd=tmp_path, timeout_seconds=5)

    assert result.exit_code == 7


def test_run_python_code_marks_timeout_and_cleans_up(tmp_path):
    result = run_python_code(
        "import time; time.sleep(2)",
        cwd=tmp_path,
        timeout_seconds=1,
    )

    assert result.timed_out is True
    assert result.exit_code == 124
    assert list(tmp_path.glob(".easy_claw_*.py")) == []
