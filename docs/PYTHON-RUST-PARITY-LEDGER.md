# Python → Rust Parity Ledger

**Date:** 2026-07-02
**Workspace:** forge (Rust runtime hot path, Python reference surface)
**Authority:** Playbook 003 (SDK/Harness/Agent Split) Card 4

## Mapping

| Python Module | Status | Notes |
|---|---|---|
| `src/forge_sdk/__init__.py` | **keep as reference** | Public SDK surface; Rust-derived |
| `src/forge_sdk/__main__.py` | **delete after Rust parity** | CLI entry point → forge-cli |
| `src/forge_sdk/agents/` | **ported (Rust)** | LifecycleAgent in forge-core/src/agent.rs |
| `src/forge_sdk/agents/react.py` | **ported (Rust)** | Agent loop in agent.rs |
| `src/forge_sdk/audit/` | **ported (Rust)** | AuditLog + EventSink in forge-core/src/audit.rs |
| `src/forge_sdk/audit/__init__.py` | **ported (Rust)** | Hash-chain audit in audit.rs |
| `src/forge_sdk/cli/` | **ported (Rust)** | forge-cli/src/main.rs + commands/ |
| `src/forge_sdk/config/` | **ported (Rust)** | ForgeConfig in forge-core/src/config.rs |
| `src/forge_sdk/eval/` | **keep as reference** | Reference for forge-evals design |
| `src/forge_sdk/eval/harness.py` | **keep as reference** | Eval harness patterns |
| `src/forge_sdk/harness/` | **ported (Rust)** | forge-harness crate |
| `src/forge_sdk/models/` | **ported (Rust)** | forge-providers crate |
| `src/forge_sdk/models/providers/` | **ported (Rust)** | DeepSeekProvider etc. |
| `src/forge_sdk/policies/` | **keep as reference** | Permission policy patterns |
| `src/forge_sdk/security.py` | **ported (Rust)** | forge-core-security crate |
| `src/forge_sdk/text_tokens.py` | **keep as reference** | Token counting reference |
| `src/forge_sdk/tools/` | **ported (Rust)** | forge-harness/src/aci/tools.rs |
| `src/forge_sdk/tools/registry.py` | **ported (Rust)** | default_tools() in tools.rs |
| `src/forge_sdk/tracing/` | **ported (Rust)** | forge-core/src/tracer.rs |
| `src/forge_sdk/verifiers/` | **ported (Rust)** | forge-core/src/verifier.rs |

## Summary

| Status | Count |
|---|---|
| **Ported (Rust)** | 14 modules |
| **Keep as reference** | 4 modules |
| **Delete after Rust parity** | 1 module |
| **Dev-only** | 0 modules |
