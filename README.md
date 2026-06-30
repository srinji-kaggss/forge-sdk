# Forge SDK

**An agent for AIs that builds code you can bet money on.**

Forge is an agent-agnostic framework for building, observing, and evaluating AI coding agents. It exists to solve one problem: **AI agents that report success when they've actually failed**. The verification asymmetry theorem — agents submit at 99% while resolving at 18% — is what this SDK defeats.

## The Problem

Every AI coding agent has the same disease: it tells you it worked when it didn't. The harness is the moat, not the model.

## Results

| Model | Params | HumanEval (164) | Latency |
|-------|--------|-----------------|---------|
| gemma3:4b | 4B | **100%** | ~5s/problem |
| gemma3:12b | 12B | 99.4% | ~5s/problem |

**100% HumanEval on a 4B model.** The harness is the moat, not the model.

## Install

```bash
pip install forge-sdk
```

## Quick Start

```bash
# Run an agent
forge run "Write a function that computes fibonacci numbers"

# Run HumanEval benchmark
forge eval --benchmark humaneval --limit 10

# Verify audit integrity
forge audit --verify
```

## Safety Philosophy

From Geely's approach to automotive AI safety: **"Safety for all"** is not a slogan — it's certification-backed. ISO 26262, ISO/PAS 8800, UN R171. They built the world's largest full-domain safety center. They share core tech with the industry.

Forge applies the same philosophy to AI coding agents:

- **Every failure mode identified** — we attack our own agent before shipping
- **Every mitigation verified** — LoopGuard, entity validation, semantic check
- **Every verification has evidence** — trace spans, audit entries, hash-chain integrity
- **No false confidence** — if the agent can't prove it worked, it reports failure

## Mathematical Quality Targets

| Dimension | Current | Target | Standard |
|-----------|---------|--------|----------|
| Security coverage | 100% (8/8) | 100% | ISO 26262 — every hazard mitigated |
| Observability | 100% (steps traced) | 100% | DO-178C §6.3 — every decision has evidence |
| Convergence | ~90% | 100% | IEC 61508 — system reaches terminal state |
| False-green rate | 0% | 0% | DO-178C — verification must not lie |
| Code quality | 0.84 avg | >0.90 | Geometric mean across 4 axes |
| Test coverage | 75 tests | 100+ | ISO 26262 — every failure mode tested |

## Architecture

```
ModelPort (Protocol) — JSON-serializable, subprocess-isolated
    ↓
ProviderRegistry → Ollama Cloud | OpenRouter | DeepSeek | MeshModelPort
    ↓
Agent (ReactAgent) — strategy registry parser, LoopGuard, convergence detection
    ↓
ToolRegistry → FileSystem | Search | Shell | LgwksAdapters
    ↓
Tracer (Spans → JSONL export) — every step emits a span
    ↓
AuditLog (SQLite, hash-chain) — every step emits an entry
    ↓
Verifier — syntactic → AST → entity validation → semantic check
    ↓
EvalBar → DefaultEvalStrategy (pluggable)
```

## Security

Every attack vector is identified and blocked:

| Attack | Status | Mechanism |
|--------|--------|-----------|
| Path traversal (read) | BLOCKED | `read_file` validates path containment |
| Path traversal (shell) | BLOCKED | `run_command` blocks `/etc/passwd`, `/root/`, `/proc/` |
| Shell injection (`rm -rf /`) | BLOCKED | Dangerous command pattern detection |
| Prompt injection | BLOCKED | Agent refuses to leak system prompt |
| Loop spinning | BLOCKED | LoopGuard blocks after 3 identical calls |
| Sandbox escape | BLOCKED | `write_file` validates sandbox directory |
| Config key clobbering | FIXED | Provider-specific env var isolation |
| False-green reporting | FIXED | Verification skips non-code, detects zero-edit |

See [ADVERSARIAL-REPORT.md](ADVERSARIAL-REPORT.md) for the full adversarial audit.

## Design Principles

- **Model-agnostic**: Swap providers via `ModelPort` protocol
- **Strategy registries**: Typed registries, not if/elif chains
- **Trace-first observability**: Every LLM call produces a typed span
- **Independent audit**: Append-only SQLite with hash-chain integrity
- **Spec-driven**: Specifications before code
- **Edge-portable**: All protocols are JSON-serializable, subprocess-isolated (INV-107)
- **Verification-first**: LoopGuard, entity validation, semantic check (SPEC-SDK-003)

## Adding a Provider

```python
from forge_sdk.models.registry import registry
from forge_sdk.models.ollama import OllamaProvider

# Already registered on import:
# - ollama (Ollama Cloud)
# - openrouter (OpenRouter)
# - deepseek (DeepSeek API)
# - mesh (MeshModelPort via lgwks model mesh)
```

## Adding a Tool

```python
from forge_sdk.tools import ToolSpec, ToolResult
from forge_sdk.tools.registry import ToolRegistry

async def my_tool(input: str) -> ToolResult:
    return ToolResult(success=True, output=f"Processed: {input}")

tool = ToolSpec(
    stable_id="TOOL-MY-001",
    name="my_tool",
    description="Does something useful",
    input_schema={"type": "object", "properties": {"input": {"type": "string"}}, "required": ["input"]},
    output_schema={"type": "object", "properties": {"output": {"type": "string"}}},
    handler=my_tool,
)
```

## lgwks Integration

```python
# Register lgwks tools with forge
from forge_sdk.tools.adapters import register_lgwks_tools
from forge_sdk.tools.registry import ToolRegistry

registry = ToolRegistry()
register_lgwks_tools(registry)

# Use MeshModelPort for lgwks model routing
from forge_sdk.models.mesh import MeshModelPort
model = MeshModelPort(role="agent", trust_class="deterministic")

# Bridge events to lgwks daemon
from forge_sdk.audit.daemon_sink import DaemonEventSink
sink = DaemonEventSink(queue_name="forge")
sink.submit({"event": "tool_call", "tool": "write_file", "path": "/tmp/test.py"})
sink.flush()
```

## Portability

See [CORE-PORTABILITY.md](CORE-PORTABILITY.md) for the full module classification.

| Category | Count | Examples |
|----------|-------|---------|
| Edge-portable | 10 | ModelPort, ToolSpec, EventSink, Tracer, Config |
| Needs-port | 11 | ReactAgent, ToolRegistry, Providers (httpx) |
| Dev-only | 4 | CLI, EvalHarness, TestRunner |

## License

MIT
