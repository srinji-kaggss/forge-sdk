# Forge SDK

Agent-agnostic framework for building, observing, and evaluating AI coding agents.

## Principles

- **Model-agnostic**: Swap providers via `ModelPort` protocol. No hardcoded providers.
- **Strategy registries**: All extension points use typed registries, not if/elif chains.
- **Trace-first observability**: Every LLM call and tool execution produces a typed span.
- **Independent audit**: Append-only SQLite log with hash-chain integrity. Agent cannot tamper.
- **Spec-driven**: Specifications before code. Machine-readable front matter on all docs.
- **AI-first consumer**: All outputs structured JSON, self-describing, machine-parseable.

## Quick Start

```bash
# Install
pip install -e ".[dev]"

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
ProviderRegistry → DeepSeek | OpenRouter | Ollama | ...
    ↓
Agent (ReactAgent | ...)
    ↓
ToolRegistry → FileSystem | Search | Shell | ...
    ↓
Tracer (Spans → JSONL export)
    ↓
AuditLog (SQLite, hash-chain integrity)
```

## Configuration

```bash
# Environment variables
export DEEPSEEK_API_KEY=sk-...
export OPENROUTER_API_KEY=sk-or-...
export FORGE_PROVIDER=deepseek
export FORGE_MODEL=deepseek-v4-pro

# Or config file
forge --config ~/.forge/config.json run "..."
```

## Adding a Provider

```python
from forge_sdk.models.port import ModelPort
from forge_sdk.models.registry import registry

class MyProvider:
    @property
    def name(self) -> str: return "my-model"
    @property
    def provider(self) -> str: return "my-provider"
    # ... implement ModelPort protocol

registry.register("my-provider", MyProvider)
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

registry = ToolRegistry()
registry.register(tool)
```

## License

MIT
