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

## Part 8: Where the Human Actually Steps In (verified against both real codebases, 2026-07-01)

The docs above assert forge and lgwks don't duplicate each other, but they say nothing about the one place a human physically intervenes — and verification found **two separate, non-communicating approval gates already live today**, not one:

**lgwks's gate (`lgwks_agent.py::act()`, L349-363, real code):** every plan carries a string field `approval ∈ {none, once, force}`, set by `_effect_class()`'s read/write/network classification (e.g. L165: `"once" if effect == "write" else "none"`; L117: `"force" if worst >= 3 else "once" if worst >= 1 else "none"`). `act()` checks this before calling `compose()`: `needs=="once"` blocks without a `--yes`/`approve=True`; `needs=="force"` blocks without `--force`. This is a **flat, 3-value, string-typed** gate with no audit trail beyond the block_reason string.

**forge's gate (`permission.rs` §4, specced not built):** `PermissionMode{Interactive, Yolo, Plan}` × `ActionClassification` (10 variants) × 4 always-on anti-slop strategies → `PermissionVerdict{Allowed, Denied, NeedsApproval}`, with every decision emitted as a `PermissionGateEvent` into the audit chain.

**These do not talk to each other.** `lgwks_agent.py::_build_forge_tools()` (verified real, L370+) already wraps lgwks capabilities as forge `ToolSpec` objects for a `ReactAgent` — meaning **the two systems already call into each other in Python today**, but the approval decision is made twice, independently, by two different type systems, with no shared trace_id between lgwks's `block_reason` string and forge's typed `PermissionGateEvent`. A human running `lgwks agent "<intent>" --act` who clears lgwks's `--yes` gate has told lgwks "I approve this," but if `compose()` hands off to a forge-mediated tool call, forge's own Interactive-mode gate will ask the *same human* to approve the *same action* again, with no memory of the first approval — two gates, one human, zero correlation.

**Hardening action (v1, not deferred):** the merger design must pick a single owner for "does a human need to approve this." Recommendation: **forge's `PermissionGate` becomes the single authoritative approval surface**; lgwks's `approval` field on a plan becomes an *input hint* (`ActionClassification` seed) fed into forge's gate rather than a second independent block, and lgwks's own `--yes`/`--force` flags become aliases that pre-populate forge's `PermissionMode` rather than short-circuiting before forge is ever consulted. This is the concrete "different models and layers interacting from when the human steps in" boundary the Director asked to be made explicit — it was previously only asserted as "forge owns execution, lgwks owns control," which is too coarse to answer "which system asks the human, and does asking twice count as consent once."

## Part 9: DeepSeek-Inspired Efficiency Hardening (DSA + DSpark, researched live 2026-07-01)

Per Director instruction, researched DeepSeek's two live 2026 efficiency techniques (via Vertex AI Gemini + Google Search grounding, not training-data recall — both post-date this model's knowledge cutoff) to see whether their core *shape* — not their GPU-kernel specifics, which don't apply to an API-consumer harness — hardens anything already in this spec.

**DeepSeek Sparse Attention (DSA)**, DeepSeek-V3.2 (arXiv 2512.02556, Dec 2025): a cheap "lightning indexer" scores relevance of every token, then only the **top-k** highest-scoring tokens get the expensive full-attention computation — replacing O(L²) with O(L·k), 2x per-token cost reduction on long context, without losing access to any part of the context (unlike a sliding window, which discards it).

**DSpark**, DeepSeek-V4 (released 2026-06-27, days before this session): a small "draft model" proposes a block of tokens; the large "target model" verifies the whole block in **one forward pass**; a confidence head adjusts how much of the block gets fully re-verified under load. Output is mathematically identical to the target model running alone — this is a lossless speedup, not an approximation.

**Both are the same shape lgwks's escalation ladder already is** — a cheap, always-on filter (indexer / draft model / lgwks's deterministic+sensor tiers) decides how much of the expensive resource (full attention / target-model verification / the generative tier) actually gets spent. This isn't a new idea being imported — it's independent confirmation that the ladder's core structure (`~/logicalworks-/lgwks_model_port.py`'s `TIER_ORDER`) is the right shape at a different layer of the stack. Two concrete, buildable-now hardenings follow from taking the *shape* seriously rather than just noting the coincidence:

1. **`verifier.rs`'s 5-gate pipeline should degrade under budget pressure like DSpark's confidence scheduler, not run at fixed depth.** Today `VerifierPipeline::run_all()` (§5) always attempts L0→L4 in order, stopping only on failure — no budget awareness. Add a `verification_budget` to `VerifierPipeline` (mirrors `LoopGuard`'s existing `max_cost`/`max_tokens` fields, §6.1 — same struct shape, not a new concept) so that under real, already-lived rate-limit pressure (this project's own account-cap rotations, GLM credit exhaustion this session) the pipeline **always** runs L0 (SyntaxCheck) and L1 (LintAnalysis) — cheap, deterministic, never skipped — and only *degrades* L3 (PropertyCheck) / L4 (FormalBound) — the two most expensive, currently-unimplemented-beyond-a-name gates — under pressure, emitting `VerificationEvent{status: Skipped}` with the reason recorded (never silently). This is DSpark's "verify the confident prefix under load, skip the rest" applied to CI gates instead of tokens.
2. **The ladder's existing kill-switch is DSA's `k=0` case, already built — name it as such and reuse the pattern for forge.** `lgwks_model_port.py`'s `LGWKS_NO_MODELS` env var (`ceiling="deterministic"`) is functionally identical to setting DSA's top-k selection to zero — skip the expensive tier entirely, deterministic-only. forge's `LoopGuard`/`PermissionGate` should expose the same ceiling concept (`--ceiling deterministic` forcing `PermissionMode` to auto-deny any `Exec`/`NetworkOut` classification) so a Director-level "stop spending on the generative tier" instruction works identically whether it's issued to lgwks or to forge — one kill-switch semantic, not two.

## Part 10: Language-Cost-Aware Routing (harness-level, model-weights-untouched)

Researched (Vertex AI Gemini + Google Search, live 2026-07-01) why non-English input costs ~1.5-2x more tokens: training-data bias in the vendor's BPE vocabulary, UTF-8 multi-byte overhead for non-Latin scripts, and morphological complexity — this is a property of tokenizers we consume via API, not train. Every real mitigation that doesn't require retraining a base model (vocabulary expansion, tokenizer swap + embedding remap, adapter re-tokenization) requires **write access to model weights we don't have** — Claude, Gemini, GLM are all vendor-hosted. The one mitigation that needs no weight access — byte-level fallback — is already baked into every modern tokenizer we call and isn't ours to improve.

**This means "improve tokenizer architecture without breaking models" for a harness that only calls vendor APIs cannot mean touching tokenization at all — it can only mean *routing around the cost*, using data the system already collects.** Concrete, buildable-now proposal, scoped to fit inside forge's **already-planned** `router.rs` (Phase 1.1, CHANGE_ORDER_MAP.md — "AutoRouter with retry-backoff... model fallback chain," not a new module):

1. **`RunStartEvent`'s `Correlation` already carries `model`+`provider` on every call (§3.1) — add one more cheap, deterministic-tier field: `detected_language`.** This is a fast heuristic classification (script/langid, no model call — the "sensor tier" doing what it already does elsewhere in lgwks), not an LLM call, so it costs nothing and doesn't slow the hot path.
2. **`TokenUsageEvent` + `Correlation` together already let the existing `audit.rs` hash-chain (§7, already specced) compute real tokens-per-semantic-unit by `(model, provider, detected_language)` from data the system is already logging to `~/.forge/audit/` — no new storage, just a new query over existing audit records.**
3. **`router.rs`'s fallback chain (already speced to exist for 429/404 handling) gets one more selection input: for non-English-heavy requests, prefer the empirically-cheapest-per-language model from step 2's aggregation, not just the first model in a static fallback list.** This is real cost reduction — potentially the "almost twice as much" the Director named — achieved entirely by *choosing which already-deployed model to call*, never by touching a vendor's tokenizer or weights. It also directly serves this project's own rate-limit economy (free-lane vs paid-lane routing already exists as a manual practice in `MEMORY.md`'s `feedback_model_outlook_tool_economy`) — this makes that routing decision data-driven instead of manually curated.

No new crate, no new event type beyond one field, no new module — this is entirely inside `router.rs`'s already-planned scope (Phase 1.1). Flagging it here so it's built into v1's router from the start rather than retrofitted.

## Part 11: What This Lets lgwks Deprecate (the Director's stated end-goal)

Once forge's `PermissionGate` (Part 8) and cost-aware `router.rs` (Part 10) are real and load-bearing, three lgwks surfaces become candidates for shrink-or-delete rather than parallel maintenance:

1. **`lgwks_agent.py`'s own `approval` string field + the L358-363 `--yes`/`--force` block.** Once forge's `PermissionGate` is the single authoritative approval surface (Part 8), this becomes a redundant second gate. `act()` shrinks to: classify effect → decide whether to escalate past the deterministic tier at all → hand off to forge for execution AND approval. lgwks stops re-implementing consent.
2. **Any hand-curated, memory-file-based "which model is cheap for what" bookkeeping** (e.g. the manual free-lane/paid-lane notes already accumulating in this project's own memory system) — once Part 10's router has real per-language, per-model cost telemetry, that becomes a queryable fact instead of a remembered opinion.
3. **lgwks's own event/telemetry surface, to the extent it exists only to answer "what did the AI just do"** — forge's 13-event `Correlation`-keyed stream (§3) plus its audit hash chain (§7) is a strict superset of what a bespoke lgwks logging path would need to reconstruct; once forge owns "the generative tier," lgwks doesn't need its own parallel record of what happened inside a forge-mediated call, only the pointer (`trace_id`) to it.

None of these are v1 deletions — they're the concrete payoff *once* Parts 8-10 are real, which is the honest sequencing: harden the merger boundary first, then let redundant lgwks surfaces fall away, not the reverse.

## Part 12: Mass-Search Economics (Director question, answered live 2026-07-01)

Direct answer to "is Vertex AI Search the best option we have, or is there better/cheaper": **Vertex AI Search (Discovery Engine) is the wrong tool for this entirely** — verified live, it's a RAG-over-*your-own*-data product ($4-6/1,000 queries, Standard Search $1.50/1,000 within Agent Builder), built for enterprises searching internal document stores, not the open web. It is not a mass web-search engine and was never the right comparison point.

**What this session actually used** — Gemini's built-in Google Search grounding tool (`google_search`) called via Vertex `generateContent` — *is* the right category (general web search for live agent research), and it is genuinely mid-pack on price: **$14/1,000 queries** for Gemini 3-class models (was $35/1,000 on Gemini 2.x; this session's `gemini-2.5-flash` calls likely bill nearer the $35 rate). Checked the real alternatives (all live 2026 pricing, cited sources, not recalled):

| Option | Cost / 1,000 queries | Shape | Fit for this harness |
|---|---|---|---|
| Vertex AI Search / Discovery Engine | $4-6 (or $1.50 Standard) | RAG over **your own** data | Wrong category — not web search |
| Vertex Gemini + Google Search grounding | $14 (Gemini 3-class) / $35 (2.x) | General web search | What was used this session; convenient (same Vertex auth/billing already live) but not the cheapest |
| **Brave Search API** | **$5** | General web search, independent 40B-page index, has a token-optimized **LLM Context** endpoint | **Best quality-per-dollar** — 2.8x cheaper than Vertex grounding, and its LLM Context endpoint pre-shapes results into token-efficient chunks *before* they hit our own generative-tier tokenizer, which directly compounds with Part 10's token-cost-reduction goal (less raw text in means fewer tokens burned regardless of language) |
| Exa API | $7-8 (search+contents) | Semantic/neural index, has a **Context API built specifically for coding agents** (GitHub/docs/StackOverflow) | Best fit for *code*-specific research (library docs, API references) — complements Brave rather than replacing it |
| Tavily | $8 | AI-optimized snippets, JSON+citations | Fine, no clear edge over Brave/Exa for this harness |
| SerpAPI | $10 (falls to ~$3.75 only above 1M/month) | Raw SERP scrape, multi-engine | Wrong shape (SERP parsing, not agent-ready content) and not cheap at this project's actual volume |
| Bing "Grounding with Bing Search" | $14-35 | Platform commitment inside Azure AI Foundry | No reason to adopt — would add a second cloud vendor for no gain over what's already live |

**Recommendation for the end-state**: `forge-catalog` (Part 9) should carry a **search adapter, not just a model adapter** — `forge-search` — defaulting to **Brave Search API** for general live research ($5/1,000, independent index, token-optimized output feeds directly into the language-cost-routing work in Part 10) with **Exa's Context API** as the preferred escalation for code/library/API-doc lookups specifically (the exact shape of research this harness does most: "what does crate X's API actually look like," "is crate Y real and what version"). Keep the already-working Vertex-Gemini-grounding path (used throughout this session) as the zero-new-account fallback when Brave/Exa aren't configured — it costs more per query but needs no new signup, which matters for a same-day decision. This is a genuine **cost-vs-convenience tradeoff to hand to the Director**, not a unilateral crate choice: Brave/Exa need new API keys and a (small, per-law-requiring-approval) new vendor relationship; Vertex grounding needs nothing new but costs ~3x more per query at Gemini-3 rates and ~7x more at the 2.x rate this session actually used.

---

*End of refactored plan. See CLAUDE-REVIEW.md for the Claude review handoff document.*

