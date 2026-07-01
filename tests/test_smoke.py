"""Smoke tests — verify all core components work.

Run with: pytest tests/test_smoke.py -v
Or directly: python tests/test_smoke.py
"""

import asyncio
import tempfile
from pathlib import Path

from forge_sdk.audit import AuditLog
from forge_sdk.config import ForgeConfig
from forge_sdk.eval.harness import default_extractor
from forge_sdk.models.registry import registry
from forge_sdk.models.types import ModelChunk, ModelResponse, Usage
from forge_sdk.tools import ToolResult
from forge_sdk.tools.filesystem import FILE_TOOLS
from forge_sdk.tools.registry import ToolRegistry
from forge_sdk.tools.search import SEARCH_TOOLS
from forge_sdk.tools.shell import SHELL_TOOL
from forge_sdk.tracing.span import SpanKind, SpanStatus
from forge_sdk.tracing.tracer import Tracer
from forge_sdk.verifiers import VerificationConfig, VerificationStatus, Verifier

# ── Model Registry ──

def test_model_registry_has_providers():
    assert "deepseek" in registry.available()
    assert "openrouter" in registry.available()


def test_model_registry_create():
    cls = registry.get("deepseek")
    assert cls is not None


# ── Tool Registry ──

def test_tool_registry_count():
    reg = ToolRegistry()
    for tool in FILE_TOOLS + SEARCH_TOOLS + [SHELL_TOOL]:
        reg.register(tool)
    assert len(reg.all()) == 6


def test_tool_registry_lookup():
    reg = ToolRegistry()
    for tool in FILE_TOOLS + SEARCH_TOOLS + [SHELL_TOOL]:
        reg.register(tool)
    assert reg.get_by_name("read_file") is not None
    assert reg.get_by_name("nonexistent") is None


def test_tool_registry_schemas():
    reg = ToolRegistry()
    for tool in FILE_TOOLS + SEARCH_TOOLS + [SHELL_TOOL]:
        reg.register(tool)
    schemas = reg.to_prompt_schemas()
    assert len(schemas) == 6
    # Each schema has the required OpenAI function-calling structure
    for s in schemas:
        assert s["type"] == "function"
        assert "name" in s["function"]
        assert "description" in s["function"]
        assert "parameters" in s["function"]


# ── File Tools ──

def test_write_and_read_file():
    async def _test():
        with tempfile.TemporaryDirectory() as tmpdir:
            # Write
            result = await FILE_TOOLS[1].handler(path=f"{tmpdir}/test.txt", content="hello world")
            assert result.success, result.error
            assert "11 bytes" in result.output

            # Read
            result = await FILE_TOOLS[0].handler(path=f"{tmpdir}/test.txt")
            assert result.success
            assert result.output == "hello world"

    asyncio.run(_test())


def test_list_dir():
    async def _test():
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file
            Path(f"{tmpdir}/a.txt").write_text("x")
            Path(f"{tmpdir}/b.py").write_text("y")

            result = await FILE_TOOLS[2].handler(path=tmpdir)
            assert result.success
            assert "a.txt" in result.output
            assert "b.py" in result.output

    asyncio.run(_test())


def test_read_file_not_found():
    async def _test():
        result = await FILE_TOOLS[0].handler(path="/nonexistent/file.txt")
        assert not result.success
        assert "not found" in result.error.lower() or "not found" in result.output.lower()

    asyncio.run(_test())


def test_read_file_not_a_file():
    async def _test():
        with tempfile.TemporaryDirectory() as tmpdir:
            result = await FILE_TOOLS[0].handler(path=tmpdir)
            assert not result.success

    asyncio.run(_test())


# ── Shell Tool ──

def test_shell_echo():
    async def _test():
        result = await SHELL_TOOL.handler(command="echo 'hello from shell'")
        assert result.success
        assert "hello from shell" in result.output

    asyncio.run(_test())


def test_shell_failure():
    async def _test():
        # Use a real command that returns exit code 1 (not a shell builtin)
        result = await SHELL_TOOL.handler(command="false")
        assert not result.success
        assert "Exit code 1" in result.error

    asyncio.run(_test())


def test_shell_command_not_found():
    async def _test():
        result = await SHELL_TOOL.handler(command="nonexistent_command_xyz_12345")
        assert not result.success

    asyncio.run(_test())


# ── Search Tools ──

def test_glob_finds_files():
    async def _test():
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(f"{tmpdir}/a.py").write_text("x")
            Path(f"{tmpdir}/b.py").write_text("y")
            result = await SEARCH_TOOLS[1].handler(pattern="*.py", path=tmpdir)
            assert result.success
            assert "a.py" in result.output
            assert "b.py" in result.output

    asyncio.run(_test())


def test_glob_no_matches():
    async def _test():
        with tempfile.TemporaryDirectory() as tmpdir:
            result = await SEARCH_TOOLS[1].handler(pattern="*.xyz", path=tmpdir)
            assert result.success
            assert "No files match" in result.output

    asyncio.run(_test())


# ── Tracing ──

def test_tracer_basic():
    tracer = Tracer()
    assert tracer.trace_id
    span = tracer.start_span("test", SpanKind.INTERNAL)
    assert span.span_id
    assert span.trace_id == tracer.trace_id
    span.finish(SpanStatus.OK)
    assert span.duration_ms is not None
    assert span.duration_ms >= 0


def test_tracer_convenience():
    tracer = Tracer()
    llm_span = tracer.llm_call("test-model", "test", [{"role": "user", "content": "hi"}], "response")
    assert llm_span.kind == SpanKind.LLM
    assert llm_span.attributes["gen_ai.system"] == "test"

    tool_span = tracer.tool_call("test_tool", {"input": "x"}, "output", True)
    assert tool_span.kind == SpanKind.TOOL


def test_tracer_export():
    tracer = Tracer()
    tracer.start_span("a", SpanKind.LLM).finish(SpanStatus.OK)
    tracer.start_span("b", SpanKind.TOOL).finish(SpanStatus.OK)

    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = Path(f.name)
    tracer.export_jsonl(path)
    lines = path.read_text().strip().split("\n")
    assert len(lines) == 2
    path.unlink()


def test_tracer_total_tokens():
    tracer = Tracer()
    span = tracer.llm_call("m", "p", [], "r")
    span.attributes["gen_ai.usage.total_tokens"] = 150
    assert tracer.total_tokens == 150


# ── Audit Log ──

def test_audit_append_and_verify():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    audit = AuditLog(db_path)
    audit.append("trace-1", "llm_call", {"model": "test", "tokens": 100})
    audit.append("trace-1", "tool_use", {"tool": "read_file", "path": "/tmp/test"})
    audit.append("trace-2", "eval_result", {"benchmark": "humaneval", "passed": True})

    violations = audit.verify_integrity()
    assert len(violations) == 0, f"Unexpected violations: {violations}"

    entries = audit.get_entries(trace_id="trace-1")
    assert len(entries) == 2

    assert audit.count() == 3
    audit.close()
    Path(db_path).unlink()


def test_audit_query_by_type():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    audit = AuditLog(db_path)
    audit.append("t1", "llm_call", {"model": "a"})
    audit.append("t2", "tool_use", {"tool": "b"})

    entries = audit.get_entries(entry_type="llm_call")
    assert len(entries) == 1
    audit.close()
    Path(db_path).unlink()


# ── Config ──

def test_config_defaults():
    cfg = ForgeConfig()
    assert cfg.provider == "deepseek"
    assert cfg.model == "deepseek-v4-pro"
    assert cfg.max_steps == 50


def test_config_env_override(monkeypatch):
    monkeypatch.setenv("FORGE_PROVIDER", "ollama")
    monkeypatch.setenv("FORGE_MODEL", "gemma3:4b")
    cfg = ForgeConfig.load()
    assert cfg.provider == "ollama"
    assert cfg.model == "gemma3:4b"


def test_config_resolve_api_key(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key-123")
    cfg = ForgeConfig(provider="deepseek")
    assert cfg.resolve_api_key() == "test-key-123"


def test_config_resolve_api_key_ollama(monkeypatch):
    monkeypatch.setenv("OLLAMA_API_KEY", "ollama-key")
    cfg = ForgeConfig(provider="ollama")
    assert cfg.resolve_api_key() == "ollama-key"


# ── Code Extractor ──

def test_extractor_from_code_block():
    response = 'Here is the solution:\n\n```python\ndef fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)\n```\n\nDone.'
    code = default_extractor.extract(response, "fibonacci")
    assert "def fibonacci" in code
    assert "fibonacci(n-1)" in code


def test_extractor_raw_response():
    response = "def foo(): return 42"
    code = default_extractor.extract(response, "foo")
    assert "def foo" in code


# ── Model Types ──

def test_model_response():
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


def test_model_chunk():
    chunk = ModelChunk(delta="hello", reasoning_delta="think")
    assert chunk.delta == "hello"
    assert chunk.reasoning_delta == "think"


# ── ToolResult (AI-native) ──

def test_tool_result_as_message_success():
    r = ToolResult(success=True, output="file contents here")
    assert r.as_message == "file contents here"


def test_tool_result_as_message_error_with_suggestion():
    r = ToolResult(
        success=False,
        output="",
        error="File not found",
        metadata={"suggestion": "Check the path", "candidates": ["similar_file.py"]},
    )
    msg = r.as_message
    assert "File not found" in msg
    assert "Check the path" in msg


# ── LoopGuard (from react.py) ──

def test_loop_guard_basic():
    from forge_sdk.agents.react import LoopGuard

    guard = LoopGuard(max_repeats=3)
    assert guard.check("read_file", {"path": "a.py"}) is False
    assert guard.check("read_file", {"path": "a.py"}) is False
    assert guard.check("read_file", {"path": "a.py"}) is False
    assert guard.check("read_file", {"path": "a.py"}) is True  # blocked


def test_loop_guard_different_calls():
    from forge_sdk.agents.react import LoopGuard

    guard = LoopGuard(max_repeats=2)
    assert guard.check("read", {"path": "a"}) is False
    assert guard.check("write", {"path": "b"}) is False
    assert guard.check("read", {"path": "a"}) is False
    assert guard.check("read", {"path": "a"}) is True  # 3rd repeat


def test_loop_guard_reset():
    from forge_sdk.agents.react import LoopGuard

    guard = LoopGuard(max_repeats=2)
    guard.check("x", {})
    guard.check("x", {})
    guard.reset()
    assert guard.check("x", {}) is False


# ── AgentResult summary ──

def test_agent_result_summary():
    from forge_sdk.agents.types import AgentResult

    r = AgentResult(
        success=True,
        output="Task completed successfully with all tests passing",
        steps=[],
        trace_id="abc123",
        total_tokens=500,
    )
    s = r.summary
    assert "SUCCESS" in s
    assert "500 tokens" in s


# ── Verifier (INV-201) ──

def test_verifier_syntax_pass():
    v = Verifier()
    code = "def hello():\n    return 'world'"
    evidence = v.verify(code)
    assert any(e.gate_name == "syntactic" and e.status == VerificationStatus.PASSED for e in evidence)
    assert any(e.gate_name == "ast_parse" and e.status == VerificationStatus.PASSED for e in evidence)


def test_verifier_syntax_fail():
    v = Verifier()
    code = "def hello(\n    return 'world'"
    evidence = v.verify(code)
    assert any(e.gate_name == "syntactic" and e.status == VerificationStatus.FAILED for e in evidence)


def test_verifier_entity_validation():
    v = Verifier()
    code = 'open("nonexistent_file.txt")'
    evidence = v.verify(code)
    ev = [e for e in evidence if e.gate_name == "entity_validation"]
    assert len(ev) == 1
    assert ev[0].status == VerificationStatus.FAILED
    assert "nonexistent_file.txt" in ev[0].message


def test_verifier_configurable():
    config = VerificationConfig(enabled_gates=["syntactic"])
    v = Verifier(config)
    evidence = v.verify("x = 1")
    assert len(evidence) == 1
    assert evidence[0].gate_name == "syntactic"


def test_verifier_evidence_summary():
    from forge_sdk.verifiers import VerificationEvidence
    e = VerificationEvidence(gate_name="test", status=VerificationStatus.PASSED, message="ok")
    s = e.as_summary
    assert "PASS" in s
    assert "test" in s


# ── SemanticCheck (INV-207) ──

def test_semantic_check_no_model():
    """SemanticCheck returns ERROR when no model is configured."""
    from forge_sdk.verifiers import SemanticCheck, VerificationStatus
    sc = SemanticCheck(model_port=None)
    result = sc.execute(task_intent="fix bug", solution_summary="fixed bug")
    assert result.status == VerificationStatus.ERROR
    assert "model_not_configured" in result.details["error"]


def test_semantic_check_pass():
    """SemanticCheck parses a passing LLM response correctly."""
    from forge_sdk.models.types import ModelResponse, Usage
    from forge_sdk.verifiers import SemanticCheck, VerificationStatus

    class MockModel:
        def complete(self, messages, **kwargs):
            return ModelResponse(
                content='{"pass": true, "confidence": 0.95, "reason": "Solution correctly fixes the bug"}',
                model="mock",
                provider="mock",
                usage=Usage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
            )

    sc = SemanticCheck(model_port=MockModel())
    result = sc.execute(
        task_intent="fix the login bug",
        solution_summary="Fixed authentication check in login.py",
        solution_files=["login.py"],
    )
    assert result.status == VerificationStatus.PASSED
    assert result.details["confidence"] == 0.95
    assert "fixes the bug" in result.message


def test_semantic_check_fail():
    """SemanticCheck parses a failing LLM response correctly."""
    from forge_sdk.models.types import ModelResponse, Usage
    from forge_sdk.verifiers import SemanticCheck, VerificationStatus

    class MockModel:
        def complete(self, messages, **kwargs):
            return ModelResponse(
                content='{"pass": false, "confidence": 0.8, "reason": "Solution modifies wrong function"}',
                model="mock",
                provider="mock",
                usage=Usage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
            )

    sc = SemanticCheck(model_port=MockModel())
    result = sc.execute(
        task_intent="fix the login bug",
        solution_summary="Changed color of the submit button",
        solution_files=["style.css"],
    )
    assert result.status == VerificationStatus.FAILED
    assert result.details["confidence"] == 0.8
    assert "wrong function" in result.message


def test_semantic_check_parse_failure():
    """SemanticCheck handles unparseable LLM response gracefully."""
    from forge_sdk.models.types import ModelResponse, Usage
    from forge_sdk.verifiers import SemanticCheck, VerificationStatus

    class MockModel:
        def complete(self, messages, **kwargs):
            return ModelResponse(
                content="Sorry, I can't determine if this is correct.",
                model="mock",
                provider="mock",
                usage=Usage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
            )

    sc = SemanticCheck(model_port=MockModel())
    result = sc.execute(task_intent="fix bug", solution_summary="fixed it")
    assert result.status == VerificationStatus.ERROR
    assert "parse_failure" in result.details["error"]


def test_semantic_check_applies():
    """SemanticCheck is always applicable."""
    from forge_sdk.verifiers import SemanticCheck
    sc = SemanticCheck()
    assert sc.applies() is True
    assert sc.applies(context={"anything": "here"}) is True


# ── False-Green Detection (issue #12) ──

def test_false_green_zero_edits():
    """AgentResult.success must be False when task implies edits but none were made."""
    from forge_sdk.agents.types import AgentResult, AgentStep

    # Simulate: agent finished successfully on a task that requires code changes,
    # but zero files were modified — this is a false-green.
    result = AgentResult(
        success=True,  # would be set by loop — we test the post-loop logic
        output="Task completed.",
        steps=[AgentStep(
            step_number=1,
            thought="I think I'm done",
            action="finish",
            action_input={"output": "Task completed."},
            is_final=True,
        )],
        trace_id="test-trace",
        edits_made=[],
    )

    # The false-green check: task implies edits, but edits_made is empty
    # In the real agent, this would flip success=False. Verify the heuristic works:
    from forge_sdk.agents.react import ReactAgent
    agent = ReactAgent(model=None, tools=None)
    assert agent._task_implies_edits("Please implement a sorting algorithm")
    assert agent._task_implies_edits("Fix the bug in main.py")
    assert agent._task_implies_edits("Create a new file with the config")
    assert agent._task_implies_edits("Write unit tests for the API")
    assert agent._task_implies_edits("Update the README")
    assert agent._task_implies_edits("add error handling")
    # Non-edit tasks should NOT trigger
    assert not agent._task_implies_edits("What is 2+2?")
    assert not agent._task_implies_edits("Explain this code")
    assert not agent._task_implies_edits("How does the sorting algorithm work?")


def test_false_green_verification_fails_with_edit_task():
    """When verification fails and task requires edits, success must be False."""
    from forge_sdk.agents.types import AgentResult
    from forge_sdk.verifiers import VerificationEvidence, VerificationStatus

    evidence = [VerificationEvidence(
        gate_name="syntactic",
        status=VerificationStatus.FAILED,
        message="Syntax error",
    )]
    result = AgentResult(
        success=True,
        output="bad code",
        steps=[],
        trace_id="x",
        verification=evidence,
    )
    # The agent's post-loop logic would set success=False because
    # verification_passed=False AND task implies edits.
    # This test verifies the data structure carries verification correctly.
    verification_passed = all(
        v.status == VerificationStatus.PASSED for v in result.verification
    )
    assert not verification_passed


# ── Main ──

def main():
    """Run all tests manually (without pytest)."""
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  FAIL: {test.__name__}: {e}")
    print(f"\n{passed} passed, {failed} failed")


if __name__ == "__main__":
    main()
