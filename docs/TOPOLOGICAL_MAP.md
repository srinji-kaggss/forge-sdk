# Forge Rust Port — Topological Map & Team Dispatch

**Created:** 2026-07-01
**Source:** meaning_runtime_okf (MRIL) + engineering-team roles + Karpathy + FORGE_FEEDBACK.md
**Standards:** SOC 2 Type II + DO-178C DAL A + IEC 61508 SIL 3
**Security:** STRICTEST Defense-in-Depth + Privacy-by-Design

---

## Four-Plane Topology

```
┌─────────────────────────────────────────────────────────────────────┐
│  CONTROL PLANE (LogicalWorks daemon)                                │
│  tenant/session referee, event ingestion, memory promotion          │
│  OUR SCOPE: forge sends episodes TO this plane                      │
│  PRIVACY: forge controls what leaves via user-configured policy     │
├─────────────────────────────────────────────────────────────────────┤
│  EXECUTION PLANE (forge-sdk) — WE ARE HERE                         │
│  model/provider isolation    tool execution/validation              │
│  trace spans + audit hash    verification pipeline                  │
│  eval harness                permission gate                       │
│  session checkpointing       doctor L0-L5                          │
│  DEFENSE: L0 sandbox → L1 process → L2 gate → L3 verify → L4 audit │
│  ▲ forge-core + forge-cli + forge-tui                              │
├─────────────────────────────────────────────────────────────────────┤
│  INTERPRETATION PLANE (shared)                                      │
│  semantic coding (8 meaning-frame labels)  OKF doc parsing          │
│  wrong-abstraction detection               growth policy decisions  │
│  SECURITY: labels gate success, not just annotate it                │
│  ▲ forge-core provides: semantic labels, OKF types, episodes       │
├─────────────────────────────────────────────────────────────────────┤
│  LOCAL MECHANISTIC PLANE (future research)                          │
│  activation snapshots, probes/SAEs, steering, distillation          │
│  PRIVACY: local-only by design, no cloud dependency                 │
│  ▲ forge-core provides: activation_snapshot_id field on episode    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Defense-in-Depth Layers (forge-core)

| Layer | Name | Mechanism | SOC 2 TSC | DO-178C | IEC 61508 |
|-------|------|-----------|-----------|---------|-----------|
| L5 | Physical/OS | cgroups, containers, landlock | Physical Security | HW/SW | HW integrity |
| L4 | Audit | AuditLog, hash chain, tracer spans | Monitoring | Traceability | Diagnosis |
| L3 | Verification | 5-gate pipeline, evidence chain | Processing Integrity | Verifiability | Functional Safety |
| L2 | Permission | PermissionGate, anti-slop, Yolo-still-guards | Access Control | Sec. Reqs | Access Control |
| L1 | Process | LoopGuard, sandbox, path safety | Logical Security | Robustness | Fault Tolerance |
| L0 | Network | ModelProvider isolation, no telemetry | Confidentiality | Data Security | Comms Security |

---

## Privacy-by-Design Principles

1. **Local-first**: forge runs ENTIRELY on the user's machine. No cloud dependency.
2. **No telemetry**: forge-cli and forge-tui make ZERO unsolicited network calls.
3. **Config persistence at ~/.forge/**: user controls every setting.
4. **Audit trail is always-on**: every action logged to ~/.forge/audit/.
5. **Data retention configurable**: user sets retention policy, TTL, max size.
6. **Right to delete**: user can delete all traces via forge session delete + rm -rf ~/.forge.
7. **Transparency**: TUI shows EVERYTHING. No hidden model calls. No hidden tool executions.
8. **Consent**: Permission gate requires user approval for non-safe actions (interactive mode).
9. **NO_COLOR/CLICOLOR**: terminal output is respectful of user's terminal preferences.
10. **JSON output**: machine-readable output for CI/CD — never mixed with ANSI.

---

## Team Dispatch (7 Agents)

| Agent | Plane | Task | Deliverables |
|-------|-------|------|-------------|
| architect-karpathy | All 4 | Harden architecture, validate dep graph, enforce SOC2/DO178C | architecture document, requirements matrix, FMEA |
| backend-forge-core | Execution | forge-core Rust code (event/result/context/port/agent/permission/verifier/session/doctor/guard/security/tracer/audit) | 16 .rs files, DO178C traceability |
| backend-interpretation | Interpretation | Semantic labels (8 variants), OKF doc types, episode schema, GH #67 integration | semantic.rs, okf.rs, experience.rs |
| devops-ci | Execution (infra) | Cargo workspace, CI/CD, playbook, keel config | 2 Cargo.tomls, forge-ci.yml, PLAYBOOK.md, keel.yaml |
| tui-designer | Execution (UX) | Spine-based TUI with crossterm+ratatui | 8 .rs files, config screen, inspector |
| cli-engineer | Execution (UX) | CLI surface with clap, 7 subcommands | 10+ .rs files, renderers |
| qa-harness | Execution (quality) | Test harness, 30+ tests, SOC2/DO178C docs | harness tests, safety tests, schema |

---

## Key Anti-Duplication Boundaries

1. forge-tui is NOT lgwks_ui.py — different tech (crossterm vs raw ANSI), different palette, different app state
2. forge-cli is NEW Rust code — NOT a port of forge-experience Python CLI
3. forge-core is NEW Rust code — typed enums instead of stringly-typed Python dataclasses
4. forge-gemini wraps google-genai-rs — NOT a port of forge-experience Python model wrappers
5. forge-harness is NEW Rust code — property tests for invariants, not just unit tests

