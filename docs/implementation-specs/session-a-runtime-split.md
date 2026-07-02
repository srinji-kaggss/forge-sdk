# Session A Runtime Split

Status: ready for implementation
Branch: `feat/runtime-split`
Parent epic: issue #74
Primary playbook: `docs/playbooks/003-sdk-harness-agent-split.md`

## Objective

Make the Rust runtime ownership boundary real:

- `forge-harness` owns ACI tools and runtime assembly.
- `forge-cli` parses commands, loads config, invokes the harness, and renders
  output.
- `forge-core` remains dependency-light SDK contracts and portable runtime
  types.

This PR should not change agent intelligence, provider behavior, brain
semantics, field-test receipts, or benchmark adapters except where needed to
compile through the new boundary.

## Current State

Known post-PR77 state:

- `forge-cli/src/tools/*` contains canonical repo tools.
- `forge-harness/src/aci/tools.rs` says canonical tools live in CLI.
- `forge-cli/src/commands/run.rs` directly constructs:
  - `SandboxRoot`
  - `PermissionGate`
  - `VerifierPipeline`
  - provider
  - `tools::default_tools`
  - `LifecycleAgent`
- `forge-harness/src/builder.rs` exists but only assembles config and a
  permission gate.

This is still a context blur. The CLI is doing runtime orchestration.

## Non-Goals

- Do not add new model providers.
- Do not add new brain dependencies.
- Do not implement Harbor, SWE-bench, or browser-engine receipts.
- Do not rewrite `LifecycleAgent`.
- Do not remove Python reference code.
- Do not add new crates unless strictly required.

## Required Design

### 1. Move ACI tool implementations into `forge-harness`

Move these modules from `forge-cli/src/tools/` into `forge-harness/src/aci/`:

- `gated_mutation.rs`
- `grep.rs`
- `safe_read.rs`

Expected harness shape:

```text
forge-harness/src/aci/mod.rs
forge-harness/src/aci/gated_mutation.rs
forge-harness/src/aci/grep.rs
forge-harness/src/aci/safe_read.rs
```

`forge-harness::aci` should export:

- `default_tools`
- `ReadFileTool`
- `GrepTool`
- `ListDirTool`
- `GlobTool`
- `OpenFileWindowTool`
- `SearchRepoTool`
- `RepoMapTool`
- `WriteFileTool`
- `PatchFileTool`
- `RunCommandTool`
- `BashTool`

`forge-cli` must stop declaring `pub mod tools`.

### 2. Expand `HarnessBuilder`

`HarnessBuilder` should become the single runtime assembly entrypoint. It must
be able to receive or derive:

- `ForgeConfig`
- `SandboxRoot`
- `cwd`
- `PermissionMode`
- `VerifierPipeline`
- `Arc<dyn ModelPort>`
- ACI tool registry
- Optional event sender

The builder should return a runtime object that can execute a task through
`LifecycleAgent` without the CLI manually constructing the agent internals.

Suggested minimal API:

```rust
pub struct HarnessBuilder {
    config: Option<ForgeConfig>,
    cwd: Option<PathBuf>,
    sandbox: Option<SandboxRoot>,
    permission_mode: PermissionMode,
    verifier: Option<VerifierPipeline>,
    model_port: Option<Arc<dyn ModelPort>>,
    tools: Option<Vec<Box<dyn Tool<Input = Value, Output = Value>>>>,
}

impl HarnessBuilder {
    pub fn with_cwd(self, cwd: impl Into<PathBuf>) -> Self;
    pub fn with_sandbox(self, sandbox: SandboxRoot) -> Self;
    pub fn with_model_port(self, model_port: Arc<dyn ModelPort>) -> Self;
    pub fn with_tools(self, tools: Vec<Box<dyn Tool<Input = Value, Output = Value>>>) -> Self;
    pub fn with_default_repo_tools(self) -> Self;
    pub fn build(self) -> Result<AssembledHarness, BuildError>;
}
```

`AssembledHarness` should expose a clear run method rather than leaking all
internals back to CLI:

```rust
impl AssembledHarness {
    pub async fn run_with_events(
        &mut self,
        task: Trusted<String>,
        max_steps: u32,
        max_tokens: Option<u64>,
        max_cost: Option<f64>,
        event_tx: tokio::sync::mpsc::Sender<AgentEvent>,
    ) -> AgentResult;
}
```

The exact signatures may differ, but the boundary must be preserved: CLI should
not directly instantiate `LifecycleAgent`.

### 3. Keep verifier finishing logic out of CLI where practical

PR77 added explicit verify command support in CLI. In this PR, move the reusable
parts into harness:

- run configured verifier pipeline
- run optional verify command
- emit `VerifyStart`, `Verify`, and `VerifyEnd`
- attach `VerificationEvidence`
- fail with `FailureReason::VerificationFailed` when a gate fails

CLI may still parse `--verify-command` and pass it to the harness.

If moving all verifier code causes excessive churn, split it as:

- Session A required: CLI no longer assembles tools/agent directly.
- Session A allowed follow-up: verifier finalization remains temporarily in CLI with
  a `TODO(pr78-followup)` comment and issue reference.

Do not silently drop any PR77 verification behavior.

### 4. Enforce dependency boundaries

`forge-core` must not depend on:

- `clap`
- `reqwest`
- `ratatui`
- `crossterm`
- `rusqlite`
- `forge-cli`
- `forge-tui`
- `forge-evals`

`forge-harness` may depend on `forge-core`, `forge-core-security`, and normal
small runtime dependencies already in the workspace. Avoid adding new external
dependencies.

### 5. Add parity ledger update

Update `docs/PYTHON-RUST-PARITY-LEDGER.md` with the new ownership state for:

- Python tool registry
- Python CLI run path
- Rust harness ACI
- Rust CLI run path

This should be factual and short. Do not turn it into a new strategy doc.

## Files To Touch

Expected:

- `forge-harness/src/aci/mod.rs`
- `forge-harness/src/aci/gated_mutation.rs`
- `forge-harness/src/aci/grep.rs`
- `forge-harness/src/aci/safe_read.rs`
- `forge-harness/src/builder.rs`
- `forge-harness/src/lib.rs`
- `forge-harness/Cargo.toml`
- `forge-cli/src/main.rs`
- `forge-cli/src/commands/run.rs`
- `forge-cli/Cargo.toml`
- `docs/PYTHON-RUST-PARITY-LEDGER.md`

Avoid touching:

- `forge-brain/*`
- `forge-evals/*`
- Python runtime files under `src/forge_sdk/*`

## Acceptance Criteria

### Code

- `forge-cli` no longer defines or owns repo tool implementations.
- `forge-harness::aci::default_tools` is the canonical default repo tool
  factory.
- `forge-cli/src/commands/run.rs` invokes `HarnessBuilder` or an equivalent
  harness assembly API.
- Existing PR77 behavior still works:
  - tools are rooted at `--cwd`
  - `--verify-command <cmd>` gates success
  - `--no-verify` disables verification
  - stream-json still emits run, model, tool, permission, and verify events

### Tests

Add or move tests so these pass:

```bash
cargo test -p forge-harness aci
cargo test -p forge-harness builder
cargo test -p forge-cli verify_command
cargo test -p forge-core agent
```

Boundary checks:

```bash
rg -n "pub mod tools|mod tools|crate::tools|tools::default_tools" forge-cli/src && exit 1 || true
rg -n "struct ReadFileTool|struct GrepTool|struct BashTool" forge-cli/src && exit 1 || true
cargo tree -p forge-core | rg "clap|reqwest|ratatui|crossterm|rusqlite|forge-cli|forge-tui|forge-evals" && exit 1 || true
```

Full gates:

```bash
cargo fmt --all --check
cargo check --workspace --all-targets
cargo test --workspace
cargo clippy --workspace --all-targets -- -D warnings
git diff --check
```

### Smoke

```bash
cargo run -p forge-cli -- doctor --json
cargo run -p forge-cli -- run \
  --cwd . \
  --task "Name three existing files in this repository. Do not edit." \
  --output-format json \
  --max-steps 4 \
  --no-verify
```

The run may fail for missing API keys in a fresh environment, but it must fail
through typed config/provider errors, not through unresolved imports or missing
tool registry symbols.

## Stop Conditions

Stop and report instead of expanding scope if:

- Moving verifier finalization into harness requires a large `LifecycleAgent`
  rewrite.
- A new dependency seems necessary.
- `forge-cli` requires business logic that is not expressible through the
  harness API.
- Baseline `origin/uat` fails before changes.

## PR Body Template

```markdown
## Summary
- Moved canonical ACI tools from CLI to harness.
- Routed `forge run` through harness assembly.
- Preserved PR77 verification and stream behavior.

## Verification
- [ ] cargo fmt --all --check
- [ ] cargo check --workspace --all-targets
- [ ] cargo test --workspace
- [ ] cargo clippy --workspace --all-targets -- -D warnings
- [ ] git diff --check
- [ ] boundary rg checks from spec

## Notes
Any verifier finalization left in CLI: none / describe temporary follow-up.
```
