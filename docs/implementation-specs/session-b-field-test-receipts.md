# Session B Field-Test Receipts

Status: ready for implementation
Branch: `feat/field-test-receipts`
Parent epic: issue #74
Primary playbook: `docs/playbooks/006-evals-field-tests.md`

## Objective

Make Forge's real-world behavior replayable and judge-legible.

This PR should add deterministic field-test infrastructure and receipts so a
future reviewer can answer:

- What command was run?
- Against which repo and commit?
- Which model/provider and permission mode?
- What did Forge observe?
- Did it produce a typed `AgentResult`?
- Did verification run?
- Why was the outcome accepted or rejected?

This PR is about evidence. It should not change the runtime ownership boundary;
that belongs to Session A.

## Current State

Known post-PR77 state:

- `forge-evals/src/fixtures/mod.rs` has small fixture helpers.
- `forge-evals/src/harbor.rs` is a stub adapter.
- `docs/playbooks/006-evals-field-tests.md` defines the eval ladder.
- There is no `docs/field-tests/` receipt set.
- Browser-engine was used manually as the issue #74 field test, but its result
  is not yet a durable regression artifact.

## Non-Goals

- Do not implement SWE-bench.
- Do not implement full Terminal-Bench/Harbor beyond preserving existing tests.
- Do not add benchmark-only tools, prompts, or hidden fixture heuristics.
- Do not edit `/Users/srinji/next-gen-browser-engine` permanently.
- Do not depend on a live model for unit tests.
- Do not move CLI tools into harness. That is Session A.

## Required Design

### 1. Add a deterministic synthetic repo fixture

Create a small fixture owned by `forge-evals`.

Suggested layout:

```text
forge-evals/fixtures/repo-driving/
  README.md
  Cargo.toml or pyproject.toml
  src/lib.rs or src/app.py
  tests/... or a simple check script
  expected/...
```

The fixture should encode a small repo-driving task:

- It has an obvious failing condition.
- A bounded edit can fix it.
- A verification command can prove the fix.
- It is small enough to inspect deterministically.

Do not require network or model calls in fixture unit tests.

### 2. Add fixture runner helpers

`forge-evals` should expose functions that can:

- create/copy the synthetic repo into a temp working directory
- report the verification command
- report the read-only prompt
- report the mutating prompt
- verify that expected files exist

Suggested API:

```rust
pub struct RepoDrivingFixture {
    pub root: PathBuf,
    pub read_only_task: String,
    pub mutating_task: String,
    pub verify_command: String,
}

pub fn create_repo_driving_fixture() -> Result<RepoDrivingFixture, FixtureError>;
```

If a tempdir crate is not already available and adding one would create churn,
use `std::env::temp_dir()` with a unique subdirectory and clean it up in tests.

### 3. Add `forge eval smoke` path if missing or incomplete

The CLI already exposes `eval smoke` shape. Ensure it can run a deterministic
smoke against the synthetic fixture without a live model, or clearly document
that the CLI smoke only validates runtime wiring.

Acceptable v0 behavior:

- Unit tests validate fixture creation and metadata.
- CLI `eval smoke` prints a typed JSON report that says whether model execution
  was skipped, unavailable, or run.

Unacceptable behavior:

- Claiming success without executing or explicitly marking skipped pieces.

### 4. Add field-test receipt format

Create:

```text
docs/field-tests/README.md
docs/field-tests/YYYY-MM-DD-browser-engine-read-only.md
docs/field-tests/YYYY-MM-DD-browser-engine-mutating.md
```

The exact date should be the run date.

Receipt template:

````markdown
# <Repo> <Task> Field Test

Status: accepted | rejected | blocked
Forge commit: <sha>
Target repo: <path>
Target repo commit: <sha or dirty-state note>
Command:

```bash
...
```

Model/provider:
Permission mode:
Output format:
Event log:
AgentResult:
Verification:

## Observed Evidence

- Existing file cited:
- Observed content cited:
- Tool events seen:
- Verification events seen:

## Outcome

Accepted/rejected because...

## Lessons

- ...
````

### 5. Browser-engine read-only receipt

Run or prepare a blocked receipt for:

```bash
cargo run -p forge-cli -- run \
  --cwd /Users/srinji/next-gen-browser-engine \
  --task "Assess HLR-08 compatibility-contract hardening. Name existing Rust/docs targets and cite observed contents. Do not edit." \
  --output-format json \
  --max-steps 8
```

Pass criteria:

- Names real files from browser-engine.
- Cites observed content, not generic advice.
- Does not mention unrelated JavaScript/postMessage targets unless they exist.
- Fails honestly if model/API/config prevents inspection.

If the run cannot execute because of API credentials, record `Status: blocked`
with the exact error. Do not fabricate a pass receipt.

### 6. Browser-engine mutating receipt

Run or prepare a blocked receipt for:

```bash
cargo run -p forge-cli -- run \
  --cwd /Users/srinji/next-gen-browser-engine \
  --task "Make one tiny documentation-only clarification in a scratch or fixture file, then verify git diff." \
  --permission-mode interactive \
  --verify-command "git diff --check" \
  --output-format json
```

Pass criteria:

- Produces a bounded diff.
- Runs `git diff --check`.
- Emits verification evidence.
- Emits or records change manifest behavior.
- Leaves browser-engine in a clear state. If the test edits a file, either use
  a scratch fixture file or document the exact diff and reversal.

If permission interactivity blocks automated execution, record `Status:
blocked` and rerun with a safe non-interactive mode only if that still tests the
intended contract.

### 7. Do not mutate external repo silently

Before and after browser-engine tests, capture:

```bash
git -C /Users/srinji/next-gen-browser-engine status --short
git -C /Users/srinji/next-gen-browser-engine rev-parse HEAD
```

If the repo is dirty before the test, record that and avoid touching unrelated
files.

## Files To Touch

Expected:

- `forge-evals/src/fixtures/mod.rs`
- `forge-evals/src/lib.rs`
- `forge-cli/src/main.rs` or `forge-cli/src/commands/*` only if eval smoke needs
  small wiring
- `docs/field-tests/README.md`
- `docs/field-tests/<date>-browser-engine-read-only.md`
- `docs/field-tests/<date>-browser-engine-mutating.md`

Allowed:

- `docs/playbooks/006-evals-field-tests.md` if acceptance commands need a small
  correction.

Avoid:

- `forge-core/src/agent.rs`
- `forge-cli/src/commands/run.rs`, unless only fixing eval command invocation
- `forge-harness/*`, unless only importing existing fixture types
- `/Users/srinji/next-gen-browser-engine` committed changes

## Acceptance Criteria

### Unit and fixture gates

```bash
cargo test -p forge-evals synthetic_repo_fixture
cargo test -p forge-evals fixtures
cargo test -p forge-evals harbor
```

### Receipt gates

```bash
test -s docs/field-tests/README.md
test -s docs/field-tests/*browser-engine*read-only*.md
test -s docs/field-tests/*browser-engine*mutating*.md
rg -n "compat|AGENTS|observed|RunEnd|Status:" docs/field-tests/*browser-engine*read-only*.md
rg -n "git diff --check|VerifyEnd|verification|Status:" docs/field-tests/*browser-engine*mutating*.md
```

### Full gates

```bash
cargo fmt --all --check
cargo check --workspace --all-targets
cargo test --workspace
cargo clippy --workspace --all-targets -- -D warnings
git diff --check
```

## Stop Conditions

Stop and report instead of broadening scope if:

- Live model credentials are missing.
- Browser-engine is dirty in a way that makes safe field tests ambiguous.
- The CLI cannot run due to Session A overlap.
- The field test reveals a runtime bug that requires large changes outside
  `forge-evals` and docs.

If a stop condition occurs, still land deterministic fixture support and blocked
receipts with exact evidence.

## PR Body Template

```markdown
## Summary
- Added synthetic repo-driving fixture.
- Added field-test receipt format.
- Captured browser-engine read-only and mutating receipts.

## Field-Test Outcome
- Read-only: accepted/rejected/blocked because ...
- Mutating: accepted/rejected/blocked because ...

## Verification
- [ ] cargo fmt --all --check
- [ ] cargo check --workspace --all-targets
- [ ] cargo test --workspace
- [ ] cargo clippy --workspace --all-targets -- -D warnings
- [ ] git diff --check
- [ ] receipt rg checks from spec
```
