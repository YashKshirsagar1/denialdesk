"""Test that the eval runner script works end-to-end with --mock."""
import subprocess
import sys
import os


def test_mock_eval_runs():
    script = os.path.join(os.path.dirname(__file__), "..", "scripts", "run_eval.py")
    result = subprocess.run(
        [sys.executable, script, "--mock"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Eval runner failed:\n{result.stdout}\n{result.stderr}"
    assert "Root cause accuracy" in result.stdout, (
        f"Expected summary not found in output:\n{result.stdout}"
    )
