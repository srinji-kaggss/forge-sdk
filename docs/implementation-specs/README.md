# Post-PR77 Implementation Dispatch

Status: active
Base: `origin/uat` after PR #77 merge commit `4233c4a`
Parent epic: GitHub issue #74, "Make Forge a real repo-driving agent harness"

These specs are for three parallel implementation sessions. Each session should
take one spec, create its own branch from `origin/uat`, implement only that
scope, run the listed gates, and open a PR.

Do not replan the product. The locked direction is:

- `forge-core` is the SDK contract layer.
- `forge-core-security` owns containment and sandbox primitives.
- `forge-harness` owns runtime assembly, ACI tools, sessions, audit,
  verification, replay, and brain payload assembly.
- `forge-cli` owns command parsing and renderers only.
- `forge-brain` is a read-only bridge to semantic-memory-brain and OKF indexes.
- `forge-evals` owns field tests and benchmark adapters using normal `forge run`.

## Session Assignments

| Session | Spec | Branch name | Primary outcome |
|---|---|---|---|
| 1 | [Session A Runtime Split](session-a-runtime-split.md) | `feat/runtime-split` | CLI delegates runtime assembly and ACI tools to `forge-harness`. |
| 2 | [Session B Field-Test Receipts](session-b-field-test-receipts.md) | `feat/field-test-receipts` | Synthetic and browser-engine field tests become replayable receipts. |
| 3 | [Session C Brain Payload v0](session-c-brain-payload-v0.md) | `feat/brain-payload-v0` | Read-only brain adapters and topological payload builder become usable. |

## Common Start Protocol

```bash
cd /Users/srinji/forge-uat
git fetch origin
git checkout -B <branch-name> origin/uat
cargo test --workspace
cargo clippy --workspace --all-targets -- -D warnings
```

If the baseline gates fail before your changes, stop and report the exact
failure. Do not mix baseline repair into an implementation PR unless the spec
explicitly requires it.

## Common Finish Protocol

Every PR must include:

- Code implementation.
- Focused tests for the changed contract.
- A short receipt in the PR body listing commands run.
- No unrelated formatting churn.
- No planning-only changes.

Required final local gates:

```bash
cargo fmt --all --check
cargo check --workspace --all-targets
cargo test --workspace
cargo clippy --workspace --all-targets -- -D warnings
git diff --check
```

## Coordination Rules

- Session A is the most foundational. Session B and Session C may proceed in parallel, but if
  they need runtime assembly hooks, prefer adding small local shims over
  changing the Session A ownership boundary.
- Session B must not add benchmark-only behavior. Field tests must use normal
  `forge run` or normal Rust test fixtures.
- Session C must not write to semantic-memory-brain or OKF indexes. Read-only first.
- If two sessions touch the same file, the session with the matching ownership
  owns the final shape. For example, Session A owns `forge-cli/src/commands/run.rs`
  runtime assembly; Session C owns brain/payload APIs.

## Done At Epic Level

Issue #74 can be considered substantially handled only when:

- `forge-cli` is a thin surface over `forge-harness`.
- Repo tools are in the harness, not CLI.
- Browser-engine read-only and mutating tests have replayable receipts.
- A topological payload can be built and rendered without raw memory injection.
- The eval path calls the same runtime as normal users.
