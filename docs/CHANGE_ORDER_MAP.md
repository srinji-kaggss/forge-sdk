# Forge Rust Port — Change Order Map

**Created:** 2026-07-01  
**Source:** FORGE_FEEDBACK.md failure patterns + Karpathy first-principles + engineering-team role structure  
**Status:** 🔄 IN FLIGHT — dispatching subagents

---

## PHASE 0: forge-core Foundation (CRITICAL PATH)
*Zero external deps beyond async-trait, thiserror, serde, tokio, uuid*

| Step | File | Depends On | Agent |
|------|------|------------|-------|
| 0.0 | `forge-core/Cargo.toml` | — | backend-forge-core |
| 0.1 | `forge-core/src/lib.rs` (re-exports) | 0.0 | backend-forge-core |
| 0.2 | `forge-core/src/event.rs` (13 discriminators + Correlation + all payload structs) | 0.0 | backend-forge-core |
| 0.3 | `forge-core/src/result.rs` (AgentResult + FailureReason 7 variants + ChangeManifest) | 0.0 | backend-forge-core |
| 0.4 | `forge-core/src/context.rs` (AgentContext) | 0.0 | backend-forge-core |
| 0.5 | `forge-core/src/port.rs` (ModelPort trait + ModelError) | 0.0 | backend-forge-core |
| 0.6 | `forge-core/src/agent.rs` (Agent trait + EventRenderer) | 0.2-0.5 | backend-forge-core |
| 0.7 | `forge-core/src/permission.rs` (PermissionGate + strategies + anti-slop) | 0.0 | backend-forge-core |
| 0.8 | `forge-core/src/verifier.rs` (5-gate pipeline + VerificationEvidence) | 0.0 | backend-forge-core |
| 0.9 | `forge-core/src/session.rs` (Session + SessionStore + FileSessionStore) | 0.0 | backend-forge-core |
| 0.10 | `forge-core/src/doctor.rs` (L0-L5 DoctorEngine + DoctorCheck) | 0.0 | backend-forge-core |
| 0.11 | `forge-core/src/guard.rs` (LoopGuard + 5 break paths) | 0.0 | backend-forge-core |
| 0.12 | `forge-core/src/security.rs` (ShellTool fix + path safety) | 0.0 | backend-forge-core |
| 0.13 | `forge-core/src/tracer.rs` (Span + SpanKind — observability) | 0.0 | backend-forge-core |
| 0.14 | `forge-core/src/audit.rs` (AuditEntry + AuditLog — full observability) | 0.0 | backend-forge-core |

## PHASE 1: FORGE_FEEDBACK.md Gaps (CRITICAL)
*Incremental fixes on top of forge-core*

| Step | File | Fixes | Agent |
|------|------|-------|-------|
| 1.0 | `forge-core/src/config.rs` | **H16**: Config struct + load/save + `forge config init/show/set` | backend-forge-core |
| 1.1 | `forge-core/src/router.rs` | **Auto-router**: model fallback chain, retry-backoff with `retry_after_seconds`, 404 ZDR detection, provider health | backend-forge-core |
| 1.2 | `forge-core/src/result.rs` (modify) | **Partial output**: AgentResult.partial_output flag + partial_success_reason | backend-forge-core |
| 1.3 | `forge-core/src/guard.rs` (modify) | **Step budget**: smart step budget based on prompt complexity | backend-forge-core |

## PHASE 2: Model Providers

| Step | Crate | Depends On | Agent |
|------|-------|------------|-------|
| 2.0 | `forge-gemini/` (google-genai-rs v0.3.0 wrapper) | forge-core | backend-forge-core |
| 2.1 | `forge-ollama/` (reqwest REST → ModelPort) | forge-core | backend-forge-core |
| 2.2 | `forge-openai/` (reqwest REST → ModelPort, OpenRouter compat) | forge-core | backend-forge-core |

## PHASE 3: forge-cli

| Step | File | Depends On | Agent |
|------|------|------------|-------|
| 3.0 | `forge-cli/Cargo.toml` | forge-core | (new agent) |
| 3.1 | `forge-cli/src/main.rs` (clap derive, all subcommands) | 3.0 | (new agent) |
| 3.2 | `forge-cli/src/commands/run.rs` | 3.0 | (new agent) |
| 3.3 | `forge-cli/src/commands/doctor.rs` (with H16 config init remediation) | 3.0 | (new agent) |
| 3.4 | `forge-cli/src/commands/session.rs` | 3.0 | (new agent) |
| 3.5 | `forge-cli/src/commands/config.rs` (NEW — fix H16) | 3.0 | (new agent) |
| 3.6 | `forge-cli/src/commands/eval.rs` | 3.0 | (new agent) |
| 3.7 | `forge-cli/src/commands/audit.rs` | 3.0 | (new agent) |
| 3.8 | `forge-cli/src/render/text.rs` (TextRenderer) | 3.0 | (new agent) |
| 3.9 | `forge-cli/src/render/ndjson.rs` (NDJSONRenderer) | 3.0 | (new agent) |

## PHASE 4: forge-tui

| Step | File | Depends On | Agent |
|------|------|------------|-------|
| 4.0 | `forge-tui/Cargo.toml` (crossterm + ratatui) | forge-core | (new agent) |
| 4.1 | `forge-tui/src/main.rs` | 4.0 | (new agent) |
| 4.2 | `forge-tui/src/app.rs` (AppState machine + observability viewer) | 4.0 | (new agent) |
| 4.3 | `forge-tui/src/spine.rs` (glyph renderer) | 4.0 | (new agent) |
| 4.4 | `forge-tui/src/palette.rs` (Slate/Cream/Emerald/Amber/Ruby) | 4.0 | (new agent) |
| 4.5 | `forge-tui/src/inspector.rs` (per-event drill-down) | 4.0 | (new agent) |
| 4.6 | `forge-tui/src/config_screen.rs` (TUI config editor — H16) | 4.0 | (new agent) |

## PHASE 5: CI/CD + Playbook

| Step | File | Purpose | Agent |
|------|------|---------|-------|
| 5.0 | `Cargo.workspace.toml` | Workspace root | devops-ci |
| 5.1 | `.github/workflows/forge-ci.yml` | CI pipeline (5 gates) | devops-ci |
| 5.2 | `docs/PLAYBOOK.md` | Operations playbook | devops-ci |
| 5.3 | `docs/CHANGELOG.md` (update) | Release notes | devops-ci |

---

## FORGE_FEEDBACK.md Failure Pattern Cross-Reference

| Pattern | Severity | Fix | Phase |
|---------|----------|-----|-------|
| Shell-tool output capture broken | CRITICAL | Command::new().arg().output() | 0.12 |
| Byte-length vs char-length | CRITICAL | .chars().take(n) not text[..n] | 0.3 |
| Config persistence (H16) | HIGH | forge config init/show/set + config.rs | 1.0 |
| No auto-model fallback | HIGH | AutoRouter with retry+backoff+fallback | 1.1 |
| Wrapper failure with partial output | MEDIUM | AgentResult.partial_output flag | 1.2 |
| Max_steps too low for complex tasks | MEDIUM | Smart step budget estimation | 1.3 |
| ZDR filtering invisible | MEDIUM | 404 vs model-not-found distinction in router | 1.1 |
| Rate-limit backoff not honored | MEDIUM | retry_after_seconds in router | 1.1 |
| No retry at all | LOW | Configurable max_retries | 1.1 |
| No verification of artifacts on partial failure | LOW | Post-failure artifact check | 1.2 |
