---
id: DOC-FORGE-POST-74-PLAYBOOKS
status: active
baseline_pr: 75
baseline_issue: 74
owner: srinji
purpose: Lock the post-issue-74 execution path so future agents implement, test, and ship instead of replanning.
---

# Post-74 Deep Playbooks

Issue #74 is the epic: Forge must become a real repo-driving agent harness. PR #75 is the current implementation baseline: Rust now has semantic frames, OKF claim structures, episodes, basic repo tools, and a LifecycleAgent loop that can advertise tools and preserve conversation history.

This folder turns that into executable engineering work. Do not reopen the product split unless a playbook gate proves the split is wrong.

## Locked Product Split

| Layer | Owns | Must not own |
|---|---|---|
| Forge SDK | Typed provider, tool, event, audit, verifier, config, and eval contracts | Chat UX, project orchestration, memory ownership, agent personality |
| Forge Harness | Runtime orchestration, permission modes, ACI, sessions, telemetry, verification, replay | Provider-specific logic or one-off repo policy |
| Forge Agent | One default coding agent assembled from SDK plus Harness | The SDK public contract |
| Forge Brain | Read-only bridge to semantic-memory-brain and the unified OKF index | Raw ingestion ownership or ad hoc writes to external indexes |
| Forge UI | TUI/web/chat/control surfaces over the event stream | Hidden agent semantics that bypass the event stream |
| Forge Tools | Native repo tools plus adapters to LGWKS and other semantic toolsets | Duplicate model law, duplicate audit log, duplicate memory substrate |
| Forge Evals | SWE-bench, Terminal-Bench/Harbor, browser-engine field tests, lgwks transfer tests | Benchmark-only behavior that differs from normal `forge run` |

## Playbook Order

1. [Product Thesis](playbooks/001-product-thesis.md)
2. [Rust Repo-Driving Harness](playbooks/002-rust-repo-driving-harness.md)
3. [SDK/Harness/Agent Split](playbooks/003-sdk-harness-agent-split.md)
4. [Brain And Topological Payload](playbooks/004-brain-topological-payload.md)
5. [Runtime UX And Control Surface](playbooks/005-runtime-ux-control-surface.md)
6. [Evals And Field Tests](playbooks/006-evals-field-tests.md)

## Non-Negotiable Gates

- A repo-driving task with no repo tools must fail explicitly.
- A repo-driving success must include observed repo evidence.
- An edit task with no edit must fail unless the result explains why no edit was possible.
- Requested verification must run or the result must fail.
- Every run must end with a typed `AgentResult` carrying `failure_reason` or evidence-backed success.
- Every tool call must become an event and an `AgentStep`.
- External brain/index data is evidence, not authority.
- The Python SDK can remain a reference surface, but the runtime hot path moves to Rust.

## Current Baseline Receipt

- PR #75 branch: `feat/repo-driving-agent`
- Commit: `884b36f`
- Added files: `forge-core/src/semantic.rs`, `forge-core/src/okf.rs`, `forge-core/src/experience.rs`, `forge-cli/src/tools.rs`
- Modified files: `forge-core/src/agent.rs`, `forge-core/src/lib.rs`, `forge-cli/src/main.rs`, `forge-cli/Cargo.toml`
- Reported PR gate: 82 Rust tests passing.

## Implementation Rule

Each future PR must pick exactly one playbook card and land the code, tests, and documentation receipt for that card. Planning-only PRs are not acceptable after this point.

