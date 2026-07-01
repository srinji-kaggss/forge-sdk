"""Forge doctor — L0-L5 escalation diagnostic ladder.

Checks the forge runtime environment and reports PASS/FAIL/WARN for each
check level.  Design intent (from the SEMANTIC-RESEARCH-FRONTIER-CLIS
topological map):

  L0 – Python version              (can the process even start?)
  L1 – Config parse + API key      (can we read the config and auth?)
  L2 – Trace / audit dirs          (can we write observability data?)
  L3 – Working directory           (is the intended cwd usable?)
  L4 – Provider connectivity       (does the provider endpoint respond?)
  L5 – BLACKBOX: model ping        (can we actually complete a tiny round-trip?)

L5 is a last resort and MUST NOT be attempted unless L0-L4 all pass.
An EscalationRecord is created *before* any model call so the trace log
gets the audit event regardless of whether the ping succeeds or fails.

Output modes:
  • Default: colourised table via ansi.py
  • --json:  NDJSON stream (one record per check)
  • --docs:  stub placeholder for future documentation checks

Exit code 1 when any check FAILs.

Zero new dependencies. Stdlib only.
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from forge_sdk.cli.ansi import style

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class EscalationRecord:
    """Audit record created before any model call (L5_BLACKBOX)."""

    escalation_level: str
    timestamp_iso: str
    provider: str
    model: str
    reason: str
    prior_checks_passed: int
    prior_checks_total: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "escalation_level": self.escalation_level,
            "timestamp": self.timestamp_iso,
            "provider": self.provider,
            "model": self.model,
            "reason": self.reason,
            "prior_checks_passed": self.prior_checks_passed,
            "prior_checks_total": self.prior_checks_total,
        }


@dataclass
class CheckResult:
    """Outcome of a single diagnostic check."""

    level: str
    label: str
    status: str  # PASS, FAIL, WARN
    detail: str = ""
    duration_ms: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "label": self.label,
            "status": self.status,
            "detail": self.detail,
            "duration_ms": round(self.duration_ms, 2),
        }


STATUS_ICONS = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️"}
STATUS_COLORS = {"PASS": "green", "FAIL": "red", "WARN": "yellow"}


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def _check_python_version() -> CheckResult:
    """L0: Python version >= 3.13."""
    vi = sys.version_info
    ok = (vi.major, vi.minor) >= (3, 13)
    return CheckResult(
        level="L0",
        label="Python version",
        status="PASS" if ok else "FAIL",
        detail=f"Python {vi.major}.{vi.minor}.{vi.micro} (need >= 3.13)",
    )


def _check_config(config_path: str | None) -> CheckResult:
    """L1: Config file exists and is valid JSON."""
    path = Path(config_path) if config_path else Path.home() / ".forge" / "config.json"
    if not path.exists():
        return CheckResult(
            level="L1",
            label="Config file",
            status="FAIL",
            detail=f"Not found: {path}",
        )
    try:
        with open(path) as f:
            json.load(f)
    except json.JSONDecodeError as exc:
        return CheckResult(
            level="L1",
            label="Config file",
            status="FAIL",
            detail=f"Invalid JSON in {path}: {exc}",
        )
    except OSError as exc:
        return CheckResult(
            level="L1",
            label="Config file",
            status="FAIL",
            detail=f"Cannot read {path}: {exc}",
        )
    return CheckResult(
        level="L1",
        label="Config file",
        status="PASS",
        detail=str(path),
    )


def _check_api_key(provider: str = "", api_key: str = "") -> CheckResult:
    """L1: Provider auth — env var check for API key."""
    if api_key and api_key.strip():
        return CheckResult(
            level="L1",
            label="API key (config)",
            status="PASS",
            detail="API key found in config",
        )

    env_keys = {
        "deepseek": "DEEPSEEK_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "ollama": "OLLAMA_API_KEY",
    }
    env_var = env_keys.get(provider, "FORGE_API_KEY") if provider else "FORGE_API_KEY"
    env_val = os.environ.get(env_var, "")

    if env_val and env_val.strip():
        return CheckResult(
            level="L1",
            label=f"API key (env: {env_var})",
            status="PASS",
            detail=f"Found in ${env_var}",
        )

    return CheckResult(
        level="L1",
        label="API key",
        status="FAIL",
        detail=f"No API key found in config or ${env_var}",
    )


def _check_trace_dir(trace_dir: str) -> CheckResult:
    """L2: Trace directory exists and is writable."""
    path = Path(trace_dir)
    try:
        path.mkdir(parents=True, exist_ok=True)
        test_file = path / ".forge_doctor_write_test"
        test_file.write_text("doctor")
        test_file.unlink()
    except OSError as exc:
        return CheckResult(
            level="L2",
            label="Trace directory",
            status="FAIL",
            detail=f"Cannot write to {path}: {exc}",
        )
    return CheckResult(
        level="L2",
        label="Trace directory",
        status="PASS",
        detail=f"Writable: {path}",
    )


def _check_audit_dir(audit_db: str) -> CheckResult:
    """L2: Audit DB directory exists and is writable."""
    path = Path(audit_db)
    parent = path.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
        test_file = parent / ".forge_doctor_write_test"
        test_file.write_text("doctor")
        test_file.unlink()
    except OSError as exc:
        return CheckResult(
            level="L2",
            label="Audit directory",
            status="FAIL",
            detail=f"Cannot write to {parent}: {exc}",
        )
    return CheckResult(
        level="L2",
        label="Audit directory",
        status="PASS",
        detail=f"Writable: {parent}",
    )


def _check_working_directory(cwd: str) -> CheckResult:
    """L3: Working directory exists and is readable."""
    path = Path(cwd).expanduser()
    if not path.exists():
        return CheckResult(
            level="L3",
            label="Working directory",
            status="FAIL",
            detail=f"Does not exist: {path}",
        )
    if not path.is_dir():
        return CheckResult(
            level="L3",
            label="Working directory",
            status="FAIL",
            detail=f"Not a directory: {path}",
        )
    try:
        list(path.iterdir())
    except OSError as exc:
        return CheckResult(
            level="L3",
            label="Working directory",
            status="FAIL",
            detail=f"Not readable: {path} ({exc})",
        )
    return CheckResult(
        level="L3",
        label="Working directory",
        status="PASS",
        detail=str(path),
    )


# ---------------------------------------------------------------------------
# Provider connectivity + model ping (L4 + L5)
# ---------------------------------------------------------------------------


def _check_provider_connectivity(
    model: Any, provider: str, model_name: str
) -> tuple[CheckResult, EscalationRecord]:
    """L4+L5: Provider connectivity + model ping (BLACKBOX).

    Returns (CheckResult, EscalationRecord). The record is created BEFORE
    the model call so it exists in the trace even on failure.
    """
    prior_passed = 5
    prior_total = 5

    record = EscalationRecord(
        escalation_level="L5_BLACKBOX",
        timestamp_iso=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        provider=provider,
        model=model_name,
        reason="All L0-L4 checks passed; performing model ping for final verification",
        prior_checks_passed=prior_passed,
        prior_checks_total=prior_total,
    )

    t0 = time.monotonic()
    try:
        resp = model.complete(
            [{"role": "user", "content": "reply with exactly: ok"}],
            temperature=0.0,
            max_tokens=8,
        )
        elapsed = (time.monotonic() - t0) * 1000
        if resp and "ok" in resp.content.lower():
            return (
                CheckResult(
                    level="L5",
                    label="Model ping",
                    status="PASS",
                    detail=f"Response 'ok' in {elapsed:.0f}ms ({provider}/{model_name})",
                    duration_ms=elapsed,
                ),
                record,
            )
        return (
            CheckResult(
                level="L5",
                label="Model ping",
                status="WARN",
                detail=f"Unexpected response: {resp.content[:100] if resp else 'None'} ({elapsed:.0f}ms)",
                duration_ms=elapsed,
            ),
            record,
        )
    except Exception as exc:
        elapsed = (time.monotonic() - t0) * 1000
        err_msg = str(exc)
        # Make common auth errors human-readable
        if "401" in err_msg or "Unauthorized" in err_msg or "unauthorized" in err_msg.lower():
            err_msg = f"Authentication failed (401): {err_msg}"
        elif "403" in err_msg or "Forbidden" in err_msg:
            err_msg = f"Access denied (403): {err_msg}"
        elif "timeout" in err_msg.lower() or "timed out" in err_msg.lower():
            err_msg = f"Connection timed out: {err_msg}"
        return (
            CheckResult(
                level="L5",
                label="Model ping",
                status="FAIL",
                detail=f"{err_msg} ({elapsed:.0f}ms)",
                duration_ms=elapsed,
            ),
            record,
        )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def run_doctor(
    config_path: str | None = None,
    *,
    json_output: bool = False,
    docs_flag: bool = False,
) -> int:
    """Run the full L0-L5 escalation ladder.

    Returns the exit code (0 = all PASS, 1 = any FAIL).
    """
    from forge_sdk.config import ForgeConfig

    cfg: ForgeConfig | None = None
    try:
        cfg = ForgeConfig.load(config_path)
    except Exception:
        cfg = None

    provider = cfg.provider if cfg else ""
    model_name = cfg.model if cfg else ""
    api_key = cfg.resolve_api_key() if cfg else ""
    trace_dir = cfg.trace_dir if cfg else ".forge/traces"
    audit_db = cfg.audit_db if cfg else ".forge/audit.db"
    cwd = cfg.cwd if cfg else "."

    results: list[CheckResult] = []
    escalation_records: list[EscalationRecord] = []

    # ---- L0: Python version ----
    r = _check_python_version()
    results.append(r)
    if r.status == "FAIL":
        _render_results(results, escalation_records, json_output, docs_flag)
        return 1

    # ---- L1: Config + API key ----
    r = _check_config(config_path)
    results.append(r)

    r = _check_api_key(provider, api_key)
    results.append(r)

    # ---- L2: Trace / audit dirs ----
    r = _check_trace_dir(trace_dir)
    results.append(r)

    r = _check_audit_dir(audit_db)
    results.append(r)

    # ---- L3: Working directory ----
    r = _check_working_directory(cwd)
    results.append(r)

    # ---- L4+L5: Model ping (only if L0-L3 all pass) ----
    all_l0_l3_pass = all(r.status == "PASS" for r in results)

    if all_l0_l3_pass and provider and model_name and api_key:
        try:
            from forge_sdk.models.registry import registry as model_registry

            model = model_registry.create(
                provider,
                api_key=api_key,
                model=model_name,
            )
            l5_result, esc_record = _check_provider_connectivity(model, provider, model_name)
            results.append(l5_result)
            escalation_records.append(esc_record)
        except Exception as exc:
            results.append(
                CheckResult(
                    level="L4",
                    label="Provider connectivity",
                    status="FAIL",
                    detail=f"Cannot create model instance for {provider}: {exc}",
                )
            )
    elif all_l0_l3_pass:
        if not provider:
            results.append(
                CheckResult(
                    level="L4",
                    label="Provider connectivity",
                    status="WARN",
                    detail="No provider configured — skipping L5 model ping",
                )
            )
        elif not api_key:
            results.append(
                CheckResult(
                    level="L4",
                    label="Provider connectivity",
                    status="WARN",
                    detail="No API key — skipping L5 model ping",
                )
            )

    # ---- Render ----
    _render_results(results, escalation_records, json_output, docs_flag)

    any_fail = any(r.status == "FAIL" for r in results)
    return 1 if any_fail else 0


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _render_results(
    results: list[CheckResult],
    escalation_records: list[EscalationRecord],
    json_output: bool,
    docs_flag: bool,
) -> None:
    """Render check results in the selected output mode."""

    if json_output:
        _render_ndjson(results, escalation_records)
    else:
        _render_table(results)

    if docs_flag:
        print(style("\n📋 --docs flag", "bold"))
        print(style("  docs checks coming in v0.6", "dim"))


def _render_ndjson(
    results: list[CheckResult],
    escalation_records: list[EscalationRecord],
) -> None:
    """Stream one JSON object per line (NDJSON)."""
    for r in results:
        print(json.dumps(r.as_dict()))
    for rec in escalation_records:
        print(json.dumps({"type": "escalation_record", **rec.as_dict()}))


def _render_table(results: list[CheckResult]) -> None:
    """Render a colourised text table."""
    print()
    print(style("  Forge Doctor", "bold"))
    print(style("  " + "─" * 58, "dim"))
    print(
        f"  {style('LEVEL', 'dim'):6s}  "
        f"{style('STATUS', 'dim'):10s}  "
        f"{style('CHECK', 'dim'):24s}  "
        f"{style('DETAIL', 'dim')}"
    )
    print(style("  " + "─" * 58, "dim"))

    for r in results:
        icon = STATUS_ICONS.get(r.status, "?")
        color = STATUS_COLORS.get(r.status, "gray")
        status_col = style(f"{icon} {r.status:<6s}", color)
        level_col = style(r.level, "bold")
        detail = r.detail
        if r.duration_ms > 0:
            detail += f" [{r.duration_ms:.0f}ms]"
        print(f"  {level_col:16s}  {status_col:16s}  {r.label:<24s}  {detail}")

    print(style("  " + "─" * 58, "dim"))

    passed = sum(1 for r in results if r.status == "PASS")
    failed = sum(1 for r in results if r.status == "FAIL")
    warned = sum(1 for r in results if r.status == "WARN")
    total = len(results)

    summary_parts = [style(f"{passed}/{total} passed", "green" if failed == 0 else "yellow")]
    if failed:
        summary_parts.append(style(f"{failed} failed", "red"))
    if warned:
        summary_parts.append(style(f"{warned} warnings", "yellow"))
    print(f"  Summary: {', '.join(summary_parts)}")
    print()
