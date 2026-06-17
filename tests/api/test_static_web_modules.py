from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


def test_static_web_module_units_pass_node_tests():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is not installed; skipping browser module unit tests")

    root = Path(__file__).resolve().parents[2]
    test_file = Path(__file__).with_name("static_web_modules.test.mjs")
    result = subprocess.run(
        [node, "--test", str(test_file)],
        cwd=root,
        check=False,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        text=True,
        timeout=30,
    )

    output = (result.stdout or "") + (result.stderr or "")
    assert result.returncode == 0, output
