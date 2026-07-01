"""CLI entry point for Forge SDK."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


def scope_path_to_cwd(path_str: str, run_cwd: Path) -> Path:
    """Resolve a config-relative path (trace_dir, audit_db) against the
    run's --cwd instead of the process's real os.getcwd().

    Issue #23 covered tool-call paths via AgentContext.cwd but missed this
    CLI layer: trace_dir/audit_db are relative paths in ForgeConfig, so they
    silently resolved against wherever `forge run` was invoked from instead
    of --cwd, scattering a concurrent batch's traces into one shared
    directory instead of each task's own worktree. An absolute path is left
    untouched, matching ReactAgent._resolve_cwd's convention.
    """
    path = Path(path_str)
    return path if path.is_absolute() else run_cwd / path


def cmd_run(args: argparse.Namespace) -> None:
    """Run an agent on a task."""
    import uuid

    from forge_sdk.agents.react import ReactAgent
    from forge_sdk.agents.types import AgentContext
    from forge_sdk.audit import AuditLog

    # Phase 4 (L5a): Permission Gate
    from forge_sdk.cli.permissions import (
        ANTI_SLOP_STRATEGIES,
        DEFAULT_STRATEGIES,
        PermissionGate,
        PermissionMode,
    )

    # Phase 5 (L5b): Session Recovery
    from forge_sdk.cli.session import (
        checkpoint_restore,
        list_checkpoints,
    )
    from forge_sdk.config import ForgeConfig
    from forge_sdk.tools import ToolRegistry
    from forge_sdk.tools.filesystem import FILE_TOOLS
    from forge_sdk.tools.search import SEARCH_TOOLS
    from forge_sdk.tools.shell import SHELL_TOOL
    from forge_sdk.tracing.tracer import Tracer
    from forge_sdk.verifiers import Verifier

    # --list-sessions: print saved sessions and exit
    if getattr(args, "list_sessions", False):
        sessions = list_checkpoints(Path(args.checkpoint_dir))
        if not sessions:
            print("No saved sessions found.")
        else:
            print(f"{'SESSION ID':<40} {'STEPS':<8} {'TASK'}")
            print("-" * 80)
            for s in sessions:
                print(f"{s['session_id']:<40} {s['steps']:<8} {s['task']}")
        return

    cfg = ForgeConfig.load(args.config)
    if args.provider:
        cfg.provider = args.provider
    if args.model:
        cfg.model = args.model

    model = cfg.create_model()
    tools = ToolRegistry()
    for tool in FILE_TOOLS + SEARCH_TOOLS + [SHELL_TOOL]:
        tools.register(tool)

    run_cwd = Path(args.cwd or cfg.cwd).expanduser()

    tracer = Tracer()
    audit = AuditLog(str(scope_path_to_cwd(cfg.audit_db, run_cwd)))
    verifier = Verifier()

    # ADR-2: renderer injection — CLI chooses output format, SDK stays pure
    renderer = None
    if not args.print:
        if args.output_format == "stream-json":
            from forge_sdk.cli.renderers import NDJSONRenderer

            renderer = NDJSONRenderer()
        else:
            from forge_sdk.cli.renderers import TextRenderer

            renderer = TextRenderer()

    event_callback = renderer.on_event if renderer else None

    # Phase 4 (L5a): Build permission gate
    mode = PermissionMode(args.permission_mode)
    pg = PermissionGate(mode)
    for s in ANTI_SLOP_STRATEGIES:
        pg.register(s)
    for s in DEFAULT_STRATEGIES:
        pg.register(s)

    # Phase 5 (L5b): Session recovery — resolve session_id
    session_id = args.resume or str(uuid.uuid4())
    session_state = None
    if args.resume:
        session_state = checkpoint_restore(args.resume, Path(args.checkpoint_dir))
        if session_state:
            print(
                f"Resuming session {args.resume} (step {session_state.step_count})", file=sys.stderr
            )

    agent = ReactAgent(
        model=model,
        tools=tools,
        tracer=tracer,
        audit=audit,
        verifier=verifier,
        event_callback=event_callback,
        permission_gate=pg,
        session_id=session_id,
        sandbox_dir=args.sandbox,
        verify_command=args.verify_command,
        auto_verify=not args.no_verify,
        max_tokens=args.max_tokens,
        max_cost_usd=args.max_cost,
    )

    context = AgentContext(
        task=args.task,
        cwd=args.cwd or cfg.cwd,
        max_steps=args.max_steps or cfg.max_steps,
    )

    # Legacy: suppress header when streaming (renderer prints its own)
    if not renderer:
        print(f"Running task: {args.task}")
        print(f"Model: {model.name} ({model.provider})")
        print("---")

    result = agent.run(context)

    if renderer:
        renderer.on_end(0 if result.success else 1)
    else:
        print("---")
        print(f"Status: {'SUCCESS' if result.success else 'FAILED'}")
        print(f"Steps: {len(result.steps)}")
        print(f"Tokens: {result.total_tokens}")
    if result.verification:
        print(f"Verification: {result.verification_summary}")
        for v in result.verification:
            print(f"  {v.as_summary}")
    print(f"\nOutput:\n{result.output}")

    # Export traces
    trace_dir = scope_path_to_cwd(cfg.trace_dir, run_cwd)
    trace_dir.mkdir(parents=True, exist_ok=True)
    trace_path = trace_dir / f"{tracer.trace_id}.jsonl"
    tracer.export_jsonl(trace_path)
    print(f"\nTraces: {trace_path}")
    print(f"Audit entries: {audit.count()}")
    audit.close()

    if not result.success:
        if result.failure_reason:
            print(f"Reason: {result.failure_reason}", file=sys.stderr)
        sys.exit(1)


def cmd_eval(args: argparse.Namespace) -> None:
    """Run evaluation benchmarks."""
    from forge_sdk.audit import AuditLog
    from forge_sdk.config import ForgeConfig
    from forge_sdk.eval.harness import EvalHarness
    from forge_sdk.tracing.tracer import Tracer

    cfg = ForgeConfig.load(args.config)
    if args.provider:
        cfg.provider = args.provider
    if args.model:
        cfg.model = args.model

    model = cfg.create_model()
    tracer = Tracer()
    audit = AuditLog(cfg.audit_db)

    harness = EvalHarness(model=model, tracer=tracer, audit=audit)

    benchmark = args.benchmark or cfg.eval_benchmark
    limit = args.limit or cfg.eval_limit

    print(f"Loading {benchmark}...")
    if benchmark == "humaneval":
        problems = harness.load_humaneval()
    elif benchmark == "mbpp":
        problems = harness.load_mbpp()
    else:
        print(f"Unknown benchmark: {benchmark}")
        sys.exit(1)

    print(f"Running {benchmark} ({limit or len(problems)} problems)...")
    report = harness.run_benchmark(problems, benchmark_name=benchmark, limit=limit)

    print(f"\n{'=' * 60}")
    print(f"Resolved: {report.passed}/{report.total} ({report.resolution_rate:.1%})")
    print(f"Failed: {report.failed}, Errors: {report.errors}")
    print(f"Avg latency: {report.avg_latency_ms:.0f}ms")
    print(f"Total tokens: {report.total_tokens}")

    # Save report
    report_path = Path(cfg.trace_dir) / f"eval_{benchmark}_{int(time.time())}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(
            {
                "benchmark": report.benchmark,
                "total": report.total,
                "passed": report.passed,
                "failed": report.failed,
                "errors": report.errors,
                "resolution_rate": report.resolution_rate,
                "avg_latency_ms": report.avg_latency_ms,
                "total_tokens": report.total_tokens,
                "timestamp": report.timestamp,
            },
            f,
            indent=2,
        )
    print(f"Report: {report_path}")

    # Show failures
    if report.failed > 0:
        print("\nFailed problems:")
        for r in report.results:
            if not r.passed:
                print(f"  {r.task_id}: {r.test_result.error[:100]}")

    audit.close()


def cmd_audit(args: argparse.Namespace) -> None:
    """Show audit log and verify integrity."""
    from forge_sdk.audit import AuditLog
    from forge_sdk.config import ForgeConfig

    cfg = ForgeConfig.load(args.config)
    audit = AuditLog(cfg.audit_db)

    if args.verify:
        print("Verifying audit chain integrity...")
        violations = audit.verify_integrity()
        if violations:
            print(f"VIOLATIONS FOUND ({len(violations)}):")
            for v in violations:
                print(f"  - {v}")
        else:
            print("Chain integrity: OK")
        return

    entries = audit.get_entries(limit=args.limit or 20)
    print(f"Last {len(entries)} audit entries:")
    for e in entries:
        model = e.payload.get("model", "")
        print(f"  [{e.entry_type}] {e.entry_id} trace={e.trace_id[:8]}... {model}")
    print(f"\nTotal entries: {audit.count()}")
    audit.close()


def cmd_doctor(args: argparse.Namespace) -> None:
    """Run environment diagnostic checks."""
    from forge_sdk.cli.doctor import run_doctor

    exit_code = run_doctor(
        config_path=args.config,
        json_output=args.json_output,
        docs_flag=args.docs_flag,
    )
    sys.exit(exit_code)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="forge",
        description="Forge SDK — Agent-agnostic framework for AI coding agents",
    )
    parser.add_argument("--config", help="Config file path")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # run command
    run_parser = subparsers.add_parser("run", help="Run an agent on a task")
    run_parser.add_argument("task", help="Task description")
    run_parser.add_argument("--provider", help="Model provider")
    run_parser.add_argument("--model", help="Model name")
    run_parser.add_argument("--cwd", help="Working directory")
    run_parser.add_argument("--max-steps", type=int, help="Max agent steps")
    run_parser.add_argument(
        "--output-format",
        choices=["text", "json", "stream-json"],
        default="text",
        help="Output format (default: text)",
    )
    run_parser.add_argument(
        "--print",
        action="store_true",
        help="Suppress streaming output; print only final result (legacy)",
    )
    # Phase 3 (L2 Exposure): surface the Moat
    run_parser.add_argument("--sandbox", help="Restrict file writes to this directory")
    run_parser.add_argument("--verify-command", help="Build/test command to gate SUCCESS")
    run_parser.add_argument("--no-verify", action="store_true", help="Skip empirical verification")
    run_parser.add_argument(
        "--max-tokens", type=int, default=32000, help="Context window token limit"
    )
    run_parser.add_argument(
        "--max-cost", type=float, default=1.0, help="Max cost in USD before aborting"
    )
    # Phase 4 (L5a): Permission mode
    run_parser.add_argument(
        "--permission-mode",
        choices=["yolo", "interactive", "plan"],
        default="interactive",
        help="Permission mode: yolo, interactive, plan (default: interactive)",
    )
    # Phase 5 (L5b): Session Recovery
    run_parser.add_argument("--resume", help="Resume from session ID")
    run_parser.add_argument(
        "--checkpoint-dir",
        help="Custom checkpoint directory",
        default=str(Path.home() / ".forge" / "checkpoints"),
    )
    run_parser.add_argument(
        "--max-checkpoints", type=int, default=10, help="Max checkpoint files to keep"
    )
    run_parser.add_argument("--list-sessions", action="store_true", help="List saved sessions")

    # eval command
    eval_parser = subparsers.add_parser("eval", help="Run evaluation benchmarks")
    eval_parser.add_argument("--benchmark", choices=["humaneval", "mbpp"], help="Benchmark to run")
    eval_parser.add_argument("--limit", type=int, help="Max problems to evaluate")
    eval_parser.add_argument("--provider", help="Model provider")
    eval_parser.add_argument("--model", help="Model name")

    # audit command
    audit_parser = subparsers.add_parser("audit", help="Show audit log")
    audit_parser.add_argument("--verify", action="store_true", help="Verify chain integrity")
    audit_parser.add_argument("--limit", type=int, help="Max entries to show")

    # doctor command
    doctor_parser = subparsers.add_parser("doctor", help="Run environment diagnostic checks")
    doctor_parser.add_argument(
        "--json", dest="json_output", action="store_true", help="Output as NDJSON"
    )
    doctor_parser.add_argument(
        "--docs", dest="docs_flag", action="store_true", help="Include documentation checks (stub)"
    )

    args = parser.parse_args()
    if args.command == "run":
        cmd_run(args)
    elif args.command == "eval":
        cmd_eval(args)
    elif args.command == "audit":
        cmd_audit(args)
    elif args.command == "doctor":
        cmd_doctor(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
