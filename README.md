# Forge SDK

Agent-agnostic framework for building, observing, and evaluating AI coding agents.

**100% HumanEval on a 4B model.** The harness is the moat, not the model.

## Results

| Model | Params | HumanEval (164) | Latency |
|-------|--------|-----------------|---------|
| gemma3:4b | 4B | **100%** | ~5s/problem |
| gemma3:12b | 12B | 99.4% | ~5s/problem |
| nemotron-3-super (12B active) | 120B total | 80% | ~20s/problem |

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

## Architecture

```
ModelPort (Protocol)
    ↓
ProviderRegistry → Ollama Cloud | OpenRouter | DeepSeek | ...
    ↓
Agent (ReactAgent | ...)
    ↓
ToolRegistry → FileSystem | Search | Shell | ...
    ↓
Tracer (Spans → JSONL export)
    ↓
AuditLog (SQLite, hash-chain integrity)
```

## Design Principles

From the [OKF World-Class Coding Agent spec](https://github.com/srinji-kaggss/forge-sdk/blob/main/.specs/SPEC-SDK-001.md):

- **Model-agnostic**: Swap providers via `ModelPort` protocol
- **Strategy registries**: Typed registries, not if/elif chains
- **Trace-first observability**: Every LLM call produces a typed span
- **Independent audit**: Append-only SQLite with hash-chain integrity
- **Spec-driven**: Specifications before code

## Adding a Provider

```python
from forge_sdk.models.registry import registry
from forge_sdk.models.ollama import OllamaProvider

# Already registered on import:
# - ollama (Ollama Cloud)
# - openrouter (OpenRouter)
# - deepseek (DeepSeek API)
```

## Adding a Tool

```python
from forge_sdk.tools import ToolSpec, ToolResult
from forge_sdk.tools.registry import ToolRegistry

async def my_tool(input: str) -> ToolResult:
    return ToolResult(success=True, output=f"Processed: {input}")

tool = ToolSpec(
    name="my_tool",
    description="Does something useful",
    input_schema={"type": "object", "properties": {"input": {"type": "string"}}},
    output_schema={"type": "object", "properties": {"output": {"type": "string"}}},
    stable_id="TOOL-MY-001",
    handler=my_tool,
)
```

## License

MIT
