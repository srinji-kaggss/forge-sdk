---
id: FORGE-PLAYBOOK-003
title: SDK Harness Agent Split
status: active
---

# SDK/Harness/Agent Split

The repo is currently a context blur because SDK, agent, CLI, harness, eval, and experience work live near each other. The solution is not a rewrite first. The solution is to lock ownership boundaries, then move code only when a PR has a test proving the boundary.

## Target Crate Shape

```text
forge-core/            SDK contracts and portable runtime types
forge-core-security/   containment, sandbox, permission primitives
forge-providers/       provider implementations behind ModelPort
forge-harness/         orchestration, ACI, sessions, audit, verifier, replay
forge-agent/           default coding agent assembled from harness pieces
forge-cli/             command surface and renderers
forge-tui/             event-stream UI
forge-brain/           semantic-memory-brain and OKF index adapters
forge-evals/           SWE, Terminal-Bench/Harbor, field-test adapters
```

## Ownership Rules

| Crate | Public API allowed | Forbidden |
|---|---|---|
| `forge-core` | `ModelPort`, `Tool`, `ToolSpec`, `AgentResult`, `AgentEvent`, `Claim`, `Episode` | CLI parsing, filesystem tools, provider HTTP clients |
| `forge-core-security` | trusted/untrusted wrappers, sandbox roots, permission classification | Model calls, UI logic |
| `forge-providers` | provider clients and tool-call parsing | Agent policy or verifier logic |
| `forge-harness` | run loop, ACI, sessions, audit, verification, replay | Provider-specific config secrets |
| `forge-agent` | default coding agent profile and prompts | SDK trait definitions |
| `forge-cli` | clap commands and renderers | Business logic not exposed through harness |
| `forge-brain` | read-only search and source-backed memory promotion APIs | Owning ingestion cron or writing ad hoc state to external index |
| `forge-evals` | adapters and scoring | Runtime behavior unavailable to normal users |

## Migration Cards

### Card 1: Move repo tools out of CLI

Move `forge-cli/src/tools.rs` into `forge-harness/src/aci/tools.rs`.

Acceptance:

```bash
cargo test --workspace
rg -n "struct ReadFileTool|struct GrepTool|struct BashTool" forge-cli/src && exit 1 || true
```

### Card 2: Keep SDK contract dependency-light

`forge-core` must not depend on CLI, provider, TUI, eval, or repo-specific crates.

Acceptance:

```bash
cargo tree -p forge-core
cargo tree -p forge-core | rg "clap|reqwest|ratatui|crossterm|rusqlite" && exit 1 || true
```

### Card 3: Introduce harness assembly

Add a `HarnessBuilder` that receives:

- model port
- tool registry
- permission mode
- verifier config
- audit sink
- event renderer
- brain adapter optional

The CLI should call the builder; it should not manually assemble agent internals.

Acceptance:

```bash
cargo test -p forge-harness builder
cargo run -p forge-cli -- run --cwd . --task "List files" --output-format json
```

### Card 4: Python reference ledger

Create `docs/PYTHON-RUST-PARITY-LEDGER.md` mapping each Python module to:

- ported
- keep as reference
- delete after Rust parity
- dev-only

Acceptance:

```bash
test -s docs/PYTHON-RUST-PARITY-LEDGER.md
rg -n "src/forge_sdk/agents/react.py|src/forge_sdk/eval/harness.py|src/forge_sdk/tools/registry.py" docs/PYTHON-RUST-PARITY-LEDGER.md
```

## Done Means

- A new developer can tell where a feature belongs without asking.
- Rust runtime code no longer lives in CLI except command parsing and renderers.
- Python is explicitly reference/dev/legacy, not a hidden second runtime.

