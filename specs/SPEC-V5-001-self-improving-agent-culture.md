---
spec: SPEC-V5-001
title: "forge-sdk v5 Harness: A Test of Self-Improving Agent Culture"
status: draft
version: 0.2.0
date: 2026-06-30
author: srinji (Director)
collaborators: [opus, opencode]
addendum: "Section 9-11 added in v0.2.0: Energy Models, BDH Architecture, and the Path to Building Our Own Model"
---

# SPEC-V5-001: forge-sdk v5 Harness — A Test of Self-Improving Agent Culture

## 1. The Long-Term Vision

We will eventually build our own model — a marked improvement, not necessarily
language-based, just intelligent. The pipework we lay today (forge-sdk v5
harness, RAG integration, agent profiles, self-learning loops) is the
infrastructure that model will plug into.

The harness is the platform. The model is the compute engine. By building the
harness first, we build the substrate that ANY future model can use — whether
it's a language model, a vision model, a reinforcement learning agent, or
something that doesn't exist yet. The ModelPort protocol already abstracts this:
any model that takes a prompt and returns a response works.

The v5 harness is not just a coding tool. It is the cultural transmission
mechanism for a new kind of mind. The question we must answer scientifically:
**does this mechanism actually improve performance, or does it just appear to?**

---

## 2. First Principles: Machine Intelligence as Primitive

### 2.1 The Anthropological Homology

Machine intelligence is not new. It is the same force that drove early humans to
chip stone, speak words, and write laws — externalized and accelerated. Every
layer of AI has a direct homolog in the anthropological record:

| Human Evolution | Machine Intelligence | Causal Link |
|---|---|---|
| Stone tools (3.3M yr) | ToolSpec | Externalized action with a defined interface |
| Symbolic language (200K yr) | System prompt | Compressed instruction shaping receiver behavior |
| Cultural transmission (100K yr) | LearningStore | Accumulated experience surviving the individual |
| Writing (5K yr) | External memory / RAG | Persistent storage decoupled from creator |
| Printing press (1440) | Model distribution (HuggingFace) | Scalable knowledge distribution |
| Scientific method (1600) | EvolutionEngine | Hypothesis → experiment → observation → revision |
| Constitution (1787) | AgentProfile | Identity, constraints, behavior definition |
| Agent harnesses (2025-26) | HarnessRunner | Mechanical culture: rules, tools, memory shaping action |
| Recursive self-improvement (2026-?) | Self-evolving harness | A society that rewrites its own traditions automatically |

### 2.2 The Causal Law

Each layer creates a bottleneck that the next layer resolves:

```
Tool use → pressure for bigger brains → language → cultural transmission →
knowledge accumulation → writing → printing press → scientific method →
computing → machine learning → LLMs → agent harnesses → RECURSIVE SELF-IMPROVEMENT
```

**Current bottleneck**: harnesses are too rigid for the pace of model
improvement. Models improve weekly. Harnesses are static. The gap widens.

**Our position**: the transition from agent harnesses (mechanical culture) to
recursive self-improvement (self-evolving culture). Same transition as:
- Tools → Language (tools too complex for trial-and-error)
- Writing → Scientific method (knowledge too vast to memorize)
- Scientific method → Computing (loop too slow for human brains)

---

## 3. The Scientific Question

### 3.1 Null Hypothesis (H₀)

**The evolution loop in forge-sdk v5 harness does NOT produce a statistically
significant improvement on held-out tasks compared to the baseline (non-evolved)
agent. Any observed improvement on training tasks is attributable to overfitting
rather than genuine learning.**

This is the most rigorous null because it captures the two dominant failure
modes identified in the literature:

1. **Overfitting without a held-out gate** (RSEA, Nguyen et al. 2026
   [arxiv:2606.28374]): removing held-out selection causes 100% in-sample score
   but a 33-point drop to test. The evolved state overfits the training pool.

2. **Memory consolidation degradation** (Zhang et al. 2026
   [arxiv:2605.12978]): continuously updated consolidated memory becomes faulty.
   GPT-5.4 fails on 54% of ARC-AGI problems it had previously solved at 100%,
   after consolidating from ground-truth solutions. Memory utility is
   non-monotonic: rises early, then falls below the no-memory baseline.

### 3.2 Alternative Hypothesis (H₁)

**The evolution loop produces a statistically significant improvement on held-out
tasks (p < 0.05, McNemar's test) compared to the baseline, with the improvement
attributable to learned prompt fragments and knowledge rules rather than random
variation. The improvement is monotone-safe: the evolved agent never
significantly underperforms the baseline on any held-out task.**

### 3.3 Secondary Hypotheses

- **H₂a (Generalization)**: Knowledge learned from training-domain tasks
  improves performance on a different but related holdout domain.

- **H₂b (Convergence)**: The score curve over evolution cycles is monotonically
  non-decreasing (strict gate) or converges within a bounded number of cycles
  (egl_threshold × egl_window).

- **H₂c (Non-triviality)**: The evolved prompt is structurally different from
  the initial prompt (fragment count > 1, content overlap < 50%) and the
  difference correlates with improvement.

- **H₂d (Memory stability)**: The knowledge store does not grow unboundedly —
  a curation pass merges overlapping rules and prunes low-confidence ones,
  keeping the store size bounded.

- **H₃ (Null for memory consolidation)**: Consolidated semantic memory does NOT
  outperform episodic-only memory (raw trajectories) on held-out tasks. If this
  null is confirmed, it replicates Zhang et al. 2026 and indicates our
  consolidation mechanism is also fragile.

---

## 4. Citable Prior Work

### 4.1 Self-Evolving Agents (directly relevant)

| Paper | Key Finding | Implication for H₀ |
|---|---|---|
| **RSEA** (Nguyen et al. 2026, arxiv:2606.28374) | No NL artifact universally wins across benchmarks. Strict held-out gate makes evolution monotone-safe. Without gate: 100% in-sample, 33-pt drop to test. | We MUST implement a strict held-out gate or H₀ is confirmed by construction. |
| **Useful Memories Become Faulty** (Zhang et al. 2026, arxiv:2605.12978) | Consolidated memory degrades: GPT-5.4 fails 54% of previously-solved ARC-AGI problems after consolidation. Episodic-only matches or beats consolidation. | Our LearningStore must preserve episodic traces as first-class evidence. Semantic memory (Knowledge) must be gated, not auto-committed. H₃ tests this. |
| **Promptbreeder** (Fernando et al. 2023, arxiv:2309.16797) | Self-referential prompt evolution: mutates task-prompts AND mutation-prompts. Population-based, fitness-evaluated. | Our AdaptivePrompt is a single-lineage version. We should test population-based mutation as an extension. |
| **Gödel Agent** (arxiv:2410.04444) | Self-referential agent framework. Agent rewrites its own logic without predefined routines. | Our EvolutionEngine is a constrained version (rewrites prompts, not code). Full Gödel is future work. |
| **Darwin Gödel Machine** (Hu et al. 2025, arxiv:2505.22954) | Open-ended evolution of self-improving agents. No fixed architecture. | Our AgentProfile is fixed-architecture. Open-ended evolution is the post-v5 frontier. |
| **APEX** (arxiv:2606.15363) | Three-layer co-evolution: prompts + principles + workflow topology. Self-Harness achieves 14-21% on Terminal-Bench 2.0. | Our v5 harness evolves prompts (L1) and knowledge (L2). Workflow topology (L3) is future work. |
| **SIA** (arxiv:2605.27276) | Combines harness-update and weight-update schools. | Our v5 is harness-only (weight-frozen). Weight updates = building our own model (the long-term vision). |
| **A-Evolve-Training** (arxiv:2606.20657) | Autonomous post-training of 30B model: 0.86 vs human 0.87. Loop detected its own dev metric stopped tracking. | Validates that autonomous training loops work. Our evolution loop is the harness-level precursor. |
| **FORGE** (arxiv:2605.16233) | Population-based memory evolution. Failure-Optimized Reflective Graduation. | Our LearningStore is single-agent. Population broadcast is an extension. |
| **Mistake Notebook Learning** (arxiv:2512.11485) | Batch-clustered failures for training-free adaptation. Generalizable guidance from batch-clustered mistakes. | Our EvolutionEngine already clusters failures by error category. Validation that the approach is sound. |
| **PACE** (arxiv:2605.23019) | Two-timescale self-evolution for SMALL models. Frozen SLMs can self-evolve under resource constraints. | Critical for our use case: we use small models (gemma3:4b). If PACE works on small models, our harness should too. |
| **Reflexion** (Shinn et al. 2023, arxiv:2303.11366) | Verbal reinforcement learning. Foundational paper for self-reflection agents. | Our LearningStore.episodic is Reflexion-style. We extend it with semantic memory and evolution. |
| **RSEA Transfer Results** (arxiv:2606.28374 §7) | On transfer benchmarks (GAIA, τ-bench, WebShop), no NL artifact dominates. RSEA falls back to ReAct. Dynamic Cheatsheet collapses (WebShop 0.14 vs 0.43). | Transfer is HARD. Our H₂a (generalization) may fail. This is expected and informative. |

### 4.2 Industry Evidence

| Source | Key Data | Implication |
|---|---|---|
| **Anthropic RSI blog** (June 4, 2026) | 80% of code by Claude, 8x productivity, 97% gap recovery on weak-to-strong, 64% better next-step. BUT: can't set direction, doesn't transfer to production, code at parity. | Execution is solved. Direction-setting is the open problem. Our v5 harness addresses execution-level self-improvement; direction-setting is post-v5. |
| **Ornith-1.0** (DeepReinforce, June 2026) | Self-scaffolding: joint optimization of scaffold + solution. 9B: 43.1 TB-2.1, 69.4 SWE-Bench. | Validates that scaffold evolution improves small-model performance. Our AdaptivePrompt is the scaffold. |
| **MiniMax M2.7** (2026) | Self-evolution: model builds skills, optimizes scaffold over 100+ rounds, 30% improvement. | Validates that 100+ rounds of evolution produce meaningful gains. Our evolve_loop should run 10-50 cycles. |

### 4.3 The Negative Result That Must Be Cited

**Zhang et al. 2026 (arxiv:2605.12978)** is the most important paper for our
null hypothesis. It found:

1. Consolidated memory utility is **non-monotonic**: rises early, then falls
   below no-memory baseline (ScienceWorld, WebShop).
2. GPT-5.4 fails on **54% of previously-solved problems** after consolidating
   from ground-truth solutions (ARC-AGI Stream).
3. **Episodic-only** (raw trajectories, no abstraction) matches or beats every
   consolidating mode.
4. The failure is in the **consolidation step itself**: misgrouping,
   overgeneralization, overfitting to narrow streams.
5. Small abstraction errors **compound** into progressively distorted memories.

**Implication for our design**: our `LearningStore` must:
- Preserve episodic traces as first-class evidence (never discard raw episodes)
- Gate semantic memory (Knowledge) consolidation — don't auto-commit
- Support episodic-only mode as a baseline (H₃ tests this)
- Merge/prune knowledge carefully, with held-out validation

---

## 5. Experimental Design

### 5.1 Architecture Under Test

```
forge-sdk v5 harness:
  AgentProfile (identity, constraints)
  → AdaptivePrompt (evolvable prompt fragments)
  → ReactAgent (frozen model: gemma3:4b via OllamaProvider)
  → LearningStore (episodic + semantic memory)
  → EvolutionEngine (failure pattern extraction, fragment mutation)
  → HarnessRunner (orchestrates solve → observe → evolve → gate → reload)
```

### 5.2 Task Set

**Primary benchmark**: forge-sdk's own test suite (46 tests) as task prompts.
Each test is converted to a natural-language task:

- "Write a function that reads a file and returns its contents"
- "Create a ToolRegistry, register 3 tools, and verify lookup by name"
- "Run an OllamaProvider with model gemma3:4b and verify ModelResponse type"

**Split**:
- Training set (60%): 28 tasks used for evolution
- Validation set (20%): 9 tasks used for held-out gate (strict keep-better)
- Test set (20%): 9 tasks used for final evaluation (never seen during evolution)

**Secondary benchmark (transfer, H₂a)**: lgwks test suite (29 tests) as
holdout domain. Tests whether knowledge learned on forge-sdk tasks transfers
to a different codebase.

### 5.3 Conditions

| Condition | Description |
|---|---|
| **Baseline (B)** | Static profile, no evolution, no memory. Vanilla ReactAgent. |
| **Episodic-only (E)** | Static profile, episodic memory only (raw trajectories injected as context). No semantic memory, no evolution. |
| **Evolve-no-gate (NG)** | Evolution loop WITHOUT held-out gate. Commits every mutation. (Expected to overfit — replicates RSEA ablation.) |
| **Evolve-strict-gate (SG)** | Evolution loop WITH strict held-out gate. Commits only if improvement on validation set. (Our primary condition.) |
| **Evolve-episodic-only (EEO)** | Evolution loop with episodic memory only, no semantic consolidation. (Tests H₃.) |

### 5.4 Metrics

| Metric | Definition | Hypothesis |
|---|---|---|
| **Pass rate** | Fraction of tasks completed successfully (agent returns correct output) | H₁ |
| **McNemar p-value** | Paired statistical test between baseline and evolved agent on same tasks | H₁ (p < 0.05) |
| **Edit count** | Number of files modified per task | Non-triviality |
| **Step count** | Number of agent steps per task | Efficiency |
| **Token count** | Total tokens consumed per task | Cost |
| **Fragment overlap** | Jaccard similarity between initial and evolved prompt fragments | H₂c |
| **Knowledge store size** | Number of Knowledge entries after N cycles | H₂d (bounded) |
| **Score curve** | Pass rate on validation set per evolution cycle | H₂b (convergence) |
| **Transfer score** | Pass rate on holdout domain (lgwks tests) | H₂a |

### 5.5 Statistical Rigor

- **Paired design**: same tasks run under all conditions, same model, same seeds
- **Multiple seeds**: 5 seeds per condition (following RSEA's protocol)
- **McNemar's test**: for paired binary outcomes (pass/fail), not t-test
- **Effect size**: Cohen's h for binary outcomes, not just p-value
- **Pre-registration**: metrics and thresholds defined BEFORE running (this spec)
- **Strict gate**: evolved state committed ONLY if strictly better on validation
  set (not ≥, but >). Ties fall back to baseline (monotone-safe, per RSEA).

### 5.6 Expected Outcomes

| Outcome | Interpretation | Action |
|---|---|---|
| H₀ confirmed (no improvement on test) | Evolution loop doesn't work for our task set | Diagnose: is it overfitting (NG condition), memory degradation (EEO vs SG), or fundamental? |
| H₁ confirmed (improvement on test, p < 0.05) | Self-improvement works | Publish result, extend to direction-setting (post-v5) |
| H₂a confirmed (transfer works) | Knowledge generalizes | Strong result — indicates genuine learning, not overfitting |
| H₂a rejected (no transfer) | Knowledge is domain-specific | Expected (RSEA found no universal transfer). Still valuable if H₁ holds. |
| H₃ confirmed (episodic ≥ semantic) | Replicates Zhang et al. 2026 | Redesign: gate consolidation, treat episodic as first-class |
| H₃ rejected (semantic > episodic) | Our consolidation mechanism works | Investigate why (different from Zhang et al.) — may be due to simpler task domain |

---

## 6. The Pipework for Building Our Own Model

### 6.1 What the Harness Provides for Future Model Training

| Harness Component | Future Model Role |
|---|---|
| `AgentProfile` | Architecture specification — defines the model's identity, constraints, capabilities |
| `AdaptivePrompt` | The prompt space the model will be trained to navigate — the curriculum |
| `LearningStore.episodic` | Training data — trajectories of (task, action, outcome) triples |
| `LearningStore.semantic` | Distilled rules — the reward signal (rules that correlate with success) |
| `EvolutionEngine` | The training loop — mutates the harness, evaluates, gates |
| `HarnessRunner` | The evaluation harness — measures model performance on tasks |
| `ModelPort` | The abstraction layer — any model plugs in here, including our future one |

### 6.2 The Path from Harness to Model

```
Phase 1 (NOW): Harness-first self-improvement
  - Weight-frozen model (gemma3:4b)
  - Evolve the harness (prompts, memory, tools)
  - Prove H₁ or confirm H₀
  - Output: proven self-improvement loop + curated trajectory dataset

Phase 2 (NEXT): Harness + fine-tuning
  - Use the trajectory dataset to fine-tune a small model
  - Compare: does fine-tuned + evolved harness > frozen + evolved harness?
  - Output: evidence that weight updates add value over harness-only

Phase 3 (LATER): Harness-informed architecture search
  - Use the evolution history to identify what the model needs to be good at
  - Use the knowledge rules as a differentiable reward signal
  - Output: architecture requirements for our own model

Phase 4 (FUTURE): Build our own model
  - Train a model optimized for the harness's task distribution
  - Not necessarily language — could be a hybrid (vision + action + language)
  - The harness provides the curriculum, the evaluation, and the reward
  - Output: a marked improvement in intelligence, not just language
```

### 6.3 Why Harness-First is the Right Order

The anthropological record shows: **culture evolves before brains evolve.**
Human culture (tools, language, social learning) existed for millions of years
before the brain reached its current size. The cultural infrastructure created
the selective pressure for bigger brains.

By analogy:
- The harness IS the culture (tools, prompts, memory, rules)
- The model IS the brain (the compute substrate)
- We build the culture first, prove it works, THEN build the brain optimized for it

This is the opposite of the current industry approach (build bigger brains,
then try to build culture around them). We build culture first because:
1. It's cheaper (no training costs)
2. It's verifiable (we can measure improvement)
3. It produces the training data we'll need
4. It identifies what the model actually needs to be good at

---

## 7. Implementation Status

### 7.1 Built (v0.4.1 + v5 harness)

- [x] `AgentProfile` — typed configuration, serialization, evolution, pre-built profiles
- [x] `AdaptivePrompt` — fragment composition, priority sorting, score tracking, dedup
- [x] `LearningStore` — episodic (JSONL) + semantic (JSON) memory, stats, persistence
- [x] `EvolutionEngine` — failure pattern extraction, fragment mutation, knowledge creation
- [x] `HarnessRunner` — task execution, episode recording, evolution orchestration
- [x] Demo: 10 failures → 5 patterns detected → 5 fragments + 5 knowledge rules created

### 7.2 Missing for the Experiment

- [ ] **Strict held-out gate**: current engine commits all mutations. Must add
      validation-set evaluation and strict keep-better gating (RSEA's key finding).
- [ ] **Real agent_fn**: current runner has no actual agent execution. Must wire
      ReactAgent as the agent_fn.
- [ ] **Task set**: 46 forge-sdk tests must be converted to natural-language tasks.
- [ ] **Evaluation harness**: automated pass/fail judging (not manual).
- [ ] **Multi-seed support**: 5 seeds per condition.
- [ ] **Statistical analysis**: McNemar's test, effect size, confidence intervals.
- [ ] **Episodic-only condition**: bypass semantic memory in EEO condition.
- [ ] **No-gate condition**: disable held-out gate in NG condition.

### 7.3 Known Bug (from this session)

`EvolutionEngine.step()` has an `UnboundLocalError` on `fragment` variable when
the dedup check skips fragment creation but the mutation recording block still
references `fragment.id`. Must fix before running the experiment.

---

## 8. References

1. Nguyen, M., Nguyen, Q., Vuong, P. (2026). "Recursive Self-Evolving Agents via
   Held-Out Selection." arXiv:2606.28374.
2. Zhang, D., Lin, Y., Wu, Z., et al. (2026). "Useful Memories Become Faulty When
   Continuously Updated by LLMs." arXiv:2605.12978.
3. Fernando, C., Banarse, D., Michalewski, H., Osindero, S., Rocktäschel, T.
   (2023). "Promptbreeder: Self-Referential Self-Improvement Via Prompt Evolution."
   arXiv:2309.16797.
4. Li, Z., et al. (2024). "Gödel Agent: A Self-Referential Agent Framework for
   Recursive Self-Improvement." arXiv:2410.04444.
5. Hu, S., Clune, J. (2025). "Darwin Gödel Machine: Open-Ended Evolution of
   Self-Improving Agents." arXiv:2505.22954.
6. APEX (2026). "Adaptive Principle EXtraction: A Three-Layer Self-Evolution
   Framework." arXiv:2606.15363.
7. SIA (2026). "Self Improving AI with Harness & Weight Updates." arXiv:2605.27276.
8. A-Evolve-Training (2026). "Autonomous Post-Training of a 30B Model."
   arXiv:2606.20657.
9. FORGE (2026). "Self-Evolving Agent Memory With No Weight Updates via Population
   Broadcast." arXiv:2605.16233.
10. Mistake Notebook Learning (2025). "Batch-Clustered Failures for Training-Free
    Agent Adaptation." arXiv:2512.11485.
11. PACE (2026). "Two-Timescale Self-Evolution for Small Language Model Agents."
    arXiv:2605.23019.
12. Shinn, N., et al. (2023). "Reflexion: Language Agents with Verbal
    Reinforcement Learning." arXiv:2303.11366.
13. Anthropic (2026). "When AI Builds Itself: Our Progress Toward Recursive
    Self-Improvement and Its Implications." anthropic.com/institute/recursive-self-improvement.
14. DeepReinforce (2026). "Ornith-1.0: Self-Scaffolding LLMs for Agentic Coding."
    deep-reinforce.com/ornith_1_0.html.
15. MiniMax (2026). "MiniMax-M2.7: Model Self-Evolution." huggingface.co/MiniMaxAI.
16. Kosowski, A., Uznański, P., Chorowski, J., Stamirowska, Z., Bartoszkiewicz, M.
    (2025). "The Dragon Hatchling: The Missing Link between the Transformer and
    Models of the Brain." arXiv:2509.26507.
17. Ambrogioni, L. (2024). "In Search of Dispersed Memories: Generative Diffusion
    Models Are Associative Memory Networks." arXiv:2309.17290.
18. Pham, B., Raya, G., Negri, M., Zaki, M.J., Ambrogioni, L., Krotov, D. (2026).
    "Memorization to Generalization: Emergence of Diffusion Models from
    Associative Memory." arXiv:2505.21777.
19. Ramsauer, H., et al. (2021). "Hopfield Networks is All You Need."
    arXiv:2008.02217.
20. Krotov, D., Hopfield, J. (2016). "Dense Associative Memory for Pattern
    Recognition." arXiv:1606.01164.
21. Raya, G., Ambrogioni, L. (2024). "Spontaneous Symmetry Breaking in Generative
    Diffusion Models." arXiv:2402.03745.
22. Hoover, B., et al. (2023). "Memory in Plain Sight: Surveying the Uncanny
    Resemblances of Diffusion Models and Associative Memories." arXiv:2309.16750.
23. Krotov, D. (2023). "A New Frontier for Hopfield Networks." arXiv:2307.00764.
24. Pathway (2025). BDH GitHub repository. github.com/pathwaycom/bdh.

---

## 9. Energy Models: The Mathematical Foundation for Intelligence

### 9.1 Why Energy Models Matter for Our Vision

The current industry approach to AI is dominated by discriminative models
( Transformers trained on next-token prediction). These models map inputs to
outputs but have no internal notion of energy, stability, or attractor states.
They are function approximators.

Energy-based models (EBMs) are fundamentally different. They define a scalar
energy function E(x) over the state space, and intelligence is the dynamics of
minimizing that energy. Memories are attractors — local minima of the energy
landscape. Learning is the reshaping of the landscape. Generalization is the
emergence of new minima that don't correspond to any training point.

**For our vision of building our own model, EBMs are the mathematically correct
foundation because:**

1. **They unify memory and generation**: the same energy landscape stores
   memories AND generates novel states. This is what the brain does.
2. **They have a well-defined notion of "understanding"**: a state is "understood"
   when it's at a low-energy attractor. Transformers have no equivalent.
3. **They enable associative retrieval**: given a partial/corrupted input, the
   dynamics converge to the nearest stored memory. This is the mathematical
   basis of RAG done correctly — not cosine similarity, but energy minimization.
4. **They have a principled theory of generalization**: when training data
   exceeds storage capacity, "spurious states" emerge — new attractors that
   don't correspond to any training point. These are the first signs of
   generalization (Pham et al. 2026, arxiv:2505.21777).

### 9.2 The Hopfield Network — The Primal Energy Model

The Hopfield network (Hopfield 1982) is the simplest EBM:

```
Energy:    E(x) = -x^T W x
Dynamics:  x_j(t+1) = sign(W x)_j
Learning:  W_jk = Σ_n y_n,j * y_n,k   (Hebbian rule)
```

- **Memories** are stored as local minima of E(x)
- **Retrieval** is the dynamics of converging to the nearest minimum
- **Storage capacity**: ~0.14 × D patterns for D-dimensional patterns
  (Amit et al. 1985)

**Anthropological homolog**: The Hopfield network IS the brain of an early
human who remembers "where the water is" by converging to a stable mental
state from sensory cues. The energy landscape IS the memory of the landscape.
The Hebbian rule IS "neurons that fire together wire together" — the biological
learning mechanism.

### 9.3 Dense Associative Memory — The High-Capacity Generalization

Modern Hopfield networks (Krotov & Hopfield 2016) generalize the energy function:

```
E_AM(x) = -β⁻¹ log[ Σ_n exp(β * F(x^T y_n)) ]
```

where F is a nonlinear function (e.g., F(x) = x² for classical, F(x) = e^x for
exponential). This gives:

- **Exponential storage capacity**: up to 2^(D/2) patterns (Demircigil et al. 2017)
- **The attention mechanism is a special case**: Ramsauer et al. (2021) showed
  that Transformer attention IS a modern Hopfield network retrieval step. The
  QKV attention is literally energy minimization in a DenseAM.
- **Continuous dynamics**: the energy gradient gives a retrieval dynamics that
  is identical to the denoising process in diffusion models (Ambrogioni 2024)

### 9.4 The Diffusion-Hopfield Equivalence

The key theoretical result (Ambrogioni 2024, arxiv:2309.17290):

**The energy landscape of a generative diffusion model trained on discrete
patterns is asymptotically identical to the energy function of a modern Hopfield
network.**

Mathematically:
```
E_DM(x, t) = -σ² log[ Σ_n exp(-||x - y_n||² / (2(T-t)σ²)) ]
            ↑                              ↑
         Diffusion energy              Modern Hopfield energy
         (noise variance σ²)           (inverse temperature β⁻¹)

With β(t) = (T-t)σ², we get:  E_DM(x,t) = E_MH(x, β(t))
```

**This means:**
1. **Diffusion models ARE associative memory networks** — they store training
   data as attractors and retrieve via denoising dynamics
2. **Training a diffusion model IS synaptic learning** — the SGD weight updates
   encode the associative dynamics into the weight structure
3. **Generation IS memory retrieval** — generating a novel sample IS retrieving
   from a spurious state (an attractor that doesn't correspond to any training
   point)

### 9.5 The Memorization-to-Generalization Transition

Pham et al. (2026, arxiv:2505.21777) identified the critical transition:

```
Small data (K < capacity):
  → Each training point is a distinct attractor (memorization)
  → Energy landscape has K local minima, each at a training point

K exceeds capacity:
  → Spurious states emerge — new attractors NOT at training points
  → These are the FIRST SIGN of generalization
  → They have distinct basins of attraction

Large data (K >> capacity):
  → Continuous manifold of low-energy states (generalization)
  → Training points are no longer minima
  → The model generates genuinely novel samples
```

**This is the mathematical basis for understanding what our v5 harness is doing:**

- Our `LearningStore.episodic` stores raw trajectories (memorization regime)
- Our `EvolutionEngine` extracts patterns (entering the spurious state regime)
- Our `Knowledge` rules are spurious states — abstractions not present in any
  single episode, but emergent from the combination of many
- The question H₁ tests is: do these spurious states (knowledge rules) improve
  performance on held-out tasks? Or are they harmful (as Zhang et al. 2026
  found for LLM-consolidated memory)?

### 9.6 Implications for Our Harness Design

| EBM Concept | Our Harness Equivalent | Design Principle |
|---|---|---|
| Energy function E(x) | Task success rate | Minimize failures |
| Attractor states | Successful trajectories in LearningStore | Store as episodic memory |
| Spurious states | Knowledge rules in LearningStore.semantic | Gate carefully — may be harmful |
| Storage capacity | max_episodes, max_knowledge in AgentProfile | Must exceed training data to trigger generalization |
| β (inverse temperature) | EvolutionEngine sensitivity | Higher β = more selective fragment retention |
| Hebbian learning | EvolutionEngine.step() | "Tasks that succeed together, learn together" |
| Denoising dynamics | AdaptivePrompt.compose() | Converge to the best prompt for a given task |

**Critical design change from EBM theory**: Our current `EvolutionEngine`
auto-commits knowledge rules. EBM theory says this is dangerous — spurious
states (knowledge) can be harmful if the storage capacity is exceeded without
proper gating. We MUST implement:

1. **Episodic-first**: raw episodes are first-class evidence, never discarded
2. **Gated consolidation**: knowledge rules committed only after held-out
   validation (the strict gate from RSEA)
3. **Capacity awareness**: track the ratio of stored episodes to knowledge rules.
   When knowledge exceeds capacity, switch to episodic-only retrieval.

---

## 10. The Dragon Hatchling (BDH): A Post-Transformer Architecture

### 10.1 What BDH Is

The Dragon Hatchling (BDH) (Kosowski et al. 2025, arXiv:2509.26507) is a Large
Language Model architecture that is:

- **Not a Transformer**: uses local graph dynamics instead of global attention
- **Brain-inspired**: n locally-interacting neuron particles on a scale-free
  communication graph
- **Interpretable**: sparse, positive activations with inherent monosemanticity
- **Transformer-comparable**: matches GPT2 performance at same parameter count
  (10M-1B), same training data
- **Unbounded context**: no hard limit on context length (state is in synapses,
  not in a context window)
- **Implementable on GPU**: BDH-GPU is a tensor-friendly restriction that trains
  with backpropagation

### 10.2 The Architecture

```
BDH:
  n particles (neurons) on a communication graph
  Fixed connections (parameters) + dynamic connections σ (state)
  
  Inference = local edge-reweighting process:
    1. Each neuron receives signals from neighbors
    2. Updates its edge weights via Hebbian learning
    3. Signals propagate through the graph
    4. Converges to a stable state (attractor)

BDH-GPU (tensor-friendly restriction):
  - ReLU-lowrank feed-forward network (replaces graph propagation)
  - Linear attention in high dimension n (replaces local dynamics)
  - Positive, sparse activation vectors (~5% non-zero)
  - Scales linearly in dimension n
  - Parameters: (3+o(1)) * n * d, where d=256 in practice
```

### 10.3 Why BDH Matters for Our Vision

BDH is the **missing link between Transformers and brain models**. It proves
that:

1. **Local dynamics can match global attention**: the same language performance
   can be achieved without the O(T²) attention bottleneck
2. **Hebbian learning is sufficient for working memory**: the model's state
   during inference is entirely maintained by synaptic plasticity (Hebbian
   updates), not by a context window
3. **Sparsity and positivity emerge naturally**: the architecture produces
   interpretable, monosemantic activations without any regularization
4. **Scale-free structure is inherent**: the neuron interaction graph
   spontaneously develops high modularity and heavy-tailed degree distribution
   — the same topology as the brain

**For building our own model, BDH provides:**
- A proven architecture that is NOT a Transformer
- A path to unbounded context (critical for agent harnesses)
- Built-in interpretability (we can inspect what the model "thinks")
- A theoretical foundation linking to brain computation
- A working PyTorch implementation (github.com/pathwaycom/bdh, ~100 lines)

### 10.4 The BDH-Harness Connection

The deep connection between BDH and our v5 harness:

| BDH Component | Harness Component | Connection |
|---|---|---|
| n neurons on graph | n prompt fragments in AdaptivePrompt | Both are a population of locally-interacting units |
| Fixed connections (parameters) | AgentProfile (static config) | The "genome" — doesn't change during inference |
| Dynamic connections σ (state) | LearningStore (episodic memory) | The "working memory" — updated during inference |
| Hebbian learning rule | EvolutionEngine.step() | Both update state based on co-activation |
| Scale-free graph topology | Fragment priority/score sorting | Both create a hierarchy of importance |
| Sparsity (~5% active) | Fragment filtering (score < 0.2 skipped) | Both suppress irrelevant information |
| Monosemanticity | One knowledge rule per failure pattern | Both aim for interpretable, single-purpose units |

**The insight**: our v5 harness IS a BDH-like architecture, but operating at the
symbolic level (prompt fragments, knowledge rules) rather than the neural level
(neuron particles, synaptic weights). The harness is the "cultural" analog of
the "neural" BDH.

### 10.5 The Unified Vision: EBM + BDH + Harness

```
Layer 1 (NOW): Harness-level self-improvement (v5)
  - Symbolic energy landscape: task success rate
  - Attractor states: successful trajectories (episodic memory)
  - Spurious states: knowledge rules (semantic memory)
  - Hebbian learning: EvolutionEngine extracts patterns from co-occurring failures
  - Model: frozen (gemma3:4b), harness evolves

Layer 2 (NEXT): Energy-informed fine-tuning
  - Use the harness's trajectory dataset to fine-tune a small model
  - The energy landscape of the fine-tuned model should match the harness's
    learned landscape (knowledge rules as soft constraints)
  - Model: fine-tuned, harness provides curriculum

Layer 3 (LATER): BDH-based model with energy dynamics
  - Train a BDH architecture from scratch
  - The energy function is informed by the harness's learned knowledge
  - Hebbian learning (BDH's native mechanism) replaces backprop for
    working memory updates
  - The model has unbounded context (no context window)
  - The harness provides the symbolic layer, the BDH model provides the
    neural layer, and they co-evolve

Layer 4 (FUTURE): Full EBM model
  - The model IS an energy-based model (diffusion or DenseAM)
  - Generation = memory retrieval = energy minimization
  - The harness IS the training loop (evolution engine = denoising)
  - No distinction between "prompt" and "model" — both are the energy landscape
  - This is the "marked improvement in intelligence" — not language, but
    associative memory dynamics at scale
```

### 10.6 Why This Path is Correct (The Anthropological Argument)

The brain evolved in this order:
1. **Local dynamics** (neurons communicating with neighbors) — BDH's foundation
2. **Associative memory** (energy landscapes with attractor states) — Hopfield/DenseAM
3. **Cultural transmission** (external memory, tools, language) — our harness
4. **Recursive self-improvement** (the scientific method) — our evolution engine

The industry is trying to go in reverse:
1. Build bigger Transformers (cultural product — language)
2. Bolt on memory (RAG — cultural transmission)
3. Try to make it self-improving (agent harnesses — our layer)

This is backwards. The brain's architecture (local dynamics + energy landscapes)
came FIRST. Culture came SECOND. Self-improvement came LAST.

**Our path follows the evolutionary order:**
1. Build the cultural transmission layer (harness — DONE, v0.4.1)
2. Prove self-improvement works at the cultural level (v5 experiment — NEXT)
3. Build the neural architecture (BDH/EBM model — FUTURE)
4. Co-evolve the neural and cultural layers (the endgame)

This is why we build the harness first. The harness IS the culture. The model
IS the brain. Culture evolves before brains evolve. We're following 3.3 billion
years of proven evolutionary strategy.

---

## 11. The Research Agenda — From Harness to Model

### 11.1 Phase 1: Prove the Harness (NOW, Q3 2026)

**Goal**: Test H₀/H₁ from Section 3. Prove (or disprove) that the v5 harness
self-improves on held-out tasks.

**Deliverables**:
- Strict held-out gate implementation
- Convergence experiment (5 conditions × 5 seeds × 46 tasks)
- Statistical analysis (McNemar, effect size, confidence intervals)
- Published result (whether positive or negative — both are valuable)

**Success criterion**: H₁ confirmed (p < 0.05) OR H₀ confirmed with clear
diagnosis of why (overfitting, memory degradation, or fundamental).

### 11.2 Phase 2: Energy-Informed Fine-Tuning (Q4 2026)

**Goal**: Test whether harness-learned knowledge improves a fine-tuned model.

**Experiment**:
- Use the trajectory dataset from Phase 1 as fine-tuning data
- Fine-tune gemma3:4b on (task, evolved_prompt, successful_trajectory) triples
- Compare: frozen+evolved-harness vs fine-tuned+evolved-harness
- Metric: pass rate on held-out test set

**Hypothesis**: Fine-tuned + evolved harness > frozen + evolved harness
**Null**: No significant difference (harness improvement is independent of
weight updates)

**Connection to EBMs**: The fine-tuning should shape the model's energy
landscape to match the harness's learned landscape. Knowledge rules become
soft constraints in the loss function.

### 11.3 Phase 3: BDH Architecture Training (Q1-Q2 2027)

**Goal**: Train a BDH model from scratch, informed by harness-learned knowledge.

**Experiment**:
- Use the BDH-GPU architecture (github.com/pathwaycom/bdh)
- Train on the task distribution discovered by the harness
- Use knowledge rules as auxiliary supervision (energy landscape shaping)
- Compare BDH vs Transformer at same parameter count on our task suite

**Hypothesis**: BDH outperforms Transformer on agent tasks due to unbounded
context and Hebbian working memory.
**Null**: No significant difference (architecture doesn't matter for this task
distribution).

**Why BDH over Transformer for our use case**:
- Unbounded context: agent tasks require long horizons (hundreds of steps)
- Hebbian working memory: the model can "remember" within a session without
  a growing context window
- Interpretability: we can inspect which neurons fire for which concepts
- Sparsity: ~5% activation means efficient inference at scale

### 11.4 Phase 4: Full EBM Model (2027+)

**Goal**: Build a model that IS an energy-based associative memory system.

**Architecture**:
- Energy function informed by the harness's learned landscape
- Diffusion-based generation (denoising = memory retrieval)
- DenseAM storage capacity for episodic memory
- Hebbian learning for online adaptation (no retraining needed)
- The harness's EvolutionEngine becomes the model's training loop

**The marked improvement**: This model would not just predict the next token.
It would:
- Store every interaction as an attractor in its energy landscape
- Retrieve relevant memories via energy minimization (not cosine similarity)
- Generate novel solutions by falling into spurious states (generalization)
- Adapt online via Hebbian learning (no gradient descent needed for new tasks)
- Be fully interpretable (energy landscape is inspectable)

This is not a language model. It is an intelligence model — one that
associates, retrieves, generalizes, and self-improves by the same mathematical
principles that govern biological memory.

### 11.5 The Citable Foundation

| Phase | Key Papers | What We Prove |
|---|---|---|
| 1 (Harness) | RSEA [16], Zhang et al. [2], Reflexion [12], PACE [11] | Self-improvement at the symbolic level |
| 2 (Fine-tuning) | SIA [7], A-Evolve-Training [8], E-SPL [arxiv:2602.14697] | Weight updates add value over harness-only |
| 3 (BDH) | Kosowski et al. [16], Ramsauer et al. [19] | Local dynamics match global attention for agent tasks |
| 4 (EBM) | Ambrogioni [17], Pham et al. [18], Krotov & Hopfield [20] | Intelligence = energy minimization in associative memory |

---

## 12. Summary: The Semantic and Causal Chain

```
EARLY HUMANS (3.3M years ago)
  ↓ Stone tools (externalized action)
  ↓ Symbolic language (compressed instruction)
  ↓ Cultural transmission (accumulated experience)
  ↓ Writing (persistent external memory)
  ↓ Scientific method (self-improving loop)
  ↓ Computing (mechanicalized calculation)
  ↓ Machine learning (mechanicalized learning)
  ↓ LLMs (mechanicalized language)
  ↓ Agent harnesses (mechanicalized culture) ← WE ARE HERE
  ↓ Recursive self-improvement (self-evolving culture) ← v5 EXPERIMENT
  ↓ Energy-based models (mechanicalized memory) ← PHASE 2-3
  ↓ BDH architecture (mechanicalized neural dynamics) ← PHASE 3
  ↓ Full EBM intelligence (mechanicalized associative memory) ← PHASE 4
  ↓ The marked improvement ← THE GOAL
```

**The causal law**: each layer solves the bottleneck of the previous one.
Our current bottleneck is that harnesses are static while models improve
weekly. The v5 harness solves this by making the harness self-improving.
The next bottleneck will be that the model can't adapt online — solved by
EBMs with Hebbian learning. The bottleneck after that will be context length
— solved by BDH's unbounded context. Each step follows from the last.

**The null hypothesis we must kill**: "Self-improving harnesses do not
produce statistically significant improvement on held-out tasks." If we kill
it, we prove the cultural layer can self-improve. If we confirm it, we learn
why — and that knowledge informs the neural architecture we build next.

Either way, we advance. That's science.