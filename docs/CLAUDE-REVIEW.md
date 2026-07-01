# Claude Review: Forge Rust Port — Complete Plan Handoff

**Handoff Date:** 2026-07-01
**Author:** Agentic Engineering Team (7 parallel agents)
**Standards:** SOC 2 Type II + DO-178C DAL A + IEC 61508 SIL 3
**Security:** STRICTEST Defense-in-Depth + Privacy-by-Design

> This document is the handoff from an engineering sub-agent team to Claude for
> in-depth review. The team has produced spec documents and is actively writing
> Rust code in parallel. Claude should review for correctness, completeness,
> anti-duplication, and safety.

---

## 1. Executive Summary

We are porting **forge-sdk** (Python AI agent SDK at
/Users/srinji/forge-experience/) to a **Rust workspace** at the same path.
The Rust port is structured as a 9-crate workspace with:

- **forge-core** — zero-heavy-dep library (async-trait, thiserror, serde, tokio, uuid)
- **forge-cli** — clap binary with 7 subcommands
- **forge-tui** — spine-based TUI (separate binary, crossterm+ratatui)
- **forge-gemini** — google-genai-rs v0.3 wrapper
- **forge-ollama/forge-openai** — reqwest REST providers
- **forge-mcp** — MCP rust-sdk integration
- **forge-harness** — eval + test harness

The spec is finalized at `/Users/srinji/forge-experience/docs/FORGE-RUST-TUI-SPEC.md`
(1,283 lines, 55 sections). 7 parallel sub-agents are producing code now.

---

## 2. What Needs Review

### 2.1 Architecture Review

**Docs to review:**

| Doc | Path | Status |
|-----|------|--------|
| Main Spec | FORGE-RUST-TUI-SPEC.md | ✅ FINALIZED |
| Change Order | CHANGE_ORDER_MAP.md | ✅ WRITTEN |
| Topological Map | TOPOLOGICAL_MAP.md | ✅ WRITTEN |
| Refactored Plan | REFACTORED-PLAN-COMPLETE.md | ✅ WRITTEN |

**Key architectural questions for Claude:**

1. Is the 9-crate workspace correctly scoped? Should any crates be merged or split?
2. Is the anti-duplication boundary with lgwks (lgwks_model_mesh, lgwks_ui, lgwks_cognition) correct?
3. Is the forge-core zero-heavy-dep constraint achievable for all 16 modules?
4. Is the 13-event taxonomy complete for forge's role as execution plane?
5. Should forge-tui have any integration with forge-cli, or is separate binary correct?

### 2.2 SOC 2 Type II Review

**Controls to verify:**

| TSC | forge Control | Review Question |
|-----|---------------|-----------------|
| Security | PermissionGate + anti-slop | Is the anti-slop strategy set complete? |
| Security | Doctor L0-L5 | Does doctor cover all security failure modes? |
| Availability | Session checkpointing | Can session recovery handle crashes mid-write? |
| Proc. Integrity | 5-gate verification | Do evidence types map to all 10 evidence taxonomies? |
| Confidentiality | Local-only execution | Are there ANY code paths that could leak data? |
| Privacy | Configurable retention | Is retention actually enforced on checkpoint files? |

### 2.3 DO-178C DAL A Review

**Level A objectives to verify:**

1. **Requirements traceability**: Every struct, enum variant, and function has a REQ-ID
2. **MC/DC coverage**: Tests exercise every condition in every decision
3. **No dead code**: All match arms are used; no unreachable paths
4. **Robustness**: Every fallible operation has documented error path
5. **Configuration management**: All build artifacts are pinned and reproducible

### 2.4 IEC 61508 SIL 3 Review

**Functional safety questions:**

1. Are all 7 FailureReason variants exercised in tests?
2. Does LoopGuard cover all 5 break paths (max_steps, max_tokens, max_cost, convergence, auth)?
3. Is there a single point of failure in the verification pipeline?
4. Is the audit hash chain tamper-evident?
5. Can the PermissionGate fail open (allow when should deny)?

### 2.5 Anti-Duplication Review

**Critical boundary with lgwks:**

| forge Module | lgwks Counterpart | Duplication Risk | Review Action |
|-------------|-------------------|------------------|---------------|
| event.rs | lgwks_cognition.py | LOW — different purpose (execution events vs cognitive records) | Verify field-by-field |
| permission.rs | lgwks_agent.py (effect_class) | MEDIUM — both classify actions | forge uses ActionClassification enum; lgwks uses string matching |
| session.rs | lgwks (daemon state) | LOW — forge manages checkpoints; lgwks manages daemon state | Verify checkpoint format |
| semantic.rs | lgwks_cognition.py (meaning frames) | MEDIUM — both have semantic labels | forge labels are execution-plane; lgwks labels are memory-plane |
| okf.rs | None in lgwks yet | NONE — new capability | Review OKF schema conformance |
| experience.rs | lgwks_cognition.py (causal_tape) | MEDIUM — both have episode concepts | forge episodes are execution-focused; lgwks tapes are memory-focused |
| router.rs | lgwks_model_port.py | MEDIUM — both route model calls | forge router is auto-fallback; lgwks port is escalation ladder |
| palette.rs | lgwks_ui.py (color constants) | LOW — different hex values, different tech stack | Verify hex values are unique |

### 2.6 Defense-in-Depth Review

**Layer-by-layer verification:**

| Layer | Control | Verification |
|-------|---------|-------------|
| L5 Physical | security.rs sandbox | Test: path traversal blocked for known attack patterns |
| L4 Audit | audit.rs hash chain | Test: tampered audit entry detected on verification |
| L3 Verify | verifier.rs pipeline | Test: fail-fast on gate failure; evidence chain complete |
| L2 Permission | permission.rs gate | Test: all 3 modes (interactive/yolo/plan) with anti-slop |
| L1 Process | guard.rs loopbreaker | Test: all 5 break paths triggered; FailureReason set |
| L0 Network | port.rs isolation | Test: no outbound calls without explicit provider config |

---

## 3. File Tree (What Exists vs What's Being Built)

```
forge-experience/
├── docs/                          # All exist (5 spec docs)
├── forge-core/src/                # 🔄 BEING BUILT by backend-forge-core + backend-interpretation
│   ├── event.rs                   # 13 event discriminators
│   ├── result.rs                  # AgentResult + FailureReason + ChangeManifest
│   ├── context.rs                 # AgentContext
│   ├── port.rs                    # ModelPort trait
│   ├── agent.rs                   # Agent trait
│   ├── permission.rs              # PermissionGate
│   ├── verifier.rs                # 5-gate pipeline
│   ├── session.rs                 # Session checkpointing
│   ├── doctor.rs                  # L0-L5 DoctorEngine
│   ├── guard.rs                   # LoopGuard
│   ├── security.rs                # Shell fix + path safety
│   ├── tracer.rs                  # Observability spans
│   ├── audit.rs                   # Audit hash chain
│   ├── config.rs                  # H16: Config persistence
│   ├── router.rs                  # Auto-model fallback
│   ├── semantic.rs                # 8 SemanticLabels
│   ├── okf.rs                     # OKF doc types
│   └── experience.rs              # Episode types
├── forge-cli/src/                 # 🔄 BEING BUILT by cli-engineer
│   ├── main.rs + 7 commands + 2 renderers
├── forge-tui/src/                 # 🔄 BEING BUILT by tui-designer
│   ├── main.rs + app/spine/palette/inspector/config_screen
├── forge-harness/src/             # 🔄 BEING BUILT by qa-harness
│   ├── lib.rs + 8 test files
├── forge-gemini/                  # 🔄 BEING BUILT by backend-forge-core
├── Cargo.workspace.toml           # 🔄 BEING BUILT by devops-ci
└── .github/workflows/            # 🔄 BEING BUILT by devops-ci
```

---

## 4. Current Agent Status (as of handoff)

| Agent | Status | Work Product |
|-------|--------|-------------|
| architect-karpathy | ✅ INSTRUCTED | reviewing spec, will produce ARCHITECTURE.md |
| backend-forge-core | ✅ UPDATED with SOC2/DO178C | writing 18 .rs files |
| backend-interpretation | ✅ UPDATED with defense-in-depth | writing semantic.rs, okf.rs, experience.rs |
| devops-ci | ✅ SPAWNED | writing Cargo.tomls, CI/CD, playbook |
| tui-designer | ✅ SPAWNED with anti-duplication | writing forge-tui/src/*.rs |
| cli-engineer | ✅ SPAWNED | writing forge-cli/src/*.rs |
| qa-harness | ✅ SPAWNED | writing tests + DO178C/SOC2 docs |

---

## 5. Critical Questions for Claude

1. **Crate boundary correctness**: Are forge-core's 16 modules the right scope for
   a zero-heavy-dep library? Should config.rs or router.rs be separate crates?

2. **Event completeness**: Is the 13-event taxonomy (RunStart, RunEnd, RunError,
   Think, Act, Observe, Verify, FileEdit, TokenUsage, StateUpdate, Decide, Converge,
   PermissionGate) sufficient for forge's role as execution plane?

3. **Anti-duplication with lgwks**: Are we correctly scoping forge as execution plane
   and lgwks as control plane? Any module that should be shared rather than duplicated?

4. **Safety certification readiness**: Do the DO-178C and IEC 61508 mappings make
   sense for an AI agent SDK? Any additional standards we should consider?

5. **TUI dependency**: forge-tui uses crossterm + ratatui. Is this the right choice
   for a spine-based layout, or would a lower-level approach be better?

6. **Serialization format**: All forge-core types derive Serialize/Deserialize for JSON.
   Should we use a binary format (bincode, messagepack) for checkpoint/audit files?

---

## 6. Handoff to Claude

Claude should:

1. Read all spec docs in order:
   - `docs/FORGE-RUST-TUI-SPEC.md`
   - `docs/CHANGE_ORDER_MAP.md`
   - `docs/TOPOLOGICAL_MAP.md`
   - `docs/REFACTORED-PLAN-COMPLETE.md`
   - `docs/CLAUDE-REVIEW.md` (this file)

2. Review the Python baseline code:
   - `/Users/srinji/forge-experience/src/forge_sdk/` (Python SDK)
   - `/Users/srinji/logicalworks-/lgwks_model_mesh.py` (model law)
   - `/Users/srinji/logicalworks-/lgwks_model_port.py` (escalation ladder)
   - `/Users/srinji/logicalworks-/lgwks_ui.py` (anti-duplication boundary)

3. Check the meaning_runtime_okf context:
   - `/Users/srinji/Downloads/meaning_runtime_okf/` (MRIL blueprint)

4. Provide a structured review covering:
   - Architecture correctness
   - SOC 2 Type II control completeness
   - DO-178C DAL A readiness
   - IEC 61508 SIL 3 functional safety
   - Anti-duplication with lgwks
   - Defense-in-depth layer completeness
   - Privacy-by-design principle adherence
   - Any gaps or risks

---

*End of Claude review handoff. The engineering team awaits your review.*

