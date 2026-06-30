"""CLI entry point for Forge SDK."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


def cmd_run(args: argparse.Namespace) -> None:
    """Run an agent on a task."""
    from forge_sdk.agents.react import ReactAgent
    from forge_sdk.agents.types import AgentContext
    from forge_sdk.audit import AuditLog
    from forge_sdk.config import ForgeConfig
    from forge_sdk.tools import ToolRegistry
    from forge_sdk.tools.filesystem import FILE_TOOLS
    from forge_sdk.tools.search import SEARCH_TOOLS
    from forge_sdk.tools.shell import SHELL_TOOL
    from forge_sdk.tracing.tracer import Tracer
    from forge_sdk.verifiers import Verifier

    cfg = ForgeConfig.load(args.config)
    if args.provider:
        cfg.provider = args.provider
    if args.model:
        cfg.model = args.model

    model = cfg.create_model()
    tools = ToolRegistry()
    for tool in FILE_TOOLS + SEARCH_TOOLS + [SHELL_TOOL]:
        tools.register(tool)

    tracer = Tracer()
    audit = AuditLog(cfg.audit_db)
    verifier = Verifier()

    agent = ReactAgent(model=model, tools=tools, tracer=tracer, audit=audit, verifier=verifier)

    context = AgentContext(
        task=args.task,
        cwd=args.cwd or cfg.cwd,
        max_steps=args.max_steps or cfg.max_steps,
    )

    print(f"Running task: {args.task}")
    print(f"Model: {model.name} ({model.provider})")
    print("---")

    result = agent.run(context)

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
    trace_dir = Path(cfg.trace_dir)
    trace_dir.mkdir(parents=True, exist_ok=True)
    trace_path = trace_dir / f"{tracer.trace_id}.jsonl"
    tracer.export_jsonl(trace_path)
    print(f"\nTraces: {trace_path}")
    print(f"Audit entries: {audit.count()}")
    audit.close()


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

    args = parser.parse_args()
    if args.command == "run":
        cmd_run(args)
    elif args.command == "eval":
        cmd_eval(args)
    elif args.command == "audit":
        cmd_audit(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
