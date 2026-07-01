# Claude Review Request — Forge Rust Port

Hey Claude, I need you to review a substantial engineering plan and the work products produced by a 7-agent sub-agent team. Here is the full context:

## What This Is

We are porting the forge-sdk Python AI agent SDK to a Rust workspace (9 crates) at /Users/srinji/forge-experience/. The team spawned 7 parallel sub-agents to handle architecture hardening, forge-core implementation (18 .rs files), semantic layer (interpretation plane), CLI, TUI, CI/CD, and QA/harness.

All docs are committed on branch `exp/human-experience` at:
/Users/srinji/forge-experience/

## Reading Order

1. **docs/FORGE-RUST-TUI-SPEC.md** (1,283 lines) — The master specification, 55 sections covering crate architecture, event taxonomy (13 discriminators), permission gate, 5-gate verification pipeline, FailureReason (7 variants), session checkpointing, doctor L0-L5, CLI surface, spine-based TUI, anti-duplication boundary vs lgwks_ui, hardening from 7 packs, implementation phases 1-6

2. **docs/TOPOLOGICAL_MAP.md** (91 lines) — Four-plane topology (Control/Execution/Interpretation/Mechanistic), team dispatch (7 agents), defense-in-depth layers (L0-L5), privacy-by-design principles (10 rules), anti-duplication boundaries

3. **docs/IMPLEMENTATION_PLAYBOOK.md** (345 lines, OKF-formatted) — Implementation-ready spec with: requirements traceability matrix (48 REQ-IDs), FMEA table (8 failure modes mapped to mitigations), exact code contracts for every forge-core module, SOC 2 Type II control evidence map, AI context packet, verification requirements per module

4. **docs/CHANGE_ORDER_MAP.md** (99 lines) — Phase-by-phase change order with dependencies and agent assignments

5. **docs/REFACTORED-PLAN-COMPLETE.md** (253 lines) — Full refactored plan with ladder architecture (deterministic → sensor → generative), anti-duplication boundary, current agent status

6. **docs/CLAUDE-REVIEW.md** (225 lines) — The structured handoff doc for you, with specific review questions in §2.1-2.6

## What the Agents Have Produced

The sub-agent team architecture:

| Agent | Role | Status | Deliverables |
|-------|------|--------|-------------|
| architect-karpathy | Architecture hardening (Karpathy principles) | ✅ Instructed | ARCHITECTURE.md, requirements matrix, FMEA |
| backend-forge-core | forge-core Rust implementation | ✅ Instructed | 18 .rs files (event, result, context, port, agent, permission, verifier, session, doctor, guard, security, tracer, audit, config, router, semantic, okf, experience) |
| backend-interpretation | Semantic/OKF/episode layer | ✅ Instructed | semantic.rs, okf.rs, experience.rs |
| devops-ci | CI/CD + Cargo workspace | ✅ Instructed | Cargo.tomls, forge-ci.yml, PLAYBOOK.md, keel.yaml |
| tui-designer | Spine-based TUI | ✅ Instructed | forge-tui/src/*.rs (8 files, crossterm+ratatui) |
| cli-engineer | CLI surface | ✅ Instructed | forge-cli/src/*.rs (12+ files, clap) |
| qa-harness | Test harness + SOC2/DO178C docs | ✅ Instructed | Tests, SOC2/DO178C compliance docs |

## Key Architecture Decisions

1. **9-crate workspace**: forge-core (zero-heavy-dep), forge-cli, forge-tui, forge-gemini, forge-ollama, forge-openai, forge-mcp, forge-harness
2. **forge-core Cargo.toml**: ONLY async-trait, thiserror, serde (with derive), serde_json, tokio (rt+macros), uuid (v4+serde). Zero heavyweight deps.
3. **13 AgentEvent discriminators**: RunStart, RunEnd, RunError, Think, Act, Observe, Verify, FileEdit, TokenUsage, StateUpdate, Decide, Converge, PermissionGate
4. **7 FailureReason variants**: ModelError, UsageLimitExceeded, ConvergenceFailure, MaxStepsReached, VerificationFailed, PermissionDenied, AuthenticationFailure
5. **5-gate verification**: SyntaxCheck → LintAnalysis → TestExecution → PropertyCheck → FormalBound
6. **Anti-duplication with lgwks**: forge-tui is NOT lgwks_ui.py — different tech (crossterm+ratatui vs raw ANSI), different palette hex values, different app state model, 100% original Rust
7. **Forge role in ecology**: forge IS the AI (generative tier) in the lgwks deterministic→sensor→generative escalation ladder

## Standards Applied

- **SOC 2 Type II**: Security, Availability, Processing Integrity, Confidentiality, Privacy controls mapped in IMPLEMENTATION_PLAYBOOK.md §3
- **DO-178C DAL A**: Requirements traceability matrix (48 REQ-IDs), MC/DC test coverage, configuration management
- **IEC 61508 SIL 3**: FMEA table per module, 99%+ diagnostic coverage target
- **excellent_docs_okf_ai_codebase_pack**: OKF-formatted documents with ID, owner, criticality, review cadence, trace links
- **excellent_code_framework**: All 20 principles (referential_truth, specification_fidelity, type_soundness, etc.) mapped
- **ai_semantic_rag_pack**: OKF schema v2 with interpretability, research_logging_required, Claim/Evidence types

## What I Need You To Review

1. **Architecture correctness**: Is the 9-crate workspace correctly scoped? Are there missing crates or wrong boundaries?
2. **Event taxonomy completeness**: 13 discriminators — is this sufficient for forge's role as execution plane?
3. **Anti-duplication boundary**: Is the forge↔lgwks boundary correct? Any risk of semantic overlap between forge's semantic.rs and lgwks_cognition.py?
4. **Safety certification readiness**: Do the DO-178C and IEC 61508 mappings make sense for an AI agent SDK?
5. **forge-core dep constraint**: Is the zero-heavy-dep constraint achievable for all 18 modules?
6. **Serialization strategy**: All forge-core types use JSON — should we use a binary format for checkpoint/audit files?
7. **TUI technology choice**: crossterm+ratatui vs an alternative for the spine-based layout
8. **Missing failure modes**: Any break paths I've missed beyond the 7 FailureReason variants?
9. **Defense-in-depth layers**: Any gaps in the L0-L5 stack?
10. **Privacy-by-design**: Any code path that could accidentally leak data?

## Files to Read

The key docs are all in /Users/srinji/forge-experience/docs/. Start with FORGE-RUST-TUI-SPEC.md, then IMPLEMENTATION_PLAYBOOK.md, then CLAUDE-REVIEW.md.

The Python baseline to understand what's being ported:
- src/forge_sdk/agents/events.py (11 events → Rust needs 13)
- src/forge_sdk/agents/types.py (AgentResult, FailureReason as string → Rust typed enum)
- src/forge_sdk/cli/ansi.py (zero-dep ANSI → Rust crossterm)
- src/forge_sdk/cli/renderers.py (TextRenderer + NDJSONRenderer → Rust)

The lgwks boundary:
- /Users/srinji/logicalworks-/lgwks_ui.py (anti-duplication target for forge-tui)
- /Users/srinji/logicalworks-/lgwks_model_mesh.py (forge queries this, doesn't own it)
- /Users/srinji/logicalworks-/lgwks_model_port.py (escalation ladder forge fits into)

The meaning_runtime_okf context (interpretation plane blueprint):
- /Users/srinji/Downloads/meaning_runtime_okf/ (sensor blueprint, episode schema, OKF schema)

Thanks for the deep review.

