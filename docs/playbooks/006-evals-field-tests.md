---
id: FORGE-PLAYBOOK-006
title: Evals And Field Tests
status: active
---

# Evals And Field Tests

Goal: make Forge judge-legible in the real world before claiming benchmark strength.

## Eval Ladder

| Stage | Test | Purpose |
|---|---|---|
| E0 | Unit and integration tests | Contract safety |
| E1 | Synthetic repo fixture | Deterministic ACI and success semantics |
| E2 | Browser-engine read-only field test | Grounded repo understanding |
| E3 | Browser-engine mutating smoke | Bounded edit plus verification |
| E4 | LGWKS integration test | Semantic toolset and bus adapter |
| E5 | semantic-memory-brain run | Brain evidence and memory trust gates |
| E6 | SWE-bench Lite | Real GitHub issue fixing |
| E7 | Terminal-Bench/Harbor | Terminal task adapter |
| E8 | Regression replay | No false-green across saved sessions |

## Field-Test Receipts

Every field test writes:

- command
- git commit
- target repo
- model/provider
- permission mode
- event log path
- AgentResult JSON path
- verification commands
- accepted/rejected outcome
- lesson

Suggested location:

```text
docs/field-tests/YYYY-MM-DD-<repo>-<task>.md
```

## Implementation Cards

### Card 1: Synthetic repo fixture

Create a tiny fixture with:

- README
- Rust or Python source file
- failing test
- expected edit
- verification command

Acceptance:

```bash
cargo test -p forge-evals synthetic_repo_fixture
cargo run -p forge-cli -- eval smoke --fixture fixtures/repo-driving
```

### Card 2: Browser-engine read-only receipt

Run the issue #74 HLR-08 assessment and store the receipt.

Acceptance:

```bash
test -s docs/field-tests/*browser-engine*read-only*.md
rg -n "compat|AGENTS|verified|observed|RunEnd" docs/field-tests/*browser-engine*read-only*.md
```

### Card 3: Browser-engine mutating smoke receipt

Run a tiny controlled edit and verification.

Acceptance:

```bash
test -s docs/field-tests/*browser-engine*mutating*.md
rg -n "git diff --check|change_manifest|VerifyEnd" docs/field-tests/*browser-engine*mutating*.md
```

### Card 4: Harbor adapter

Build adapter only after E2/E3 pass. It must call normal `forge run`.

Adapter functions:

- `install`
- `run`
- `populate_context_post_run`

Acceptance:

```bash
cargo test -p forge-evals harbor_adapter
```

## Anti-Gaming Rules

- No benchmark-only tools.
- No benchmark-only prompts.
- No hidden fixture-specific heuristics.
- No success without change manifest when edits are expected.
- No eval pass if normal CLI would fail.

## Done Means

- A zero-context judge can replay the run and understand why Forge passed or failed.
- SWE-bench and Terminal-Bench are reached after repo-driving semantics are real.
- Field tests become regression tests, not anecdotes.

