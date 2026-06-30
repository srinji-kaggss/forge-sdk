"""Smoke tests — verify all core components work."""

import asyncio
from pathlib import Path

from forge_sdk.audit import AuditLog
from forge_sdk.config import ForgeConfig
from forge_sdk.eval.harness import default_extractor
from forge_sdk.models.registry import registry
from forge_sdk.models.types import ModelChunk, ModelResponse, Usage
from forge_sdk.tools.filesystem import FILE_TOOLS
from forge_sdk.tools.registry import ToolRegistry
from forge_sdk.tools.search import SEARCH_TOOLS
from forge_sdk.tools.shell import SHELL_TOOL
from forge_sdk.tracing.span import SpanKind, SpanStatus
from forge_sdk.tracing.tracer import Tracer


def test_model_registry():
    """Test provider registry."""
    assert "deepseek" in registry.available()
    assert "openrouter" in registry.available()
    print("  [OK] Model registry")


def test_tool_registry():
    """Test tool registry with filesystem tools."""
    reg = ToolRegistry()
    for tool in FILE_TOOLS + SEARCH_TOOLS + [SHELL_TOOL]:
        reg.register(tool)
    assert len(reg.all()) == 6
    assert reg.get_by_name("read_file") is not None
    assert reg.get_by_name("nonexistent") is None
    schemas = reg.to_prompt_schemas()
    assert len(schemas) == 6
    print("  [OK] Tool registry")


async def test_file_tools():
    """Test file system tools."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        # Write
        result = await FILE_TOOLS[1].handler(path=f"{tmpdir}/test.txt", content="hello world")
        assert result.success, result.error

        # Read
        result = await FILE_TOOLS[0].handler(path=f"{tmpdir}/test.txt")
        assert result.success
        assert result.output == "hello world"

        # List
        result = await FILE_TOOLS[2].handler(path=tmpdir)
        assert result.success
        assert "test.txt" in result.output
    print("  [OK] File tools")


async def test_shell_tool():
    """Test shell tool."""
    result = await SHELL_TOOL.handler(command="echo 'hello from shell'")
    assert result.success
    assert "hello from shell" in result.output
    print("  [OK] Shell tool")


def test_tracing():
    """Test tracer and spans."""
    tracer = Tracer()
    assert tracer.trace_id
    span = tracer.start_span("test", SpanKind.INTERNAL)
    assert span.span_id
    assert span.trace_id == tracer.trace_id
    span.finish(SpanStatus.OK)
    assert span.duration_ms is not None
    assert span.duration_ms >= 0

    # Convenience methods
    llm_span = tracer.llm_call(
        "test-model", "test", [{"role": "user", "content": "hi"}], "response"
    )
    assert llm_span.kind == SpanKind.LLM
    assert llm_span.attributes["gen_ai.system"] == "test"

    tool_span = tracer.tool_call("test_tool", {"input": "x"}, "output", True)
    assert tool_span.kind == SpanKind.TOOL

    # Export
    export_path = Path("/tmp/forge_test_traces.jsonl")
    tracer.export_jsonl(export_path)
    assert export_path.exists()
    lines = export_path.read_text().strip().split("\n")
    assert len(lines) == 3
    export_path.unlink()
    print("  [OK] Tracing")


def test_audit_log():
    """Test audit log with hash-chain integrity."""
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    audit = AuditLog(db_path)

    # Append entries
    audit.append("trace-1", "llm_call", {"model": "test", "tokens": 100})
    audit.append("trace-1", "tool_use", {"tool": "read_file", "path": "/tmp/test"})
    audit.append("trace-2", "eval_result", {"benchmark": "humaneval", "passed": True})

    # Verify chain
    violations = audit.verify_integrity()
    assert len(violations) == 0, f"Unexpected violations: {violations}"

    # Query
    entries = audit.get_entries(trace_id="trace-1")
    assert len(entries) == 2
    entries = audit.get_entries(entry_type="eval_result")
    assert len(entries) == 1

    assert audit.count() == 3
    audit.close()
    Path(db_path).unlink()
    print("  [OK] Audit log")


def test_config():
    """Test config loading."""
    cfg = ForgeConfig()
    assert cfg.provider == "deepseek"
    assert cfg.model == "deepseek-v4-pro"
    assert cfg.max_steps == 50
    print("  [OK] Config")


def test_code_extractor():
    """Test code extraction strategies."""
    response = """Here is the solution:

```python
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)
```

This uses recursion."""

    code = default_extractor.extract(response, "fibonacci")
    assert "def fibonacci" in code
    assert "fibonacci(n-1)" in code
    print("  [OK] Code extractor")


def test_model_response_types():
    """Test model response types."""
    resp = ModelResponse(
        content="hello",
        reasoning="thinking...",
        model="test",
        provider="test",
        usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )
    assert resp.content == "hello"
    assert resp.reasoning == "thinking..."
    assert resp.usage.total_tokens == 15

    chunk = ModelChunk(delta="hello", reasoning_delta="think")
    assert chunk.delta == "hello"
    print("  [OK] Model types")


def main():
    print("Running smoke tests...")
    test_model_registry()
    test_tool_registry()
    asyncio.run(test_file_tools())
    asyncio.run(test_shell_tool())
    test_tracing()
    test_audit_log()
    test_config()
    test_code_extractor()
    test_model_response_types()
    print("\nAll smoke tests passed!")


if __name__ == "__main__":
    main()
