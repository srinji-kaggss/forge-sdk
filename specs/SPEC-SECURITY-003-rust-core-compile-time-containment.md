---
spec: SPEC-SECURITY-003
title: "Compile-Time Containment & the Rust Core Migration"
status: DRAFT — plan for Director review, chunked for agent dispatch, nothing implemented yet
version: 0.1.0
date: 2026-07-01
author: claude (Sonnet 5, orchestrator session)
collaborators: [srinji (Director)]
supersedes_recommendation_in: [SPEC-SECURITY-002 §3.3 ("do not port this layer to Rust now")]
depends_on: [SPEC-SECURITY-002, AUDIT-MATRIX-001, .specs/SPEC-SDK-002 (INV-107), ADVERSARIAL-REPORT.md (~/forge, v0.3.0)]
director_directive: "Move forge out of Python and into Rust for good. Stay fully proprietary — no
  new external dependency — but lean on OSS/existing framework PATTERNS. Be better than cline/
  opencode/agy at giving users control over their AI experience, matching Claude Code's auto-mode
  classifier tiering. As seamless as Anthropic's own SDK. Research Pliny + prompt injection to
  ground why our containment is mechanical/structural, not semantic/probabilistic."
---

# SPEC-SECURITY-003: Compile-Time Containment & the Rust Core Migration

## 0. What changed since SPEC-SECURITY-002, and why this doc exists

SPEC-SECURITY-002 (v0.2.0, 2026-06-30) designed `contain_untrusted_text() -> ContainmentResult` as
forge's canonical structural-containment primitive and explicitly recommended, in §3.3, **against**
a Rust port "now" — citing no WASM/edge target yet, negligible measured latency benefit, and loss of
existing Python test coverage. That recommendation is **overridden by explicit Director directive**
this session: move forge's core out of Python into Rust, permanently, leaning on OSS framework
*patterns* (not dependencies) for the design, and matching Anthropic's own SDK on developer ergonomics.
This document does not relitigate that call — it plans the migration honestly, phased, without
overclaiming a big-bang rewrite is credible in one pass.

Three things happened in parallel that changed the evidence base since §3.3 was written:

1. **A real containment gap was found and demonstrated, not hypothesized**, in forge's *other* denylist
   layer (L5, not L4). Running forge's actual `security.py` against a real credential file on this
   machine: `_check_command_safety('cat ~/.cline/data/settings/settings.json')` returns `None` (i.e.
   ALLOWED) because that path isn't in the hardcoded `SENSITIVE_READ_PATHS` list, even though it is a
   real API-key store. Claude Code's own auto-mode classifier — a semantic/reasoning-based gate, not a
   path denylist — independently blocked the same action for "Credential Materialization" risk. This
   is the same *category* of bug SPEC-SECURITY-002 diagnosed for L4 (enumerated pattern lists don't
   generalize) showing up in L5 too. It sharpens this doc's central claim: **the fix for both is the
   same shape — stop enumerating bad values, make the illegal state unrepresentable.**
2. **Pliny the Prompter / L1B3RT4S taxonomy + broader injection literature was researched fresh**
   (Transluce's Investigator Agents work, ADVERSA arXiv:2603.10068, "Plentiful Jailbreaks with String
   Compositions" arXiv:2411.01084, Pliny's own interviews). Verdict, stated precisely in §1 below: no
   documented technique — from Pliny's corpus or the academic literature — defeats a schema-constrained/
   closed-enum defense. The one genuinely new, structural finding (PRBO/token-steering via logprob/
   prefill API access) is out of scope for text containment and belongs with the capability/daemon
   boundary, not this layer.
3. **`~/forge/ADVERSARIAL-REPORT.md` (v0.3.0, same day) was found** — an already-executed, real
   adversarial pass against forge's own agent loop. Its CRITICAL-002 finding is the *same bug class*
   SPEC-SECURITY-002 patches (`SemanticCheck` interpolating untrusted `task_intent`/`solution_summary`
   into a prompt) but its recorded fix — "wrap user content in labeled delimiters" — is exactly the
   weak `[UNTRUSTED_DATA]` wrapper SPEC-SECURITY-002 §2.1 says is a hint, not a guarantee. **This is a
   live inconsistency in the codebase today**: two files disagree on what "fixed" means for the same
   bug class. Per CLAUDE.md prime directive 3, this gets collapsed to one canonical treatment, not
   left as two.

---

## 1. Injection research delta (Pliny + broader literature, vs. SPEC-SECURITY-002 §1.2)

Full technique table cross-referenced against the existing bypass table in SPEC-SECURITY-002 §1.2:

| Technique class | Source | New vs. §1.2's rows 1-8? | Survives schema-constrained containment? |
|---|---|---|---|
| Encoding/string-composition (base64, ROT13, leetspeak, bijection ciphers) | Pliny corpus; arXiv:2411.01084 | No — same family as §1.2 rows 1/7/8 | No |
| Roleplay/narrative-legitimacy framing (DAN, credential-framing, "Ph.D./postdoc" framing) | Pliny corpus; confirmed by Transluce as the *most effective* class in their study | No — §1.2 row 6, now with independent confirmation it's empirically the strongest phrasing-level class | No |
| Multi-turn/conversational erosion | ADVERSA arXiv:2603.10068 | **Partially new** — distinct from §1.2 row 5 (literal payload-splitting): no instruction is ever reassembled in text; cumulative context softens the *model's own categorization judgment* over many turns | Text-containment holds (still no free-text slot); this is a residual against the *judgment* a category-classifier makes, not the containment mechanism — see §2 below |
| PRBO / token-steering / logprob-prefill attacks | Transluce's Investigator Agents work | **New, and real** — a structural attack on API-level logprob access + forced token prefill, not on prompt text at all | Out of scope for `contain_untrusted_text()`; this is a capability/API-surface concern (belongs with AUDIT-MATRIX-001 F3/F4-style findings, daemon boundary per SPEC-SECURITY-002 §3.2) |
| Multi-agent/segmented-subagent propagation | Pliny's "BT6" framing; generalizes Prompt Infection (already cited in §1.1) | No — already covered | No |
| Meta-jailbreak / reassurance framing | Same delimiter/frame-confusion family | No — §1.2 row 10 | No |

**Verdict, stated as precisely as the evidence supports:** no documented case, from Pliny's own public
corpus/commentary or the academic red-teaming literature surveyed, defeats a schema-constrained/closed-
enum defense of the kind SPEC-SECURITY-002 §4 already specifies. This is not because such a defense is
proven unbreakable in general — every source in SPEC-SECURITY-002 §1.1 is explicit that no defense is
provably complete — it is because **the entire field's red-teaming targets free-text-output systems**
(chatbots producing harmful prose), which is a different attack surface than "can attacker-controlled
text ever occupy a slot that gets composed into a future prompt at all." Two real, honest gaps found:

1. **Multi-turn erosion** is a residual not named in SPEC-SECURITY-002 §5. It doesn't defeat the "no
   free-text slot" property, but it can degrade a *judgment call* a categorization step makes over a
   long session (e.g., `_categorize_error()`'s enum choice itself, if that categorizer is ever backed
   by an LLM rather than a closed rule set — today it is not, per SPEC-SECURITY-002 §4.3, which is
   exactly why this residual is currently low-severity: forge's categorizer is a deterministic rule,
   not a model call, so there's no judgment to erode. This must stay true as a design invariant, not
   an accident — see §3.4.
2. **PRBO/token-steering** is real and structural, but it's an attack on the *model API surface*
   (logprobs, forced prefill), not on forge's prompt-construction code. It's out of scope for this
   doc's containment layer and belongs with the daemon-side capability boundary (AUDIT-MATRIX-001
   F3/F4, SPEC-SECURITY-002 §3.2's "action/capability containment" bucket) — named here so it isn't
   silently dropped, not solved here.

---

## 2. Why "mechanical and mathematical" beats "semantic" — restated precisely for this doc

The Director's framing ("more mechanical and mathematical to reduce scope") maps exactly onto the
distinction SPEC-SECURITY-002 §1.1 already established from primary sources, restated in the terms
that matter for the Rust decision:

- A **semantic** gate (a regex denylist, an LLM classifier, a phrase list) makes a *guess* about intent
  from content. Every guess-based gate in the literature — Anthropic's own RL-trained, red-teamed
  classifier included — has a non-zero false-negative rate (Anthropic's own reported floor: 1% ASR
  under adversarial search, the best-defended system found in any source cited).
- A **mechanical/structural** gate makes certain states **unrepresentable** — not unlikely, not flagged,
  *impossible to construct*. `contain_untrusted_text()`'s core idea (no free-text field reaches a
  prompt-construction surface) is already this category in SPEC-SECURITY-002 §4. Its one weakness,
  named honestly in that doc's own §4.4 and §6: in Python, "no free-text field reaches a prompt surface"
  is enforced by **convention + a best-effort lint**, because Python has no compile-time taint tracking.
  A caller who ignores the convention and writes `f"{fragment.raw_text}"` into a prompt string compiles
  and runs fine. The gate is mechanical in *design* but not mechanical in *enforcement*.
- **This is precisely the gap Rust closes**, and precisely why "mechanical and mathematical" is not a
  slogan here — it's a specific, buildable property: make the illegal state a **type error**, not a
  runtime check, not a lint suggestion. §3 below specifies exactly how, using patterns already proven
  in the OSS Rust ecosystem (researched fresh this session, not assumed) and in our own proprietary
  Rust codebase (keel-core's `gates.rs`, already shipped and tested this session).

This is also the honest answer to "are we better than cline/opencode/agy at giving users control over
their AI experience": none of those three tools' actual configuration surfaces (checked this session —
cline's tool contract is enforced by the driving model's compliance, not by cline itself; opencode has
no comparable permission-tier system found; agy is a wrapper with no independent containment layer)
expose anything like Claude Code's `hard_deny`/`soft_deny`/`allow`/`environment` tiering, and none of
them make their containment guarantees load-bearing at compile time. Matching Claude Code's *tiering
concept* (§3.3) while exceeding it on *enforcement strength* (compile-time vs. runtime-classifier) is
the concrete, falsifiable target — not a marketing claim.

---

## 3. Rust architecture — patterns to steal, not dependencies to add

Per Director instruction: **zero new external crates**. Everything below is a *pattern* researched
from OSS (cited), reimplemented as forge's own proprietary code — the same policy CLAUDE.md prime
directive 4 already applies to the Python codebase (e.g. `security.py`'s own docstring: encoding-anomaly
detection "ported from `logicalworks-/engine/membrane_sanitize.py`... re-implemented, not imported").

### 3.1 Reuse, don't reinvent: keel-core's `SafetyGate` trait + Kleene logic

`~/keel/keel-core/src/gates.rs` (shipped and tested this session, PR #15 merged) already has the
exact shape forge's Rust core needs for its L1-L5 layered checks:

```rust
pub trait SafetyGate {
    fn name(&self) -> &'static str;
    fn evaluate(&self, ctx: &GateContext) -> Result<Kleene>;
}
```

with `Kleene::{True, False, Unknown}` — `Unknown` on parse failure or ambiguous input, **fails closed**
(verified this session: server.rs's `execute_run` was fixed specifically so `Unknown` never gets
silently treated as success). This is directly reusable as an *idiom* for forge's Rust
`SecurityLayer` trait — one canonical "gate" shape across our proprietary Rust stack (keel = daemon-
side deterministic gates; forge = harness-side AI-reasoning gates; same trait shape, different
`GateContext` fields, per the daemon/harness split SPEC-SECURITY-002 §3.2 already established). This
is not importing keel-core as a dependency (forge and keel remain architecturally separate per that
split) — it's adopting the same *trait pattern* by hand, the same way membrane_sanitize.py's
encoding-anomaly signal was reimplemented rather than imported.

Honest caveat, checked directly this session: keel's `TaintGate` is **not** actual data-flow taint
tracking — its `ctx.untrusted_input_to_script: bool` is a caller-supplied flag, not something the gate
computes from the AST. Do not cite it as a taint-tracking precedent; it's a Kleene-logic precedent
only. The real taint-tracking mechanism forge needs comes from §3.2, not from keel.

### 3.2 The compile-time containment primitive: `Tainted<T>` / `Trusted<T>`

Researched pattern: the `untrusted_value` crate's `UntrustedValue<T>` newtype — a private inner field,
with the *only* way to extract a plain `T` being `.sanitize_with(fn) -> Result<Clean, Error>`. Because
the field is private, no code outside the module can compile a path that uses the raw value without
going through a sanitizer. This is the general Rust **newtype pattern** (a zero-cost, privacy-enforced
validation barrier), not a novel invention.

Forge's own version (proprietary, hand-written, no dependency on `untrusted_value` itself):

```rust
pub struct Tainted<T>(T);          // no public constructor outside this module except from raw I/O
pub struct Trusted<T>(T);          // the ONLY thing a prompt-construction surface accepts

impl Tainted<String> {
    pub fn raw(&self) -> &str { &self.0 }         // for logs/debugging ONLY — no path to PromptSafe
    pub fn contain(&self) -> ContainmentResult { ... }   // the only way "out" toward a prompt
}

pub enum ContainmentResult {
    Safe { category: Category, risk_score: f32 },   // Category: closed enum, e.g. TimeoutHandling | PermissionErrors | ...
    Quarantined { risk_score: f32 },                  // no text field AT ALL — nothing to leak
}

pub struct PromptFragment {
    content: Trusted<String>,      // constructor requires a Trusted<String> — Tainted<String> doesn't satisfy the type
}
```

A call site that tries to build `PromptFragment { content: some_tainted_value }` **fails to compile** —
type mismatch, not a lint warning, not a runtime check that a forgotten call site might skip. This
directly closes SPEC-SECURITY-002 §4.4's own named gap: "Python doesn't have the taint-tracking to do
better cheaply." Rust does, via this pattern, at zero runtime cost.

### 3.3 L1 path safety: capability objects, not a denylist — closes the cline-credential gap directly

The `.cline/data/settings/settings.json` miss (§0.1) is a **denylist-shape** bug: `SENSITIVE_READ_PATHS`
enumerates known-bad paths, and anything not enumerated is implicitly allowed. `cap-std` (Bytecode
Alliance, the production foundation of Wasmtime's WASI sandboxing) inverts this: a `Dir` capability is
scoped to a root; every open call is *relative to that capability* and there is no API that accepts an
absolute or escaping path at all. Nothing is "checked and rejected" — the illegal access **has no
function to call**.

Forge's version: a `SandboxRoot` capability type, constructed once per agent run from `cwd`/`sandbox_dir`,
with `.open(relative_path) -> io::Result<File>` as the *only* filesystem entry point exposed to tool
handlers. There is no `security::_check_path_safety(path, cwd)` function to forget to call, because
there is no other way to open a file. This is strictly stronger than an allowlist-of-safe-paths (which
would just move the same enumeration problem to the other side) — it's "the capability doesn't exist
to escape," matching cap-std's own framing exactly. Sensitive-path awareness (today's `SENSITIVE_READ_
PATHS`/`SENSITIVE_WRITE_PATHS`) becomes a secondary, defense-in-depth check *inside* `SandboxRoot::open`
for defense against symlink escapes and misconfigured roots — not the primary containment mechanism.

### 3.4 The permission-tier system — Anthropic's own SDK shape, matched exactly

Researched: Anthropic's TS/Python agent SDK exposes permission decisions as a closed discriminated
union: `{behavior: "allow", updatedInput?, updatedPermissions?}` | `{behavior: "deny", message,
interrupt?}`, with `updatedPermissions` persisting a learned rule at `localSettings`/`projectSettings`/
`userSettings` scope — i.e. Claude Code's own `hard_deny`/`soft_deny`/`allow`/`environment` tiering
*is* this shape, just documented at the settings-file layer rather than the SDK-type layer.

Forge's Rust equivalent — same shape, our own enum, matching Anthropic's ergonomics 1:1 conceptually
without depending on their SDK:

```rust
pub enum PermissionDecision {
    Allow { updated_input: Option<ToolInput> },
    Deny  { reason: DenyReason, interrupt: bool },   // DenyReason: closed enum, not a free-text message
}

pub enum PolicyTier { HardDeny, SoftDeny, Allow, Environment }
```

`HardDeny` rules are unconditional (no `Allow` or explicit-intent override can clear them — same
semantics as Claude Code's own tiering). `SoftDeny` can be overridden by an `Allow` exception or by
**explicit, specific** user intent in the current task (matching Claude Code's own documented rule:
"general requests don't count as explicit intent... asking to 'clean up the repo' doesn't authorize
force-pushing, but asking to 'force-push this branch' does" — forge's version of this check is a typed
comparison against the task string's specificity, not a semantic judgment call, to keep it mechanical).
`Environment` entries define what counts as "internal" vs. an exfiltration target for L2 (network
egress) — today's `_NETWORK_CMD_PATTERNS` blanket-blocks `curl`/`wget`/etc. with no trusted-destination
concept at all; this is the layer that would let a forge agent legitimately `curl` an internal,
Director-declared-trusted endpoint without loosening the block for everything else.

**This is the concrete "give users control over their AI experience" deliverable** — a real, typed,
persistable policy surface, not a fixed denylist a user cannot extend without editing forge's own
source.

### 3.5 Tool definition ergonomics — matching "as seamless as Anthropic's SDK"

Researched: `rig`'s `Tool` trait (typed input/output via Serde, compiler-checked schema, no hand-rolled
JSON-schema strings) and Anthropic's own SDK (`tool(name, description, schema, handler)` — one call,
inferred typing) are the ergonomics bar. Forge's Rust `ToolSpec` becomes a trait:

```rust
pub trait Tool {
    type Input: DeserializeOwned + JsonSchema;
    type Output: Serialize;
    fn name(&self) -> &'static str;
    async fn call(&self, input: Self::Input, ctx: &SandboxRoot) -> Result<Self::Output, ToolError>;
}
```

— the `ctx: &SandboxRoot` parameter is not incidental: per §3.3, a `Tool` implementation *cannot* touch
the filesystem without being handed the capability, so the type signature itself documents and enforces
containment, matching §3's overall thesis (illegal states unrepresentable, not merely checked).

### 3.6 Agent loop shape — `swiftide`'s lifecycle-hook framing

`swiftide`'s "loop over LLM calls, tool calls, and lifecycle hooks until a final answer" maps directly
onto forge's existing evolution-engine step loop (`gather → compile → reason → refute → ledger →
advance → stop`, per the lgwks-side R6.5 step-seam split already in flight on a separate thread — not
this doc's concern, but worth naming as the same idiom appearing on both sides of the daemon/harness
split). Adopt named lifecycle-hook stages (`PreToolUse`-equivalent, `PostToolUse`-equivalent) as
first-class loop stages in the Rust agent core, each returning a `PermissionDecision` (§3.4) — this is
also where Claude Code's own hook model (`PreToolUse`, `PostToolUse`, `PermissionRequest`) gets matched
conceptually, again without depending on it.

---

## 4. Phased delivery — honest sequencing, not a big-bang claim

A full rewrite of forge-sdk's agent loop, all tool adapters, the eval harness, and the audit chain in
one pass is not credible to promise and would repeat the exact failure mode SPEC-SECURITY-002 §0 and
this session's forge-sdk PR history already show (partial-completion-over-claim, false-green). Phased:

**Phase 0 (immediate, Python, no Rust yet — do this regardless of Rust timeline):**
- Migrate `verifiers/__init__.py`'s `SemanticCheck` (ADVERSARIAL-REPORT.md CRITICAL-002) off the
  delimiter-wrapper and onto `contain_untrusted_text()`/`ContainmentResult`, closing the live
  inconsistency named in §0.3. Cheap, immediate, no Rust dependency.
- Add `.cline/`, `.cursor/`, and a generalized `*/settings/*credential*|*apikey*|*token*` pattern
  family to `SENSITIVE_READ_PATHS` as a stopgap — explicitly labeled as a stopgap, not the fix, per
  §3.3's point that denylists are the wrong shape long-term.

**Phase 1 (Rust, first crate — the highest-value, smallest-surface target):**
- New crate `forge-core-security`: `Tainted<T>`/`Trusted<T>` (§3.2), `ContainmentResult`/`Category`
  enum, and the `SafetyGate`-trait-shaped L1-L3/L5 checks reimplemented as pure functions. This is
  exactly the layer SPEC-SECURITY-002 §3.3 already identified as the best first Rust candidate ("pure
  function-shaped... zero Python-only dependencies") — that analysis doesn't change, only the timing
  decision does. Ships as a Python-callable module initially (PyO3-free — a CLI subprocess boundary or
  a simple JSON-in/JSON-out pipe, to avoid taking on a new build-toolchain dependency prematurely;
  revisit PyO3/FFI only if subprocess latency proves material, measured, not assumed).
- `SandboxRoot` capability type (§3.3) as part of the same crate, since path safety and text
  containment are both "make illegal states unrepresentable" and share the crate's reason for existing.

**Phase 2 (Rust, agent core):**
- `Tool` trait (§3.5), `PermissionDecision`/`PolicyTier` (§3.4), and the lifecycle-hook loop (§3.6) —
  this is the actual agent-loop rewrite, gated on Phase 1 landing and being dogfooded against real
  forge tasks first.

**Phase 3 (Rust, full parity):**
- Port remaining tool adapters, the eval harness, and the audit chain. Not scoped in detail here —
  revisit once Phase 1-2 are proven, per the same "don't schedule what you haven't earned visibility
  into" discipline SPEC-SECURITY-002 §3.3 applied to the original no-Rust-yet call.

Python and Rust cores coexist during this migration (the Python CLI shells out to the Rust security
crate starting Phase 1); this is not a flag day. Each phase has its own acceptance gate (§5) before the
next starts.

---

## 5. Acceptance criteria

- Phase 0: `tests/test_security_containment.py`-style adversarial cases (SPEC-SECURITY-002 §6 table)
  re-run against `verifiers/__init__.py`'s migrated `SemanticCheck`, not just `engine.py`. The
  `.cline/`-class stopgap path addition has its own regression test asserting the exact case found
  this session (`cat ~/.cline/data/settings/settings.json` → BLOCKED).
- Phase 1: a real adversarial suite (reuse `~/forge/attack_deepseek.py`'s harness shape, already proven
  this session against the Python agent) run against the Rust crate's `Tainted`/`Trusted` boundary,
  asserting (a) the 10-case table from SPEC-SECURITY-002 §6 all pass, and (b) at least one test that
  *attempts* to construct a `PromptFragment` from a `Tainted<String>` directly and asserts it is a
  **compile error** (a `trybuild`-style negative-compilation test, or documented manually if that
  tooling isn't already available — do not claim this without an actual failed-build artifact).
- No phase is reported "done" without the same evidence bar this session applied to keel: real commands
  run, real output pasted, not a self-report.

---

## 6. Chunks for agent dispatch (`forge run`)

Each chunk below is scoped to be independently implementable and verifiable, per the "bounded prompts
land, over-spec'd stall" lesson already logged in memory. Dispatch via `forge run "<task>" --provider
<p> --model <m> --cwd <sandbox-dir>` into an isolated worktree per chunk, not the shared checkout.

1. **P0-A**: Migrate `SemanticCheck` (`src/forge_sdk/verifiers/__init__.py`) to use
   `contain_untrusted_text()`/`ContainmentResult` instead of the delimiter-wrapper, matching how
   `engine.py` already consumes it. Add a regression test mirroring
   `tests/harness/test_engine.py::test_step_sanitizes_injection_payload_in_error` for this call site.
2. **P0-B**: Add `.cline/`, `.cursor/`, `*/settings/*credential*|*apikey*|*token*|*secret*` patterns to
   `SENSITIVE_READ_PATHS` in `security.py`, with a regression test asserting the exact
   `cat ~/.cline/data/settings/settings.json` case is now blocked. Label the commit message as an
   explicit stopgap per §4 Phase 0, not a structural fix.
3. **P1-A**: Scaffold `forge-core-security` as a new Cargo crate (workspace member, no new external
   crates — `std` only where possible; if a crate is genuinely needed, e.g. `serde`/`serde_json` for
   the JSON-in/JSON-out boundary, name it explicitly and flag for Director approval per CLAUDE.md
   prime directive 4, do not silently add it). Implement `Tainted<T>`/`Trusted<T>` (§3.2) and
   `ContainmentResult`/`Category` with unit tests covering the SPEC-SECURITY-002 §6 ten-case table.
4. **P1-B**: Implement `SandboxRoot` (§3.3) in the same crate with unit tests covering: legitimate
   relative access, absolute-path rejection, symlink-escape rejection, and the temp-dir allowance
   (mirroring `_temp_roots()`/`_is_within_temp_dir()`'s existing Python behavior for parity).
5. **P1-C**: Wire `forge-core-security` into the Python CLI via a subprocess JSON pipe (documented
   protocol: request `{op, args}` → response `{verdict, ...}` on stdin/stdout), replacing
   `_check_command_safety`/`_check_path_safety`'s internals while keeping their existing call sites'
   Python signatures stable (no breakage to `shell.py`'s current callers).

Each chunk's agent must run against real tests (not mocked) before being reported complete, per
AUDIT-MATRIX-001's own meta-finding that the existing adversarial suite's biggest gap was testing mocks.
