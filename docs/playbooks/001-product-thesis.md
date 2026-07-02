---
id: FORGE-PLAYBOOK-001
title: Product Thesis
status: active
depends_on: [issue-74, pr-75]
---

# Product Thesis

Forge is not trying to be only an SDK and not trying to be only an IDE agent. The SDK is the clean contract layer. The harness is the product moat. The agent and UI are replaceable consumers of that harness.

The end-state claim is proof-carrying AI output:

> This artifact is not correct because an AI said it. It is correct because the generated claim, code, diff, and conclusion carry source evidence, tool traces, verification receipts, provenance, and replayable evaluation records. A critic can refute it only by defeating the evidence chain.

## Research Anchors

- Geely's 2026 G-ASD and Full-Domain AI story frames autonomy as vehicle-wide integration of compute, data, models, sensing, safety, and continuous evolution, not a single model feature. Forge should copy the product lesson: autonomy is a supervised system architecture with evidence, redundancy, and field data. Source: https://www.geely.com/en/news/2026/geely-ces-2026-full-domain-ai
- Geely's G-Pilot rollout describes real-world driving data, scenario generation, NOA testing, tiered deployment, and redundant L3 architecture. The lesson for Forge is that "agent autonomy" must be tiered by permission, verification, and blast radius. Source: https://autonews.gasgoo.com/articles/icv/70036108
- SWE-agent's NeurIPS 2024 paper shows that Agent-Computer Interface design changes software-engineering performance; simple actions, compact feedback, guardrails, search, file viewing, editing, and execution are part of agent intelligence. Source: https://proceedings.neurips.cc/paper_files/paper/2024/file/5a7c947568c1b1328ccc5230172e1e7c-Paper-Conference.pdf
- Activation steering and representation engineering research supports steerable behavior through latent directions, but also documents side effects and capability degradation risks. Forge should support activation steering only where it owns compatible inference, and otherwise implement surrogate steering through profiles, retrieved laws, tool constraints, verifiers, and feedback loops. Source: https://arxiv.org/html/2501.09929v3
- NIST AI RMF frames trustworthy AI as lifecycle risk management with governance, mapping, measurement, and management. Forge maps this into specs, traces, verification, audit, and eval gates. Source: https://www.nist.gov/itl/ai-risk-management-framework
- C2PA treats provenance as a manifest, assertions, claims, validation, signatures, and content binding. Forge needs analogous provenance for generated code and claims: claim manifests, evidence assertions, proof obligations, validation states, and hashable receipts. Source: https://spec.c2pa.org/specifications/specifications/2.4/specs/C2PA_Specification.html

## Product Decisions

1. Forge SDK remains small and agent-agnostic.
2. Forge Harness becomes the deterministic plus ML plus symbolic runtime.
3. Forge Brain is semantic-memory-brain plus OKF index bridge, not a new memory store.
4. Forge Agent is one agent assembled on top of the harness, not the whole product.
5. Forge UI must make steering, telemetry, claims, tools, tabs, slash commands, and proof state clickable.
6. SWE-bench and Terminal-Bench are end-state evals, not the first proof of product truth.

## "AI Generated Content Is Not Wrong" Claim Ladder

| Level | Artifact | User claim strength |
|---|---|---|
| L0 | Raw model text | Weak. Opinion only. |
| L1 | Cites repo files that exist | Grounded. Still may be wrong. |
| L2 | Uses audited tools and records observations | Inspectable. |
| L3 | Produces typed claims, invariants, and proof obligations | Disputable in structured form. |
| L4 | Runs verification and stores receipts | Evidence-backed. |
| L5 | Produces signed/hashable provenance and replay data | Strong enough to challenge unsupported objections. |
| L6 | Repeats across field tests and benchmarks | Product-grade. |

Forge must never let UI copy imply L5/L6 when the run is only L0-L3.

## Stop Conditions

- If a proposed feature cannot produce an event, it does not belong in the runtime.
- If a proposed memory cannot cite source evidence and trust class, it does not enter the brain.
- If a proposed eval requires special behavior not used by normal `forge run`, it is benchmark gaming.
- If a provider cannot tool-call, Forge must route to a no-tool mode with honest limits or fail closed.

