---
id: FORGE-PLAYBOOK-005
title: Runtime UX And Control Surface
status: active
---

# Runtime UX And Control Surface

Goal: give the human deterministic and visual control over the agent runtime. The UI is not a chat wrapper. It is an event cockpit for steering, telemetry, proof state, tools, memory, and verification.

## Modes

Forge must expose runtime modes as first-class controls:

- `chat`: no repo mutation, explanation and exploration.
- `plan`: repo inspection allowed, edits denied.
- `patch`: bounded edits, verification required.
- `surgery`: explicit high-risk mode, destructive actions require confirmation.
- `eval`: benchmark adapter mode, same semantics as normal run.
- `replay`: no model calls, replay existing event/session data.

## Control Surface

CLI:

- slash-like commands through `forge run` and `forge session`.
- stream-json for machine consumers.
- strict nonzero exits on false-green conditions.

TUI:

- tabs: Chat, Plan, Tools, Files, Diff, Verify, Claims, Brain, Telemetry, Eval.
- clickable file refs and tool calls.
- permission prompts with blast radius and rollback plan.
- claim status chips: asserted, verified, disputed, refuted.
- token/cost/step budget meters.

Web:

- same event stream as TUI.
- shareable run receipt.
- timeline inspection.

## Implementation Cards

### Card 1: Event renderer contract

Every UI consumes `AgentEvent`, not private runtime state.

Acceptance:

```bash
cargo test -p forge-core event_round_trip
cargo run -p forge-cli -- run --cwd . --task "List files" --output-format stream-json | jq -c '.type'
```

### Card 2: Claims panel data

Wire OKF claims into result output:

- claims
- invariants
- proof obligations
- evidence refs
- status transitions

Acceptance:

```bash
cargo test -p forge-core okf
cargo run -p forge-cli -- run --cwd . --task "State the safety claims before editing" --output-format json | jq '.claims'
```

### Card 3: Permissions as UX, not hidden policy

Every permission decision must show:

- action
- classification
- affected paths
- reversibility
- verification plan
- mode
- decision

Acceptance:

```bash
cargo test -p forge-core permission_event_contains_blast_radius
```

### Card 4: TUI tabs over existing events

Do not invent TUI-only state. Add tabs that project the event stream.

Acceptance:

```bash
cargo test -p forge-tui
cargo run -p forge-cli -- run --cwd . --task "List files" --output-format stream-json > /tmp/forge-events.jsonl
cargo run -p forge-tui -- replay /tmp/forge-events.jsonl
```

## Done Means

- The human can steer modes, tools, evidence depth, and verification strictness without prompt surgery.
- Every visible panel maps back to events.
- UI whimsy is allowed only after the run is inspectable and replayable.

