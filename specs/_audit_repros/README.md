# Audit repros — AUDIT-MATRIX-001

Each script is self-contained, uses only real `forge_sdk` classes (no mocking the
vulnerable path), and prints a clear pass/fail line. Run from the repo root:

```
python3 specs/_audit_repros/repro_a_injection_survival.py
python3 specs/_audit_repros/repro_b_knowledge_id_collision.py
python3 specs/_audit_repros/repro_c_gate_bypass.py
```

All three currently print the **vulnerable** outcome (`True`/collision present) on
unpatched code, as of 2026-06-30. When a fix lands for F1/F2/F6, re-run these and
flip them into regression tests under `tests/harness/` asserting the *safe*
outcome — do not delete them, convert them.
