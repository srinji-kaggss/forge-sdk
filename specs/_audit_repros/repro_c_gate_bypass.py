"""AUDIT-MATRIX-001 F2 — proves a freshly-added "evolved" fragment passes the
compose() score gate (score >= 0.2) before any outcome evidence exists.
Run: python3 specs/_audit_repros/repro_c_gate_bypass.py
Expected: MALICIOUS TEXT IN COMPOSE BEFORE ANY EVIDENCE: True (this is the BUG)."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))
from forge_sdk.harness.profiles import AgentProfile
from forge_sdk.harness.adaptive import AdaptivePrompt

profile = AgentProfile(name="coder", domain="python")
prompt = AdaptivePrompt(profile)
frag = prompt.add_fragment(content="MALICIOUS UNVALIDATED INSTRUCTION TEXT", priority=60, source="evolved")
print("fragment score before any outcome recorded:", frag.score)
composed = prompt.compose("some task")
print("MALICIOUS TEXT IN COMPOSE BEFORE ANY EVIDENCE:", "MALICIOUS UNVALIDATED INSTRUCTION TEXT" in composed)
