---
id: SPEC-SDK-002
status: draft
criticality: L1
review_cadence: weekly
owner: srinji
created: 2026-06-30
last_reviewed: 2026-06-30
supersedes_none: true
depends_on: [SPEC-SDK-001]
map: .specs/lgwks-integration-map.mmd
---

# Specification: lgwks Integration & Dedup

> **For the implementing agent (opencode):** you are good but you lack context about the system this
> framework plugs into. THIS spec + `lgwks-integration-map.mmd` ARE that context. Read both before
> writing code. The lgwks repo lives at `/Users/srinji/logicalworks-`; its contract is its `CLAUDE.md`.

## 1. Purpose & thesis

forge-sdk must become the **canonical agentic execution loop for lgwks** — and plug into the lgwks CLI
so a user runs `lgwks forge run "<task>"`. lgwks is NOT a greenfield target: it **already owns** the
substrate services an agent loop needs (model law, an append-only event bus, a code atlas, a rules
engine, git-worktree isolation, a research/crawl pipeline). What lgwks lacks — proven by ISS-003,
where `lgwks agent --act` plans but never truly edits-tests-verifies — is the **assembled loop**.
forge-sdk IS that loop.

Therefore the prime constraint is **dedup, not addition** (lgwks `CLAUDE.md` §"One canonical
implementation. Kill duplicates"): every forge-sdk extension point becomes an **adapter over an
existing lgwks primitive**. A second, slightly-different copy of model-selection, audit, or tooling
IS the bug. Where forge already has a generic capability lgwks lacks (generic shell/fs/search, the
ReactAgent loop, the eval harness), forge owns it and lgwks defers to forge.

## 2. Invariants

### INV-101: One model authority — the lgwks model LAW
forge's model selection MUST be able to resolve a model id from the lgwks model law, not a hardcoded
literal. Provide a `MeshModelPort` (or a `mesh` provider in `ProviderRegistry`) that, given a *role*
(e.g. `proposal`, `reasoning`) and optional `trust_class` (`deterministic`|`sensor`|`generative`),
pins the model id via `lgwks_model_mesh.model_name_for_role(role, trust_class=..., default=...)`.
MUST NOT hardcode `deepseek-v4-pro`/`glm-5.2` etc. when running inside lgwks — the law is the source
of truth (it exists precisely so ports stop drifting). The underlying HTTP call still reuses the
existing OpenRouter/DeepSeek/Ollama `ModelPort` impls; only *which model* is law-resolved.

### INV-102: One append-only log — the daemon event bus is the audit
forge's `Tracer` spans and `AuditLog` entries MUST be emittable as lgwks daemon events via
`lgwks ops daemon emit --kind <k> --lane <l> --scope <s> --actor <a> --session-id <sid> --agent-id <aid>`
(envelope `lgwks.daemon.event.v2`, store `store/daemon/daemon-events.db`). Map: model call →
`kind=model_output`, tool execution → `kind=tool_call`, agent step/turn → `kind=transcript_turn`.
MUST NOT stand up a parallel `.forge/audit.db` as the *system of record* when running inside lgwks
(DO-178 invariant: render/history = pure function of ONE append-only log). forge MAY keep its
hash-chain as an integrity *wrapper* over the same events, but the bus is canonical. **Payoff:** every
forge run becomes a typed training trajectory for the Standalone Aetherius model (lgwks `CLAUDE.md`
"Standalone Foundation Strategy": every daemon event is training data) — this is the unfair advantage
cursor structurally cannot match.

### INV-103: Tools wrap lgwks primitives; don't reimplement
Tools for capabilities lgwks already owns MUST wrap the lgwks surface, not duplicate it:
- isolation → enqueue daemon WORK_KINDS `worktree_open`/`worktree_close` (do not shell out a second
  worktree manager).
- research/crawl → `research_run` WORK_KIND (the existing crawl→chunk→index pipeline).
- code context / retrieval → query the **navmap** (`docs/navmap/index.json`, `lgwks.navmap.v1`) and the
  daemon `packet` BEFORE raw grep (retrieve-before-edit, DO-178 #3).
Generic `shell`/`filesystem`/`search` tools (lgwks has no canonical for these) stay native to forge.

### INV-104: CLI plug-in — `lgwks forge ...`
forge MUST be reachable as a first-class lgwks subcommand. Add `lgwks_forge.py` at the lgwks repo root
exposing `add_parser(sub)` (the registration contract every lgwks module follows — see the root `lgwks`
script: `import lgwks_research; lgwks_research.add_parser(sub)`), registering `forge run|eval|audit`
that call into `forge_sdk`. MUST be importable by the lgwks dispatcher's module-name loader; MUST NOT
require moving the root `lgwks_*.py` files (they are load-bearing — lgwks `CLAUDE.md` §structural
invariant). The forge-sdk package is the engine; `lgwks_forge.py` is the thin CLI adapter.

### INV-105: Eval harness extended to the lgwks bar
Beyond HumanEval/MBPP (SPEC-SDK-001 INV-005), the eval harness MUST support registering domain
benchmarks. Register the **lgwks cockpit eval bar** (the cursor-blueprint metrics: context_recall,
patch_correctness, autonomy, trust, cost-per-accepted-diff) so "world-class against evals" is a
runnable score, not a claim. Eval results MUST be emittable to the daemon bus (INV-102).

### INV-106: Kill the duplicate agent loop (ISS-003)
There MUST be exactly one execution loop. lgwks `agent` (planning/worldview half) MUST delegate the
act-test-verify loop to forge's `ReactAgent` rather than maintaining its own half-built `--act` path.
Concretely: `lgwks forge run` is the canonical loop; `lgwks agent` either calls it or is documented as
planning-only with `lgwks forge run` as the executor. No two parallel "do the task" code paths.

### INV-107: Python is interim — keep a portable, edge-targetable core
**End-state (Director, 2026-06-30):** the agent must eventually run **optimized for edge computing**;
**Python is not the right long-term choice** (cf. Keel's own JS→Rust rewrite for the deterministic
floor). Python forge-sdk is **v1 scaffolding** — fast to iterate, hardened *alongside* real-world use
as issues surface — NOT the final runtime. To make the eventual native/Rust (edge) re-host cheap, the
v1 MUST keep the core boundaries clean and the hot loop free of Python-only luxuries:
- The four boundaries (`ModelPort`, `ToolRegistry`/`ToolSpec`, the event/audit sink, the eval harness)
  MUST stay protocol-typed, serializable, and free of framework magic — they are the **portability
  seams**; a Rust port reimplements behind the same contracts.
- Tool I/O and event payloads MUST be plain JSON-serializable structures (no Python objects on the
  wire) so the same contracts survive a language change.
- Avoid Python-only deps in the hot path (the agent step loop, model call, tool dispatch); confine
  conveniences to the CLI/dev layer. No dependency that has no native/Rust equivalent in the core.
- Keep a `CORE-PORTABILITY.md` ledger: for each module, "edge-portable as-is | needs port | dev-only".
This is a **direction**, not a v1 deliverable: do not rewrite in Rust now. Just don't author v1 in a
way that traps the loop in CPython. Real edge constraints (binary size, cold-start, no-GC latency,
WASM/embedded targets) will be specced when the v1 contracts are proven against real lgwks work.

## 3. Interfaces (adapters — concrete)

```python
# forge_sdk/models/providers/mesh.py  (NEW, INV-101)
class MeshModelPort:                      # satisfies ModelPort
    """Resolves the model id from the lgwks model LAW, delegates HTTP to a base provider."""
    def __init__(self, role: str, trust_class: str | None = None,
                 base: ModelPort | None = None): ...
    # model id = lgwks_model_mesh.model_name_for_role(role, trust_class=trust_class, default=...)
    # provider/HTTP = existing OpenRouter/DeepSeek/Ollama impl, just with the law-pinned model name.

# forge_sdk/audit/daemon_sink.py  (NEW, INV-102)
class DaemonEventSink:                     # a Tracer/AuditLog export target
    """Emits spans/audit entries as lgwks daemon events via `lgwks ops daemon emit`."""
    def __init__(self, repo_root: Path, session_id: str, agent_id: str = "forge"): ...
    def emit(self, kind: str, lane: str, scope: str, payload: dict) -> None: ...

# forge_sdk/tools/lgwks/{worktree,research,navmap}.py  (NEW, INV-103)
#   ToolSpec handlers that enqueue daemon WORK_KINDS / query navmap — NOT new managers.

# lgwks_forge.py  (NEW, lives in lgwks repo root, INV-104)
def add_parser(sub) -> None:               # 'forge' subparser -> forge run|eval|audit
    ...
```

## 4. Dedup ledger (what replaces / defers to what)

| forge-sdk piece | lgwks canonical | Action |
|---|---|---|
| ProviderRegistry hardcoded model ids | `lgwks_model_mesh.model_name_for_role` | forge **defers** (MeshModelPort) — INV-101 |
| AuditLog `.forge/audit.db` (as SoR) | daemon event bus `daemon-events.db` | forge **defers** (DaemonEventSink) — INV-102 |
| Tracer `.forge/traces/*.jsonl` (as SoR) | daemon events | forge **defers**; jsonl becomes a local mirror — INV-102 |
| worktree tool | daemon `worktree_open/close` WORK_KINDS | forge **wraps** — INV-103 |
| research tool | daemon `research_run` WORK_KIND | forge **wraps** — INV-103 |
| search/context | navmap + daemon `packet` | forge **wraps** (retrieve-before-edit) — INV-103 |
| ReactAgent loop | lgwks `agent --act` (ISS-003, half-built) | **forge replaces** lgwks' loop — INV-106 |
| generic shell / filesystem | (none in lgwks) | forge **owns** — keep native |
| eval harness | (none canonical in lgwks) | forge **owns** + register lgwks benchmarks — INV-105 |

## 5. Acceptance criteria
- `lgwks forge run "<task>"` runs the ReactAgent loop end-to-end (deps: bugs #1, #2 fixed first).
- With `FORGE_PROVIDER=mesh FORGE_ROLE=proposal`, the resolved model id equals
  `lgwks_model_mesh.model_name_for_role("proposal", trust_class="generative")`.
- A forge run produces ≥1 `tool_call` and ≥1 `model_output` event in `store/daemon/daemon-events.db`
  for its session (verify with `lgwks ops daemon packet --session-id <sid> --agent-id forge`).
- No new `.forge/audit.db` is treated as system-of-record when `--cwd` is an lgwks repo.
- `lgwks forge eval --benchmark humaneval --limit 5` runs; results land on the bus.
- Tests cover the CLI import path and one real tool call through the sync run path (close the
  false-green gap from issues #1/#2).

## 6. Sequencing (issues)
1. Fix blockers #1 (ToolRegistry export — DONE), #2 (event-loop tool exec).  ← must land first
2. INV-104 CLI plug-in (`lgwks_forge.py`) — smallest end-to-end win.
3. INV-102 DaemonEventSink — the strategic dedup (training data).
4. INV-101 MeshModelPort — model-law dedup.
5. INV-103 tool adapters (worktree/research/navmap).
6. INV-105 eval extension; INV-106 agent-loop dedup (largest, last).
