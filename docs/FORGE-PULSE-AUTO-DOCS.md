---
id: DOC-FORGE-PULSE-AUTO-DOCS
status: active
baseline_issue: 74
related_playbook: playbooks/007-pulse-auto-documentation-brain.md
purpose: Lock the product and architecture decisions for local auto-documentation, PULSE frames, and the unified query brain.
---

# Forge PULSE Auto-Documentation Spec

## Executive Decision

Forge should treat documentation, feedback, memory candidates, and run receipts
as first-class runtime outputs. The product should not depend on humans writing
perfect handoffs after long agent sessions, and it should not spend frontier
model tokens summarizing routine work. A local worker should continuously turn
typed events into queryable docs.

The decision is:

```text
single event spine -> PULSE frames -> local reducers -> queryable projections
```

Everything else is a surface over that spine: CLI, TUI, web, chat, brain query,
MCP, issue candidates, eval receipts, and future model context packets.

## Why This Matters

The frontier harness market has converged on stateful multi-surface engines:

- Claude Code exposes MCP, auto memory, hooks, subagents, background/remote
  agents, CLI pipes, scheduled tasks, IDE/web/mobile surfaces, and project
  memory files.
- Cline exposes CLI, IDEs, SDK, Kanban, checkpoints, plan/act, MCP, plugins,
  multi-agent teams, scheduled agents, chat connectors, headless JSON, local
  models, and diff/revert workflows.
- OpenClaw pushes the always-on gateway pattern: local-first sessions, channels,
  tools, events, voice, WebChat, sandboxing, and chat/mobile control.

Forge should not imitate these one feature at a time. Forge should make them
projections of one stronger primitive: a typed, replayable, source-backed event
and documentation substrate.

## Product Boundary

Forge is trying to be both an SDK and an agent harness. The clean split is:

| Product Layer | Customer Promise |
|---|---|
| SDK | typed provider, tool, event, verifier, audit, config, and eval contracts |
| Harness | orchestration, permission modes, sessions, telemetry, replay, doc workers |
| Agent | default repo-driving coding agent assembled from SDK plus harness |
| Brain adapter | read/query/candidate bridge to durable memory systems |
| UI | event cockpit for humans: tools, files, diff, verify, claims, brain, telemetry |
| Docs worker | local auto-documentation and queryable handoffs |

The docs worker is not a nice-to-have. It is the continuity layer that makes the
rest of the product feel stateful rather than chat-shaped.

## The Human Problem

Humans do not usually say "done" and walk away. They ask:

- what did I miss?
- why did the agent choose that path?
- where did it get stuck?
- what changed?
- can I undo it?
- what should future agents know?
- what should never become memory?

Today's harnesses make the human manually reconstruct that from terminal logs,
diffs, chat history, and half-remembered decisions. Forge should turn those
questions into default projections.

## The AI Problem

The model should receive the smallest useful payload, not a giant prompt that
asks the frontier model to rediscover state. Prompt injection should be an
afterthought because the harness already built a typed, trust-labeled payload.

The model input should look like:

```text
task
active assumptions
retrieval refs
known failures
constraints
allowed capabilities
proof obligations
current affordances
rollback plan
```

It should not be:

```text
raw transcript + pasted docs + web text + command dumps + vague memories
```

## PULSE Decision

Use PULSE as Forge's internal action and documentation language.

PULSE frame:

```text
mode op slots controls
```

Modes:

```text
ask | do | say | need | ok | fail | deny
```

Examples:

```text
ask repo.status cwd:#repo.main @trace:t1
ok repo.status branch:uat dirty:true untracked:[.env,.forge,store] @trace:t1

do file.patch path:docs/POST-74-DEEP-PLAYBOOKS.md patch:#blob.91 @idem:k42 @trace:t2
ok file.patch changed:true lines_added:4 lines_removed:0 @trace:t2

say doc.handoff path:#artifact.handoff event_watermark:e184 @trace:t3
need user.context field:deployment_target reason:required_for_irreversible_action @trace:t4
deny memory.promote reason:source.low_trust candidate:#claim.77 @trace:t5
```

This is portable activation steering at the symbolic layer. It does not pretend
to inspect or write hidden model activations. It gives the harness a stable
language for steering, affordances, feedback, docs, and memory before the LLM is
called.

## Auto-Documentation Architecture

```text
runtime event
  -> PULSE frame
  -> event envelope
  -> payload CID
  -> local reducers
  -> materialized views
  -> unified query
  -> context packet
```

### Event Sources

- user text
- voice transcript
- browser affordance/action
- repo read/write/patch
- terminal command output
- tool call/result
- model output
- verification result
- diff
- screenshot/video/media segment
- feedback/nudge
- permission decision
- rollback/undo
- artifact emission

### Local Reducers

Forge should prefer cheap local computation:

- deterministic templates for receipts;
- git/AST parsers for code and diffs;
- regex/failure-signature classifiers for terminal output;
- feature-hash embeddings for low-cost recall;
- local encoder/reranker for salience;
- local small LLM for prose cleanup only when useful.

Frontier models are reserved for hard synthesis, ambiguous product decisions, or
high-value final docs. Routine run summaries should not use frontier compute.

## Unified Query Model

The query model must be one surface over many projections. A human should not
need to know whether the answer lives in a transcript, a diff, a run receipt, a
memory candidate, a test log, or an issue draft.

Canonical hit:

```rust
pub struct ForgeHit {
    pub cid: String,
    pub projection: ProjectionKind,
    pub score: f32,
    pub snippet: String,
    pub provenance: Provenance,
    pub trust: TrustClass,
    pub ts: String,
}
```

Projection kinds:

```text
event | artifact | diff | command | verification | doc | claim | memory_candidate | media | issue_candidate | symbol | graph | vector
```

The stable merge order is:

```text
(score desc, cid asc)
```

Every hit traces to event id or artifact CID. If a result cannot trace back to
source evidence, it cannot be injected into model context.

## Memory And Defense Boundary

The brain is a durable query and projection substrate, not a prompt scrapbook.

Rules:

- raw content is evidence, not authority;
- web/tool/OCR/transcript text is low trust by default;
- generated summaries are not standing instructions;
- direct user corrections can become high trust when source-backed;
- standing rules require direct user evidence or multiple independent refs;
- conflicting memories must supersede an older record explicitly;
- rendered memory views must strip active injection-looking text;
- cloud or frontier fanout receives redacted candidates, not raw logs by default.

This design treats memory injection as persistent prompt injection. A poisoned
summary or poisoned memory view is more dangerous than a single bad tool result
because it can shape future sessions.

## Browser And Visual Control

The browser should expose affordances, not raw DOM dumps.

Instead of sending thousands of tokens of page structure, the browser emits:

```text
ask page.affordances target:page
ok page.affordances can:[
  do form.fill field:email type:text,
  do form.fill field:password type:secret,
  do form.submit @confirm:true,
  ask page.text region:login-form
]
```

The same idea applies to UI control. The human sees and changes:

- mode;
- tools allowed/denied;
- evidence depth;
- verification strictness;
- risk tolerance;
- rollback boundaries;
- feedback/nudges;
- visible alternate pathways.

The harness processes that as state, not as a vague prompt append.

## Auto-Documentation Outputs

Every meaningful run should be able to emit:

```text
.forge/runs/<run_id>/events.jsonl
.forge/runs/<run_id>/receipt.json
.forge/runs/<run_id>/briefing.md
.forge/runs/<run_id>/handoff.md
.forge/runs/<run_id>/doc-deltas.jsonl
.forge/runs/<run_id>/issue-candidates.jsonl
.forge/runs/<run_id>/brain-candidates.jsonl
.forge/runs/<run_id>/eval-receipts.jsonl
.forge/runs/<run_id>/context.packet.json
```

The Markdown files are projections for humans. JSON/JSONL is the durable machine
interface. Rebuilding Markdown from events must produce the same material facts.

## Implementation Implications

The next implementation sequence is:

1. Add a `forge-protocol` crate for PULSE frames.
2. Add event-to-PULSE lowering in the harness.
3. Add `forge-docd` as a local replay/tail worker.
4. Implement tier 0-2 reducers with no model dependency.
5. Add unified query over event/doc/artifact/claim projections.
6. Add memory candidate gates.
7. Add context packet injection before model calls.
8. Add UI/CLI/MCP views over the same query and event surfaces.

## Non-Goals

- Do not build another opaque memory store inside Forge.
- Do not write raw transcripts into prompt context by default.
- Do not use frontier models for routine docs.
- Do not make the browser API a DOM scraper.
- Do not auto-file issues or promote standing rules without configured policy.
- Do not make UI state separate from event state.

## Acceptance Standard

Forge is "proper" when a zero-context engineer can inspect one run directory and
answer:

- what was requested;
- what state the agent believed;
- what it changed;
- what it verified;
- what failed;
- what evidence supports success;
- what the human nudged or corrected;
- what should become memory;
- what should stay quarantined;
- how to replay or continue.

If that answer requires reading raw chat, the auto-documentation layer failed.

## Source Notes

- PULSE package: `/Users/srinji/Downloads/AI/OKF_Packs/pulse_okf_package.zip`
- Browser PULSE API decision: `/Users/srinji/Downloads/AI/OKF_Packs/browser_engine_okf/docs/decisions/pulse-semantic-api.md`
- Forge frontier comparison: `docs/SEMANTIC-RESEARCH-FRONTIER-CLIS.md`
- Playbook: `docs/playbooks/007-pulse-auto-documentation-brain.md`
- LGWKS schemas: `/Users/srinji/logicalworks-/docs/schemas/REGISTRY.md`
- semantic-memory-brain: `/Users/srinji/semantic-memory-brain/docs/ARCHITECTURE.md`
- memory injection: `/Users/srinji/semantic-memory-brain/docs/MEMORY_INJECTION.md`
- Claude Code: `https://docs.anthropic.com/en/docs/claude-code/overview`
- Cline: `https://github.com/cline/cline`
- OpenClaw: `https://github.com/openclaw/openclaw`
