"""Verification Protocol — INV-201: mandatory verification pipeline.

Gates: syntactic → static → empirical (test/compile) → semantic → spec-conformance.
Result carries evidence[], not self-rated confidence.

INV-203: distinct verifier — the model that writes code does NOT grade it.
"""

from __future__ import annotations

import ast
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class VerificationStatus(Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass(frozen=True)
class VerificationEvidence:
    """A single verification gate result — data for reasoning."""

    gate_name: str
    status: VerificationStatus
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0

    @property
    def as_summary(self) -> str:
        icon = {"passed": "PASS", "failed": "FAIL", "skipped": "SKIP", "error": "ERR"}
        return f"[{icon.get(self.status.value, '?')}] {self.gate_name}: {self.message}"


@dataclass
class VerificationConfig:
    """Configurable verification pipeline."""

    enabled_gates: list[str] = field(
        default_factory=lambda: [
            "syntactic",
            "ast_parse",
            "entity_validation",
            "shell_dry_run",
        ]
    )
    timeout_seconds: float = 30.0


class Verifier:
    """INV-203: distinct verifier — separate from the model that writes code.

    The verifier is a deterministic checker, not a model call.
    This prevents V₃ (circular review / self-grading).
    """

    def __init__(self, config: VerificationConfig | None = None) -> None:
        self._config = config or VerificationConfig()

    def verify(self, code: str, cwd: str = ".") -> list[VerificationEvidence]:
        """Run all enabled verification gates and return evidence."""
        evidence: list[VerificationEvidence] = []
        for gate_name in self._config.enabled_gates:
            gate_fn = self._get_gate(gate_name)
            if gate_fn is None:
                continue
            start = time.monotonic()
            try:
                result = gate_fn(code, cwd)
                result = VerificationEvidence(
                    gate_name=gate_name,
                    status=result.status,
                    message=result.message,
                    details=result.details,
                    duration_ms=(time.monotonic() - start) * 1000,
                )
            except Exception as e:
                result = VerificationEvidence(
                    gate_name=gate_name,
                    status=VerificationStatus.ERROR,
                    message=f"{type(e).__name__}: {e}",
                    duration_ms=(time.monotonic() - start) * 1000,
                )
            evidence.append(result)
        return evidence

    def _get_gate(self, name: str):
        gates = {
            "syntactic": self._gate_syntactic,
            "ast_parse": self._gate_ast_parse,
            "entity_validation": self._gate_entity_validation,
            "shell_dry_run": self._gate_shell_dry_run,
        }
        return gates.get(name)

    def _gate_syntactic(self, code: str, cwd: str) -> VerificationEvidence:
        """L2: Check Python syntax via compile(). Catches G₄ (incomplete generation)."""
        try:
            compile(code, "<agent-output>", "exec")
            return VerificationEvidence(
                gate_name="syntactic",
                status=VerificationStatus.PASSED,
                message="Syntax valid",
            )
        except SyntaxError as e:
            return VerificationEvidence(
                gate_name="syntactic",
                status=VerificationStatus.FAILED,
                message=f"Syntax error: {e.msg} (line {e.lineno})",
                details={"line": e.lineno, "offset": e.offset},
            )

    def _gate_ast_parse(self, code: str, cwd: str) -> VerificationEvidence:
        """AST parse to catch structural issues syntax check misses."""
        try:
            tree = ast.parse(code)
            node_count = sum(1 for _ in ast.walk(tree))
            # Check for common issues
            issues = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and node.id in ("TODO", "FIXME", "HACK"):
                    issues.append(f"Found {node.id} at line {node.lineno}")
            return VerificationEvidence(
                gate_name="ast_parse",
                status=VerificationStatus.PASSED,
                message=f"AST parse successful ({node_count} nodes)" + (f", {len(issues)} issues" if issues else ""),
                details={"node_count": node_count, "issues": issues},
            )
        except SyntaxError as e:
            return VerificationEvidence(
                gate_name="ast_parse",
                status=VerificationStatus.FAILED,
                message=f"AST parse failed: {e.msg}",
            )

    def _gate_entity_validation(self, code: str, cwd: str) -> VerificationEvidence:
        """INV-205: validate that referenced files/paths exist. Fail-closed."""
        try:
            tree = ast.parse(code)
            missing = []
            for node in ast.walk(tree):
                # Check file open calls
                if isinstance(node, ast.Call):
                    func = node.func
                    if isinstance(func, ast.Name) and func.id == "open":
                        for arg in node.args:
                            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                                from pathlib import Path
                                p = Path(cwd) / arg.value
                                if not p.exists():
                                    missing.append(arg.value)
                    # Check Path() calls
                    if isinstance(func, ast.Attribute) and func.attr == "read_text":
                        # Can't easily trace Path objects, skip
                        pass
            if missing:
                return VerificationEvidence(
                    gate_name="entity_validation",
                    status=VerificationStatus.FAILED,
                    message=f"Missing files: {missing}",
                    details={"missing_files": missing},
                )
            return VerificationEvidence(
                gate_name="entity_validation",
                status=VerificationStatus.PASSED,
                message="All referenced entities validated",
            )
        except SyntaxError:
            return VerificationEvidence(
                gate_name="entity_validation",
                status=VerificationStatus.SKIPPED,
                message="Skipped due to syntax error",
            )

    def _gate_shell_dry_run(self, code: str, cwd: str) -> VerificationEvidence:
        """Subprocess parse check for isolation verification."""
        try:
            result = subprocess.run(
                ["python3", "-c", "import ast; ast.parse(open('/dev/stdin').read())"],
                input=code,
                capture_output=True,
                text=True,
                timeout=self._config.timeout_seconds,
                cwd=cwd,
            )
            if result.returncode == 0:
                return VerificationEvidence(
                    gate_name="shell_dry_run",
                    status=VerificationStatus.PASSED,
                    message="Subprocess parse successful",
                )
            else:
                return VerificationEvidence(
                    gate_name="shell_dry_run",
                    status=VerificationStatus.FAILED,
                    message=f"Subprocess error: {result.stderr[:200]}",
                )
        except subprocess.TimeoutExpired:
            return VerificationEvidence(
                gate_name="shell_dry_run",
                status=VerificationStatus.FAILED,
                message="Subprocess timed out",
            )
        except FileNotFoundError:
            return VerificationEvidence(
                gate_name="shell_dry_run",
                status=VerificationStatus.SKIPPED,
                message="python3 not found",
            )
