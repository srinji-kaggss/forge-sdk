# Quality Gate — Mathematical Targets

This document defines the mathematical quality targets for forge-sdk, the measurement methodology, and the current state. Inspired by Geely's approach: **"Bet money it'll work"** means certification-backed, not marketing-backed.

## Philosophy

From safety-critical standards (DO-178C, ISO 26262, IEC 61508):

1. **Every failure mode must be identified** — we attack our own agent before shipping
2. **Every mitigation must be verified** — LoopGuard, entity validation, semantic check
3. **Every verification must have evidence** — trace spans, audit entries, hash-chain integrity
4. **No false confidence** — if the agent can't prove it worked, it reports failure

## Mathematical Targets

### 1. Security Coverage (ISO 26262 — every hazard mitigated)

**Definition:** Percentage of known attack vectors that are blocked.

**Measurement:**
```bash
# Run attack suite
DEEPSEEK_API_KEY=... python attack_deepseek.py
# Check ATTACK-RESULTS.json for blocked vs bypassed
```

**Target:** 100% (8/8 attack vectors blocked)
**Current:** 100%
**Evidence:** `ATTACK-RESULTS.json`, `ADVERSARIAL-REPORT.md`

### 2. Observability Coverage (DO-178C §6.3 — every decision has evidence)

**Definition:** Percentage of agent steps that emit both a trace span and an audit entry.

**Measurement:**
```bash
# Run agent, then check trace and audit
forge run "task" --provider deepseek
forge audit --limit 100
# Count steps in trace vs steps in audit
```

**Target:** 100% (every step emits span + audit entry)
**Current:** 100% (wired in agent loop)
**Evidence:** `.forge/traces/*.jsonl`, `.forge/audit.db`

### 3. Convergence (IEC 61508 — system reaches terminal state)

**Definition:** Percentage of runs that reach a terminal state (finish or explicit fail) without spinning.

**Measurement:**
```bash
# Run 10 different tasks
for i in $(seq 1 10); do
  forge run "task $i" --max-steps 10 2>&1 | grep -c "Max steps reached"
done
# Count "Max steps reached" occurrences
```

**Target:** 100% (no spinning)
**Current:** ~90% (convergence nudge added)
**Evidence:** Agent output, step counts

### 4. False-Green Rate (DO-178C — verification must not lie)

**Definition:** Percentage of reported successes that are actually successful.

**Measurement:**
```bash
# Run agent on known-failing tasks
forge run "Write code that imports nonexistent_module" --provider deepseek
# Check if agent reports SUCCESS
```

**Target:** 0% false-positive success rate
**Current:** 0% (detection works)
**Evidence:** Attack suite results, test_false_green_* tests

### 5. Code Quality (Geometric Mean)

**Definition:** Geometric mean of 4 axes across all source files:

| Axis | Weight | What it measures |
|------|--------|------------------|
| Self-contained | 25% | Module can be understood in isolation |
| Breakability | 25% | How easy to break with bad input |
| Explainability | 25% | Docstrings, type hints, stable IDs |
| Attack surface | 25% | Input validation, error handling |

**Measurement:**
```bash
python hardening.py src/forge_sdk
```

**Target:** >0.90 average, no file below 0.80
**Current:** 0.84 average
**Evidence:** `hardening.py` output

### 6. Test Coverage (ISO 26262 — every failure mode tested)

**Definition:** Number of tests covering every identified failure mode.

**Measurement:**
```bash
python -m pytest tests/ -v --tb=short
```

**Target:** 100+ tests, every failure mode from attack suite covered
**Current:** 75 tests (46 forge-sdk + 29 lgwks)
**Evidence:** pytest output

## Overall Score

**Geometric mean** of all 6 dimensions:

```
overall = (security × observability × convergence × false_green × code_quality × test_coverage) ^ (1/6)
```

**Target:** >0.90
**Current:** Calculated per run in `hardening.py`

## How to Verify

1. Run `python hardening.py src/forge_sdk` — check scores
2. Run `python attack_deepseek.py` — check security
3. Run `python -m pytest tests/ -v` — check tests pass
4. Run `forge audit --verify` — check audit integrity
5. Run `forge run "task"` — check trace has spans

## Safety-Critical Mapping

| forge-sdk Concept | DO-178C Equivalent | ISO 26262 Equivalent | IEC 61508 Equivalent |
|-------------------|--------------------|-----------------------|-----------------------|
| Trace spans | §6.3 Verification evidence | §8 Supporting processes | §7 Information management |
| Audit entries | §8 Configuration management | §8 Supporting processes | §8 Confidentiality |
| LoopGuard | §5.2 Software architectural design | §7 Design | §6 Software safety validation |
| Entity validation | §6.5 Source code verification | §9 Software unit verification | §7 Software verification |
| SemanticCheck | §7.2 Integration testing | §10 Software integration | §8 Functional safety assessment |
| Convergence | §5.1.2 Software safety requirements | §6 Concept phase | §5 Safety lifecycle |
| False-green fix | §6.5.2 Code coverage | §9.4.2 Metric: code coverage | §7.4.4 Validation |
