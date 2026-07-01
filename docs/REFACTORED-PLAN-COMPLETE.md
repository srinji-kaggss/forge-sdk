# Forge Rust Port — Complete Refactored Plan

**Date:** 2026-07-01
**Author:** Agentic Engineering Team (7 parallel agents)
**Standards:** SOC 2 Type II + DO-178C DAL A + IEC 61508 SIL 3
**Philosophy:** Defense-in-Depth + Privacy-by-Design + DeterministicEscalation

---

## Part 1: The Runtime Ecology — Where Forge Fits

### The Ladder (from lgwks_model_port.py)

```
deterministic (math) ──> sensor (symbolic/narrow ML) ──> generative (LLM/AI)
    ^                                                        ^
    |                                                        |
  lgwks handles this                                      forge IS this
  (scaffolding, planning,                                 (deep reasoning,
   easy stuff, routing)                                     code synthesis,
                                                            verification)
```

**Forge is the AI in the ecology.** It is what gets called when the deterministic
runtime (lgwks) cannot answer and escalates up the trust ladder. Forge does:

- Deep code reasoning and synthesis
- Multi-step tool orchestration
- Verification of its own outputs
- Audit trail generation for every action
- Permission-gated execution under human supervision

**lgwks does NOT duplicate forge.** lgwks owns the control plane (memory, routing,
context, session management, model mesh registry). forge owns the execution plane
(model calls, tool execution, verification, audit, TUI observability).

### Anti-Duplication Boundary (FORGE vs LGWKS)

| Capability | Owner | Why NOT duplicated |
|------------|-------|---------------------|
| Model mesh (registry + roles) | lgwks (lgwks_model_mesh.py) | forge queries mesh for model IDs; does NOT maintain its own registry |
| Model port (escalation ladder) | lgwks (lgwks_model_port.py) | forge implements ModelPort trait; lgwks provides the port instance |
| Memory (episodic/semantic) | lgwks (lgwks_cognition.py) | forge emits episodes; lgwks stores and promotes them |
| Navmap / substrate graph | lgwks (lgwks_repo_scan.py) | forge queries context from navmap; does NOT build it |
| UI spine visual language | lgwks (lgwks_ui.py → Python) | forge-tui (Rust) is NEW impl with different tech, palette, purpose |
| Event stream (11→13 types) | forge (events.py → event.rs) | forge's OWN event taxonomy; lgwks consumes events from forge |
| Permission gate | forge (permission.rs) | forge's OWN safety mechanism; lgwks trusts forge's verdict |
| Verification (5-gate) | forge (verifier.rs) | forge's OWN pipeline; lgwks reads evidence from forge |
| Audit hash chain | forge (audit.rs) | forge's OWN audit; lgwks indexes forge's audit IDs |

---

## Part 2: 7-Agent Team Structure & Current Status

| # | Agent ID | Plane | Status | Deliverables |
|---|----------|-------|--------|-------------|
| 1 | architect-karpathy | All 4 | ✅ SPAWNED + UPDATED | ARCHITECTURE.md, requirements matrix, FMEA |
| 2 | backend-forge-core | Execution | ✅ SPAWNED + UPDATED | 18 .rs files in forge-core/src/ |
| 3 | backend-interpretation | Interpretation | ✅ SPAWNED + UPDATED | semantic.rs, okf.rs, experience.rs |
| 4 | devops-ci | Execution (infra) | ✅ SPAWNED | Cargo.tomls, CI/CD, PLAYBOOK.md |
| 5 | tui-designer | Execution (UX) | ✅ SPAWNED | forge-tui/src/*.rs (8 files) |
| 6 | cli-engineer | Execution (UX) | ✅ SPAWNED | forge-cli/src/*.rs (12+ files) |
| 7 | qa-harness | Execution (quality) | ✅ SPAWNED | tests, schemas, DO178C/SOC2 docs |

---

## Part 3: File Tree (What Each Agent Produces)

```
forge-experience/
├── docs/
│   ├── FORGE-RUST-TUI-SPEC.md      # Original 1283-line spec (agent #1 validates)
│   ├── CHANGE_ORDER_MAP.md          # Phase map (agent #1 refines)
│   ├── TOPOLOGICAL_MAP.md           # This topology (agent #1 owns)
│   ├── REFACTORED-PLAN-COMPLETE.md  # THIS FILE
│   ├── CLAUDE-REVIEW.md             # Claude review doc (agent #1 writes)
│   └── ARCHITECTURE.md              # Hardened architecture (agent #1)
├── forge-core/                      # Agent #2 + #3 produce
│   ├── Cargo.toml                   # Agent #4 produces
│   └── src/
│       ├── lib.rs
│       ├── event.rs                 # 13 event discriminator types
│       ├── result.rs               # AgentResult, FailureReason (7 variants)
│       ├── context.rs              # AgentContext
│       ├── port.rs                 # ModelPort trait
│       ├── agent.rs                # Agent trait
│       ├── permission.rs           # PermissionGate + anti-slop
│       ├── verifier.rs             # 5-gate verification pipeline
│       ├── session.rs              # Session + checkpoints
│       ├── doctor.rs               # L0-L5 DoctorEngine
│       ├── guard.rs                # LoopGuard (5 break paths)
│       ├── security.rs             # Shell fix + path safety
│       ├── tracer.rs               # Span/SpanKind observability
│       ├── audit.rs                # Audit hash chain
│       ├── config.rs               # H16: Config persistence (NEW)
│       ├── router.rs               # Auto-model fallback (NEW)
│       ├── semantic.rs             # 8 SemanticLabel variants (agent #3)
│       ├── okf.rs                  # OKF doc types (agent #3)
│       └── experience.rs           # Episode types (agent #3)
├── forge-cli/                       # Agent #6 produces
│   ├── Cargo.toml
│   └── src/
│       ├── main.rs
│       ├── commands/run.rs
│       ├── commands/doctor.rs
│       ├── commands/session.rs
│       ├── commands/config.rs       # H16 fix
│       ├── commands/eval.rs
│       ├── commands/audit.rs
│       └── render/
│           ├── mod.rs
│           ├── text.rs
│           └── ndjson.rs
├── forge-tui/                       # Agent #5 produces
│   ├── Cargo.toml
│   └── src/
│       ├── main.rs
│       ├── app.rs
│       ├── spine.rs
│       ├── palette.rs
│       ├── inspector.rs
│       └── config_screen.rs         # H16 fix
├── forge-gemini/                    # Agent #2 produces
│   ├── Cargo.toml
│   └── src/lib.rs
├── forge-harness/                   # Agent #7 produces
│   ├── Cargo.toml
│   ├── src/lib.rs
│   └── tests/*.rs
├── Cargo.workspace.toml             # Agent #4 produces
├── .github/workflows/forge-ci.yml   # Agent #4 produces
├── docs/PLAYBOOK.md                 # Agent #4 produces
└── keel.yaml                        # Agent #4 produces
```

---

## Part 4: Integration Points with lgwks

### forge → lgwks (forge emits, lgwks consumes)

1. **Episode records** — forge.experience.Episode → lgwks consumes for memory promotion
2. **Verification evidence** — forge.verifier.VerificationEvidence → lgwks uses for growth policy
3. **Audit hash chain** — forge.audit.AuditEntry → lgwks indexes for provenance
4. **Change manifests** — forge.result.ChangeManifest → lgwks records in daemon ledger
5. **Semantic labels** — forge.semantic.SemanticLabel → lgwks uses for salience scoring

### lgwks → forge (lgwks configures, forge executes)

1. **Model mesh selection** — lgwks_model_mesh.model_for_role(role, trust_class) → forge uses as ModelPort
2. **Navmap context** — lgwks_repo_scan → forge uses as AgentContext.cwd + file context
3. **Substrate graph** — lgwks_oriented → forge uses for dependency analysis
4. **Memory packets** — lgwks_cognition → forge uses for episode replay
5. **Config/law** — lgwks_substrate_config → forge reads for permission defaults

### Shared IDs (cross-plane)

- trace_id (spans execution plane)
- episode_id (binds execution→memory)
- evidence_id (binds verification→growth)
- okf_doc_id (binds OKF→verification gates)
- invariant_id (binds invariants→wrong-abstraction detector)
- memory_id (binds memory→promotion decisions)

---

## Part 5: Defense-in-Depth Layers (Final)

| Layer | Name | forge-core Module | SOC 2 | DO-178C | IEC 61508 |
|-------|------|-------------------|-------|---------|-----------|
| L5 | Physical/OS | security.rs (sandbox) | Physical | HW/SW | HW integrity |
| L4 | Audit | audit.rs, tracer.rs | Monitoring | Traceability | Diagnosis |
| L3 | Verification | verifier.rs | Processing Integrity | Verifiability | Functional Safety |
| L2 | Permission | permission.rs | Access Control | Sec. Reqs | Access Control |
| L1 | Process | guard.rs, security.rs | Logical Security | Robustness | Fault Tolerance |
| L0 | Network | port.rs, router.rs | Confidentiality | Data Security | Comms Security |

### Privacy-by-Design (10 inviolable rules)

1. **Local-first**: forge-core runs entirely on user machine. Zero cloud dependency.
2. **No telemetry**: forge-cli and forge-tui make ZERO unsolicited network calls.
3. **Config persistence**: ~/.forge/ — user controls every setting.
4. **Always-on audit**: every action logged to ~/.forge/audit/. Cannot be disabled.
5. **Configurable retention**: user sets TTL, max size, max checkpoints.
6. **Right to delete**: forge session delete + rm -rf ~/.forge removes all traces.
7. **Full transparency**: TUI shows every model call, every tool execution.
8. **Consent-based**: permission gate requires approval for non-safe actions.
9. **Terminal respect**: NO_COLOR, CLICOLOR, CLICOLOR_FORCE honored.
10. **Machine-readable**: --json output for CI/CD, never polluted with ANSI.

---

## Part 6: Standards Compliance Matrix

### DO-178C (Aerospace Software)

| DO-178C Objective | forge Implementation | Evidence |
|-------------------|---------------------|----------|
| Requirements Traceability | Every struct/enum has REQ-ID in doc comment | architecture.md, code annotations |
| Design Documentation | ARCHITECTURE.md + TOPOLOGICAL_MAP.md | doc review |
| Source Code Standards | Rust edition 2021, clippy, no unsafe | cargo clippy |
| Test Coverage (MC/DC) | proptest, unit tests per requirement | coverage report |
| Configuration Management | Cargo.workspace.toml, CI/CD pinning | CI pipeline |
| Quality Assurance | qa-harness agent, review gates | All tests pass |
| Verification Independence | Different agent (qa-harness) reviews code | code review doc |

### IEC 61508 (Functional Safety)

| IEC 61508 Element | forge Implementation | SIL 3 Target |
|--------------------|---------------------|--------------|
| Risk Assessment | FMEA table per module | 100% documented |
| Failure Modes | FailureReason enum (7 variants) | >99% coverage |
| Fault Tolerance | LoopGuard (5 break paths) | No single point of failure |
| Diagnostic Coverage | VerificationEvidence on every gate | >99% for critical |
| Systematic Capability | Type-safe enums, no unwrap(), exhaustive match | SIL 3 capable |
| Safety Manual | PLAYBOOK.md §Safety | Complete |

### SOC 2 Type II (System and Organization Controls)

| Trust Service Criterion | forge Control | Monitoring |
|------------------------|--------------|------------|
| Security (access) | PermissionGate, anti-slop | audit trail |
| Security (auth) | FailureReason::AuthenticationFailure | doctor L2 |
| Availability | Session checkpoint, error recovery | uptime metrics |
| Processing Integrity | 5-gate verification | evidence chain |
| Confidentiality | Local-only, encrypted checkpoints | network audit |
| Privacy | User-configurable retention | right to delete |

---

## Part 7: Implementation Phases Completed vs Remaining

| Phase | Scope | Status | Agent |
|-------|-------|--------|-------|
| Spec | FORGE-RUST-TUI-SPEC.md | ✅ COMMITTED | — |
| Spec | CHANGE_ORDER_MAP.md | ✅ WRITTEN | — |
| Spec | TOPOLOGICAL_MAP.md | ✅ WRITTEN | — |
| Spec | REFACTORED-PLAN-COMPLETE.md | ✅ THIS FILE | — |
| Spec | CLAUDE-REVIEW.md | 🔄 WRITING | architect-karpathy |
| P0 | forge-core types + traits | 🔄 IN FLIGHT | backend-forge-core |
| P0 | forge-core semantic layer | 🔄 IN FLIGHT | backend-interpretation |
| P0.5 | forge-core config + router | 🔄 IN FLIGHT | backend-forge-core |
| P1 | Cargo workspace + CI/CD | 🔄 IN FLIGHT | devops-ci |
| P2 | forge-cli | 🔄 IN FLIGHT | cli-engineer |
| P3 | forge-tui | 🔄 IN FLIGHT | tui-designer |
| P4 | forge-harness + tests | 🔄 IN FLIGHT | qa-harness |
| P5 | Integration + hardening | ⏳ PENDING | All |
| P6 | Review + CLAUDE-REVIEW.md handoff | ⏳ PENDING | architect-karpathy |

---

*End of refactored plan. See CLAUDE-REVIEW.md for the Claude review handoff document.*

