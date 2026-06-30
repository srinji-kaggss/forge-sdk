"""Smoke tests for forge_v2 core components."""

import hashlib
import json
import time

from forge_v2.agent_loop.loop_guard import LoopGuard
from forge_v2.agents.types import AgentResult, VerificationEvidence, VerificationStatus
from forge_v2.memory import MemoryEntry, MemorySystem, MemoryTier
from forge_v2.policy import PolicyDecision, PolicyKernel, RiskLevel, Permission, ToolLease
from forge_v2.verifiers import VerificationConfig, Verifier


def test_loop_guard_basic():
    guard = LoopGuard(max_repeats=3)
    assert guard.check("read_file", {"path": "a.py"}) is False
    assert guard.check("read_file", {"path": "a.py"}) is False
    assert guard.check("read_file", {"path": "a.py"}) is False
    assert guard.check("read_file", {"path": "a.py"}) is True  # blocked
    assert guard.total_calls == 4
    assert guard.unique_calls == 1


def test_loop_guard_different_calls():
    guard = LoopGuard(max_repeats=2)
    assert guard.check("read", {"path": "a"}) is False
    assert guard.check("write", {"path": "b"}) is False
    assert guard.check("read", {"path": "a"}) is False
    assert guard.check("read", {"path": "a"}) is True  # 3rd repeat
    assert guard.check("write", {"path": "b"}) is False  # only 2nd
    assert guard.unique_calls == 2


def test_loop_guard_reset():
    guard = LoopGuard(max_repeats=2)
    guard.check("x", {})
    guard.check("x", {})
    guard.reset()
    assert guard.check("x", {}) is False  # reset worked


def test_loop_guard_repeated_calls():
    guard = LoopGuard(max_repeats=1)
    guard.check("a", {})
    guard.check("a", {})
    guard.check("b", {})
    repeated = guard.repeated_calls()
    assert len(repeated) == 1


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


def test_verifier_import_check():
    v = Verifier()
    code = "import os\nimport json\ndef f(): return os.path.join('a', 'b')"
    evidence = v.verify(code)
    assert any(e.gate_name == "import_check" and e.status == VerificationStatus.PASSED for e in evidence)


def test_verifier_configurable():
    config = VerificationConfig(enabled_gates=["syntactic"])
    v = Verifier(config)
    evidence = v.verify("x = 1")
    assert len(evidence) == 1
    assert evidence[0].gate_name == "syntactic"


def test_policy_kernel_basic():
    pk = PolicyKernel()
    pk.register_tool_risk("read_file", RiskLevel.LOW)
    pk.register_tool_risk("write_file", RiskLevel.MEDIUM)
    pk.register_tool_risk("shell_exec", RiskLevel.HIGH)
    pk.register_tool_risk("sudo", RiskLevel.CRITICAL)

    d1 = pk.request_lease("read_file", (Permission.READ,))
    assert d1.allowed is True

    d2 = pk.request_lease("sudo", (Permission.EXEC,))
    assert d2.allowed is False  # CRITICAL needs human gate


def test_policy_kernel_deny():
    pk = PolicyKernel()
    pk.deny_tool("rm_rf")
    d = pk.request_lease("rm_rf", (Permission.EXEC,))
    assert d.allowed is False


def test_policy_kernel_lease_expiry():
    pk = PolicyKernel()
    pk.register_tool_risk("fast_tool", RiskLevel.LOW)
    pk.request_lease("fast_tool", (Permission.READ,), ttl_seconds=0.01)
    time.sleep(0.02)
    d = pk.check_lease("fast_tool")
    assert d.allowed is False


def test_policy_kernel_summary():
    pk = PolicyKernel()
    pk.register_tool_risk("a", RiskLevel.LOW)
    pk.request_lease("a", (Permission.READ,))
    s = pk.summary()
    assert s["active_leases"] == 1


def test_memory_working_tier():
    mem = MemorySystem(":memory:")
    mem.write("current task context", MemoryTier.WORKING)
    results = mem.read(tier=MemoryTier.WORKING)
    assert len(results) == 1
    assert results[0].content == "current task context"
    mem.close()


def test_memory_episodic_tier():
    mem = MemorySystem(":memory:")
    mem.write("fixed bug in auth.py", MemoryTier.EPISODIC, source="auth.py")
    results = mem.read(tier=MemoryTier.EPISODIC)
    assert len(results) == 1
    assert results[0].source == "auth.py"
    mem.close()


def test_memory_query():
    mem = MemorySystem(":memory:")
    mem.write("auth module uses JWT", MemoryTier.SEMANTIC)
    mem.write("payment module uses Stripe", MemoryTier.SEMANTIC)
    results = mem.read(query="JWT")
    assert len(results) == 1
    mem.close()


def test_memory_count():
    mem = MemorySystem(":memory:")
    mem.write("a", MemoryTier.WORKING)
    mem.write("b", MemoryTier.EPISODIC)
    mem.write("c", MemoryTier.EPISODIC)
    assert mem.count(MemoryTier.WORKING) == 1
    assert mem.count(MemoryTier.EPISODIC) == 2
    mem.close()


def test_memory_invalidate():
    mem = MemorySystem(":memory:")
    entry = mem.write("temporary", MemoryTier.EPISODIC)
    assert mem.invalidate(entry.entry_id) is True
    assert mem.count(MemoryTier.EPISODIC) == 0
    mem.close()


def test_agent_result_verification_summary():
    r = AgentResult(success=True, output="code", steps=[], trace_id="x")
    assert r.verification_summary == "no verification run"

    r2 = AgentResult(
        success=True,
        output="code",
        steps=[],
        trace_id="x",
        verification=[
            VerificationEvidence(gate_name="syn", status=VerificationStatus.PASSED),
            VerificationEvidence(gate_name="ast", status=VerificationStatus.PASSED),
        ],
    )
    assert r2.verification_passed is True
    assert r2.verification_summary == "2/2 gates passed"


def test_agent_result_verification_fail():
    r = AgentResult(
        success=True,
        output="code",
        steps=[],
        trace_id="x",
        verification=[
            VerificationEvidence(gate_name="syn", status=VerificationStatus.PASSED),
            VerificationEvidence(gate_name="ast", status=VerificationStatus.FAILED),
        ],
    )
    assert r.verification_passed is False
