# VISION-WORLD-RESEARCH: A Technical Blueprint for Non-Text-Binned Intelligence

> **Forge-SDK v5+ Research Document**
> 
> Authors: srinji (Director) + opus + opencode
> 
> Date: 2026-07-01
> 
> Status: Living research blueprint — the foundation for building our own model
>
> **Core Thesis**: Current AI models "bin everything into text" — they reduce
> the continuous, spatial, causal, physical world to discrete token sequences.
> True intelligence requires architectures that operate natively on structured
> world representations. This document lays out the mathematical and architectural
> path to building one.

---

## Table of Contents

1. [The Motivating Gap: Why Current Models Lack a World View](#1-the-motivating-gap)
2. [BDH Architecture: Local Graph Dynamics Replace Global Attention](#2-bdh-architecture)
3. [Energy Models: Diffusion Models ARE Hopfield Networks](#3-energy-models)
4. [World Models: V-JEPA 2 and Latent Predictive Learning](#4-world-models)
5. [Vision Grounding: 3D Spatial Reasoning in VLMs](#5-vision-grounding)
6. [The Unified Gap Analysis: Everything Binned into Text](#6-the-unified-gap)
7. [What We Should Build: A Non-Text-Binned Architecture for Forge-SDK v5+](#7-what-we-should-build)
8. [Implementation Roadmap](#8-implementation-roadmap)
9. [References](#9-references)

---

## 1. The Motivating Gap: Why Current Models Lack a World View

### 1.1 The Text Binning Problem

Every major LLM and VLM today operates on the same fundamental principle:

```
Reality (continuous, multi-modal) 
  → Tokenization (discretization into a vocabulary) 
  → Autoregressive next-token prediction
  → Text output
```

This pipeline **bins everything into text**. A 3D scene becomes a list of
object labels. A physical interaction becomes a sequence of "the ball rolled".
A spatial relationship becomes "left of" or "above". The model never builds an
internal 3D coordinate frame, never maintains object permanence, never simulates
physics — because none of those exist in token space.

**The consequence**: Current VLMs can describe an image but cannot *reason*
about it spatially. They cannot predict what happens next in a video beyond
high-level captions. They cannot answer "if I rotate this object 90 degrees,
what will I see?" without having seen that exact rotation in training data.

### 1.2 What a True World Model Requires

A genuine world model must maintain:

| Capability | Current LLM/VLM | Required |
|---|---|---|
| **Object permanence** | No — everything is attention over tokens | Yes — persistent latent slots for entities |
| **3D coordinate frame** | No — spatial relations are linguistic | Yes — allocentric and egocentric coordinate transforms |
| **Physics simulation** | No — implicit in training data statistics | Yes — forward dynamics model (even at coarse level) |
| **Causal reasoning** | Emergent, unreliable, text-based | Explicit — counterfactual "what if" in latent space |
| **Associative memory** | Cosine similarity over embeddings | Energy-based attractor networks with convergence dynamics |
| **Unbounded context** | Fixed context window | Synaptic state (BDH) or recurrent latent dynamics |

### 1.3 The Research Question

**Can we build an architecture that natively represents the world as a
structured, continuous, energy-based latent space — rather than as text tokens
— and can that architecture be trained end-to-end to perform spatial reasoning,
physical prediction, and associative memory retrieval?**

This blueprint answers: **yes**, and here is how, drawing on four converging
research threads.

---

## 2. BDH Architecture: Local Graph Dynamics Replace Global Attention

### 2.1 The Transformer Bottleneck

Transformers scale quadratically in context length: **O(T²) attention**. This
is not just a computational problem — it's a *representational* one. Every
token must attend to every other token, meaning the model cannot maintain
persistent, localized state. Memories must be re-derived from scratch each
forward pass. There is no "working memory" that persists across time steps
— only a growing context window.

For a world model, this is fatal. The world is persistent. Objects exist
continuously. You shouldn't need to re-attend to the entire history of a
rolling ball at every frame.

### 2.2 BDH: The Dragon Hatchling

The **Dragon Hatchling (BDH)** (Kosowski et al. 2025, arXiv:2509.26507) is a
Large Language Model architecture that replaces global attention with **local
edge-reweighting dynamics on a scale-free communication graph**.

#### Architecture

```
BDH Core Components:
  n: number of neuron particles
  G = (V, E): scale-free directed graph (communication topology)
  W_fixed ∈ ℝ^(n×d): learned parameters (synaptic weights)
  σ_dynamic(t): dynamic edge weights (working memory state)

Inference = local Hebbian relaxation process:
  1. Input encoded as initial neural activation vector
  2. For each edge (i→j):
       σ_ij(t+1) = σ_ij(t) + η · a_i · a_j          [Hebbian update]
       a_j(t+1) = ReLU(Σ_i σ_ij(t+1) · a_i(t))      [propagation]
  3. Process converges to a fixed point (attractor)
  4. Output decoded from final activation state
```

#### Key Properties

| Property | Transformer | BDH |
|---|---|---|
| **Attention mechanism** | Global (all-to-all) | Local (graph neighbors only) |
| **Context** | Fixed window (T tokens) | Unbounded (state in synapses) |
| **Working memory** | KV cache (grows with context) | Dynamic edge weights (fixed size) |
| **Computational complexity** | O(T²·d) per layer | O(|E|·d) per step, |E| ≈ n·log(n) |
| **Activation sparsity** | Dense (~100% active) | Sparse (~5% active, naturally emergent) |
| **Interpretability** | Polysemantic neurons | Monosemantic positive activations |
| **Learning rule** | Backpropagation only | Hebbian for inference, backprop for training |

#### BDH-GPU: The Trainable Restriction

For practical GPU training with backpropagation, BDH-GPU restricts the dynamics
to be tensor-friendly while retaining the core properties:

```
BDH-GPU Forward Pass:
  h = ReLU( W_in · x )                  # Input encoding
  h = ReLU( W_ff · h + W_skip · x )     # Feedforward + residual
  h = h + LinearAttention(Q, K, V, h)   # High-dim linear attention
  y = W_out · h                          # Output decoding

Parameters: (3 + o(1)) · n · d  where d=256 in practice
```

This achieves **GPT-2 comparable performance** at the same parameter count
(10M-1B) on the same training data, proving that local dynamics CAN match
global attention for language modeling.

### 2.3 Why BDH is the Foundation for Our World Model

For a world model, we need architecture that:
1. **Maintains persistent state across time** — BDH's synaptic weights ARE state
2. **Handles unbounded context** — no context window, state is in the graph
3. **Converges to attractors** — memories are stable fixed points
4. **Is interpretable** — we can inspect which "neurons" encode which concepts
5. **Scales efficiently** — O(n·log(n)) vs O(T²)

The BDH graph becomes the **neural substrate** for our world model. Instead of
predicting the next text token, it predicts the next world state in a
structured latent space.

---

## 3. Energy Models: Diffusion Models ARE Hopfield Networks

### 3.1 The Mathematical Equivalence (Ambrogioni 2024)

The central theoretical result (Ambrogioni 2024, arXiv:2309.17290):

**The energy landscape of a generative diffusion model trained on discrete
patterns is asymptotically identical to the energy function of a modern
Hopfield network.**

```
Diffusion Model Energy:
  E_DM(x, t) = -σ²(t) · log[ Σ_n exp( -||x - y_n||² / (2σ²(t)) ) ]

Modern Hopfield (DenseAM) Energy:
  E_MH(x, β)  = -β⁻¹  · log[ Σ_n exp( β · K(x, y_n) ) ]
  where K(x,y) = x^T y  (dot-product similarity)

Equivalence:
  Set β(t) = 1/σ²(t)  and  K(x,y) = -||x-y||²/2 + const
  Then:  E_DM(x,t) = E_MH(x, β(t))
```

### 3.2 What This Means

| Insight | Implication |
|---|---|
| **Diffusion models ARE associative memories** | Training data points become attractors in the energy landscape |
| **Generation = memory retrieval** | Denoising is gradient descent on E(x), converging to stored memories |
| **Novel generation = spurious states** | New samples are attractors NOT in the training set — emergent minima |
| **Training = synaptic learning** | SGD encodes associative dynamics into the weight structure |
| **β controls retrieval sharpness** | Inverse temperature determines how precisely we retrieve vs generalize |

### 3.3 The Memorization-to-Generalization Transition

Pham et al. (2026, arXiv:2505.21777) identified three regimes:

```
Regime 1: K < Capacity (0.14·D for classical Hopfield)
  → Each training point = distinct attractor (pure memorization)
  → No generalization

Regime 2: K ≈ Capacity
  → Spurious states emerge — new attractors not at any training point
  → FIRST SIGN of generalization
  → These are abstract composites of multiple memories

Regime 3: K >> Capacity  
  → Continuous manifold of low-energy states
  → Training points are no longer minima
  → Genuine generalization — model generates truly novel samples
```

**For our world model**: we want to operate in Regime 3. The model should store
millions of interactions as attractors, but the energy landscape should smooth
into a continuous manifold that supports interpolation to novel situations.

### 3.4 Energy Models in Practice: From Theory to Architecture

```
Traditional approach (discriminative):
  Input → Neural Network → Output
  No notion of energy, stability, or memory

Energy-based approach:
  Input → Energy Function E(x, θ) → Gradient Dynamics → Output
           ↑
           Attractors = memories
           Minima = solutions
           Dynamics = reasoning
```

For our model, the energy function is learned. It defines what "good" world
states look like. Prediction is finding the lowest-energy next state given
the current state and action. Memory retrieval is converging from a partial
cue to the nearest attractor.

---

## 4. World Models: V-JEPA 2 and Latent Predictive Learning

### 4.1 The JEPA Architecture (LeCun's Vision)

The **Joint Embedding Predictive Architecture (JEPA)**, proposed by Yann LeCun
as the core of autonomous AI, is a self-supervised learning framework that
predicts in **latent representation space** rather than in pixel/token space.

```
JEPA Core Architecture:

  x (context) ──→ Encoder_ctx ──→ s_x (latent context)
                                       │
                                  Predictor
                                       │
                                       ↓
  y (target)  ──→ Encoder_tgt ──→ s_y (latent target) ←── prediction loss
```

**Key insight**: Instead of predicting raw pixels (which wastes capacity on
irrelevant detail), JEPA predicts the *latent representation* of the target.
The encoders learn to extract the predictable, abstract features. The
predictor learns the dynamics of the world in this abstract space.

### 4.2 V-JEPA: Video JEPA and V-JEPA 2

**V-JEPA** (Meta AI, 2024-2025) applies JEPA to video:

- **Context**: A sequence of video frames (e.g., 16 frames)
- **Target**: A future sequence of frames (e.g., next 8 frames)
- **Training**: Mask large spatiotemporal blocks (not individual patches)
- **Objective**: Predict the latent representation of the masked target from the unmasked context

**V-JEPA 2** (2025) extends this with:

1. **Multimodal JEPA**: Joint embedding across video, audio, and text
2. **Action-conditioned prediction**: Latent prediction conditioned on agent actions
3. **Hierarchical JEPA**: Multiple prediction horizons (short: 0.5s, medium: 2s, long: 10s)
4. **Object-centric latent slots**: Instead of dense feature maps, the latent
   space is decomposed into entity slots ("object files") that persist across time

```
V-JEPA 2 Architecture:

  Video frames (t-16:t) ──→ Vision Transformer ──→ Context latents
                                                        │
  Action embedding ─────────────────────────────────────┤
                                                        │
                                                Hierarchical Predictor
                                                   ├── Short-horizon head (0.5s)
                                                   ├── Medium-horizon head (2s)
                                                   └── Long-horizon head (10s)
                                                        │
                                                        ↓
  Video frames (t:t+8) ──→ Target Encoder ──→ Target latents ←── Contrastive loss
```

### 4.3 Why Latent Predictive Learning is Essential for World Models

| Property | Pixel-space prediction | Latent-space prediction (JEPA) |
|---|---|---|
| **What is predicted** | Raw pixels (3×H×W) | Abstract features (d-dimensional) |
| **Capacity usage** | Mostly on low-level texture/physics | Mostly on high-level structure/dynamics |
| **Generalization** | Overfits to pixel statistics | Generalizes across visual domains |
| **Computational cost** | High (generator network) | Low (predictor in latent space) |
| **Controllable** | Difficult (pixel generation is stochastic) | Direct (predicts representation) |

For our world model, JEPA provides the **predictive mechanism**: given the
current world state (encoded into latent space) and an action, predict the
next world state's latent representation. The energy model then provides the
**verification mechanism**: check if the predicted state is consistent with
stored experiences (low energy = plausible, high energy = implausible).

---

## 5. Vision Grounding: 3D Spatial Reasoning in VLMs

### 5.1 What Current VLMs Can Do

Current Vision-Language Models (GPT-4V, Gemini, LLaVA, Claude 3.5) can:

- **Describe** spatial relationships in natural language ("the cup is on the table")
- **Answer questions** about visible objects ("what color is the car?")
- **Follow navigation instructions** from images ("turn left at the red door")
- **Count objects** in scenes (with varying reliability)

### 5.2 What Current VLMs Cannot Do

They fundamentally cannot:

| Task | Why They Fail |
|---|---|
| **Mental rotation** | No internal 3D coordinate frame; relies on seen examples |
| **Physical prediction** | No forward dynamics model; text statistics don't capture physics |
| **Perspective-taking** | Can't compute "what would this look like from over there?" |
| **Object permanence** | No persistent object slots; each frame is re-processed from scratch |
| **Spatial planning** | Can generate text plans but not simulate spatial consequences |
| **Metric distance** | Only approximate relative terms ("near", "far"); no coordinates |

### 5.3 The Architectural Gap

```
Current VLM pipeline:
  Image → Vision Encoder (ViT) → Patch features → Project to LLM token space → 
  Autoregressive text generation
  
  Problem: The LLM's "world model" is linguistic. It has no internal 3D grid,
  no object-centric slots, no physics simulator. Spatial reasoning is reduced
  to linguistic pattern matching.
```

### 5.4 What Real Vision Grounding Requires

For genuine 3D spatial reasoning, a model needs:

1. **Egocentric-to-allocentric transform**: Convert from "what I see" to
   "where things are in the world" — requires depth estimation, camera pose,
   and coordinate frame alignment.

2. **Object-centric representations**: Not a grid of patches, but distinct
   latent vectors ("slots") for each entity, with persistent identity across
   views and occlusions.

3. **3D-aware neural fields**: Implicit representations (NeRF, 3D Gaussian
   Splatting) that encode continuous volumetric density and radiance, not
   discrete tokens.

4. **Metric spatial memory**: A learned map from (object, viewpoint) →
   3D coordinates, maintained in an energy landscape where retrieval is
   convergence to the nearest matching configuration.

```
Proposed Vision Grounding Module:

  RGB/Depth input ──→ 3D Encoder (e.g., DUSt3R, MASt3R) ──→ Pointmap (H×W×3)
                                                                  │
                                                  ┌───────────────┤
                                                  ↓               ↓
                                          Object Slot        Camera Pose
                                          Attention          Estimator
                                                  │               │
                                                  ↓               ↓
  Persistent Object Slots  ←→  Energy-Based Associative Memory
  (vectors with 3D position,          (stores object configurations
   orientation, velocity,                  as attractors)
   and appearance features)
                                                  │
                                                  ↓
                                          World State Latent
                                          (energy-minimized configuration)
                                                  │
                                                  ↓
                                          JEPA Predictor
                                          (predicts next world state)
```

---

## 6. The Unified Gap: Everything Binned into Text

### 6.1 The Root Cause

The fundamental limitation of all current frontier models is that they convert
everything into tokens — discrete symbols from a finite vocabulary — and then
process those tokens with architectures designed for language (Transformers).

This worked surprisingly well for text because text IS discrete and sequential.
But the world is not. The world is continuous, spatial, hierarchical, and
persistent. Tokenizing it destroys the very structure that makes reasoning
possible.

```
Text-native reasoning (works):
  "If A > B and B > C, then A > C"
  → Tokens capture logical structure

World reasoning (fails in text):
  "If the cup is on the tilted table, will it slide off?"
  → Tokens lose: table angle, cup mass, friction coefficient, gravity vector
  → Model must answer from linguistic statistics, not physics
```

### 6.2 The Five Missing Capabilities

| Missing Capability | Text-Binned Substitute | What We Need |
|---|---|---|
| **Continuous spatial memory** | "left of", "above", "near" | 3D coordinate frames + transform networks |
| **Physical dynamics** | Text descriptions of motion | Learned forward simulator in latent space |
| **Object persistence** | Mentioned when visible, forgotten when occluded | Persistent object slots with occlusion handling |
| **Hierarchical planning** | Chain-of-thought text | Latent hierarchical JEPA with multi-scale prediction |
| **Associative retrieval** | Cosine similarity embedding lookup | Energy-based attractor dynamics |

### 6.3 The Path Forward

We must build an architecture where **language is a modality, not the medium**.
The model's internal representation is not a sequence of tokens — it is a
structured, continuous, energy-based latent space that can represent:

- 3D geometry (continuous coordinates)
- Object properties (mass, velocity, appearance)
- Physical laws (constraints on state transitions)
- Causal relationships (intervention = state perturbation)

Language becomes an **input/output interface**, not the internal representation.
This is the same relationship the human brain has: we think in spatial, sensory,
and motor representations; language is a serialization layer on top.

---

## 7. What We Should Build: A Non-Text-Binned Architecture for Forge-SDK v5+

### 7.1 The Unified Architecture: WAVE (World Associative Vision Engine)

We propose **WAVE**: a model that integrates BDH graph dynamics, energy-based
associative memory, JEPA latent predictive learning, and 3D vision grounding
into a single architecture with **no text bottleneck**.

```
WAVE Architecture:

┌─────────────────────────────────────────────────────────────────────┐
│                        SENSORY ENCODERS                              │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐       │
│  │  Vision  │    │  Depth   │    │  Audio   │    │  Language │       │
│  │ Encoder  │    │ Encoder  │    │ Encoder  │    │  Encoder  │       │
│  │ (ViT)    │    │ (Pointmap│    │ (Audio   │    │ (Text →   │       │
│  │          │    │  via     │    │  spectro) │    │  latent)  │       │
│  │          │    │  MASt3R) │    │          │    │           │       │
│  └────┬─────┘    └────┬─────┘    └────┬─────┘    └─────┬─────┘       │
│       │               │               │                │             │
│       └───────────────┴───────────────┴────────────────┘             │
│                           │                                          │
│                    ┌──────┴──────┐                                   │
│                    │  Multimodal │                                   │
│                    │  Projector  │  ← Projects all modalities        │
│                    │             │    into shared world latent       │
│                    └──────┬──────┘                                   │
└───────────────────────────┼──────────────────────────────────────────┘
                            │
┌───────────────────────────┼──────────────────────────────────────────┐
│                 WORLD STATE (continuous latent)                       │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────┐      │
│  │              OBJECT SLOTS (persistent entities)             │      │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │      │
│  │  │ Slot 1   │  │ Slot 2   │  │ Slot 3   │  │ Slot N   │   │      │
│  │  │ pos: xyz │  │ pos: xyz │  │ pos: xyz │  │ pos: xyz │   │      │
│  │  │ vel: dx  │  │ vel: dx  │  │ vel: dx  │  │ vel: dx  │   │      │
│  │  │ feat: f  │  │ feat: f  │  │ feat: f  │  │ feat: f  │   │      │
│  │  │ id: k    │  │ id: k    │  │ id: k    │  │ id: k    │   │      │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │      │
│  └────────────────────────────────────────────────────────────┘      │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────┐      │
│  │         BDH GRAPH (neural dynamics on object slots)         │      │
│  │                                                             │      │
│  │  Slots = neurons on scale-free graph                        │      │
│  │  Edges = learned relationships (spatial, causal, semantic)  │      │
│  │  Dynamics = Hebbian edge reweighting → energy minimization  │      │
│  │  Convergence = attractor state = "understood" configuration │      │
│  └────────────────────────────────────────────────────────────┘      │
│                                                                       │
└───────────────────────────────┬───────────────────────────────────────┘
                                │
┌───────────────────────────────┼───────────────────────────────────────┐
│                   PREDICTIVE DYNAMICS                                  │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────┐     │
│  │              JEPA PREDICTOR (next world state)                │     │
│  │                                                               │     │
│  │  world_state(t), action(t) ──→ world_state(t+1) prediction    │     │
│  │                                                               │     │
│  │  ┌─────────────────┐    ┌─────────────────┐                   │     │
│  │  │ Short horizon   │    │ Long horizon     │                  │     │
│  │  │ (0.5s, physics) │    │ (10s, planning)  │                  │     │
│  │  │ Δpos, Δvel      │    │ goal state       │                  │     │
│  │  └─────────────────┘    └─────────────────┘                   │     │
│  └──────────────────────────────────────────────────────────────┘     │
│                                                                        │
└───────────────────────────────┬────────────────────────────────────────┘
                                │
┌───────────────────────────────┼────────────────────────────────────────┐
│               ENERGY-BASED ASSOCIATIVE MEMORY                           │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────┐     │
│  │         DIFFUSION ENERGY LANDSCAPE (DenseAM)                   │     │
│  │                                                                │     │
│  │  E(x) = -β⁻¹ log[ Σ_n exp( β · K(x, memory_n) ) ]            │     │
│  │                                                                │     │
│  │  memories = stored world states (trajectories)                 │     │
│  │  retrieval = gradient descent on E(x) from partial cue x      │     │
│  │  generalization = spurious attractors (novel compositions)    │     │
│  │                                                                │     │
│  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │     │
│  │  │ Episode     │    │ Semantic    │    │ Spurious    │        │     │
│  │  │ Memory      │    │ Memory      │    │ States      │        │     │
│  │  │ (raw states)│    │ (abstracted │    │ (novel      │        │     │
│  │  │             │    │  patterns)  │    │  solutions) │        │     │
│  │  └─────────────┘    └─────────────┘    └─────────────┘        │     │
│  └───────────────────────────────────────────────────────────────┘     │
│                                                                         │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
┌───────────────────────────────┼─────────────────────────────────────────┐
│                    OUTPUT DECODERS                                      │
│                                                                         │
│  world_state ──→ Language Decoder ──→ text output (if needed)           │
│  world_state ──→ Vision Decoder  ──→ rendered view (if needed)          │
│  world_state ──→ Action Decoder  ──→ motor commands (if embodied)       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 7.2 Key Design Principles

#### Principle 1: The World State is NOT Text

The core representation is a **structured latent vector** with explicit
slots for objects, their 3D positions, velocities, and features. Language
is only attached at the input/output boundaries via modality-specific
encoders and decoders.

#### Principle 2: Memory is Energy-Based

All memory retrieval is energy minimization. There is no separate "RAG"
module that does cosine similarity lookup. The model's associative memory
IS the energy landscape, and retrieval IS the convergence dynamics.

- **Episode storage**: World state trajectories stored as energy minima
- **Retrieval**: Partial state (cue) → gradient descent → nearest attractor
- **Consolidation**: Similar episodes merge into composite attractors
- **Novelty**: When no attractor matches → model generates via diffusion denoising

#### Principle 3: Dynamics is Latent Prediction (JEPA)

The model predicts future world states in latent space, not in pixel space.
Prediction is conditioned on actions (for embodied settings) and the current
world state. Multiple prediction heads handle different time horizons.

#### Principle 4: Reasoning is Graph Dynamics (BDH)

The relationships between objects are modeled as a BDH graph. Edges represent
spatial proximity, causal influence, or semantic association. The graph
converges to an energy minimum, which IS the "understood" configuration of
the scene.

#### Principle 5: Learning is Hebbian + Energy-Shaping

Training combines:
- **Hebbian learning** (BDH graph edges): "neurons that fire together, wire together"
- **Energy landscape shaping** (DenseAM loss): Training data becomes attractors
- **JEPA contrastive loss**: Predicted latent matches target latent
- **Sparsity regularization**: Natural emergence of sparse, monosemantic activations

### 7.3 Why This Architecture Addresses the Five Gaps

| Gap | How WAVE Fixes It |
|---|---|
| **Continuous spatial memory** | Object slots with explicit 3D coordinates; BDH graph edges encode spatial relationships |
| **Physical dynamics** | JEPA predictor learns forward dynamics in latent space from video + depth data |
| **Object persistence** | Object slots persist by identity (not by being visible); occlusion handled via slot attention with memory |
| **Hierarchical planning** | Multi-scale JEPA: short horizon for physics, long horizon for planning; action decoder for execution |
| **Associative retrieval** | Diffusion energy landscape: retrieval = energy minimization; generalization = spurious attractors |

### 7.4 Connection to Forge-SDK v5+

The forge-sdk v5 harness is the **cultural layer** that wraps around this
architecture. The harness provides:

- **Task distribution**: The tasks we solve become training trajectories
- **Evolution loop**: The EvolutionEngine's feedback becomes Hebbian signals
- **Knowledge store**: The LearningStore maps to the energy landscape's semantic memory
- **Agent profile**: Defines the model's identity, constraints, and objectives

```
Forge-SDK v5+ Integration:

  HarnessRunner ──→ tasks ──→ WAVE Model ──→ world states ──→ output
       ↑                                                        │
       │                                                        │
       └────────── EvolutionEngine ←── LearningStore ←──────────┘
                    (feedback)          (trajectories)

  The harness evolves the prompts/instructions.
  The model evolves its energy landscape.
  They co-evolve — culture and brain, together.
```

---

## 8. Implementation Roadmap

### Phase 1: Foundation (Q3 2026 - Q1 2027)

**Goal**: Implement the core components in isolation, verify they work.

| Component | Implementation | Validation |
|---|---|---|
| **Object Slot Attention** | Implement slot attention with persistent IDs over video frames | Track objects through occlusions in CLEVRER or Physion |
| **BDH Graph Dynamics** | Implement BDH-GPU as a standalone module (from github.com/pathwaycom/bdh) | Verify attractor convergence and sparsity on toy data |
| **DenseAM Memory** | Implement modern Hopfield network as associative memory | Store and retrieve patterns; verify capacity limits |
| **JEPA Predictor** | Implement V-JEPA-style latent prediction on video | Predict future frame latents on Kinetics-400 |
| **3D Encoder** | Integrate MASt3R or DUSt3R for pointmap extraction | Reconstruct 3D from monocular video |

### Phase 2: Integration (Q2-Q3 2027)

**Goal**: Wire components together into the full WAVE architecture.

- Connect object slots → BDH graph (slots as neurons, spatial relations as initial edges)
- Connect BDH convergence → energy landscape (converged state is the input to memory)
- Connect JEPA predictor → object slots (predicts next slot states)
- Connect energy memory → JEPA (retrieved memories condition prediction)
- Train end-to-end on video + action + text data

### Phase 3: Harness Integration (Q4 2027)

**Goal**: Connect WAVE to the forge-sdk v5+ harness.

- ModelPort: WAVE becomes a ModelProvider
- LearningStore trajectories become energy landscape memories
- EvolutionEngine feedback shapes Hebbian learning updates
- Agent tasks evaluate spatial reasoning, physical prediction, planning

### Phase 4: The Marked Improvement (2028)

**Goal**: Demonstrate that WAVE outperforms text-binned architectures on
world-modeling tasks.

**Evaluation suite**:
- Physion (physical prediction)
- CLEVRER (causal reasoning from video)
- Habitat (embodied navigation)
- SpatialVQA (3D spatial reasoning)
- ARC-AGI 2.0 (abstraction and reasoning)

**Success criterion**: WAVE at 1B parameters exceeds 7B VLMs on spatial
and physical reasoning tasks, with interpretable internal representations.

---

## 9. References

### BDH Architecture
1. Kosowski, A., Uznański, P., Chorowski, J., Stamirowska, Z., Bartoszkiewicz, M. (2025). "The Dragon Hatchling: The Missing Link between the Transformer and Models of the Brain." arXiv:2509.26507.
2. Pathway (2025). BDH GitHub repository. github.com/pathwaycom/bdh.

### Energy Models & Hopfield Networks
3. Ambrogioni, L. (2024). "In Search of Dispersed Memories: Generative Diffusion Models Are Associative Memory Networks." arXiv:2309.17290.
4. Pham, B., Raya, G., Negri, M., Zaki, M.J., Ambrogioni, L., Krotov, D. (2026). "Memorization to Generalization: Emergence of Diffusion Models from Associative Memory." arXiv:2505.21777.
5. Ramsauer, H., et al. (2021). "Hopfield Networks is All You Need." arXiv:2008.02217.
6. Krotov, D., Hopfield, J. (2016). "Dense Associative Memory for Pattern Recognition." arXiv:1606.01164.
7. Raya, G., Ambrogioni, L. (2024). "Spontaneous Symmetry Breaking in Generative Diffusion Models." arXiv:2402.03745.
8. Hoover, B., et al. (2023). "Memory in Plain Sight: Surveying the Uncanny Resemblances of Diffusion Models and Associative Memories." arXiv:2309.16750.
9. Krotov, D. (2023). "A New Frontier for Hopfield Networks." arXiv:2307.00764.

### JEPA & World Models
10. LeCun, Y. (2022). "A Path Towards Autonomous Machine Intelligence." arXiv:2206.07294v1.
11. Assran, M., et al. (2023). "Self-Supervised Learning from Images with a Joint-Embedding Predictive Architecture." arXiv:2301.08243. (I-JEPA)
12. Bardes, A., et al. (2024). "Revisiting Feature Prediction for Learning Visual Representations from Video." arXiv:2404.08471. (V-JEPA)
13. Meta AI (2025). "V-JEPA 2: Multimodal and Action-Conditioned Joint Embedding Prediction." (technical report)
14. Hafner, D., et al. (2020). "Mastering Atari with Discrete World Models." arXiv:2010.02193. (DreamerV2)
15. Ha, D., Schmidhuber, J. (2018). "World Models." arXiv:1803.10122.

### Vision Grounding & 3D Spatial Reasoning
16. Wang, S., et al. (2024). "DUSt3R: Geometric 3D Vision Made Easy." arXiv:2312.14132.
17. Leroy, V., et al. (2024). "MASt3R: Matching and Stereo 3D Reconstruction." arXiv:2406.04494.
18. Locatello, F., et al. (2020). "Object-Centric Learning with Slot Attention." arXiv:2006.15055.
19. Mildenhall, B., et al. (2020). "NeRF: Representing Scenes as Neural Radiance Fields for View Synthesis." arXiv:2003.08934.
20. Kerbl, B., et al. (2023). "3D Gaussian Splatting for Real-Time Radiance Field Rendering." arXiv:2308.04079.
21. Chen, Y., et al. (2024). "SpatialVLM: Endowing Vision-Language Models with Spatial Reasoning Capabilities." arXiv:2401.12168.

### Our Harness Foundation
22. Nguyen, M., et al. (2026). "Recursive Self-Evolving Agents via Held-Out Selection." arXiv:2606.28374.
23. Zhang, D., et al. (2026). "Useful Memories Become Faulty When Continuously Updated by LLMs." arXiv:2605.12978.
24. SPEC-V5-001: forge-sdk v5 Harness — A Test of Self-Improving Agent Culture. (this repository)

---

## Appendix A: The Anthropological Argument (Reprise)

```
EVOLUTIONARY SEQUENCE:
  Stone tools → Language → Cultural transmission → Writing → 
  Scientific method → Computing → Machine learning → LLMs → 
  Agent harnesses (WE ARE HERE) → Recursive self-improvement → 
  Energy-based world models → BDH neural dynamics → 
  Full non-text-binned intelligence → THE MARKED IMPROVEMENT

BIOLOGICAL SEQUENCE (for comparison):
  Neurons → Local circuits → Associative memory → Hippocampus → 
  Cortex → Symbolic thought → Language → Culture → Self-awareness

INSIGHT: Biology built neural dynamics FIRST, then language on top.
Industry built language FIRST, and is now trying to bolt on neural dynamics.
WAVE inverts this: build the neural/world dynamics first, language on top.
```

## Appendix B: Design Decisions Log

| Decision | Rationale | Date |
|---|---|---|
| Object slots, not dense feature maps | Enables persistent entity tracking and compositional generalization | 2026-07 |
| BDH, not Transformer for internal dynamics | Unbounded context, Hebbian learning, emergent sparsity, interpretability | 2026-07 |
| Diffusion energy, not contrastive embedding | Unifies memory storage, retrieval, and generation; principled generalization via spurious states | 2026-07 |
| JEPA latent prediction, not pixel prediction | Computational efficiency, focuses learning on high-level dynamics | 2026-07 |
| 3D pointmaps as vision backbone, not 2D patches | Provides metric spatial information; enables coordinate transforms | 2026-07 |
| Language as decoder only, not internal representation | Prevents text-binning; forces model to think in structured world states | 2026-07 |

---

*This document is a living research blueprint. It will be updated as we
implement, test, and discover. The speculation today is the experiment tomorrow.*
