"""Test runner — runs generated code in subprocess isolation."""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TestResult:
    passed: bool
    output: str
    error: str = ""
    exit_code: int = 0
    timed_out: bool = False


class TestRunner:
    """Runs Python test code in isolated subprocesses."""

    def __init__(self, timeout: int = 30) -> None:
        self._timeout = timeout

    def run(self, code: str, test_code: str) -> TestResult:
        """Run test_code against the generated code."""
        combined = f"{code}\n\n{test_code}\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(combined)
            f.flush()
            tmp_path = f.name
        try:
            result = subprocess.run(
                ["python3", tmp_path],
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )
            return TestResult(
                passed=result.returncode == 0,
                output=result.stdout,
                error=result.stderr,
                exit_code=result.returncode,
            )
        except subprocess.TimeoutExpired:
            return TestResult(passed=False, output="", error="Timed out", timed_out=True)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def run_standalone(self, test_code: str) -> TestResult:
        """Run standalone test code (no separate code file)."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(test_code)
            f.flush()
            tmp_path = f.name
        try:
            result = subprocess.run(
                ["python3", tmp_path],
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )
            return TestResult(
                passed=result.returncode == 0,
                output=result.stdout,
                error=result.stderr,
                exit_code=result.returncode,
            )
        except subprocess.TimeoutExpired:
            return TestResult(passed=False, output="", error="Timed out", timed_out=True)
        finally:
            Path(tmp_path).unlink(missing_ok=True)
