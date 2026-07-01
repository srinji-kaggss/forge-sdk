# Deep Semantic Research — Frontier Coding-Agent CLI Human Experience

**Author stance:** Experience engineer first.
**Date:** 2026-07-01
**Purpose:** Semantically extract what frontier coding-agent CLIs do *well at the human-experience layer*, grounded in their **actual source codebases** (the “semantic brain”), not `--help` surfaces or marketing. Hardened with citations.

---

## 0. Method & Evidence Base

This is not a feature-list comparison. The goal is to extract the **felt experience primitives** — the underlying mechanism and philosophy that make a CLI *feel* good to a human — and pin each to real source evidence.

**How the evidence was gathered:**
1. **Resolved every installed binary** to its real source path (`opencode`, `claude`, `codex`, `gemini`, `cline` all present locally).
2. **Pinned each canonical repo** from installed `package.json` `repository` fields, brew formulae, and web search.
3. **Scraped the actual source/docs** with firecrawl (GitHub repo READMEs + official docs pages) — not snippets.
4. **Read full local source clones** for three research-grade agents whose entire brain is on disk: `smolagents`, `SWE-agent`, `openclaw`.
5. **Cross-checked** disambiguations that are easy to get wrong (see §5).

**Source corpus (scraped to `~/.firecrawl/`):**
| CLI | Canonical repo / docs | Lang | Source grade |
|---|---|---|---|
| opencode | `github.com/anomalyco/opencode` (docs: opencode.ai) | Go | docs + binary (bundled) |
| crush | `github.com/charmbracelet/crush` | Go (Charm) | README + docs (**ex-opencode lineage**) |
| cline | `github.com/cline/cline` (`apps/cli`) | TS (Bun) | README (very rich) |
| claude code | closed source (binary) | — | **docs only** (code.claude.com) |
| codex | `github.com/openai/codex` (`codex-cli/`, `codex-rs/`) | Rust+TS | README + `--help` |
| gemini-cli | `github.com/google-gemini/gemini-cli` | TS (bundle) | README + `--help` |
| goose | `github.com/block/goose` | Rust | README (light) |
| smolagents | `github.com/huggingface/smolagents` (**local full src**) | Python | **full source read** |
| SWE-agent | `github.com/princeton-nlp/SWE-agent` (**local full src**) | Python | **full source read** |
| openclaw | `github.com/openclaw/openclaw` (**local full src**) | TS | **full source read** |

---

## 1. The Semantic Brain Index — where the core logic lives

For each CLI, the “brain” is the set of modules that decide the human experience: the **agent loop**, the **permission system**, the **rendering layer**, the **session store**, and the **config/provider system**.

### opencode (anomalyco/opencode, Go)
Brain modules (from docs nav + repo): `tui/`, `cli/` (`opencode run`, `opencode serve`, `opencode web`), session manager (`opencode session list`), `share` (public links `opncd.ai/s/<id>`), `zen` (**a curated model provider — NOT a background mode**, see §5), `permissions`, `policies`, `mcp-servers`, `lsp`, `custom-tools`, `formatters`, `agents`, `skills`, `references`, `plugins`, `sdk`, `server`, `acp`. Config: `~/.config/opencode`.
*Evidence: opencode.ai/docs nav (opencode-docs.md); brew formula → anomalyco/opencode; npm pkg `opencode-ai`.*

### crush (charmbracelet/crush, Go — ex-opencode)
Brain: **workspace** = a shared backend keyed by `--cwd`; clients with the same cwd share *session list, message history, permission queue, LSP, MCP state* (crush-readme.md:666-670). Live session signals `IsBusy` + `AttachedClients` (crush-readme.md:678-683). `--yolo`/`--debug` follow **first-wins** per workspace (crush-readme.md:685-690). Mid-session **LLM switch preserving context** (crush-readme.md:298). LSP-enhanced context (crush-readme.md:300). Hooks (`docs/hooks`). Permission = `allowed_tools` allowlist + `--yolo` (crush-readme.md:741-763) + `disabled_tools` (crush-readme.md:765-771). Global context `~/.config/crush/CRUSH.md` + `~/.config/AGENTS.md` (crush-readme.md:698-710). `.crushignore`. File-based secrets expansion `"$TOKEN"` / `"$(cat /path)"` (crush-readme.md:592-601). `compact_mode` (crush-readme.md:399).
*Evidence: crush-readme.md lines cited.*

### cline (cline/cline apps/cli, TS/Bun)
Brain: a **shared agent core** across VS Code extension / JetBrains / SDK / CLI — “plan/act modes, MCP servers, checkpoints, rules, skills, and provider configuration all behave the same across surfaces” (cline-cli.md:439). Five run **shapes**: Interactive TUI, One-shot, JSON (NDJSON), Yolo, **Zen** (background hub daemon, fire-and-forget) (cline-cli.md:501-507). Plan/Act toggle (cline-cli.md:531). Checkpoints + `/undo` to rewind workspace (cline-cli.md:533). Sub-agent spawning + agent teams (cline-cli.md:534). `--thinking none|low|medium|high|xhigh` budgets (cline-cli.md:688). `--compaction agentic|basic|off` (cline-cli.md:689). `--retries` = max consecutive mistakes before halt, default 3 (cline-cli.md:690) — **the forge LoopGuard analog, human-configurable**. `--data-dir` auto-enables sandbox (cline-cli.md:692). `--auto-approve false` gating (cline-cli.md:693, 745). `cline doctor` / `doctor fix` / `doctor log` (cline-cli.md:716-718). `cline history`, `cline connect` (Telegram/Google Chat/WhatsApp/Slack/Linear), `cline schedule` (cron+event), `cline hub` (daemon) (cline-cli.md:709-721). Streaming TUI on **OpenTUI** (sst/opentui) with markdown + **syntax-highlighted diffs** + mouse (cline-cli.md:530). OAuth (cline/openai-codex/OCA) **fails fast in non-interactive** rather than launching a hidden browser (cline-cli.md:495).
*Evidence: cline-cli.md lines cited.*

### claude code (closed source; docs code.claude.com)
Brain (reconstructed from docs): **permission modes** = a 5-state machine `default → acceptEdits → plan → auto → dontAsk → bypassPermissions` with a single `Shift+Tab` cycle (`default→acceptEdits→plan`) and a status-bar indicator (claude-permission-modes.md:104-111, 130). Baseline mode + **layered permission rules** (allow/deny/ask); **deny + explicit-ask apply in EVERY mode incl. bypassPermissions**; **protected paths never auto-approved** except bypass (claude-permission-modes.md:113). Sessions: `--resume`/`--continue`/`--fork-session`, `--name`, `/resume` (overview nav). Context window + **prompt caching** + compaction + **subagents** (`Agent` tool, `maxTurns`, restricted tool set) (overview nav + FRONTIER-COMPARISON.md). Hooks `PreToolUse`/`PostToolUse`. `CLAUDE.md` memory. Output formats `text`/`json`/`stream-json` + `--print` + `--input-format stream-json` + `--json-schema` structured output (claude --help). `--background` agents, remote-control, desktop app, web (claude.ai/code), Slack/VS Code/JetBrains/Chrome. `--ax-screen-reader` flat output; `--bare` minimal mode (claude --help).
*Evidence: claude-permission-modes.md lines cited; claude --help grep.*

### codex (openai/codex, Rust+TS)
Brain: `codex exec` (non-interactive), `review`, `resume`/`fork` (session picker, `--last`), `apply` (`git apply` the latest diff), `cloud` (Codex Cloud tasks), `doctor` (**`--json` redacted report**), `sandbox` + `sandbox_permissions` config, `mcp`/`mcp-server`/`app-server`/`remote-control`, **AGENTS.md discovery** (root-aware parent traversal, `PathUri`) (codex commit log dce6739), `-c` dotted-TOML config overrides, `features` flags, `login`/`logout`, `completion`, `update`. Shell-snapshot restoration; native tool-calling; worktree support (codex --help, codex exec --help).
*Evidence: codex --help, codex exec --help, codex-readme.md commit log.*

### gemini-cli (google-gemini/gemini-cli, TS)
Brain: `-p`/`--prompt` headless, `--output-format json|stream-json`, `--approval-mode default|auto_edit|yolo|plan`, `--sandbox`, `--yolo`, `--skip-trust`, **trusted folders**, **checkpointing** (save/resume), `GEMINI.md` context, **token caching**, MCP, extensions, hooks, skills, **gemma local routing**, telemetry, **GitHub Action** (PR reviews, issue triage, `@gemini-cli` mentions), `--acp`, `-w`/`--worktree` (new git worktree). Free tier: Google OAuth 60 req/min + 1000/day; API key 1000/day (gemini --help, gemini-readme.md:451, 658, 684).
*Evidence: gemini --help, gemini-readme.md lines cited.*

### goose (block/goose, Rust)
Brain (light read): sessions, fork, hooks, MCP, agents, provider config, `goose-docs.ai`. (Read at README level only this pass — depth flagged in §5.)
*Evidence: goose-readme.md.*

### smolagents (huggingface — LOCAL FULL SOURCE)
Brain = `src/smolagents/`: `cli.py` (argparse + **Rich Console**) ; `monitoring.py` = **`AgentLogger` + `Monitor` + `LogLevel` (OFF/ERROR/INFO/DEBUG) + `TokenUsage` + `Timing`** — the rendering brain; per-step metrics printed `[Step N: Duration Xs | Input tokens: … | Output tokens: …]` (monitoring.py:108-117); `log_markdown`/`log_code`/`log_rule`/`log_task` use Rich `Panel`/`Syntax`/`Rule`/`Table`/`Tree` (monitoring.py:152-200); `agents.py` (`CodeAgent`/`ToolCallingAgent`); `memory.py`; `local_python_executor.py`.
*Evidence: monitoring.py:80-200, cli.py:1-60 (read in full).*

### SWE-agent (princeton-nlp — LOCAL FULL SOURCE)
Brain = `sweagent/tools/`: `commands.py` = **`Command` + `Argument` pydantic models** (typed args, `enum` validation, jinja `argument_format`) (commands.py:52-80); `parsing.py` = **`AbstractParseFunction` registry** (`ThoughtActionParser`, `FunctionCallingParser`; `parse_function` type selector) (parsing.py:1-70); `tools.py` (install/execute); `inspector/` (web inspector). **The action/observation contract = typed command models + a parser strategy registry** — the exact pattern forge’s `ReactAgent` uses (`_PARSE_STRATEGIES`).
*Evidence: commands.py:1-80, parsing.py:1-70 (read in full).*

### openclaw (LOCAL FULL SOURCE)
Brain = `ui/src/ui/` (TypeScript, web/chat surface): `session-display`, `activity-model`, `chat/message-normalizer`, `chat/grouped-render`, `chat/copy-as-markdown`, `chat/realtime-talk`, `browser-redact`, `usage-cache-status`, `strip-thinking-tags`. A web/chat agent — different surface, but rich **rendering + redaction + usage-cache** primitives.
*Evidence: file tree (find openclaw/ui/src/ui).*


---

## 2. The Cross-Cutting Experience Primitives (the semantic backbone)

These are the **recurring felt-experience primitives** that frontier CLIs converge on — abstracted across all sources. Each is stated as a mechanism + the philosophy behind it, with the CLIs that embody it. This is the layer that matters most for an experience engineer: the *primitive*, not the flag name.

### P1 — Live transparency (the agent shows its work as it happens)
**Mechanism:** streaming TUI rendering thought → action → observation token-by-token, with per-step metrics. **Philosophy:** a human watching a long task should never stare at a silent prompt; perceived latency is killed by visible progress. **Embodied by:** cline (streaming TUI on OpenTUI, syntax-highlighted diffs), crush (TUI + `IsBusy` live signal), opencode (TUI), gemini (stream-json events), codex (`--print` streaming), smolagents (`Monitor` prints `[Step N: Duration | tokens]` every step — monitoring.py:108). **The wound this exposes in forge:** `forge run` prints `---` then silence; thoughts/tool calls/observations go only to `logging`/Tracer/Audit and are invisible by default.

### P2 — Permission choreography (a graduated state machine, not a boolean)
**Mechanism:** a baseline *mode* (what auto-runs) + per-tool *rules* (allow/deny/ask) + *protected paths* + a single fast cycle key. **Philosophy:** trust is a dial, not a switch; the human dials it per-task with one keystroke, and hard guardrails (deny/protected) survive even the loosest setting. **Embodied by:** claude (5 modes + `Shift+Tab` cycle + layered rules + protected paths — the canonical design), gemini (`--approval-mode default|auto_edit|yolo|plan`), cline (plan/act + `--auto-approve` + `--yolo`), crush (`allowed_tools` allowlist + `--yolo` + `disabled_tools`), codex (`sandbox_permissions`). **Forge:** has `sandbox_dir` + path containment but no user-facing permission mode, no per-tool allow/deny, no ask-gate.

### P3 — Honest terminal attribution (the real reason it failed)
**Mechanism:** the terminal cause of failure is captured and reported verbatim; diagnostics are a first-class subcommand. **Philosophy:** an agent that says “Max steps reached” when the real cause was a bad API key is *lying* — and a lying agent destroys trust faster than a failing one. **Embodied by:** codex `doctor --json` (redacted machine report), cline `doctor`/`doctor fix`/`doctor log`, claude `stream-json` events carrying real errors, gemini telemetry. **The wound this exposes in forge:** the model exception (`Illegal header value b'Bearer '`) is caught and **discarded** at `react.py:1051-1053`; the human is then told “Max steps reached” — the wrong reason. `AgentResult` has no `failure_reason` field.

### P4 — Session continuity (the conversation survives)
**Mechanism:** a durable session store + `resume` + `fork` (branch a conversation). **Philosophy:** a multi-hour task must survive a crash, a closed terminal, or a “let me try a different tack”; forking lets you explore without losing the main line. **Embodied by:** codex (`resume`/`fork`/`--last`, `apply`), cline (`history`, checkpoints + `/undo`), claude (`--resume`/`--continue`/`--fork-session`), opencode + crush (session manager/picker), gemini (checkpointing). **Forge:** `AgentContext` is in-memory; crash = total state loss; no resume, no fork.

### P5 — Machine composability (the CLI is also a pipe)
**Mechanism:** a non-interactive headless mode emitting **NDJSON events** for downstream tooling + stdin piping. **Philosophy:** the same agent that serves a human in a TUI must serve a script in CI, identically. **Embodied by:** claude (`--output-format text|json|stream-json`, `--print`, `--input-format stream-json`), gemini (`--output-format json|stream-json`), cline (`--json` NDJSON), codex (`exec` + `--json`), opencode (`run --format json`). Pipe idiom: `cat file | cline "…"`, `git diff | cline "review"` (cline-cli.md:519-520). **Forge:** text-only output, no JSON, no streaming events, no stdin pipe.

### P6 — Self-diagnosis (the CLI checks itself)
**Mechanism:** a `doctor` subcommand that checks install/config/auth/runtime health, prints a (redacted) report, and can auto-fix stale processes. **Philosophy:** “why isn’t it working” should be one command, not archaeology; never print secrets. **Embodied by:** codex `doctor --json`, cline `doctor`/`doctor fix`/`doctor log`. **Forge:** none — a bad key surfaces as a misleading “Max steps reached”.

### P7 — Ambient context (the agent knows your project)
**Mechanism:** a layered context-file hierarchy (global → project) + ignore semantics + LSP integration. **Philosophy:** the agent should arrive already knowing your conventions, without being told each session. **Embodied by:** claude (`CLAUDE.md`), gemini (`GEMINI.md`), crush (`CRUSH.md` + `AGENTS.md` global + `.crushignore`), codex (`AGENTS.md` root-aware discovery), opencode (rules/references), **LSP-enhanced** (crush — “uses LSPs for additional context, just like you do”), gemini (trusted folders). **Forge:** none.

### P8 — Cost & token telemetry (you know what you spent)
**Mechanism:** per-step + per-run token/cost accounting surfaced to the human, plus aggregate stats. **Philosophy:** agents spend money invisibly; the human must always see the meter. **Embodied by:** cline (`--verbose`: elapsed, tokens, est. cost), opencode (`stats`), crush (cost/token), smolagents (`Monitor.total_input/output_token_count`), gemini (token caching). **Forge:** `total_tokens` only, no cost estimate, buried in the footer.

### P9 — Convergence & retry control (the agent stops spinning)
**Mechanism:** a bounded *mistake cap* + a *context compaction mode*, both human-configurable. **Philosophy:** a stuck agent must halt honestly, and a long context must be compacted (not truncated blindly) before it breaks the model. **Embodied by:** cline (`--retries` max consecutive mistakes, default 3; `--compaction agentic|basic|off`), claude (context compaction + `maxTurns`), crush (`compact_mode`). **Forge:** **has** `LoopGuard` (the mistake-cap analog) and a `ContextManager` (truncation) — but exposes neither cap nor compaction mode to the human; compaction is blind truncation, not agentic.

### P10 — Background / fire-and-forget (long tasks walk away)
**Mechanism:** dispatch to a background daemon + later inspection + completion notification. **Philosophy:** a 20-minute refactor shouldn’t hold your terminal; fire it, walk away, get notified. **Embodied by:** cline `--zen` (hub daemon, exits immediately, menubar notifies on completion — cline-cli.md:727-738), claude `--background`, codex `cloud`, opencode `serve`/`server`. **Forge:** foreground blocking only; `run()` hard-blocks with a 120s thread timeout.

### P11 — Safety sandbox (bounded blast radius)
**Mechanism:** a configurable execution sandbox + per-tool enable/disable, surfaced as a first-class mode. **Philosophy:** autonomy and safety scale together; the sandbox is the precondition for `--yolo`. **Embodied by:** codex (`sandbox` + `sandbox_permissions`), gemini (`--sandbox` + trusted folders), cline (`--data-dir` auto-sandbox), claude (protected paths), crush (`disabled_tools`). **Forge:** **has** `sandbox_dir` + path containment + destructive-command block (strong internals) but does **not** surface it as a CLI mode or let the human scope a run to a sandbox easily.

### P12 — Extensibility surface (tools / hooks / MCP / subagents)
**Mechanism:** a hook lifecycle (pre/post tool) + MCP tool protocol + subagent delegation. **Philosophy:** the agent is a platform, not a closed loop; the human extends behavior without forking. **Embodied by:** MCP everywhere (claude, cline, crush, gemini, codex, goose); hooks (claude `PreToolUse`/`PostToolUse`, cline `--hooks-dir`, crush/gemini/codex/opencode hooks); subagents/teams (cline spawn+teams, claude `Agent` tool, opencode agents, crush `.agents/skills`). **Forge:** `ToolRegistry` + `Tracer` but **no hooks, no MCP, no subagents**.

### P13 — Diff-first output (you see what changed)
**Mechanism:** edits rendered as reviewable, syntax-highlighted diffs; a way to apply/reject. **Philosophy:** the human reviews *changes*, not *files*; a diff is the correct unit of trust. **Embodied by:** cline (streaming TUI with syntax-highlighted diffs), claude (inline diffs), codex (`apply` → `git apply` the diff), openclaw (`chat/copy-as-markdown`, `grouped-render`). **Forge:** `edits_made` is a path list; the human never sees the diff in the run output.

---

## 3. The Two Designs That Separate Frontier From Forge

Synthesizing the primitives, two *designs* explain most of the experience gap:

1. **The event-stream spine.** Every frontier CLI has, at its core, a stream of typed events (thought/action/observation/token/error) that feeds **two consumers from one source**: the human TUI *and* the machine NDJSON pipe. Forge computes the same events but routes them only to `logging`/Tracer/Audit — the human and the pipe both get nothing live. **The fix is architectural, not cosmetic:** add an event emitter at the loop’s existing lifecycle points and let renderers subscribe. (This is the single highest-leverage experience change.)
2. **The permission-mode state machine.** Frontier CLIs treat “how much can the agent do without asking” as a *mode* the human dials, layered with hard rules. Forge treats it as a static sandbox config. The frontier design is more humane because it lets the human match autonomy to risk per-task with one keystroke, while never weakening the hard guardrails.

---

## 4. What This Means for Forge (experience-engineer reading, not a roadmap)

Mapped against forge’s current surface (proven live: a `forge run` with a bad key prints `---`, stays silent, then reports “Max steps reached” — the wrong reason):

- **P3 (honest attribution)** is the most damaging gap: forge’s whole thesis is “agents lie about success,” yet its own CLI lies about *failure*. This contradicts the project’s identity.
- **P1 (live transparency)** is the most *felt* gap: silence during a run.
- **P5 (machine composability)** + **P6 (self-diagnosis)** are the cheapest high-impact wins (NDJSON output + `forge doctor`, both dependency-free).
- **P2 (permission mode)**, **P4 (session continuity)**, **P10 (background)**, **P12 (extensibility)** are larger architectural additions.
- **P9 (convergence/retry)** and **P11 (sandbox)**: forge **already has the internals** (LoopGuard, ContextManager, sandbox_dir) — the gap is *exposure to the human*, not capability.
- **P13 (diff-first)**, **P7 (ambient context)**, **P8 (cost telemetry)** are render/config-layer additions.

*(No code changes are made in this research pass — per the pause on implementation. This section is a reading, not a plan.)*

---

## 5. Hardening Notes (disambiguations, caveats, unverified)

**Disambiguations that are easy to get wrong:**
- **“Zen” means two different things.** opencode Zen = a *curated model provider* (a list of tested models you log into — opencode-zen.md:104-112). cline `--zen` = a *background hub daemon* that fire-and-forgets a task (cline-cli.md:727). Do **not** conflate them.
- **crush is ex-opencode.** `github.com/charmbracelet/crush` shares lineage with opencode (thenewstack article: “Crush (ex-OpenCode)”). They share the workspace/session/permission DNA but diverge on the Charm ecosystem + LSP-first stance.
- **opencode repo pin.** Brew installs from `anomalyco/tap` → `anomalyco/opencode`; npm package is `opencode-ai`; docs footer says `anomalyco/opencode`; search also surfaced `opencode-ai/opencode` (likely the prior name/redirect). Canonical today = `anomalyco/opencode`.
- **goose canonical** = `github.com/block/goose` (Block’s official, per block.xyz announcement); search also surfaced `aaif-goose/goose` (a fork). I scraped block/goose.

**Source-grade caveats:**
- **claude code is closed source** — all claude claims are from official docs (code.claude.com), not source. Permission-mode mechanics are doc-verified; internal implementation is not.
- **opencode/crush/codex/gemini/cline are bundled/compiled locally** — README + docs + `--help` are the evidence, not decompiled source. The *brain module* names come from docs nav + repo file trees, not line-level source.
- **smolagents, SWE-agent, openclaw are full local source** — claims are line-cited and verified by reading the actual `.py`/`.ts`.

**Depth flagged (read at README level only, not deep-source):** goose, aider (not scraped this pass). These should get a second pass before any claim depending on them is hardened.

**Pre-existing codebase observation (not a research finding, noted for context):** forge `main`’s `models/__init__.py` imports `vertex.py` **unguarded** (only ollama is try/except’d) — `import forge_sdk` crashes in any env lacking `google-genai`. This is an environment-portability bug, separate from the experience research, but relevant to “blur in the codebase.”

---

## 6. Source Index (all evidence files)

Scraped corpus (`~/.firecrawl/`): `opencode-docs.md`, `opencode-zen.md`, `opencode-share.md`, `opencode-sst.md`, `crush-readme.md`, `cline-cli.md`, `claude-code-overview.md`, `claude-permission-modes.md`, `codex-readme.md`, `gemini-readme.md`, `goose-readme.md`. Local full source: `/Users/srinji/smolagents/src/smolagents/{cli,monitoring,agents,memory,tools}.py`, `/Users/srinji/SWE-agent/sweagent/tools/{commands,parsing,tools}.py`, `/Users/srinji/openclaw/ui/src/ui/`. Forge baseline: `/Users/srinji/forge/src/forge_sdk/{cli/main.py,agents/react.py,agents/types.py}`.


================================================================
PART II — THE NEXT-GEN CLI AGENT TOPOLOGY + FORGE GAP ANALYSIS
================================================================

**Stance:** Experience engineer first. GitHub = source of truth.
**Baseline:** forge `main` @ `b417ccf` (cleaned up: `.firecrawl` cache removed via #54).
**Scope:** A *topological map* of what must be true for any next-gen CLI coding agent, then a forge-vs-topology gap analysis on the cleaned baseline. No code changes — this is research.

---

## 7. The Next-Gen CLI Agent Topology (what must be true)

A topology, not a checklist: these are the **load-bearing layers** a next-gen CLI agent needs, with the **dependencies between them**. Every layer is a precondition for the one above it. A tool missing a lower layer cannot fake the upper one.

```
                    ┌─────────────────────────────────────┐
                    │  L7  MULTI-SURFACE & EXTENSIBILITY   │  (TUI+CLI+Web+IDE, MCP, hooks, subagents)
                    ├─────────────────────────────────────┤
                    │  L6  TRUST & DIFF-FIRST REVIEW        │  (diffs, apply/reject, checkpoints/undo)
                    ├─────────────────────────────────────┤
                    │  L5  AUTONOMY & CONTINUITY            │  (permission modes, background, session resume/fork)
                    ├─────────────────────────────────────┤
                    │  L4  HONEST TERMINATION               │  (real failure attribution, doctor, exit codes)
                    ├─────────────────────────────────────┤
                    │  L3  THE EVENT STREAM                 │  (one typed event spine → human TUI + machine NDJSON)
                    ├─────────────────────────────────────┤
                    │  L2  VERIFICATION & GUARDRAILS        │  (build/test gate, semantic check, sandbox, loop guard)
                    ├─────────────────────────────────────┤
                    │  L1  THE AGENT CORE                   │  (model port, tool registry, parse strategy, context mgmt)
                    └─────────────────────────────────────┘
```

### L1 — The Agent Core (precondition for everything)
**Must be true:** a model-portable protocol, a typed tool registry, a parser-strategy registry (native tool-calling OR free-text recovery), and bounded context management (token-aware truncation/compaction). **Why foundational:** nothing above works if the loop can’t call a model, can’t parse its output, or overflows the context window. **Frontier norm:** native tool-calling with free-text fallback; model-agnostic; compaction (cline `--compaction`, claude context compaction). **Dependency:** none — this is the floor.

### L2 — Verification & Guardrails (precondition for autonomy)
**Must be true:** a build/test gate that empirically checks edits; a sandbox with bounded blast radius; a loop-guard that halts spinners; semantic alignment that catches shallow edits; usage limits. **Why foundational:** autonomy (L5) is unsafe without verification (L2) — you cannot let an agent run unattended if you can’t prove it worked or contain the damage. **Frontier norm:** codex `sandbox`+`sandbox_permissions`, gemini `--sandbox`+trusted folders, cline `--data-dir` auto-sandbox. **Dependency:** builds on L1 (needs the tool registry to enforce the sandbox).

### L3 — The Event Stream (the architectural hinge)
**Must be true:** a single typed event spine (thought/action/observation/token/error/verification) that feeds **two consumers from one source**: the human TUI renderer AND the machine NDJSON pipe. **Why foundational:** this is what makes live transparency (P1) and machine composability (P5) the *same mechanism*, not two features. Splitting them (separate human path + separate machine path) causes drift and duplicate bugs. **Frontier norm:** claude `--output-format text|json|stream-json` from one stream; gemini `--output-format json|stream-json`; cline `--json` NDJSON. **Dependency:** builds on L1 (the loop emits the events).

### L4 — Honest Termination (precondition for trust)
**Must be true:** the *real* terminal cause of a FAILED run is captured and reported; a `doctor` subcommand self-diagnoses; exit codes are meaningful (0 success / 1 failure). **Why foundational:** an agent that misattributes failure is lying, and a lying agent destroys trust faster than a failing one. This is the layer where a project’s credibility lives. **Frontier norm:** codex `doctor --json`, cline `doctor`/`fix`/`log`, real error text in stream-json events. **Dependency:** builds on L3 (the event stream carries the real error).

### L5 — Autonomy & Continuity (precondition for unattended + long work)
**Must be true:** (a) a **permission-mode state machine** — graduated trust the human dials with one keystroke, with hard guardrails that survive the loosest setting; (b) **background/fire-and-forget** for long tasks; (c) **session resume + fork** so a conversation survives a crash or a “different tack.” **Why foundational:** without these, the human must babysit every run, and a 20-min task holds the terminal hostage. **Frontier norm:** claude 5-mode machine + `Shift+Tab` cycle; cline `--zen` hub + checkpoints + `/undo`; codex `resume`/`fork`/`--last`; claude/codex/crush `--background`/serve/cloud. **Dependency:** builds on L2 (autonomy needs guardrails) and L3 (background needs an event stream to replay).

### L6 — Trust & Diff-First Review (precondition for review flow)
**Must be true:** edits rendered as reviewable, syntax-highlighted **diffs** (not file dumps), with apply/reject; checkpoints to rewind workspace state. **Why foundational:** the human reviews *changes*, not *files*; a diff is the correct unit of trust. Checkpoints turn “the agent broke something” from a crisis into a `/undo`. **Frontier norm:** cline streaming diffs + `/undo`; claude inline diffs; codex `apply` (`git apply`); claude/codex/gemini/cline checkpoints. **Dependency:** builds on L5 (checkpoints are a continuity primitive) and L3 (diffs render from the event stream).

### L7 — Multi-Surface & Extensibility (the platform layer)
**Must be true:** the same agent core serves TUI + headless CLI + Web + IDE; a **hook lifecycle** (pre/post tool); **MCP** tool protocol; **subagents/teams**. **Why foundational:** the agent is a platform, not a closed loop; the human extends behavior without forking, and the same brain runs in a terminal, a CI pipe, and an IDE identically. **Frontier norm:** cline “shared agent core across VS Code/JetBrains/SDK/CLI”; MCP everywhere; hooks (claude PreToolUse/PostToolUse, cline `--hooks-dir`, crush/gemini/codex/opencode); subagents (cline teams, claude `Agent` tool, opencode agents, crush `.agents/skills`). **Dependency:** builds on L3 (the event stream is what every surface renders) and L1 (the core is what every surface shares).

---

## 8. The Auto-Mode Classifier — the primitive the image pointed at

The image highlighted **Claude Code’s `auto` permission mode classifier** — the sophisticated middle ground between `--dangerously-skip-permissions` (blanket allow) and `default` (ask for everything). This deserves its own treatment because it is the frontier’s answer to *safe autonomy* and it is genuinely novel. Verified from `claude-permission-modes.md`.

**The mechanism (not a flag, a *system*):**
- A **separate classifier model** reviews each action *before* it runs. It is not the agent grading itself — it is a distinct model judging each action against your request. (claude-permission-modes.md:227)
- **Evaluation order:** (1) explicit allow/deny **rules** resolve immediately → (2) writes to **protected paths** route to the classifier *even when an allow rule matches* → (3) everything else goes to the classifier. (claude-permission-modes.md:317-319)
- **Trusted by default:** your working directory + your repo’s configured remotes. **Everything else is external** until you configure trusted infrastructure. (claude-permission-modes.md:256)
- **Blocked by default:** actions that escalate beyond your request, target unrecognized infrastructure, appear driven by hostile content the agent read, and destructive git ops (`git reset --hard`, `git checkout -- .`, `git restore .`, `git clean -fd`, `git stash drop`, `git stash clear`). (claude-permission-modes.md:266)
- **Conversation boundaries become block signals:** if you say “don’t push” or “wait until I review,” the classifier blocks matching actions *even when default rules would allow*. The classifier **re-reads the boundary from the transcript on each check** — so a boundary is *lost if context compaction removes the message that stated it*. (claude-permission-modes.md:307) This is a profound design choice: it makes safety conversational but **non-durable** — hard guarantees require a deny *rule*, not a boundary.
- **Fallback (anti-runaway):** if the classifier blocks **3 consecutive** actions or **20 total** in a session, auto mode *pauses* and the agent resumes prompting. In non-interactive (`-p`) mode, repeated blocks **abort** the session (no human to prompt). Any allowed action resets the consecutive counter; the total counter persists. These thresholds are **not configurable**. (claude-permission-modes.md:309-311)

**Why this is the smart permission primitive (the image’s thesis):** `--dangerously-skip-permissions` is a boolean — it grants *all* autonomy or none. The classifier makes autonomy **conditional and per-action**: the agent can run free on the 95% of actions that match your intent and your trusted surface, while the 5% that would escalate, destroy, or exfiltrate are gated *by a different model than the one doing the work*. This is the architecture that lets a next-gen agent be genuinely autonomous without being reckless.

**Topology placement:** this is the **L5 permission-mode state machine, upgraded**. It sits on top of L2 (sandbox) and L3 (event stream — the classifier is itself an event consumer) and is the precondition for trustworthy background execution (L5b). A tool that only has a boolean `--yolo` is stuck at the *floor* of L5; the classifier is the *ceiling*.

---

## 9. Gap Analysis — forge (cleaned baseline) vs the Topology

Forge baseline: `main` @ `b417ccf`, read line-by-line. Each layer: **what forge has / what it lacks / the gap**. All forge claims verified against the actual source on GitHub-truth HEAD.

### L1 — Agent Core → **STRONG**
**Has:** `ModelPort` protocol (model-agnostic, port.py:11-47) + `ProviderRegistry` (registry.py) + `complete`/`complete_stream` both defined; `ToolRegistry` + `ToolSpec` (typed); **parser-strategy registry** (`_PARSE_STRATEGIES`, react.py — the SWE-agent `AbstractParseFunction` pattern, native tool-calling + free-text fallback); `ContextManager` (token-aware truncation, react.py:539); `UsageLimiter`; `LoopGuard` (mistake cap, react.py:421). **Lacks:** **compaction is blind truncation, not agentic** (cline `--compaction agentic` summarizes with an LLM; forge just drops messages) — so long runs lose hard-won context silently. **Gap:** medium — the core is frontier-grade; compaction quality is the weak seam.

### L2 — Verification & Guardrails → **STRONG (forge’s moat)**
**Has:** the **INV-201 verification pipeline** (syntactic → AST → entity-validation → empirical build/test → spec-conformance → semantic alignment, verifiers/__init__.py + react.py:1292-1317); `sandbox_dir` + path containment + destructive-command block (security.py); `LoopGuard`; `UsageLimiter`; **named-target coverage** (detects dropped edits, react.py:1350-1360); **false-green gates** (`_FAILURE_GATES`, react.py:1328-1338). This is forge’s thesis made code, and it is *ahead* of most frontier CLIs on empirical verification. **Lacks:** **no CLI exposure** — `sandbox_dir` is a constructor arg, not a `forge run --sandbox` flag; the human can’t easily scope a run. **Gap:** low capability gap, **high exposure gap** — the moat exists but is invisible to the human.

### L3 — The Event Stream → **MISSING (the architectural hinge)**
**Has:** the loop *computes* every event (thought/action/observation/tokens/verification) and routes them to `Tracer` (JSONL spans) + `AuditLog` (SQLite hash-chain) + Python `logging`. **Lacks:** **no renderer subscribes live** — the CLI prints `---`, runs synchronously, prints a final summary (main.py:65-79). There is no typed event bus, no TUI, no NDJSON output. The events exist but feed *no human* and *no machine* at runtime. **Gap:** **critical** — this is the single highest-leverage layer. Fixing it unlocks P1 (live transparency) and P5 (machine composability) from one mechanism.

### L4 — Honest Termination → **BROKEN (contradicts forge’s identity)**
**Has:** the internal `ReasoningTrace` carries `failure_reason` (react.py:1364) and sets it for the finish-branch and the max-steps branch (react.py:1389). **Lacks:** (1) **`AgentResult` has no `failure_reason` field** (types.py:43-62 — verified on clean `main`), so the truthful reason dies inside the trace and never reaches the human/CLI; (2) **the model-exception path discards the cause entirely** — `except Exception as e: log.error(...); break` (react.py:1051-1053) sets no reason, so the human *always* gets “Max steps reached” even when the real cause was `Illegal header value b'Bearer '` (empty API key); (3) **no `forge doctor`** — a bad key is archaeology; (4) **no exit codes** — `cmd_run` always returns 0 (main.py:27, no `sys.exit`). **Gap:** **critical** — a project whose thesis is “agents lie about success” has a CLI that *lies about failure*. This is the most damaging gap because it attacks the project’s credibility directly.

### L5 — Autonomy & Continuity → **MISSING (two sub-gaps)**
**L5a Permission mode:** **Has** `sandbox_dir` + path containment (the guardrail floor). **Lacks** a permission-mode *state machine*: no `--permission-mode`, no per-tool allow/deny rules, no ask-gate, no protected-paths, no auto-mode classifier. `forge run` is effectively always in one implicit mode. **Gap:** high — autonomy is un-dialable.
**L5b Continuity/background:** **Has** nothing — `AgentContext` is in-memory (crash = total loss); `run()` blocks with a 120s thread timeout (react.py:1402-1423); no session store, no resume, no fork, no background daemon. **Gap:** high — multi-hour tasks are impossible; a closed terminal loses everything.

### L6 — Trust & Diff-First Review → **MISSING**
**Has:** `edits_made` (a path list, react.py) + `named_targets_missing` (advisory). **Lacks:** edits are *never rendered as diffs* in run output; no apply/reject; no checkpoints; no `/undo`. The human gets a list of paths, not the changes. **Gap:** high — the human must `git diff` manually after every run; trust is a path list, not a review.

### L7 — Multi-Surface & Extensibility → **MISSING**
**Has:** `ToolRegistry` (pluggable tools) + `Tracer`/`AuditLog` (observability hooks, but not lifecycle hooks). **Lacks:** **no hooks** (no pre/post-tool lifecycle), **no MCP**, **no subagents**, **single surface** (CLI only, no TUI/Web/IDE). **Gap:** high — forge is a closed loop, not a platform. **Note:** the existing `harness/` (adaptive learning, evolution engine) is a *unique* extensibility axis no frontier CLI has, but it’s not surfaced as a CLI primitive.

---

## 10. The Gap Topology — visualized by severity and dependency

```
L1  Agent Core          [████████████████░░░]  STRONG   (compaction weak)
L2  Verification        [██████████████████░]  STRONG*  (moat; low CLI exposure)
L3  Event Stream        [██░░░░░░░░░░░░░░░░░]  MISSING  ← architectural hinge
L4  Honest Termination  [████░░░░░░░░░░░░░░░]  BROKEN   ← identity contradiction
L5  Autonomy/Continuity [██░░░░░░░░░░░░░░░░░]  MISSING  (mode + resume/bg)
L6  Diff-First Review   [██░░░░░░░░░░░░░░░░░]  MISSING
L7  Multi-Surface/Ext   [██░░░░░░░░░░░░░░░░░]  MISSING  (no hooks/MCP/subagents)
```

**Reading the map:** forge is *bottom-heavy* — L1/L2 (the hard internals) are frontier-grade or ahead. L3+ (the human-facing layers) are missing or broken. **The architectural hinge is L3**: adding the event stream unlocks L3, enables L4 (honest attribution flows through the same stream), and is the precondition for L5/L6/L7. L4 is the *moral* priority because it contradicts the project identity. **L2 is the moat that nobody can see** — the verification pipeline is forge’s differentiator, but it’s invisible at the CLI surface.

---

## 11. What These Tools Lack (the reverse gap — where forge is ahead)

To be balanced, the frontier CLIs *lack* what forge has — this is forge’s defensible ground:

- **Empirical verification pipeline (L2):** most frontier CLIs trust the agent’s self-report or a single build run. Forge’s INV-201 pipeline (syntactic → AST → entity → build/test → spec-conformance → semantic) with a *distinct verifier* (INV-203: the model that writes code does NOT grade it) is genuinely ahead. None of claude/codex/gemini/cline/crush/opencode expose a multi-gate verification pipeline as a first-class result.
- **Hash-chain audit log:** forge’s `AuditLog` (SQLite, append-only, SHA-256 hash-chain, `verify_integrity`) is tamper-evident forensics. Frontier CLIs have tracing (claude/codex) or telemetry (gemini) but not a *cryptographically verifiable* audit trail. This is a trust primitive forge has that others fake.
- **False-green detection:** forge explicitly detects and refuses to report success on (a) edits-without-a-build-gate, (b) partial-completion over-claim (named-target coverage), (c) shallow edits (semantic alignment). Frontier CLIs assume success = the agent said “done.” This is forge’s thesis, and it’s a real moat.
- **Adaptive learning harness:** the `harness/` module (evolution engine, learning store, validation gate) is a self-improvement loop no frontier CLI ships.

**The irony:** forge is strongest exactly where the frontier is weakest (verification/trust), and weakest exactly where the frontier is strongest (human experience). The two are not in conflict — they are the two halves of the same product. L3 (event stream) is the bridge: it is what would make forge’s L2 moat *visible* to a human and *consumable* by a machine.

---

## 12. Synthesis — the three truths a next-gen CLI agent must hold simultaneously

A next-gen CLI agent must be true on three axes at once, or it fails on all three:

1. **It must be able to do the work** (L1/L2): call the model, run tools, verify the result empirically, contain the blast radius. **Forge: ✅ (strong).**
2. **It must be honest about whether it worked** (L2/L3/L4): empirical verification, real failure attribution, no false greens, no misattributed failures. **Forge: ✅ on success-honesty, ❌ on failure-honesty (L4 broken).**
3. **It must be bearable to use** (L3/L5/L6/L7): live transparency, dialable autonomy, continuity, diff review, multi-surface. **Forge: ❌ (missing).**

A tool that holds truth #1 but not #2 is dangerous (it lies about success). A tool that holds #2 but not #3 is unusable (the truth is unreachable). A tool that holds #3 but not #1 is a toy. **Forge holds #1 and most of #2; it fails #3 entirely and half-fails #2 on the failure path.** The experience-engineer’s job is to make #2 and #3 reachable without weakening #1 — and the event stream (L3) is the single architectural change that does both at once.

---

## 13. What Forge Needs (ordered by topology dependency, not effort)

This is a *reading*, not a roadmap (no implementation this pass). Ordered so each step’s precondition is met:

1. **L4 — Honest termination (fix the identity contradiction first).** Add `failure_reason` to `AgentResult`; capture the model-exception cause (don’t `break` with no reason); add `forge doctor`; add exit codes. **Why first:** it’s the moral priority, it’s cheap, and it makes every later layer trustworthy to debug.
2. **L3 — The event stream (the hinge).** Add a typed event emitter at the loop’s existing lifecycle points; inject a renderer (Text/JSON/NDJSON) from the CLI; the SDK stays pure. **Why second:** it unlocks live transparency + machine composability from one mechanism, and it’s the precondition for L5/L6/L7.
3. **L2 exposure — surface the moat.** `forge run --sandbox`, `--verify-command`, expose verification gates in the run output. **Why third:** the moat exists; make it visible.
4. **L5a — Permission mode.** A graduated mode machine (even a 3-mode `default/acceptEdits/yolo` is a huge jump from the implicit single mode), with per-tool allow/deny rules; the auto-mode classifier is a later, ambitious extension. **Why fourth:** autonomy needs L2 guardrails visible first.
5. **L5b — Continuity.** Session store + `forge resume`/`fork`; background dispatch. **Why fifth:** needs L3 (replay) and L4 (honest end states).
6. **L6 — Diff-first review.** Render edits as diffs; checkpoints + `/undo`. **Why sixth:** needs L3 (diffs render from the event stream) and L5b (checkpoints = continuity).
7. **L7 — Platform.** Hooks (pre/post tool), MCP, subagents, multi-surface. **Why last:** it’s the platform layer; everything below must be solid first.

**The one architectural decision that changes everything:** emit a typed event stream from the agent loop and let renderers subscribe. That single change is the precondition for L3, the enabler for L4/L5/L6, and the thing that makes forge’s L2 moat *visible*. Everything else is a layer on top of that stream.
