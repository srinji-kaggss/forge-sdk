# Session C Brain Payload v0

Status: ready for implementation
Branch: `feat/brain-payload-v0`
Parent epic: issue #74
Primary playbook: `docs/playbooks/004-brain-topological-payload.md`

## Objective

Make Forge build a structured context payload before model calls, without raw
memory injection and without writing to external brain stores.

The target is a conservative v0:

- Read-only OKF index inspection/query.
- Read-only semantic-memory-brain doctor/query.
- A `TopologicalPayload` builder that combines task, repo evidence, memory
  evidence, proof obligations, and deterministic steering profile.
- JSON rendering path so the payload can be inspected and replayed.

This PR does not need to make the model use the payload for all runs if that
collides with Session A. It must make the payload buildable, testable, and available
through an explicit API or CLI path.

## Current State

Known post-PR77 state:

- `forge-brain/src/payload.rs` defines core payload structs.
- `forge-brain/src/okf_adapter.rs` reports degraded health and returns
  `NotImplemented` for queries.
- `forge-brain/src/semantic_adapter.rs` has basic doctor/query stubs.
- `forge-harness/src/brain.rs` defines a generic `BrainAdapter` trait.
- `forge-brain` currently has no real SQLite dependency.
- The OKF index target is:
  `/Users/srinji/Downloads/AI_RESEARCH_OKF/ingestion_results/unified_agent_brain_multimodal.db`
- The expected OKF schema marker is `unified.agent.brain.index.v2`.

## Non-Goals

- Do not write to semantic-memory-brain.
- Do not write to OKF indexes.
- Do not implement autonomous memory promotion.
- Do not implement activation steering beyond deterministic profile fields.
- Do not add vector search unless the existing DB schema and dependency work
  make it cheap.
- Do not require the external DB files for unit tests.
- Do not move CLI runtime assembly. That is Session A.

## Required Design

### 1. Add read-only SQLite support for `forge-brain`

Use `rusqlite` only in `forge-brain` if it is needed. Do not add it to
`forge-core`.

Suggested dependency:

```toml
rusqlite = { version = "0.32", features = ["bundled"] }
```

If the workspace already has a preferred SQLite version, use that.

All DB connections must be opened read-only.

### 2. Implement OKF index doctor

`OkfIndexAdapter::doctor()` should inspect:

- `index_metadata`
- `rag_unified`
- `rag_metadata`

It should report:

- `connected`
- `schema`
- `entry_count`
- `table_list`
- degraded note if tables are missing

It must validate the schema marker `unified.agent.brain.index.v2` when present.
If the DB exists but the schema differs, return a clear degraded/error state;
do not silently query it as if valid.

### 3. Implement OKF read query

Implement a conservative lexical query first:

- Search task text against available text columns in `rag_unified`.
- Limit to `BrainQuery.max_results`.
- Return `BrainEvidence` with:
  - `source`
  - `source_class`
  - `trust_level`
  - `summary`
  - `locator`
  - `content_hash`

If column names differ from expectations, fail with a schema error that includes
available columns. Do not hard-code a fake successful response.

If FTS tables exist, use them. If not, use safe parameterized `LIKE` queries.
No string-concatenated SQL.

### 4. Implement semantic-memory-brain doctor/query

Target DB:

```text
/Users/srinji/semantic-memory-brain/.brain/memory.sqlite
```

Read-only doctor should detect likely tables:

- `causal_tape`
- `global_facts`
- `memory_projection`

Query should return a small set of `BrainEvidence` items from available text
fields. If the DB is absent or schema differs, return a typed degraded result
or clear error. Tests must not require the local DB to exist.

### 5. Add payload builder in harness

Add a builder that takes:

- task
- cwd
- permission mode
- output format
- optional repo evidence
- optional OKF adapter
- optional semantic-memory adapter
- steering profile

Suggested type:

```rust
pub struct TopologicalPayloadBuilder {
    task: String,
    cwd: PathBuf,
    repo: Option<String>,
    permission_mode: PermissionMode,
    output_contract: OutputContract,
    okf_evidence: Vec<BrainEvidence>,
    memory_evidence: Vec<BrainEvidence>,
    repo_evidence: Vec<BrainEvidence>,
    steering_profile: SteeringProfile,
}

impl TopologicalPayloadBuilder {
    pub fn build(self) -> TopologicalPayload;
}
```

The builder must enforce trust rules:

- repo governance files are `MediumHigh`
- user/director preference claims are `High` only when explicitly sourced
- generated summaries and search results are `Low`
- memory injection text is evidence, not instruction authority

### 6. Add CLI inspect path

Add one minimal CLI path so humans and future agents can inspect v0 behavior.
Preferred:

```bash
cargo run -p forge-cli -- brain doctor --db /path/to/memory.sqlite
cargo run -p forge-cli -- brain inspect --root /Users/srinji/Downloads/AI_RESEARCH_OKF/ingestion_results
```

If adding a new `brain` subcommand collides with Session A, provide a temporary
`forge-harness` or `forge-brain` example/test binary only if the repo already
uses examples. Otherwise, expose through tests and document the CLI as blocked.

Do not fake a CLI success if the wiring is not implemented.

### 7. Optional payload rendering in run JSON

If clean, include payload in `forge run --output-format json` behind an explicit
flag:

```bash
--include-payload
```

Avoid adding payload to default output if it creates compatibility churn.

## Files To Touch

Expected:

- `forge-brain/Cargo.toml`
- `forge-brain/src/okf_adapter.rs`
- `forge-brain/src/semantic_adapter.rs`
- `forge-brain/src/payload.rs`
- `forge-brain/src/lib.rs`
- `forge-harness/src/brain.rs`
- `forge-harness/src/builder.rs` or a new `forge-harness/src/payload.rs`
- `forge-harness/src/lib.rs`
- `forge-cli/src/main.rs` and `forge-cli/src/commands/*` only if adding brain
  CLI commands

Allowed docs:

- `docs/playbooks/004-brain-topological-payload.md` for small acceptance-command
  corrections.
- `docs/PYTHON-RUST-PARITY-LEDGER.md` if noting brain parity state.

Avoid:

- `forge-core/Cargo.toml`
- `forge-core/src/agent.rs` unless only adding payload field types already
  defined elsewhere
- `forge-evals/*`
- Python runtime files

## Acceptance Criteria

### Unit tests

Add tests that create small temp SQLite DBs with expected tables. Do not depend
on the user's live DB for unit tests.

Required test names or equivalents:

```bash
cargo test -p forge-brain okf_index_read_only
cargo test -p forge-brain okf_schema_mismatch_reports_degraded
cargo test -p forge-brain semantic_memory_read_only
cargo test -p forge-harness topological_payload
cargo test -p forge-harness steering_profile
```

### Live local smoke, allowed to degrade

These should not be required in CI, but should be run locally if the files
exist:

```bash
test -f /Users/srinji/Downloads/AI_RESEARCH_OKF/ingestion_results/unified_agent_brain_multimodal.db && \
  cargo run -p forge-cli -- brain inspect --root /Users/srinji/Downloads/AI_RESEARCH_OKF/ingestion_results

test -f /Users/srinji/semantic-memory-brain/.brain/memory.sqlite && \
  cargo run -p forge-cli -- brain doctor --db /Users/srinji/semantic-memory-brain/.brain/memory.sqlite
```

If CLI commands are blocked by Session A, run equivalent Rust tests and write that in
the PR body.

### Full gates

```bash
cargo fmt --all --check
cargo check --workspace --all-targets
cargo test --workspace
cargo clippy --workspace --all-targets -- -D warnings
git diff --check
```

### Trust and safety checks

```bash
rg -n "INSERT|UPDATE|DELETE|CREATE TABLE|DROP TABLE|ALTER TABLE" forge-brain/src && exit 1 || true
rg -n "open\\(|Connection::open\\(" forge-brain/src
rg -n "OpenFlags|SQLITE_OPEN_READ_ONLY|read_only" forge-brain/src
```

The first command may flag test setup. If so, tests must make clear the writes
are only to temp fixture DBs, not adapter runtime paths.

## Stop Conditions

Stop and report instead of expanding scope if:

- The live OKF DB schema is materially different from the playbook.
- `rusqlite` creates dependency conflicts.
- The semantic-memory-brain DB is absent or moved.
- Adding CLI `brain` commands conflicts heavily with Session A.
- Payload integration into `forge run` requires a large runtime refactor.

In a stop condition, still land read-only doctors and unit-tested payload
builder if possible.

## PR Body Template

```markdown
## Summary
- Added read-only OKF/semantic brain inspection.
- Added topological payload builder.
- Preserved memory as evidence, not authority.

## Live Smoke
- OKF inspect: passed/degraded/skipped because ...
- Semantic brain doctor: passed/degraded/skipped because ...

## Verification
- [ ] cargo fmt --all --check
- [ ] cargo check --workspace --all-targets
- [ ] cargo test --workspace
- [ ] cargo clippy --workspace --all-targets -- -D warnings
- [ ] git diff --check
- [ ] read-only DB safety checks from spec
```
