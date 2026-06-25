"""Runs the end-to-end smoke test as an isolated subprocess.

It is run out-of-process so the third-party stubs it installs do not leak into
the rest of the (real) test session.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_smoke_end_to_end():
    result = subprocess.run(
        [sys.executable, "-m", "tests.smoke.run_smoke"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    output = result.stdout + result.stderr
    assert result.returncode == 0, f"smoke test failed:\n{output}"
    assert "0 failed" in output, output
