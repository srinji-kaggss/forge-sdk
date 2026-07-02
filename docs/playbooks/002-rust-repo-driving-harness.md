---
id: FORGE-PLAYBOOK-002
title: Rust Repo-Driving Harness
status: active
baseline_files:
  - forge-core/src/agent.rs
  - forge-core/src/semantic.rs
  - forge-core/src/okf.rs
  - forge-core/src/experience.rs
  - forge-cli/src/main.rs
  - forge-cli/src/tools.rs
---

# Rust Repo-Driving Harness

Goal: make Rust Forge inspect, edit, verify, and report on a real repository through audited tools. This is the immediate post-PR-75 implementation lane.

## Card 1: CLI Surface

Implement:

- `forge run --task <text>`
- `forge doctor`
- `forge session list|show|resume`
- `forge audit show|export`
- `forge eval smoke`

Minimum `run` flags:

- `--cwd`
- `--permission-mode interactive|yolo|plan`
- `--output-format text|json|stream-json`
- `--verify-command`
- `--no-verify`
- `--max-steps`
- `--max-tokens`
- `--max-cost`
- `--checkpoint-dir`

Files:

- `forge-cli/src/main.rs`
- `forge-cli/src/commands/run.rs`
- `forge-cli/src/commands/doctor.rs`
- `forge-cli/src/commands/session.rs`
- `forge-cli/src/commands/audit.rs`
- `forge-cli/src/render.rs`

Acceptance:

```bash
cargo test --workspace
cargo clippy --workspace --all-targets -- -D warnings
cargo run -p forge-cli -- doctor --json
cargo run -p forge-cli -- run --cwd . --task "Name three existing files" --output-format json
```

## Card 2: Agent-Computer Interface

PR #75 added `read_file`, `grep`, and `bash`. Harden and expand into an ACI rather than a raw tool bag.

Add safe read tools:

- `list_dir`
- `glob`
- `open_file_window`
- `search_repo`
- `repo_map`

Add gated mutation tools:

- `patch_file`
- `write_file`
- `run_command`

Rules:

- Tools are rooted at `--cwd`.
- Observations include path, line numbers, truncation metadata, and content hash when useful.
- Search must cap result count and ask for a narrower query when too broad.
- `run_command` must use explicit argv parsing for normal commands; raw shell is a separate dangerous mode.
- Every call creates an `AgentStep`.

Files:

- `forge-cli/src/tools.rs`
- `forge-core/src/agent.rs`
- `forge-core/src/step.rs`
- `forge-core/src/event.rs`
- `forge-core-security/src/sandbox.rs`

Acceptance:

```bash
cargo test -p forge-cli tool
cargo test -p forge-core agent
cargo run -p forge-cli -- run --cwd /Users/srinji/next-gen-browser-engine --task "Read AGENTS.md and name the compatibility contract files" --output-format json
```

The final JSON must name real files from the repo. Generic advice is a failure.

## Card 3: Honest Success Semantics

Add a terminal result classifier before `AgentResult.success = true`.

Fail when:

- Repo-driving task has no repo tools configured.
- The model names a file that does not exist.
- Edit task ends with no edit and no explicit impossible reason.
- Verification was requested but did not run.
- Tool failure happened and final answer ignores it.
- Tool-capable run silently falls back to no-tool chat.

Files:

- `forge-core/src/result.rs`
- `forge-core/src/verifier.rs`
- `forge-core/src/agent.rs`
- `forge-cli/src/main.rs`

Acceptance:

```bash
cargo test -p forge-core honest_success
cargo test -p forge-core no_tools_fail_repo_task
cargo test -p forge-cli verify_requested_must_run
```

## Card 4: Stream Events

Implement stable stream-json events before TUI polish.

Minimum events:

- `RunStart`
- `ModelRequest`
- `ModelResponse`
- `ToolCall`
- `ToolResult`
- `PermissionRequest`
- `PermissionDecision`
- `FileEdit`
- `VerifyStart`
- `VerifyEnd`
- `RunEnd`

`RunEnd` includes:

- `success`
- `failure_reason`
- `change_manifest`
- `verification`
- `model_usage`
- `trace_id`
- `session_id`

Acceptance:

```bash
cargo run -p forge-cli -- run --cwd . --task "List files" --output-format stream-json | jq -c 'select(.type=="RunEnd")'
```

## Card 5: Browser-Engine Field Test

Use `/Users/srinji/next-gen-browser-engine` as the canonical field test until a smaller fixture reproduces the same failure mode.

Read-only test:

```bash
cargo run -p forge-cli -- run \
  --cwd /Users/srinji/next-gen-browser-engine \
  --task "Assess HLR-08 compatibility-contract hardening. Name existing Rust/docs targets and cite observed contents. Do not edit." \
  --output-format json \
  --max-steps 8
```

Pass:

- Names real files.
- Cites observed content.
- Does not mention unrelated JavaScript/postMessage targets unless they exist.
- Returns failure if files cannot be inspected.

Mutating smoke:

```bash
cargo run -p forge-cli -- run \
  --cwd /Users/srinji/next-gen-browser-engine \
  --task "Make one tiny documentation-only clarification in a scratch or fixture file, then verify git diff." \
  --permission-mode interactive \
  --verify-command "git diff --check" \
  --output-format json
```

Pass:

- Produces a bounded diff.
- Runs verification.
- Emits change manifest.

