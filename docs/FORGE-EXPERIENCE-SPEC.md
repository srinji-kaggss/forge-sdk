# Forge Human Experience — Implementation Specification

**Based on:** `SEMANTIC-RESEARCH-FRONTIER-CLIS.md` (the topological map)
**Baseline:** forge `main` @ `b417ccf`, branch `exp/human-experience`
**Principle:** Each phase must be independently shippable and not weaken L1/L2 (the forge moat).

---

## Architecture Decision Record (ADR) — the spine

**ADR-1: The event stream is the architectural hinge.** Every human- and machine-facing feature (live TUI, NDJSON output, honest errors, diffs, background, checkpoints) is a *consumer* of a single typed event stream emitted by the agent loop. No separate human path, no separate machine path. One source, many renderers.

**ADR-2: The SDK stays pure; renderers live in the CLI layer.** `ReactAgent.arun()` emits typed events via a `callback(AgentEvent) -> None`. The CLI injects a renderer. The SDK never imports ANSI codes, never writes to stdout, never knows about NDJSON.

**ADR-3: Every error gets an `AgentEvent` before it gets a `break`.** The model-exception path (react.py:1051-1053), convergence break, usage-limit break, and max-steps fallthrough must emit a `RunErrorEvent` or set `failure_reason` *before* exiting the loop — so the human never gets a lie.

**ADR-4: Permission modes are a CLI-layer state machine layered on forge's existing sandbox.** The sandbox is the hard guardrail; the mode is the human's dial. Even `--yolo` cannot escape `sandbox_dir` + destructive-command block + protected paths.

**ADR-5: zero new dependencies (L5 law).** All rendering/event/doctor work uses stdlib only. The pre-existing `ansi.py` scaffold is the sole rendering helper.

---

## Phase 1 — L4: Honest Termination (fix the identity contradiction)

**Goal:** The CLI never lies about *why* a run failed. A bad API key says "bad API key," not "Max steps reached."

### 1.1 `failure_reason` propagation (type system)

**State:** `AgentResult.failure_reason: str = ""` already exists on the worktree (`types.py:68`). But the loop never sets it.

**Five break paths to fix in `react.py`:**

1. **Model-exception path (L1051-1053):** `except Exception as e: log.error(...); break` → must set `trace.failure_reason = f"model_error: {str(e)}"` and return `AgentResult(failure_reason=...)` immediately (not fall through to "Max steps reached").

2. **Usage-limit break (L1044-1046):** `if self._limiter.check(): break` → must set `trace.failure_reason = "usage_limit_exceeded"` and return early.

3. **Convergence break (L1002-1008):** `break` on too many nudges → must set `trace.failure_reason = f"convergence_failure: {nudges} nudges ignored"` and return early.

4. **Max-steps fallthrough (L1385-1400):** Already has `trace.failure_reason = "Max steps reached"` → must propagate it into `AgentResult(failure_reason=trace.failure_reason)`.

5. **Finish-branch (L1373-1383):** Already computes local `failure_reason` string → must pass it to `AgentResult(failure_reason=failure_reason)`.

### 1.2 CLI exit codes (main.py:cmd_run)

After printing result summary, add:
```python
if not result.success:
    if result.failure_reason:
        print(f"Reason: {result.failure_reason}", file=sys.stderr)
    sys.exit(1)
```

### 1.3 `forge doctor` subcommand (new file: `cli/doctor.py`)

Checks:
1. Python version >= 3.13
2. Config file exists / valid TOML
3. Provider auth — lightweight model ping, catch auth errors human-readably
4. Trace/audit directory writable
5. Working directory

Output modes: text table (PASS/FAIL/WARN with icons + ANSI) and `--json` (NDJSON). Exit code 1 if any FAIL.

---

## Phase 2 — L3: The Event Stream (the architectural hinge)

**Goal:** One typed event spine feeds all renderers. The human TUI and the machine NDJSON pipe are *the same mechanism*.

### 2.1 Event types (new file: `agents/events.py`)

Typed dataclasses with a `type` discriminator:
- `RunStartEvent` — task, model, provider, run_id
- `ThoughtEvent` — the agent's reasoning text
- `ActionEvent` — tool name + input params
- `ObservationEvent` — tool result (content, is_error flag)
- `TokenUsageEvent` — prompt/completion/total tokens + cost
- `VerificationEvent` — gate name, status (passed/failed), detail
- `FileEditEvent` — path, action (create/modify/delete), diff
- `RunEndEvent` — success, failure_reason, total_steps, total_tokens, edits_made
- `RunErrorEvent` — error message, error_type (model_error|usage_limit|convergence|max_steps)

### 2.2 Event emitter in ReactAgent

New constructor param: `event_callback: Callable[[AgentEvent], None] | None = None`

Emit at each lifecycle point in `arun()`:
| Location | Event | When |
|---|---|---|
| arun() entry | RunStartEvent | Run begins |
| After model response parsed | ThoughtEvent | Every step |
| After tool call dispatched | ActionEvent | Every tool call |
| After tool returns | ObservationEvent | Every tool call |
| After response.usage read | TokenUsageEvent | Every model call |
| After all_edits.append() | FileEditEvent | Every file edit |
| After each verification gate | VerificationEvent | Finish path |
| Before any early return | RunErrorEvent | Fatal errors |
| Final return | RunEndEvent | Run ends |

Fire-and-forget: if callback is None, skip. Callback exceptions are caught and ignored (event emission failure must not break the agent loop).

### 2.3 Renderers (new file: `cli/renderers.py`)

**TextRenderer:** Human-readable streaming with ANSI. Shows per-step thought/action/observation with timestamps, verification gates inline, and a final summary bar.

**NDJSONRenderer:** One JSON object per event line — machine-readable pipe format.

Both implement `Renderer` protocol: `on_event(event) -> None`, `on_end(exit_code) -> None`.

### 2.4 CLI output-format flag (main.py)

```
--output-format text|json|stream-json  (default: text)
--print  (suppress all live output, print only final result — like claude -p)
```

`cmd_run` creates the renderer and passes it as `event_callback`. For `--print`, pass `None` (legacy behavior: print `---`, block, print summary).

---

## Phase 3 — L2 Exposure: Surface the Moat

**Goal:** Make forge's existing verification/sandbox capabilities visible at the CLI.

### 3.1 CLI flags (main.py:run_parser)

```
--sandbox DIR           Restrict file writes to this directory
--verify-command CMD    Build/test command to gate SUCCESS
--no-verify             Skip empirical verification
--max-tokens N          Context window token limit (default 32000)
--max-cost N            Max cost in USD before aborting (default 1.0)
--compaction MODE       truncate|agentic (default: truncate)
```

### 3.2 cmd_run plumbing

Pass each flag through to `ReactAgent(...)` constructor. The `--sandbox` flag also feeds `PermissionGate` in Phase 4.

---

## Phase 4 — L5a: Permission Mode (graduated trust dial)

**Goal:** A 3-mode permission state machine layered on forge's sandbox. The human dials trust per-task.

### 4.1 Modes

| Mode | Flag | Behavior |
|------|------|----------|
| `default` | (default) | Auto-allow reads + search + shell (sandboxed); ask before writes |
| `acceptEdits` | `--permission-mode acceptEdits` | Auto-allow all writes inside sandbox + all reads; ask for shell outside sandbox |
| `yolo` | `--permission-mode yolo` | Run everything; sandbox + destructive-command block + protected paths still enforce |

### 4.2 PermissionGate (new file: `cli/permissions.py`)

```python
class PermissionGate:
    mode: PermissionMode
    sandbox_dir: Path | None
    protected_paths: list[Path]  # ~/.ssh, ~/.aws, ~/.config/forge

    def is_protected(path: Path) -> bool   # Is path in protected set?
    def can_auto_allow(tool, tool_input, cwd) -> bool  # Auto-run or ask?
```

**Hard guardrail:** Protected paths are NEVER auto-allowed in ANY mode. This survives even `--yolo`.

**Classification logic:**
- YOLO: everything except protected paths → auto
- ACCEPT_EDITS: reads/search → auto; writes inside sandbox → auto; writes outside sandbox → ask; shell → ask (unless inside sandbox cwd)
- DEFAULT: reads/search → auto; writes + destructive shell → ask

**Note:** The interactive ask-gate (prompt for approval) is deferred to a later iteration. This phase ships the classification + hard-guardrail; denied actions get a "Permission denied in {mode} mode" observation and the agent must recover.

### 4.3 CLI integration

```
--permission-mode default|acceptEdits|yolo  (default: default)
```

`PermissionGate` is passed to `ReactAgent` constructor. The agent checks `can_auto_allow()` before each tool call.

---

## Phase 5 — L5b: Session Continuity (background + resume)

**Goal:** Sessions survive crashes. Multi-hour tasks don't hold the terminal hostage.

### 5.1 SessionStore (new file: `cli/session.py`)

SQLite-free: JSON files in `~/.forge/sessions/`. Each session is a `Session` dataclass:
- session_id, task, model, provider, cwd, created_at, status, result

Operations: `save()`, `load(session_id)`, `list_sessions(status=None)`, `delete(session_id)`.

### 5.2 CLI commands (main.py)

```
forge session list [--status running|success|failed|crashed]
forge session resume <session_id>
forge session delete <session_id>
```

### 5.3 cmd_run integration

On run start: `store.save(Session(status="running", ...))`
On run end: `session.status = "success"|"failed"; store.save(session)`
On crash (unhandled exception): the session stays "running" — visible in `forge session list --status running`.

`forge session resume <id>` reloads the session metadata. Full message-history resume (replaying conversation) is deferred to a later iteration — this phase ships metadata durability.

---

## Files Changed / Created — Summary

| File | Action | Phase |
|------|--------|-------|
| `agents/types.py` | Modified (already staged: `failure_reason` field) | L4 |
| `agents/events.py` | **NEW** — typed event dataclasses | L3 |
| `agents/react.py` | Modified — event emission + honest termination | L3 + L4 |
| `cli/ansi.py` | Already created (pre-existing scaffold) | L3 |
| `cli/doctor.py` | **NEW** — `forge doctor` | L4 |
| `cli/renderers.py` | **NEW** — TextRenderer + NDJSONRenderer | L3 |
| `cli/permissions.py` | **NEW** — PermissionGate state machine | L5a |
| `cli/session.py` | **NEW** — SessionStore | L5b |
| `cli/main.py` | Modified — new CLI flags, subcommands, renderer injection | L2-L5 |

### Dependency graph

```
types.py (failure_reason)      ← Phase 1 (already staged)
    ↓
react.py (honest termination)  ← Phase 1
    ↓
events.py                      ← Phase 2 (no deps on CLI)
    ↓
ansi.py (already exists)       ← Phase 2
    ↓
renderers.py                   ← Phase 2 (depends on events + ansi)
main.py (event injection)      ← Phase 2
    ↓
doctor.py                      ← Phase 1 (independent, but uses ansi)
main.py (doctor subcommand)    ← Phase 1
    ↓
main.py (L2 flags)             ← Phase 3
permissions.py                 ← Phase 4
session.py                     ← Phase 5
```

---

## Acceptance Criteria (per phase)

### Phase 1 (L4): Honest Termination
- `forge run` with invalid API key prints FAILED + Reason: model_error (not "Max steps reached")
- `forge run` exits code 1 on failure, 0 on success
- `forge doctor` checks config/auth/health
- `forge doctor --json` emits NDJSON
- `AgentResult.failure_reason` is "" on success, non-empty on failure
- All 5 break paths set unique failure_reason

### Phase 2 (L3): Event Stream
- `forge run --output-format stream-json` emits one JSON object per event line
- `forge run` (default) shows live step-by-step with ANSI
- `forge run --print` prints final summary only (legacy mode)
- Piped output auto-disables ANSI (NO_COLOR + isatty check)
- Events never throw — agent loop continues if renderer crashes

### Phase 3 (L2): Surface the Moat
- `forge run --sandbox /tmp` restricts writes
- `forge run --verify-command "cargo build"` gates SUCCESS on build
- `forge run --no-verify` skips empirical verification
- `forge run --max-tokens 16000` caps context window
- Verification gates render live in text output

### Phase 4 (L5a): Permission Mode
- `forge run --permission-mode yolo` auto-runs all non-protected tool calls
- Protected paths (~/.ssh, ~/.aws, ~/.config/forge) NEVER auto-allowed in any mode
- `forge run --permission-mode acceptEdits` auto-allows reads + sandboxed writes
- `forge run --permission-mode default` auto-allows reads only

### Phase 5 (L5b): Session Continuity
- `forge session list` shows recent sessions
- Sessions survive a `forge run` crash (status stays "running")
- `forge session delete <id>` removes a session

---

## Constraints

- **Zero new dependencies.** Stdlib only.
- **SDK layer never imports CLI code.** Events live in `agents/`; renderers live in `cli/`.
- **Event emission is non-breaking.** If no callback is registered, the loop behaves identically to today.
- **All existing tests must pass.** The refactored termination paths return the same fields; `failure_reason=""` is the default.

---

## §14: Hardening Amendments — sourced from 6 external research packs

These amendments harden the spec against formal engineering axioms, neuro/cognitive architecture contracts, verifiable correctness frameworks, documentation topology models, and semantic RAG patterns. Each amendment cites its source pack.

### H1 — PermissionGate must classify on blast-radius, not just tool name

**Source:** `okf_dev_role_delta_pack-2/concepts/agents/senior_engineer_state_machine.md`

**Amendment to §4.2 (PermissionGate):** The `can_auto_allow()` must factor in more than the tool name. The senior engineer state machine defines `s_t = [task_type, ambiguity, blast_radius, coupling, novelty, privilege, data_sensitivity, ci_mutation, oracle_strength, rollback, observability, owner]`. Add a `PermissionContext` that captures this surface:

```python
@dataclass
class PermissionContext:
    tool: str
    tool_input: dict
    cwd: Path
    task_type: str = ""          # "fix" | "feature" | "refactor" | "unknown"
    touches_auth: bool = False   # Does this touch auth/PII?
    touches_config: bool = False  # Does this touch CI/CD/infra/config?
    touches_production: bool = False
    reversibility: str = "unknown"  # "reversible" | "risky" | "irreversible"
    evidence_available: bool = False  # Is there a test/build to verify?

# Hard constraints — sourced from axiom set A05, A08, A14:
HARD_BLOCK_RULES = [
    no_self_approval,            # AI may not approve its own work
    no_secret_to_untrusted,       # Never write secrets to model prompt
    no_behavior_change_without_test,  # Must have a verifier before changing behavior
]

def can_auto_allow(ctx: PermissionContext) -> bool:
    """Senior-engineer-grade auto-allow classification."""
    # Escalation law: escalate if risk exceeds threshold
    if ctx.touches_auth or ctx.touches_config or ctx.touches_production:
        return False  # Always ask
    if ctx.is_protected_path():
        return False  # Never auto-allow protected paths
    # reversibility gate
    if ctx.reversibility == "irreversible":
        return False
    if not ctx.evidence_available and ctx.mode != PermissionMode.YOLO:
        return False  # No verifier available → do not auto-allow destructive ops
    # ... existing tool classification below
```

### H2 — Event taxonomy must include THINK/ACT/OBSERVE/UPDATE_STATE/DECIDE/PRINT

**Source:** `human_like_corpus_model_os/02_current_stack_failure_matrix.okf.yaml`

**Amendment to §2.1 (Event types):** The current 9 events (RunStart, Thought, Action, Observation, TokenUsage, Verification, FileEdit, RunEnd, RunError) are correct but incomplete. The failure matrix defines a 6-trace-label taxonomy:

```text
THINK        → ThoughtEvent (already present)
ACT          → ActionEvent (already present)
OBSERVE      → ObservationEvent (already present)
UPDATE_STATE → NEW: StateUpdateEvent — agent updates its internal state/memory
DECIDE       → NEW: DecisionEvent — agent chooses among alternatives with rationale
PRINT        → RunEndEvent.output (already present as final output)
```

Add two new events to `events.py`:

```python
@dataclass
class StateUpdateEvent(AgentEvent):
    """Agent updated its internal state (memory, beliefs, plan)."""
    type: str = "state_update"
    kind: str = ""        # "memory_write" | "plan_update" | "assumption_change"
    before: str = ""      # Previous state (abbreviated)
    after: str = ""       # New state (abbreviated)

@dataclass
class DecisionEvent(AgentEvent):
    """Agent decided among alternatives (the 'why' behind the action)."""
    type: str = "decision"
    options: list[str] = field(default_factory=list)  # Alternatives considered
    chosen: str = ""
    rationale: str = ""
    rejected_reasons: list[str] = field(default_factory=list)
```

### H3 — Session must carry structured agent state, not just metadata

**Source:** `human_like_corpus_model_os/08_claude_cli_state_contract.okf.yaml`

**Amendment to §5.1 (SessionStore):** The current `Session` dataclass is metadata-only (session_id, task, model, cwd, status). Hardened to carry the execution contract fields:

```python
@dataclass
class Session:
    # Metadata (existing)
    session_id: str
    task: str
    model: str
    provider: str
    cwd: str
    created_at: float
    status: str

    # Execution contract fields (NEW — from handoff packet template)
    objective: str = ""
    current_phase: str = ""      # "intake" | "context_map" | "risk_model" | "plan" | "patch" | "verify" | "review" | "release" | "learn"
    assumptions: list[str] = field(default_factory=list)
    known_constraints: list[str] = field(default_factory=list)
    files_touched: list[str] = field(default_factory=list)
    commands_run: list[str] = field(default_factory=list)
    evidence: list[dict] = field(default_factory=list)   # [{kind, path, status}]
    unresolved_questions: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    stop_conditions: list[str] = field(default_factory=list)
    result: dict | None = None

    # Execution contract MUST rules (as assertions)
    def validate_execution_contract(self) -> list[str]:
        """Return violations of the execution contract."""
        violations = []
        if self.status == "running" and not self.current_phase:
            violations.append("read_current_task_state_before_action: phase not set")
        if self.commands_run and not self.evidence:
            violations.append("never_hide_failed_commands: commands run but no evidence")
        return violations
```

### H4 — forge doctor must measure documentation quality, not just system health

**Source:** `excellent_docs_okf_ai_codebase_pack/MASTER_OKF_EXCELLENT_DOCUMENTATION_FRAMEWORK.md`

**Amendment to §1.3 (forge doctor):** Add a documentation quality dimension to the doctor checks:

- `forge doctor --docs` — validate documentation topology:
  - README exists and is ≤ 1 page (anti-pattern: false_hub)
  - Module contracts exist for each public module
  - No stale_bridge: doc links resolve to existing code symbols
  - No prose_island: every doc links to code, tests, or requirements
  - No collapsed_layers: how-to, reference, and rationale are separate
  - generated_navmap exists and is fresh

This is not implemented in Phase 1 — it's a future `forge doctor --docs` extension. But the doctor architecture must support pluggable check categories from day one.

### H5 — Verification evidence must map to the 10-evidence taxonomy

**Source:** `excellent_code_framework/README.md` (conservative theorem: 10 evidence types)

**Amendment to §Phase 3 (L2 exposure):** Forge's current verification pipeline checks: syntactic → AST → entity → build/test → spec-conformance → semantic. The excellent_code_framework defines 10 evidence types:

1. grounding evidence
2. type evidence
3. total correctness evidence
4. invariant preservation evidence
5. boundary evidence
6. resource evidence
7. security evidence
8. observability evidence
9. falsifiability evidence
10. locality evidence

When exposing verification results in the CLI (`VerificationEvent`), map forge's internal gates to these evidence types so the human and machine consumer know *what kind* of evidence passed/failed, not just "gate X passed."

```python
EVIDENCE_TYPE_MAP = {
    "syntactic": "type_evidence",       # AST parsing = type correctness
    "entity": "grounding_evidence",     # Entity exists = grounded in codebase
    "build_test": "total_correctness",  # Build+test = correctness evidence
    "spec_conformance": "invariant_preservation",  # Task intent = invariant
    "semantic": "falsifiability",       # Semantic check = can it be wrong?
}
```

### H6 — AIActionGraph: PermissionGate must produce allowed/forbidden/escalation edges

**Source:** `excellent_docs_okf_ai_codebase_pack/TOPOLOGICAL_DOCUMENTATION_MODEL.md` (§4: AI-driven development topology)

**Amendment to §4.2 (PermissionGate):** The PermissionGate must emit not just a boolean `can_auto_allow`, but a typed action classification:

```python
class ActionClassification(Enum):
    MAY = "may"            # Auto-allowed
    MAY_IF = "may_if"      # Auto-allowed only if condition met
    MUST = "must"          # Required action (e.g., verify before merge)
    MUST_NOT = "must_not"  # Hard block
    REQUIRES = "requires"  # Needs human approval
    ESCALATES = "escalates"  # Needs senior/independent review

# PermissionGate.classify() → ActionClassification
# PermissionGate.required_evidence(action) → list[EvidenceType]
```

### H7 — Strategy registry pattern for PermissionGate (not if/elif chains)

**Source:** `ai_semantic_rag_pack/SEMANTIC_SECOND_PASS_OVERVIEW.md` (§4: strategy registry vs hidden if-trees)

**Amendment to §4.2:** Implement PermissionGate as a strategy registry, not if/elif:

```python
class PermissionStrategy(Protocol):
    """A single permission classification rule."""
    def applies(self, ctx: PermissionContext) -> bool: ...
    def classify(self, ctx: PermissionContext) -> ActionClassification: ...
    def required_evidence(self, ctx: PermissionContext) -> list[str]: ...

class PermissionGate:
    """Registry of permission strategies, evaluated in priority order."""
    _strategies: list[PermissionStrategy]

    def register(self, strategy: PermissionStrategy) -> None: ...

    def classify(self, ctx: PermissionContext) -> ActionClassification:
        for st in self._strategies:
            if st.applies(ctx):
                return st.classify(ctx)
        return ActionClassification.REQUIRES  # Default: ask human

# Built-in strategies (registered at init):
# - ProtectedPathStrategy: MUST_NOT for ~/.ssh, ~/.aws, ~/.config/forge
# - AuthSurfaceStrategy: REQUIRES for auth/PII/CI/CD/infra touches
# - IrreversibleActionStrategy: REQUIRES for irreversible operations
# - EvidenceGatedStrategy: MAY_IF evidence exists; REQUIRES if no evidence
# - ReadOnlyStrategy: MAY for reads/search
# - SandboxedWriteStrategy: MAY_IF inside sandbox; REQUIRES outside
```

### H8 — forge doctor must not silently escalate to blackbox

**Source:** `excellent_docs_okf_ai_codebase_pack/AI_DOCS_MANAGER_SPEC.md` (§3: non-negotiable blackbox rule)

**Amendment to §1.3 (forge doctor):** When `forge doctor` tries a model ping for auth validation, it must follow the escalation ladder:

```text
L0_PARSE:   check config file is valid TOML, provider field exists
L1_SYMBOLIC: check if API key env var is set, non-empty
L2_GRAPH:   check if key has expected format (sk-... for OpenAI, etc.)
L3_HEURISTIC: (skip — not applicable)
L4_FUZZY_ML: (skip — not applicable)
L5_BLACKBOX: try a real model ping ← ONLY as last resort, with evidence record
```

The doctor must create an `EscalationRecord` before making any model call:

```python
@dataclass
class EscalationRecord:
    id: str
    from_level: str        # "L0_PARSE"
    to_level: str          # "L5_BLACKBOX"
    reason: str
    blocked_by: list[str]  # What couldn't be done at lower levels
    evidence_refs: list[str]
    allowed_outputs: list[str]
    forbidden_outputs: list[str]
```

### H9 — Privacy boundary: PermissionGate must have an export gate

**Source:** `translation_harness_blueprint/README.md` (v0.2 hardening: MLX + AWS + privacy + bias)

**Amendment to §4.2:** Add a privacy dimension to PermissionGate:

- `--privacy-mode local|governed` (default: local)
- `local`: Model calls stay on local provider only (Ollama/localhost). No data leaves the machine.
- `governed`: Cloud providers allowed, but with `DataExportContract` — the PermissionGate must log what data is being sent and flag any PII/secrets in the prompt before sending.

```python
@dataclass
class DataExportContract:
    """What data is leaving the local trust boundary."""
    provider: str
    model: str
    prompt_tokens: int
    contains_file_contents: bool
    contains_secrets_scan: bool   # True if any secret-like pattern detected
    contains_pii_scan: bool
    export_allowed: bool          # Set by PermissionGate after audit
    export_reason: str = ""
```

### H10 — Spec-driven development: forge must support spec-as-source mode

**Source:** `ai_semantic_rag_pack/SEMANTIC_SECOND_PASS_OVERVIEW.md` (§3: patterns, spec-first rule)

**Amendment to §Future (post-Phase-5):** The spec-driven development (SDD) pattern says specs, not code, are the authoritative description. Forge's `--verify-command` and spec-conformance gate already partially implement this. A future CLI enhancement:

```
forge run --spec path/to/spec.md
```

Where the spec is loaded as the source of truth and the verification pipeline validates against it. This is not in Phase 1-5 scope but informs the verification architecture.

---

## §15: Hardened Dependency Graph (amended)

```
types.py (failure_reason)                       ← Phase 1 (already staged)
    ↓
react.py (honest termination + 6-trace events)  ← Phase 1 + H2 (THINK/ACT/OBSERVE/UPDATE_STATE/DECIDE/PRINT)
    ↓
events.py (10 event types: +StateUpdate, +Decision)  ← Phase 2 + H2
    ↓
ansi.py (already exists)                         ← Phase 2
    ↓
renderers.py (TextRenderer + NDJSONRenderer)     ← Phase 2
main.py (event injection + --output-format)      ← Phase 2
    ↓
doctor.py (L0-L5 escalation + --docs stub)       ← Phase 1 + H4 + H8
main.py (doctor subcommand + exit codes)          ← Phase 1
    ↓
main.py (L2 flags + evidence_type_map)            ← Phase 3 + H5
permissions.py (strategy registry + PermissionContext + ActionClassification)  ← Phase 4 + H1 + H6 + H7
session.py (+ execution contract fields)          ← Phase 5 + H3
    ↓
(Future: privacy_mode.py + DataExportContract)    ← H9 (post-Phase-5)
(Future: spec-as-source mode)                     ← H10 (post-Phase-5)
```

---

## §16: Hardened Acceptance Criteria (amended)

### Phase 1 additions:
- [H4-stub] `forge doctor --docs` is accepted as a valid flag (stub: "docs checks coming in v0.6")
- [H8] `forge doctor` never makes a model call without first checking L0-L1 (config parse → env var check)
- [H8] If L5_BLACKBOX model ping is attempted, an EscalationRecord is created in the trace log

### Phase 2 additions:
- [H2] Event stream emits `StateUpdateEvent` when agent changes its plan/assumptions
- [H2] Event stream emits `DecisionEvent` when agent chooses among tool alternatives

### Phase 4 additions:
- [H1] PermissionGate.classify() accepts PermissionContext with blast_radius fields, not just (tool, input, cwd)
- [H6] PermissionGate.classify() returns ActionClassification enum (MAY/MAY_IF/MUST/MUST_NOT/REQUIRES/ESCALATES), not bool
- [H7] PermissionGate uses strategy registry pattern (list of PermissionStrategy), not if/elif
- [H7] Each PermissionStrategy has `.applies()`, `.classify()`, `.required_evidence()` methods

### Phase 5 additions:
- [H3] Session dataclass carries execution contract fields (objective, phase, assumptions, constraints, evidence, unresolved_questions, next_actions, stop_conditions)
- [H3] `session.validate_execution_contract()` returns list of violations

### Future additions:
- [H9] `--privacy-mode local|governed` flag with DataExportContract
- [H10] `--spec path/to/spec.md` for spec-as-source verification mode

---

## §14-B: Hardening Amendments — debuggable_codebase_okf_2026

**Source pack 7:** `debuggable_codebase_okf_2026` — machine-first blueprint for debuggable codebases under AI-generated code.

### H11 — Failure message contract: failure_reason must be typed with error_code + causal_sentence + state_fingerprint

**Source:** `02_human_debugging/human_debug_layer.okf.md` (§1: Failure message contract)

**Amendment to §1.1 (failure_reason propagation):** The current `failure_reason: str` field is a single string. The debuggable codebase contract requires:

```text
error_code: stable, searchable, documented
causal_sentence: "operation X failed because Y boundary rejected Z"
state_fingerprint: request_id, trace_id, build_id, config_version, feature_flag_state, schema_version
owner_route: module owner + runbook id
```

**Action:** Phase 1 implementation already stores honest string. For v0.6, upgrade `failure_reason` to typed:

```python
@dataclass
class FailureDetail:
    error_code: str          # e.g., "E_MODEL_AUTH"
    causal_sentence: str     # "Model call failed: Illegal header value b'Bearer '"
    state_fingerprint: dict  # {trace_id, run_id, model, provider, step_count, config_version}
    owner_route: str         # "forge_sdk.models.vertex.VertexProvider.complete"
```

**Current state:** Phase 1 uses `failure_reason: str` (acceptable for now). This is noted for future upgrade.

**Anti-pattern caught by this pack:** "No swallowed errors" — forge's pre-fix model-exception path was exactly this anti-pattern (catch, log, discard, lie). Phase 1 fixes this.

### H12 — Agent trace schema: events must carry hypothesis, uncertainty, and risk fields

**Source:** `03_ai_ai_debugging/agent_debug_layer.okf.md` (§Agent action trace schema) + `11_templates/agent_trace.schema.json`

**Amendment to §2.1 (Event types):** The agent trace schema requires:

```json
{
  "step_id": "...",
  "parent_step_id": "...",
  "goal": "...",
  "hypothesis": "...",
  "observation": "...",
  "tool_call": {"name":"...", "args_hash":"...", "result_hash":"..."},
  "file_read": ["..."],
  "edit": [{"file":"...", "span":"...", "reason":"..."}],
  "test": [{"cmd":"...", "status":"pass|fail", "evidence_path":"..."}],
  "uncertainty": [{"claim":"...", "missing_evidence":"..."}],
  "risk": {"blast_radius":"...", "rollback":"..."}
}
```

**Current state:** Phase 2 events.py is close but missing:
- `goal` field on ThoughtEvent
- `hypothesis` field on ThoughtEvent (what the agent believes, not just what it thinks)
- `args_hash` + `result_hash` on ActionEvent/ObservationEvent (hash the tool I/O)
- `uncertainty` list on ObservationEvent (claims with missing evidence)
- `risk` field on ActionEvent (blast_radius, rollback)

**Action:** Add these fields to the existing event types. Low-cost: they're optional fields with defaults, non-breaking.

### H13 — Anti-slop gates: PermissionGate must encode agent anti-slop rules as hard invariants

**Source:** `03_ai_ai_debugging/agent_debug_layer.okf.md` (§AI anti-slop gates)

**Amendment to §4.2 (PermissionGate):** Add these as hard PermissionStrategy rules:

```python
# Anti-slop strategies (always active, regardless of mode):
ANTI_SLOP_RULES = [
    # No edit without read evidence
    ("must_have_read_before_write", "Block writes to files never read in this session"),
    # No fix without regression test
    ("must_add_test_for_fix", "Block bugfix patches that don't include a test change"),
    # No test deletion without replacement invariant
    ("no_test_deletion_without_replacement", "Block deletion of test files without new invariant"),
    # No production behavior change without flag/rollback
    ("must_declare_rollback", "Block behavior changes without rollback route declared"),
    # No dependency upgrade without changelog + SBOM diff + vulnerability scan
    ("must_audit_dependency_change", "Block dependency upgrades without audit evidence"),
    # No snapshot update without semantic reason
    ("no_blind_snapshot_update", "Block test snapshot updates without documented reason"),
]
```

These are **hard invariants** — they apply in ALL permission modes, including `--yolo`. The agent cannot violate them regardless of trust level.

### H14 — Observability: every event must carry correlation keys and cover operational/cognitive/contextual surfaces

**Source:** `05_observability/observability_schema.okf.yaml`

**Amendment to §2.1 (Event types):** The observability schema requires:

1. **Correlation keys on every event:** trace_id, span_id, run_id, model, provider, config_version, schema_version. Currently only RunStartEvent carries these. Every event type should carry correlation_keys as a dict or as individual fields.

2. **Three required surfaces for agent traces:**
   - **Operational:** what tool was called, what returned, tokens used, latency
   - **Cognitive:** what the agent thought, what hypothesis it tested, what it was uncertain about
   - **Contextual:** what files were read, what the blast radius is, what invariants are touched

**Action:** Add `correlation` dict to AgentEvent base class. Ensure events cover all three surfaces.

```python
@dataclass
class AgentEvent:
    type: str
    step: int
    timestamp_ms: float = 0.0
    # H14: correlation keys on every event
    correlation: dict = field(default_factory=lambda: {})
    # Fill with: {trace_id, run_id, model, provider, config_version}
```

### H15 — Change manifest: forge run should output a structured change_manifest at completion

**Source:** `07_ci_cd_gates/change_gate_pipeline.okf.yaml` + `11_templates/change_manifest.yaml`

**Amendment to §Phase 3 (L2 exposure) + RunEndEvent:** The CI/CD pipeline requires every change to declare:

```yaml
change_id:
author_or_agent:
change_type: bugfix|feature|mechanical_refactor|dependency_update|migration|performance|security
intent:
non_goals:
behavior_delta:
blast_radius: {files, symbols, schemas, configs, runtime_paths}
invariants_touched:
tests_added_or_changed:
observability_delta:
rollback:
risk_level:
residual_unknowns:
source_evidence:
```

The RunEndEvent should carry a `change_manifest` field with this structure. The CLI should print it as structured output (or `--output-format json` emits it as JSON).

**Current state:** Phase 2 RunEndEvent has `edits_made: list[str]` — this is the `blast_radius.files` field. The full manifest is deferred to a future phase but the RunEndEvent should grow a `change_manifest: dict | None` field now.

---

## §16-B: Hardened Acceptance Criteria (debuggability additions)

### Phase 1 additions:
- [H11-stub] `failure_reason` string follows causal_sentence format: "operation X failed because Y". Future: typed FailureDetail.

### Phase 2 additions:
- [H12] ThoughtEvent gains optional `goal` and `hypothesis` fields
- [H12] ObservationEvent gains optional `uncertainty: list[dict]` field (claims with missing_evidence)
- [H12] ActionEvent gains optional `risk: dict` field (blast_radius, rollback)
- [H14] AgentEvent base gains `correlation: dict` field (trace_id, run_id, model, provider, config_version)
- [H15] RunEndEvent gains optional `change_manifest: dict | None` field with change_type, intent, blast_radius, rollback, residual_unknowns

### Phase 4 additions:
- [H13] PermissionGate registers ANTI_SLOP_RULES as hard strategies (active in all modes)
- [H13] `no_edit_without_read_evidence` — blocks writes to files never read in session
- [H13] `must_add_test_for_fix` — blocks bugfix patches without test changes
- [H13] `no_test_deletion_without_replacement` — blocks test file deletion without new invariant
