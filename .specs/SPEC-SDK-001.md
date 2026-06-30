---
id: SPEC-SDK-001
status: draft
criticality: L1
review_cadence: weekly
owner: srinji
created: 2026-06-30
last_reviewed: 2026-06-30
---

# Specification: Agent-Agnostic SDK (Forge SDK)

## 1. Purpose

Forge SDK is a Python framework for building, observing, and evaluating AI coding agents.
It must NOT be tied to any specific model provider, agent paradigm, or evaluation benchmark.

## 2. Invariants

### INV-001: Model-Agnostic Abstraction
MUST expose a `ModelPort` interface that any OpenAI-compatible provider can satisfy.
MUST NOT import or reference any specific provider at the framework level.
SHOULD support streaming and non-streaming modes.
SHOULD support reasoning models (thinking/reasoning_content fields).

### INV-002: Strategy Registry Over Conditionals
MUST use a typed strategy registry for all extension points:
- Tool registration (ToolRegistry)
- Model provider registration (ProviderRegistry)
- Evaluation benchmark registration (BenchmarkRegistry)
- Policy registration (PolicyRegistry)
SHOULD NOT use if/elif chains for dispatch.
MUST support `applies()` predicate and `execute()` method per strategy.

### INV-003: Trace-First Observability
MUST record every LLM call, tool execution, and agent step as a typed span.
MUST conform to OpenTelemetry GenAI semantic conventions where applicable.
MUST support correlation across a full agent session (trace_id).
SHOULD support export to OTLP, JSONL, and console formats.

### INV-004: Independent Audit Log
MUST maintain an append-only SQLite audit log separate from agent state.
MUST compute hash-chain integrity (each entry hashes the previous).
MUST NOT allow the agent to modify or delete audit entries.
SHOULD detect regressions when re-running evaluations.

### INV-005: Eval Harness
MUST support HumanEval and MBPP benchmarks out of the box.
MUST extract code from agent responses using a registered strategy (not hardcoded regex).
MUST run generated tests in an isolated subprocess.
SHOULD support parallel execution and resumption.

### INV-006: Configuration
MUST load config from environment variables and/or config file.
MUST auto-detect available providers (DeepSeek, OpenRouter, Ollama).
MUST NOT hardcode API keys in source code.
SHOULD support per-run overrides via CLI flags.

## 3. Interfaces

### 3.1 ModelPort

```python
class ModelPort(Protocol):
    name: str
    provider: str
    context_window: int
    max_output: int
    supports_reasoning: bool

    def complete(self, messages: list[dict], **kwargs) -> ModelResponse: ...
    def complete_stream(self, messages: list[dict], **kwargs) -> Iterator[ModelChunk]: ...
```

### 3.2 Tool

```python
@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict  # JSON Schema
    output_schema: dict  # JSON Schema
    stable_id: str  # e.g. TOOL-FILE-READ-001
    handler: Callable[..., Awaitable[ToolResult]]

    def applies(self, context: AgentContext) -> bool: ...
```

### 3.3 Span

```python
@dataclass
class Span:
    span_id: str
    trace_id: str
    parent_span_id: str | None
    name: str  # e.g. "llm.complete", "tool.read_file"
    kind: SpanKind  # LLM, TOOL, AGENT, INTERNAL
    start_time: float
    end_time: float | None
    attributes: dict[str, Any]  # GenAI semantic conventions
    events: list[SpanEvent]
    status: SpanStatus
```

### 3.4 AuditEntry

```python
@dataclass
class AuditEntry:
    entry_id: str
    timestamp: float
    trace_id: str
    entry_type: str  # "llm_call", "tool_use", "decision", "eval_result"
    payload: dict
    previous_hash: str
    entry_hash: str  # SHA-256(previous_hash + payload)
```

## 4. Module Structure

```
src/forge_sdk/
├── __init__.py          # Public API exports
├── models/
│   ├── __init__.py      # ModelPort protocol
│   ├── port.py          # ModelPort definition
│   ├── registry.py      # ProviderRegistry
│   ├── deepseek.py      # DeepSeek provider
│   ├── openrouter.py    # OpenRouter provider
│   ├── ollama.py        # Ollama provider
│   └── types.py         # ModelResponse, ModelChunk
├── tools/
│   ├── __init__.py      # ToolSpec, ToolResult, ToolRegistry
│   ├── registry.py      # ToolRegistry
│   ├── filesystem.py    # File I/O tools
│   ├── search.py        # Code search tools
│   └── shell.py         # Shell execution tool
├── agents/
│   ├── __init__.py      # Agent protocol
│   ├── react.py         # ReAct agent implementation
│   ├── types.py         # AgentContext, AgentStep, AgentResult
│   └── config.py        # AgentConfig
├── tracing/
│   ├── __init__.py      # Tracer, Span, SpanKind
│   ├── tracer.py        # Tracer implementation
│   ├── span.py          # Span dataclass
│   ├── exporter.py      # JSONL, OTLP exporters
│   └── conventions.py   # GenAI semantic convention helpers
├── audit/
│   ├── __init__.py      # AuditLog
│   ├── log.py           # AuditLog implementation
│   └── integrity.py     # Hash chain verification
├── config/
│   ├── __init__.py      # ForgeConfig
│   ├── settings.py      # Config loading
│   └── providers.py     # Provider auto-detection
├── policies/
│   ├── __init__.py      # PolicyRegistry
│   ├── registry.py      # Policy registry
│   ├── code_extract.py  # Code extraction strategy
│   └── guardrails.py    # Safety guardrails
├── eval/
│   ├── __init__.py      # EvalHarness
│   ├── harness.py       # EvalHarness implementation
│   ├── benchmarks/
│   │   ├── __init__.py
│   │   ├── humaneval.py # HumanEval benchmark
│   │   └── mbpp.py      # MBPP benchmark
│   └── runner.py        # Test runner (subprocess isolation)
├── cli/
│   ├── __init__.py
│   └── main.py          # CLI entry point
└── py.typed             # PEP 561 marker
```

## 5. Non-Goals

- NOT a chat interface
- NOT a deployment platform
- NOT a model fine-tuning framework
- NOT tied to any specific agent architecture (ReAct is one implementation)

## 6. Success Criteria

- [ ] All LLM providers interchangeable via ModelPort
- [ ] All tools registered via ToolRegistry, not hardcoded
- [ ] Every LLM call produces a typed span
- [ ] Audit log has hash-chain integrity
- [ ] HumanEval pass@1 >= 70% on DeepSeek V4 Pro
- [ ] Zero hardcoded provider references in framework code
