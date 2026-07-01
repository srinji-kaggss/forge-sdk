# Changelog

All notable changes to forge-sdk are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); versions follow semver.

## [0.7.0] — 2026-07-01

### Added — Human Experience (L1-L5 layered architecture)

**L5b: Session Recovery**
- `forge run --resume <id>`, `--checkpoint-dir`, `--max-checkpoints`, `--list-sessions`
- `SessionState` checkpoint save/restore to `~/.forge/checkpoints/` (JSON)

**L5a: Permission Gate**
- `forge run --permission-mode yolo|interactive|plan`
- Strategy registry pattern (`PermissionGate` + `PermissionStrategy` protocol)
- `ActionClassification` enum (SAFE, LOCAL_WRITE, DESTRUCTIVE, NETWORK_OUT, NETWORK_IN, EXEC, GIT_HISTORY)
- Anti-slop hard gates (active in all modes): no-edit-without-read, must-add-test-for-fix, no-blind-snapshot, no-test-deletion-without-replacement

**L4: Honest Termination**
- 5 distinct break paths with truthful `failure_reason` (model-auth, context-exhausted, usage-limit, convergence, max-steps)
- Previously: model-auth failures were caught, discarded, and reported as "Max steps reached"

**L3: Typed Event Stream**
- 11 event types: `RunStartEvent`, `ThoughtEvent`, `ActionEvent`, `ObservationEvent`, `TokenUsageEvent`, `VerificationEvent`, `FileEditEvent`, `StateUpdateEvent`, `DecisionEvent`, `RunEndEvent`, `RunErrorEvent`
- `Renderer` protocol: `TextRenderer` (streaming ANSI) + `NDJSONRenderer` (machine pipe)
- `forge run --output-format text|json|stream-json`
- ADR-1: Single event stream consumed by all human/machine surfaces

**L2: Moat Surface**
- `--verify-command`, `--no-verify`, `--max-tokens`, `--max-cost`, `--sandbox`
- `EVIDENCE_TYPE_MAP` (5-gate → 10-evidence taxonomy on `VerificationEvent`)
- `change_manifest` on `RunEndEvent` for CI/CD pipeline consumption
- Correlation keys (`trace_id`, `run_id`, `model`, `provider`) on every event

**L1: Doctor**
- `forge doctor` with L0-L5 escalation (env, config, install, connectivity, write, model)
- `forge doctor --json` for machine consumption

### Changed
- CLI exit codes: 0=success, 1=run_error, 2=config, 3=model, 4=usage_limit, 5=max_steps
- `failure_reason` field on `AgentResult` (INV-208)
- ANSI styling helpers with `NO_COLOR` support, convenience wrappers
- Guarded Vertex import (silent fallback when `google-genai` not installed)

### Spec
- 801-line `docs/FORGE-EXPERIENCE-SPEC.md`: topological map of every frontier CLI agent (Claude Code, OpenCode, Cline, Aider, Goose, Qwen Code, Codex CLI, Gemini CLI), gap analysis, layered L1-L5 architecture
- 15 hardening amendments from 7 source packs: excellent_code_framework, human_like_corpus_model_os, ai_semantic_rag_pack, okf_dev_role_delta_pack-2, translation_harness_blueprint, debuggable_codebase_okf_2026

### Fixed Issues
- [#65](https://github.com/srinji-kaggss/forge-sdk/issues/65) — forge CLI broken: ImportError on google.genai (guarded import)
- [#56](https://github.com/srinji-kaggss/forge-sdk/issues/56) — [frontier-gap] permission-tiered HITL and lifecycle hooks (L5a)
- [#53](https://github.com/srinji-kaggss/forge-sdk/issues/53) — [frontier-gap] durable run checkpoints, resume, and forkable sessions (L5b)
- [#11](https://github.com/srinji-kaggss/forge-sdk/issues/11) — Failure-Taxonomy countermeasures (partial: L4 honest termination + LoopGuard)
- [#19](https://github.com/srinji-kaggss/forge-sdk/issues/19) — Finish action must include tool output summary (partial: L4 truthful failure_reason)
- [#18](https://github.com/srinji-kaggss/forge-sdk/issues/18) — Ambiguous tasks cause agent to spin (partial: L4 convergence detector)
- [#9](https://github.com/srinji-kaggss/forge-sdk/issues/9) — Keel CI deterministic verification floor (confirmed: all 7 CI jobs green on PR #66)

### Docs
- `PLAYBOOK.md`: repeatable verification & release playbook (3-command quick verify, full CI, release process, observability, test inventory, failure taxonomy, layer map)

## [Unreleased] — targeting 0.6.1 (now shipped as 0.7.0)

Eight PRs open against `main`, none merged yet — this section documents what's
pending Director review, not what's shipped. All found and fixed by dogfooding
forge against real work (semantic-memory-brain, next-gen-browser-engine,
logicalworks- #349 module-coverage debt), not code review.

### Added
- **Vertex AI (Gemini) provider**, rebuilt twice this batch: first as a
  hand-rolled REST client (ADC via `gcloud` subprocess + raw `httpx`), then
  replaced with the official `google-genai` SDK once real dispatches surfaced
  a `finishReason=MALFORMED_FUNCTION_CALL` failure mode the SDK appears to
  avoid (observed once in a side-by-side comparison, not asserted as
  guaranteed). Defaults to `northamerica-northeast1` (Canada-residency
  requirement — `northamerica-northeast2` 400s). (#41, #48)
- **Native provider tool-calling** (`agents/react.py`, all 5 model providers):
  replaces free-text-JSON-then-regex-parse with each provider's real
  function/tool-calling API. `ToolRegistry.to_prompt_schemas()` existed and
  was tested but never called anywhere in the actual agent loop — this wires
  it through. Root-cause fix for the entire class of parsing bugs below,
  not another patch to the parser. (#46)
- **Python-syntax pre-write guard** (`tools/filesystem.py`): `write_file`
  now `ast.parse()`s `.py` content before writing and refuses (with
  line/column/message) if it doesn't parse, same `force=true` escape hatch
  as the existing elision/shrink guards. Found live: a model edit replaced
  two unrelated `\n` escapes with literal newlines while making an
  unrelated correct change, corrupting the file silently. (#47)

### Fixed
- **JSON parser rejected literal control characters in string values**
  (`agents/react.py`): `json.loads()` in strict mode raises on a raw
  newline inside a string — common enough in real model output that it
  caused a byte-identical retry loop (the model's JSON was fine from its
  own perspective). `strict=False` at all three parse-strategy call sites. (#42)
- **`cargo build` verify-gate ran on unrelated Rust repos for non-Rust
  edits** (`agents/react.py`): `_detect_verify_command` triggered on any
  repo with a `Cargo.toml`, regardless of whether an edited file was
  actually `.rs` — unlike the parallel Python-branch check three lines
  below it. A pure doc-review task failed on a pre-existing, task-unrelated
  dependency-fetch error in the repo's *entire* crate. Now scoped to
  `any(f.endswith(".rs") for f in edited_files)`, matching the Python
  branch's existing pattern. (#43)
- **Duplicate file-token regex, same false-positive in two places**
  (`text_tokens.py`, new): `verifiers/__init__.py` and `agents/react.py`
  each independently defined the identical regex for detecting file-path
  mentions in a task description, both with the same blind spot — a
  parenthetical `(e.g. RATIFIED or ...)` parsed as a fake required file
  `"e.g"`. Collapsed into one canonical regex + denylist. (#44)
- **Phantom-edit false-success via a scoped read-only negation**
  (`agents/react.py`): `"Do not edit code. Write docs/X.md."` has an
  unscoped `"Do not edit"` (the word right after it, `"code."`, isn't a
  recognized scoped-tail target), so `_task_implies_edits` returned
  `False` for the *entire* task — disabling the has-edits safety net even
  though the next sentence named a real write target. A real run made zero
  `write_file` calls and still reported `Status: SUCCESS` on the strength
  of its own closing summary sentence. Fixed by deferring to
  `_named_edit_targets()` (already used elsewhere in this file) when an
  unscoped negation is found. The most severe bug found this batch. (#45)
- **Empty model response silently became a `finish` with blank output**
  (`agents/react.py`): live-reproduced via Gemini's own
  `MALFORMED_FUNCTION_CALL` (content empty, no tool_calls at all) — no
  braces for any parse strategy to even attempt, so it fell through to the
  same bottom fallback as a genuine no-braces prose completion. Empty
  content is never a valid finish; now treated as `__parse_failed__`. (#46)
- **Native tool call left no readable trace in message history**
  (`agents/react.py`): a native tool call leaves `response.content` empty,
  so the assistant turn recorded in history was blank — on the next turn
  the model had no way to tell "Tool output: ..." was the result of its
  own prior action, and in a real run this produced a stuck loop
  re-issuing a call the LoopGuard had already blocked. (#46)

## [0.6.0] - 2026-06-30

Named-target coverage detector, INV-201 verification pipeline completion,
held-out validation gate, agent_fn wiring into v5 harness, plus the
phantom-edit fix. 159 tests passing.

### Added
- **Named-target coverage detector** (`agents/react.py`): prototypes the
  mitigation flagged as open work in the 0.5.2 entry below. When an agent
  finishes claiming success, `_missing_named_targets()` diffs the file
  paths the task literally named as edit targets against what was actually
  edited. Advisory only — a mismatch appends a visible `[REVIEW FLAG]` to
  the output and populates the new `AgentResult.named_targets_missing`
  field. (#31)
- **INV-201 verification pipeline** (`agents/react.py`, `verifiers/`):
  formal pipeline with L2 syntactic → L4 static/AST → L5 empirical
  (build/test) → L6 spec-conformance → INV-207 semantic alignment gates.
  SemanticCheck and spec_conformance_check wired into ReactAgent finish
  handler; all evidence collected regardless of individual failures. (#20)
- **Held-out validation gate** (`harness/gate.py`): `ValidationGate` class
  implementing RSEA-style strict keep-better gating. Mutations committed
  only when post-mutation validation score > pre-mutation baseline (not
  ≥). Includes snapshot/rollback for prompt fragments and knowledge. (#33)
- **Agent function wiring** (`harness/runner.py`): HarnessRunner now
  accepts `Agent` (duck-typed) or `agent_fn` callable, with
  `with_react_agent()` classmethod factory. (#34)

### Fixed
- **Phantom edits from blocked/failed tool calls** (`agents/react.py`):
  found live — a `forge run` research task correctly hit the L2
  network-egress block on a `curl` attempt, but the blocked command's own
  stderr redirect (`2>/dev/null`) matched the shell write-pattern regex as
  a file write. Edit extraction now short-circuits on `Tool failed:`
  observations and excludes numeric-fd redirects (`N>`). (#32)
- **Import bugs**: fixed `forge_sdk.harness.security` → `forge_sdk.security`
  in engine.py; removed unused imports across test files.

## [0.5.2] - 2026-06-30

Trust-gate hardening. Found via hands-on dogfooding (a real concurrent
fan-out batch against lgwks issue #349), not code review — each fix has a
regression test exercising the actual failure.

### Fixed
- **False-success on malformed model output** (`agents/react.py`): a
  non-JSON / unparseable model response was silently classified as a
  successful `finish`, producing a "Status: SUCCESS" with zero tool calls
  executed. Parser now returns an explicit `__parse_failed__` sentinel,
  which triggers a bounded corrective retry (2 attempts) before the run
  honestly reports failure. (#28)
- **Read-only safety-net bypass** (`agents/react.py`): `_task_implies_edits()`
  treated a task's own scoping caveats (e.g. "do not modify X.py itself")
  as a blanket read-only signal, disabling the zero-edits-on-an-edit-task
  safety net. Added `_READ_ONLY_SCOPED_TAIL` to distinguish a genuine
  read-only marker from a scoped exclusion naming one other file. (#28)
- **Residual `shell=True` fallback** (`tools/adapters.py`):
  `LgwksToolAdapter` fell back to `shell=True` when `shlex.split` failed on
  unbalanced quotes, reopening a shell-injection path layer L3 was meant to
  close. Now returns a blocked `ToolResult` with a quoting-fix hint instead
  of ever shelling out. (#27)
- **Concurrent-run trace/audit path collision** (`cli/main.py`): `trace_dir`
  and `audit_db` were resolved against the process's real `os.getcwd()`
  instead of the run's `--cwd`, so N concurrent `forge run` invocations
  launched from one shared directory wrote all N runs' traces into one
  shared folder — forensic evidence from a 6-task concurrent batch nearly
  collided. Added `scope_path_to_cwd()`; both paths now resolve against
  `--cwd` when relative. (#29)

### Known open issue (not fixed, tracked)
- Partial-completion over-claim: an agent that completes 1 of 2 named
  edits and silently drops the second can still report full success — the
  existing zero-edits safety net doesn't fire because ≥1 edit did happen.
  See `blackbox2/PLAYBOOK-forge-fanout.md` §9 for the full writeup and the
  prototyped verify-gate mitigation.

## [0.5.1] - 2026-06-30

Defense-in-depth security hardening — 5-layer model (path containment,
network egress block, destructive-command block, prompt-injection
sanitization, sensitive-path allowlist). See GitHub release notes.

## [0.5.0] and earlier

See GitHub releases for v0.5.0 and earlier — this file starts at 0.5.2;
earlier history wasn't backfilled.
