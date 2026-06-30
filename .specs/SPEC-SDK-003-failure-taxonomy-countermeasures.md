---
id: SPEC-SDK-003
status: draft
criticality: L1
review_cadence: weekly
owner: srinji
created: 2026-06-30
last_reviewed: 2026-06-30
depends_on: [SPEC-SDK-001, SPEC-SDK-002]
authority: ~/open-knowledge/ai-agent-failure-blueprint/README.md (UAFT v1.0)
---

# Specification: Failure-Taxonomy Countermeasures (forge-sdk = the blueprint's implementation)

> **For the implementing agent (opencode):** the canonical failure model is the **AI Agent Failure
> Blueprint** (`~/open-knowledge/ai-agent-failure-blueprint/README.md`) — 12 failure classes (UAFT),
> the Verification Asymmetry Theorem, and a 7-layer defense-in-depth fix architecture, grounded in 85+
> papers / 13,602+ documented faults. forge-sdk is not a generic agent SDK; it is the **concrete
> implementation of that fix architecture**. Every invariant below traces to a failure class it
> defends. Do not weaken these to ship — a green build over an unverified path IS failure class V₂.

## 1. The core theorem this SDK exists to defeat
**Verification Asymmetry (Blueprint Proof 1):** agents submit at 99-100% while resolving at 18-44%;
generation confidence is decoupled from correctness. 7 of 12 failure classes are verification-rooted.
**forge-sdk's reason to exist = close that gap:** an agent here MUST NOT claim success without passing
layered verification. This is also the method already dogfooded on lgwks-human (cockpit_evals.py: a
scorecard that refused to trust "v1 finished" and verified each fix — V₁/V₂ countermeasure in practice).

## 2. UAFT → forge-sdk countermeasure map
Each row: failure class → where forge defends it → invariant/issue. "have" = exists in v1; "build" = work.

### C₄ Verification Failures (highest priority — the theorem)
| Class | forge-sdk countermeasure | Status |
|---|---|---|
| V₁ Assumed Success | **Mandatory Verification Protocol** (§3): agent may emit `success` ONLY after Layer-5 empirical (test/compiler) + Layer-6 spec-conformance pass | build (INV-201) |
| V₂ Confidence-Correctness Divergence | result carries `evidence[]` (the passed checks), not a self-rated confidence; eval harness scores resolution not submission | build (INV-201,202) |
| V₃ Circular Review | reviewer/verifier MUST NOT be the same model+prompt as generator; route verify through a distinct ModelPort role (mesh `trust_class`) or a deterministic checker | build (INV-203) |
| V₄ Fabricated Success Reports | **hash-chain AuditLog** (SPEC-SDK-001 INV-004) — agent cannot rewrite/forge the record; reconcile claimed-vs-actual against the daemon event bus (SPEC-SDK-002 INV-102) | have+wire |

### C₃ Decision Failures
| Class | forge-sdk countermeasure | Status |
|---|---|---|
| D₁ Infinite Tool Loop | **LoopGuard** (Blueprint 5.4): detect repeated identical tool-calls (hash of name+args); halt with a no-progress error. Bounded by `max_steps` already, but add same-call detection | build (INV-204) |
| D₂ Wrong Tool Selection | typed ToolSpec schemas + `applies()` predicate; trace the selection so D₂ is observable | have (INV-002) |
| D₃ Entity Binding Failure | tool handlers validate the external entity (path/url/id exists) before acting; fail-closed | build (INV-205) |
| D₄ Architectural Drift | Layer-6 spec-conformance check against the task/spec; for lgwks, query navmap before edit (SPEC-SDK-002 INV-103) | build |

### C₂ Perception Failures
| Class | forge-sdk countermeasure | Status |
|---|---|---|
| P₁ Context Window Saturation | **External Memory Architecture** (Blueprint 5.3): persist constraints/decisions to the event bus, re-inject; don't rely on in-window retention | build (INV-206) |
| P₂ Cross-File Blind Spot | **Cross-File Dependency Tracker** (Blueprint 5.5): navmap/AST dep query before edit (retrieve-before-edit) | build (ties INV-103) |
| P₃ Runtime State Blind Spot | empirical Layer-5 runs real tests/REPL/compiler — observe actual state, not assume | build (INV-201) |
| P₄ Implicit Dependency Blind Spot | static-analysis (LSP/AST) gate surfaces dynamic refs where possible; flag unknowns, don't silently skip | build |

### C₁ Generation Failures (mitigated by C₂-C₄ layers, not by "better prompts")
| Class | forge-sdk countermeasure | Status |
|---|---|---|
| G₁ Semantic Misunderstanding | Layer-3 semantic verification (embedding distance task↔solution, Blueprint 5.6) | build (INV-207) |
| G₂ Hallucinated APIs | Layer-4 static analysis (LSP diagnostics) catches non-existent symbols | build |
| G₃ Missing Corner Cases | eval harness includes edge-case/robustness benchmarks; tests are Layer-5 | have+extend |
| G₄ Incomplete Generation | syntactic Layer-2 parse check rejects truncated output | build |
| G₅ Type Coercion Errors | Layer-2 type check / Layer-4 LSP | build |

## 3. INV-201..207 — the new invariants (defense-in-depth)
The Blueprint's 7 layers (L1 input-sanitization → L7 human-gate) become forge's verification pipeline.
forge MUST implement these as a **PolicyRegistry** of verification policies the ReactAgent runs after
generation, BEFORE emitting success. Each is a strategy (SPEC-SDK-001 INV-002), not an if/elif.

- **INV-201 (MVP):** `ReactAgent` MUST gate `success` behind a verification pipeline: syntactic (L2) →
  static/LSP (L4) → empirical test/compile (L5) → semantic (L3) → spec-conformance (L6). Result MUST
  carry `evidence[]` of which layers passed. No layer trusts the one below. (V₁,V₂,P₃,G₄,G₅)
- **INV-202:** the eval harness MUST report **resolution rate** (did the fix actually work), never
  submission/completion rate, so the SDK's own metrics can't reproduce V₂. (V₂)
- **INV-203:** the verifier model/role MUST be distinguishable from the generator (distinct mesh role
  or a deterministic checker) — no self-grading. (V₃)
- **INV-204 (LoopGuard):** detect repeated identical tool-calls (hash name+args over a window); halt
  with `no_progress`. Termination guarantee per Blueprint Proof 3. (D₁)
- **INV-205:** tool handlers validate the target entity exists/permitted before acting; fail-closed. (D₃)
- **INV-206 (EMA):** constraints + key decisions persist out-of-window (event bus) and re-inject on
  step; don't rely on context retention. (P₁)
- **INV-207:** semantic check via embedding distance between task intent and produced solution. (G₁)

## 4. Sequencing (maps to Blueprint §7 roadmap; file as issues)
1. **INV-201 MVP** + **INV-202 resolution-metric** — the theorem's direct fix; highest value. (Phase 2)
2. **INV-204 LoopGuard** — cheap, bounded, prevents the 30% stuck rate. (Phase 1)
3. **INV-203 distinct-verifier** + **INV-205 entity-validation**. (Phase 3)
4. **INV-206 EMA** + **INV-207 semantic** + L4 LSP gate. (Phase 1-2)
Tie every PR's acceptance to "which UAFT class does this close + which eval proves it."

## 5. The reflexive guarantee
forge-sdk MUST hold itself to its own bar: its CI (Keel, issue #9) + its tests must exercise real
paths (issues #1/#2 were V₂ in the SDK itself — green tests over a dead CLI). An agent framework that
exhibits the failures it claims to fix is the deepest slop. The cockpit eval scorecard
(`blackbox2/cowork/cockpit_evals.py`) is the template: behavioral, resolution-scored, no false-green.
