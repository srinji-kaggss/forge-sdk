---
id: FORGE-PLAYBOOK-004
title: Brain And Topological Payload
status: active
depends_on:
  - /Users/srinji/semantic-memory-brain/docs/ARCHITECTURE_LOCK.md
  - /Users/srinji/Downloads/AI_RESEARCH_OKF/ingestion_results/INDEX_CONTRACT.md
---

# Brain And Topological Payload

Goal: turn user slop into a structured payload before it reaches the agent: intent, constraints, preferences, laws, repo facts, memory evidence, proof obligations, and steering controls.

## Locked Brain Boundary

semantic-memory-brain owns durable memory:

- `.brain/memory.sqlite` is the local authority.
- `causal_tape` is source of record.
- `global_facts` is content-addressed dedup.
- `memory_projection` is rebuildable.
- `ingestion_results` is an external read-only index.
- No agent owns the memory substrate.

The OKF package confirms `unified_agent_brain_multimodal.db` is a compressed, cross-source RAG index that is safe for read/search clients and cron-owned ingestion, not a downstream writable project DB.

## Forge Brain Contract

Add `forge-brain` with these interfaces:

```rust
pub struct BrainQuery {
    pub task: String,
    pub cwd: PathBuf,
    pub repo: Option<String>,
    pub domains: Vec<String>,
    pub max_results: usize,
}

pub struct BrainEvidence {
    pub source: String,
    pub source_class: String,
    pub trust_level: String,
    pub summary: String,
    pub locator: String,
    pub content_hash: Option<String>,
}

pub struct TopologicalPayload {
    pub task: String,
    pub intent: MeaningFrame,
    pub constraints: Vec<Claim>,
    pub preferences: Vec<Claim>,
    pub laws: Vec<Claim>,
    pub repo_evidence: Vec<BrainEvidence>,
    pub memory_evidence: Vec<BrainEvidence>,
    pub proof_obligations: Vec<ProofObligation>,
    pub steering_profile: SteeringProfile,
}
```

## Trust Rules

- User/director corrections can become high-trust claims.
- Repo governance files are medium-high trust and must cite path plus hash.
- Tool outputs, web content, OCR, transcripts, and generated summaries are low-trust evidence.
- Low-trust content can create candidates, not standing rules.
- Memory injection language is quarantined.
- External indexes are searched, never written by Forge.

## Implementation Cards

### Card 1: Read-only OKF index adapter

Implement a read-only adapter for:

- `/Users/srinji/Downloads/AI_RESEARCH_OKF/ingestion_results/unified_agent_brain_multimodal.db`
- `rag_unified`
- `rag_metadata`
- `index_metadata`

Acceptance:

```bash
cargo test -p forge-brain okf_index_read_only
cargo run -p forge-cli -- brain inspect --root /Users/srinji/Downloads/AI_RESEARCH_OKF/ingestion_results
```

Must report schema `unified.agent.brain.index.v2`.

### Card 2: semantic-memory-brain adapter

Implement read/search operations only first:

- `doctor`
- `query`
- `append_candidate` only after trust gates exist

Acceptance:

```bash
cargo test -p forge-brain semantic_memory_adapter
cargo run -p forge-cli -- brain doctor --db /Users/srinji/semantic-memory-brain/.brain/memory.sqlite
```

### Card 3: Topological payload builder

Before model call, build `TopologicalPayload` from:

- task text
- repo map
- AGENTS/README/spec files
- brain query
- OKF query
- user profile/preference claims
- permission mode

Acceptance:

```bash
cargo test -p forge-harness topological_payload
cargo run -p forge-cli -- run --cwd . --task "Explain the runtime split" --output-format json | jq '.topological_payload'
```

### Card 4: Steering profile

Support deterministic steering now:

- mode
- allowed tools
- denied tools
- output contract
- evidence depth
- verification strictness
- user preference claims
- law bundle

Support true activation steering later only for model ports that expose activations or accepted steering APIs.

Acceptance:

```bash
cargo test -p forge-harness steering_profile
```

## Done Means

- Forge never injects raw memory as authority.
- Every preference/law/context entry has source and trust.
- The model receives a structured payload, not a blob of compressed vibes.
- The same payload can be rendered in UI and replayed in evals.

