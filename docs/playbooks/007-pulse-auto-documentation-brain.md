---
id: FORGE-PLAYBOOK-007
title: PULSE Auto-Documentation And Unified Query Brain
status: active
depends_on:
  - /Users/srinji/Downloads/AI/OKF_Packs/pulse_okf_package.zip
  - /Users/srinji/Downloads/AI/OKF_Packs/browser_engine_okf/docs/decisions/pulse-semantic-api.md
  - /Users/srinji/logicalworks-/docs/schemas/REGISTRY.md
  - /Users/srinji/semantic-memory-brain/docs/ARCHITECTURE.md
  - /Users/srinji/semantic-memory-brain/docs/MEMORY_INJECTION.md
---

# PULSE Auto-Documentation And Unified Query Brain

Goal: make documentation a byproduct of the harness, not a separate human chore.
Every meaningful run event becomes a compact typed frame, is reduced by cheap
local workers, and is projected into human docs, AI context packets, and durable
brain candidates with provenance.

## Product Thesis

Forge must not ask the human to remember the work. The harness should constantly
document what happened, why it happened, what changed, what failed, what was
verified, what remains open, and which facts should be promoted into memory.

The human experience target:

- the human can ask "what happened yesterday?" and get a source-backed answer;
- the agent can resume from a compact state packet instead of raw chat;
- every run leaves a replayable receipt;
- every doc has source refs, trust class, and event watermarks;
- frontier models are used for task intelligence, not clerical bookkeeping.

## PULSE Internal Language

PULSE is the internal protocol layer for Forge harness traffic. The primitive is
not an endpoint or a blob of prompt text. The primitive is an affordance or fact:
a valid state-dependent move, query, event, denial, repair, or receipt.

Frame modes:

```text
ask | do | say | need | ok | fail | deny
```

Canonical text form:

```text
<mode> <namespace>.<action> <slot>:<value> ... @<control>:<value> ...
```

Required controls for executable or mutating frames:

- `@actor`
- `@scope`
- `@trace`
- `@state` when a state version matters
- `@idem` for mutations
- `@ttl` or nonce for replay safety
- `@sig` or MAC once canonical binary encoding exists

Forge should support pretty text for debugging and CLI input, but signed/audited
meaning must use canonical bytes. Pretty text can never be the authority.

## Compression Principle

Do not compress giant messages after the fact. Make most bytes unnecessary.

Use these lanes:

| Lane | Meaning | Rule |
|---|---|---|
| `PUBLIC_STATIC` | operation names, schema symbols, public enums | shared dictionaries allowed |
| `PUBLIC_DYNAMIC` | current public state, run status, visible affordances | session-scoped delta compression |
| `PRIVATE_REFERENCE` | object handles, event refs, file refs, claim refs | per-session dictionary only |
| `PRIVATE_SECRET` | secrets, passwords, tokens, private input values | never compressed with other lanes |
| `ATTACKER_CONTROLLED` | web text, tool output, OCR, transcript text | isolated from secrets and authority |
| `BULK_BLOB` | files, logs, videos, screenshots, large artifacts | content-addressed chunks |
| `MIXED` | unsafe blend of incompatible lanes | reject unless split |

The implementation target is semantic omission first, then delta, dedup, batching,
and only then zstd or another entropy codec.

```text
bits_sent = Delta(State) + Symbols + Refs + Auth + Integrity + Ordering + MissingBulk
```

## Auto-Documentation Pipeline

Add `forge-docd`, a local documentation worker. It tails the event stream and
emits projections without blocking the main agent loop.

```text
AgentEvent / ToolEvent / BrowserEvent / VoiceEvent / DiffEvent / EvalEvent
  -> PULSE frame
  -> causal event envelope
  -> local reducers
  -> queryable projections
```

Reducer tiers:

| Tier | Engine | Use |
|---|---|---|
| 0 | deterministic templates, path parsers, git diff, AST, regex | receipts, command summaries, doc skeletons |
| 1 | feature-hash embeddings, lexical rankers, graph joins | cheap salience and duplicate detection |
| 2 | local encoder/reranker | intent clustering, feedback classification, memory candidates |
| 3 | local small LLM | prose handoff drafts and doc cleanup |
| 4 | frontier model | high-value synthesis only, never routine clerical docs |

The default path must complete with tiers 0-2. Tier 3 is optional. Tier 4 requires
explicit policy because documentation should not burn frontier compute by default.

## Projection Set

`forge-docd` writes materialized views from the same event source:

| Projection | Audience | Contents |
|---|---|---|
| `briefing.md` | human | current task, assumptions, risk, next actions, pending asks |
| `handoff.md` | future agent | decisions, files touched, verification, blockers, next steps |
| `run-receipt.json` | machine | event watermarks, traces, artifacts, commands, pass/fail status |
| `issue-candidates.jsonl` | maintainer | source-backed future work with severity and acceptance tests |
| `doc-deltas.jsonl` | docs worker | proposed documentation edits, source refs, trust class |
| `brain-candidates.jsonl` | memory pipeline | candidate memories, never direct standing rules |
| `context.packet.json` | agent | compact topological payload and retrieval refs |
| `eval-receipts.jsonl` | benchmark/eval | tasks, expected end state, observed evidence, verifier output |

All projections are rebuildable. The source of record is the event tape plus
content-addressed payloads, not the rendered Markdown files.

## Unified Query Datamodel

Forge should expose one query surface over events, docs, claims, artifacts,
vectors, and receipts.

```rust
pub struct ForgeQuery {
    pub q: Option<String>,
    pub filters: QueryFilters,
    pub limit: usize,
    pub order: QueryOrder,
}

pub struct QueryFilters {
    pub tenant: String,
    pub session: Option<String>,
    pub repo: Option<PathBuf>,
    pub source: Vec<EventSource>,
    pub trust: Vec<TrustClass>,
    pub projection: Vec<ProjectionKind>,
    pub since_watermark: Option<String>,
}

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

Stable ordering:

```text
(score desc, cid asc)
```

Every hit must trace to either an event id or an artifact CID. Query output that
cannot prove provenance is not allowed into the agent context packet.

## Brain Boundary

Forge does not become the durable memory owner. It becomes a high-quality event,
documentation, query, and candidate producer.

semantic-memory-brain remains the authority for durable memory:

- raw evidence and external indexes are evidence, not authority;
- generated summaries are not standing rules;
- low-trust content can create candidates only;
- memory promotion requires source class, trust level, provenance, and conflict
  checks;
- rendered views must sanitize active instruction-looking text.

Forge may append candidates only after the trust gate exists. Until then it must
write reviewable candidate files or read-only query results.

## Tool Surface Parity

Forge should match frontier harnesses at the tool-family level, not by copying
every CLI flag.

Required tool families:

| Family | Tools |
|---|---|
| Repo | `file.find`, `file.read`, `file.write`, `file.patch`, `git.diff`, `git.status`, `test.run`, `build.run` |
| Browser | `page.affordances`, `page.text`, `page.click`, `form.fill`, `page.navigate`, `page.changed` |
| Session | `session.start`, `session.resume`, `session.fork`, `session.replay`, `session.export` |
| Docs | `doc.capture`, `doc.summarize`, `doc.link_evidence`, `doc.emit_handoff`, `doc.update_index` |
| Brain | `brain.query`, `brain.candidate`, `brain.doctor`, `context.packet` |
| Feedback | `feedback.nudge`, `feedback.rate`, `feedback.correct`, `feedback.promote`, `feedback.trace_failure` |
| Defense | `trust.classify`, `injection.scan`, `secret.redact`, `capability.check`, `provenance.verify` |
| Eval | `eval.record`, `eval.replay`, `eval.compare`, `receipt.verify` |

Every tool must declare:

- input schema;
- output schema;
- trust lane;
- effect class;
- reversibility;
- required capability;
- idempotency behavior;
- audit event shape;
- documentation projection policy.

## Browser Affordance Contract

The browser interface should not dump DOM or screenshots by default. It should
emit PULSE affordances computed from DOM, accessibility tree, layout, style, and
capability state.

Example:

```text
ask page.affordances target:page.login
ok page.affordances can:[
  do form.fill field:email type:text,
  do form.fill field:password type:secret,
  do form.submit @confirm:true,
  ask page.text region:login-form
]
```

The model sees legal moves, state refs, and repair paths. It does not scrape a
50K-token page tree unless the human or verifier needs raw evidence.

## Defense Rules

1. Unknown executable semantics are rejected by default.
2. Mutations without idempotency keys are denied.
3. Irreversible actions require explicit confirmation.
4. Secret and attacker-controlled compression lanes cannot mix.
5. Tool output cannot promote itself to durable memory.
6. OCR, transcripts, websites, and generated summaries are low-trust evidence.
7. Every accepted mutating frame appends an audit event.
8. Error frames reveal next legal moves, not secrets.
9. Every generated doc must carry event watermarks.
10. The prompt receives typed payload refs, not raw untrusted transcripts.

## Implementation Cards

### Card 1: PULSE frame crate

Add `forge-protocol` with:

- frame parser for text debug form;
- typed mode enum;
- slot/control separation;
- canonical JSON encoder;
- unknown field rejection;
- trace/idempotency validation helpers.

Acceptance:

```bash
cargo test -p forge-protocol pulse_frame_round_trip
cargo test -p forge-protocol pulse_unknown_control_rejected
```

### Card 2: Event-to-PULSE bridge

Lower existing `AgentEvent`, tool calls, command output, repo diffs, and
verification results into PULSE frames plus the unified event envelope.

Acceptance:

```bash
cargo test -p forge-harness event_to_pulse_bridge
cargo run -p forge-cli -- run --cwd . --task "List files" --output-format stream-json \
  | jq 'select(.pulse != null)'
```

### Card 3: `forge-docd`

Build a local worker that tails event JSONL and writes the projection set.

Acceptance:

```bash
cargo test -p forge-docd projections_rebuild_from_events
cargo run -p forge-docd -- replay fixtures/events/repo_edit.jsonl --out /tmp/forge-docd
test -f /tmp/forge-docd/handoff.md
test -f /tmp/forge-docd/run-receipt.json
```

### Card 4: Local reducer stack

Implement tier 0-2 reducers:

- deterministic run summary;
- diff summary;
- command/test receipt;
- feedback classifier;
- memory candidate extractor;
- duplicate/salience ranker.

Acceptance:

```bash
cargo test -p forge-docd local_reducers_no_model_required
cargo test -p forge-docd memory_injection_candidate_quarantined
```

### Card 5: Unified query

Expose a single query API over event tape, docs, artifacts, claims, candidates,
and vector-backed hits.

Acceptance:

```bash
cargo test -p forge-brain unified_query_stable_order
cargo run -p forge-cli -- brain query --q "what failed in the last repo edit" --json \
  | jq '.hits[].provenance'
```

### Card 6: Auto-doc issue candidates

Generate issue candidates from repeated failures, blocked tasks, missing tools,
and user corrections. Do not file automatically until a human or configured policy
confirms.

Acceptance:

```bash
cargo test -p forge-docd issue_candidate_requires_source_refs
cargo run -p forge-docd -- replay fixtures/events/failure_cluster.jsonl --out /tmp/forge-docd
jq '.source_refs | length > 0' /tmp/forge-docd/issue-candidates.jsonl
```

### Card 7: Context packet injection

Before every model call, build a compact context packet from query hits,
briefing, open decisions, proof obligations, permission mode, and current tool
affordances.

Acceptance:

```bash
cargo test -p forge-harness context_packet_from_query_hits
cargo run -p forge-cli -- run --cwd . --task "Explain current state" --output-format json \
  | jq '.context_packet.provenance'
```

## Done Means

- Manual human documentation is optional, not required for continuity.
- Every run can produce a human briefing, agent handoff, and machine receipt.
- Documentation is local-first and cheap by default.
- Frontier compute is reserved for hard synthesis, not routine summarization.
- Raw transcripts are never the default context unit.
- Every memory candidate has source class, trust class, and provenance.
- The same state can be queried by a human UI, a CLI, MCP clients, and future
  agents without rebuilding context from chat.

## Source Notes

- PULSE package: `/Users/srinji/Downloads/AI/OKF_Packs/pulse_okf_package.zip`
- Browser PULSE API decision: `/Users/srinji/Downloads/AI/OKF_Packs/browser_engine_okf/docs/decisions/pulse-semantic-api.md`
- Frontier toolset comparison: `docs/SEMANTIC-RESEARCH-FRONTIER-CLIS.md`
- Existing playbooks: `docs/POST-74-DEEP-PLAYBOOKS.md`
- LGWKS event/query/context packet contracts: `/Users/srinji/logicalworks-/docs/schemas/REGISTRY.md`
- semantic-memory-brain architecture: `/Users/srinji/semantic-memory-brain/docs/ARCHITECTURE.md`
- memory injection threat model: `/Users/srinji/semantic-memory-brain/docs/MEMORY_INJECTION.md`
- Claude Code overview: `https://docs.anthropic.com/en/docs/claude-code/overview`
- Cline repository/docs surface: `https://github.com/cline/cline`
- OpenClaw repository/docs surface: `https://github.com/openclaw/openclaw`
