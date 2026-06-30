"""ReAct agent — thought-action-observation loop.

v0.4.0: Frontier-hardened with interpretability, observability, context management.

AI-native design:
- System prompt optimized for AI consumption (not human reading)
- Structured JSON output with recovery guidance
- Tool errors include candidates and suggestions
- LoopGuard prevents repeated identical calls
- Context window management (token counting, truncation)
- Usage limits (token/cost caps)
- Retry with exponential backoff
- Deep interpretability (reasoning trace, decision logs)
- Structured observability (metrics, distributed tracing)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from forge_sdk.agents.types import AgentContext, AgentResult, AgentStep
from forge_sdk.verifiers import VerificationEvidence, VerificationStatus

# Issue #23: AgentContext.cwd was recorded but never threaded into the
# actual tool-call boundary -- every filesystem/shell/search/verify tool
# resolves its own relative path/cwd argument against the PROCESS's real
# os.getcwd(), not context.cwd, so cwd= was decorative. These tools accept
# an optional path-ish parameter that defaults to "." (i.e. falls back to
# process cwd when the LLM omits it); inject context.cwd there instead.
_CWD_RELATIVE_KEYS = ("path", "file_path", "cwd")
_CWD_DEFAULT_PARAM = {
    "list_dir": "path",
    "grep": "path",
    "glob": "path",
    "semantic_search": "path",
    "symbol_search": "path",
    "call_graph": "path",
    "impact_analysis": "path",
    "run_tests": "path",
    "git_diff": "path",
    "git_status": "path",
    "shell": "cwd",
}

# Verbs that imply the task requires code/file changes
_ACTION_VERBS = re.compile(
    r"\b(implement|fix|create|write|add|modify|update|build|refactor|"
    r"patch|repair|construct|generate|develop|compose|insert|append|"
    r"edit|change|convert|migrate|rewrite|set up|setup)\b",
    re.IGNORECASE,
)

# Module-level (not recompiled every call)
_ERROR_KEYWORDS = re.compile(
    r"\b(bug|error|vulnerability|security|critical|urgent|broken|failing|"
    r"crash|exception|stack.?trace|traceback|regression|issue|problem|"
    r"failure|fault|defect|weakness|exploit|injection|overflow)\b",
    re.IGNORECASE,
)

# Issue #24: an explicit "don't touch files" instruction must override the
# positive keyword heuristics above — an audit/research task that mentions
# "bug" or "security" in its description is not an edit task just because
# those words appear, if the task also says it's read-only.
_READ_ONLY_MARKERS = re.compile(
    r"\b(read.?only"
    r"|do\s+not\s+(?:edit|modify|write|change|touch)"
    r"|don'?t\s+(?:edit|modify|write|change|touch)"
    r"|no\s+(?:file\s+)?(?:edits|changes|modifications)"
    r"|without\s+(?:editing|modifying|writing|changing)"
    r"|(?:report|summary|analysis|audit)\s+only)\b",
    re.IGNORECASE,
)

log = logging.getLogger(__name__)


# --- Parse strategies (OKF S3-safe: strategy registry, no if/elif chains) ---
# Each strategy has: id (stable), applies(content) -> bool, execute(content) -> dict|None

from abc import ABC, abstractmethod


class ParseStrategy(ABC):
    """Base class for parse strategies. Stable ID + applies/execute contract."""
    id: str  # e.g. "PARSE-MARKDOWN-001"

    @abstractmethod
    def applies(self, content: str) -> bool:
        """Return True if this strategy can handle the content."""

    @abstractmethod
    def execute(self, content: str) -> dict[str, Any] | None:
        """Parse and return action dict, or None if parsing fails."""


def _unwrap_nested_finish(parsed: dict[str, Any]) -> dict[str, Any] | None:
    """If finish action contains a tool call as JSON string, unwrap it.
    Shared helper used by multiple strategies.
    """
    if parsed.get("action") != "finish":
        return None
    output = parsed.get("action_input", {}).get("output")
    if not isinstance(output, str):
        return None
    inner_start = output.find("{")
    inner_end = output.rfind("}") + 1
    if inner_start < 0 or inner_end <= inner_start:
        return None
    try:
        inner = json.loads(output[inner_start:inner_end])
        if "action" in inner and "action_input" in inner:
            return inner
    except (json.JSONDecodeError, ValueError):
        pass
    return None


class StripMarkdownStrategy(ParseStrategy):
    """PARSE-001: Strip markdown code fences before JSON extraction."""
    id = "PARSE-001"

    def applies(self, content: str) -> bool:
        return "```json" in content or "```" in content

    def execute(self, content: str) -> dict[str, Any] | None:
        if "```json" in content:
            stripped = content.split("```json")[1].split("```")[0].strip()
        else:
            stripped = content.split("```")[1].split("```")[0].strip()
        # Re-enter the strategy chain with stripped content
        for strategy in _PARSE_STRATEGIES:
            if strategy.id != self.id and strategy.applies(stripped):
                result = strategy.execute(stripped)
                if result is not None:
                    return result
        return None


class FullJsonStrategy(ParseStrategy):
    """PARSE-002: Parse the full JSON object (fast path). Handles nested finish→tool unwrapping."""
    id = "PARSE-002"

    def applies(self, content: str) -> bool:
        return "{" in content and "}" in content

    def execute(self, content: str) -> dict[str, Any] | None:
        start = content.find("{")
        end = content.rfind("}") + 1
        if start < 0 or end <= start:
            return None
        json_str = content[start:end]
        if len(json_str) > 100_000:
            json_str = json_str[:100_000]
        try:
            parsed = json.loads(json_str)
            if not isinstance(parsed, dict) or "action" not in parsed:
                return None
            # Try unwrapping nested finish→tool call
            unwrapped = _unwrap_nested_finish(parsed)
            return unwrapped if unwrapped else parsed
        except (json.JSONDecodeError, ValueError):
            return None


class FirstValidJsonStrategy(ParseStrategy):
    """PARSE-003: Find the FIRST valid JSON object (handles concatenated objects from small models)."""
    id = "PARSE-003"

    def applies(self, content: str) -> bool:
        return "{" in content

    def execute(self, content: str) -> dict[str, Any] | None:
        pos = 0
        while pos < len(content):
            obj_start = content.find("{", pos)
            if obj_start < 0:
                break
            depth = 0
            for i in range(obj_start, min(obj_start + 50_000, len(content))):
                if content[i] == "{":
                    depth += 1
                elif content[i] == "}":
                    depth -= 1
                    if depth == 0:
                        candidate = content[obj_start:i + 1]
                        try:
                            parsed = json.loads(candidate)
                            if isinstance(parsed, dict) and "action" in parsed:
                                unwrapped = _unwrap_nested_finish(parsed)
                                return unwrapped if unwrapped else parsed
                        except (json.JSONDecodeError, ValueError):
                            pass
                        pos = i + 1
                        break
            else:
                break
        return None


# Strategy registry — ordered by specificity (fastest/strictest first)
_PARSE_STRATEGIES: list[ParseStrategy] = [
    StripMarkdownStrategy(),
    FullJsonStrategy(),
    FirstValidJsonStrategy(),
]


# --- Interpretability: reasoning trace dataclass ---
@dataclass
class ReasoningStep:
    """One step in the agent's reasoning trace — for interpretability."""
    step: int
    thought: str
    action: str
    action_input: dict
    observation: str
    is_final: bool
    loop_guard_triggered: bool
    duration_ms: float = 0.0
    tokens_used: int = 0
    decision_rationale: str = ""


@dataclass
class ReasoningTrace:
    """Full reasoning trace for a run — deep interpretability."""
    task: str
    steps: list[ReasoningStep] = field(default_factory=list)
    total_duration_ms: float = 0.0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    success: bool = False
    failure_reason: str = ""

    def summary(self) -> str:
        """Human-readable summary of reasoning."""
        lines = [f"Task: {self.task}", f"Steps: {len(self.steps)}", f"Success: {self.success}"]
        for s in self.steps:
            flag = " [GUARD]" if s.loop_guard_triggered else ""
            flag += " [FINAL]" if s.is_final else ""
            lines.append(f"  Step {s.step}: {s.action}{flag} ({s.duration_ms:.0f}ms)")
            if s.thought:
                lines.append(f"    Thought: {s.thought[:120]}")
            if s.decision_rationale:
                lines.append(f"    Why: {s.decision_rationale}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        """JSON-serializable for observability export."""
        return {
            "task": self.task,
            "steps": [
                {
                    "step": s.step,
                    "thought": s.thought,
                    "action": s.action,
                    "action_input": s.action_input,
                    "observation": s.observation[:500],
                    "is_final": s.is_final,
                    "loop_guard_triggered": s.loop_guard_triggered,
                    "duration_ms": s.duration_ms,
                    "tokens_used": s.tokens_used,
                    "decision_rationale": s.decision_rationale,
                }
                for s in self.steps
            ],
            "total_duration_ms": self.total_duration_ms,
            "total_tokens": self.total_tokens,
            "total_cost_usd": self.total_cost_usd,
            "success": self.success,
            "failure_reason": self.failure_reason,
        }


# --- Observability: structured metrics ---
@dataclass
class AgentMetrics:
    """Structured metrics for observability — emitted per run."""
    run_id: str = ""
    model: str = ""
    provider: str = ""
    total_steps: int = 0
    tool_calls: int = 0
    tool_errors: int = 0
    loop_guard_triggers: int = 0
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_cost_usd: float = 0.0
    duration_ms: float = 0.0
    retries: int = 0
    context_truncations: int = 0
    verification_passed: bool = True
    edits_made: int = 0

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "model": self.model,
            "provider": self.provider,
            "total_steps": self.total_steps,
            "tool_calls": self.tool_calls,
            "tool_errors": self.tool_errors,
            "loop_guard_triggers": self.loop_guard_triggers,
            "total_tokens": self.total_tokens,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_cost_usd": self.total_cost_usd,
            "duration_ms": self.duration_ms,
            "retries": self.retries,
            "context_truncations": self.context_truncations,
            "verification_passed": self.verification_passed,
            "edits_made": self.edits_made,
        }


class LoopGuard:
    """INV-204: halt on repeated identical tool calls. Prevents ~30% stuck rate."""

    def __init__(self, max_repeats: int = 3) -> None:
        self.max_repeats = max_repeats
        self._counts: dict[str, int] = {}

    def _hash(self, tool_name: str, tool_input: dict) -> str:
        raw = json.dumps({"tool": tool_name, "input": tool_input}, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def check(self, tool_name: str, tool_input: dict) -> bool:
        """Returns True if this call should be BLOCKED (repeated too many times)."""
        h = self._hash(tool_name, tool_input)
        self._counts[h] = self._counts.get(h, 0) + 1
        return self._counts[h] > self.max_repeats

    def reset(self) -> None:
        self._counts.clear()


class UsageLimiter:
    """Enforce token and cost limits per run."""

    def __init__(self, max_tokens: int = 100_000, max_cost_usd: float = 1.0) -> None:
        self.max_tokens = max_tokens
        self.max_cost_usd = max_cost_usd
        self.total_tokens = 0
        self.total_cost_usd = 0.0

    def check(self, usage_tokens: int = 0, cost_usd: float = 0.0) -> bool:
        """Returns True if limit EXCEEDED."""
        self.total_tokens += usage_tokens
        self.total_cost_usd += cost_usd
        return self.total_tokens > self.max_tokens or self.total_cost_usd > self.max_cost_usd

    def remaining_tokens(self) -> int:
        return max(0, self.max_tokens - self.total_tokens)


class ContextManager:
    """Manage context window — truncate to stay within token limits."""

    def __init__(self, max_tokens: int = 32_000, reserve_output: int = 2_000) -> None:
        self.max_tokens = max_tokens
        self.reserve_output = reserve_output

    def _estimate_tokens(self, messages: list[dict]) -> int:
        """Rough token estimation: ~4 chars per token."""
        total_chars = sum(len(json.dumps(m, default=str)) for m in messages)
        return total_chars // 4

    def fit(self, messages: list[dict], system_prompt: str) -> list[dict]:
        """Truncate messages to fit within context window. Preserves system prompt + task."""
        if not messages:
            return messages

        available = self.max_tokens - self.reserve_output - len(system_prompt) // 4
        if available <= 0:
            return messages[:2]  # Keep at least system + task

        # Keep system prompt (index 0), task (last user msg), and recent messages
        system = messages[0:1]
        task_msg = messages[-1:] if messages[-1].get("role") == "user" else []
        history = messages[1:-1] if task_msg else messages[1:]

        # Estimate tokens for system + task
        fixed_tokens = self._estimate_tokens(system + task_msg)
        remaining = available - fixed_tokens

        # Keep most recent messages first
        kept = []
        for msg in reversed(history):
            msg_tokens = len(json.dumps(msg, default=str)) // 4
            if remaining - msg_tokens < 0:
                break
            remaining -= msg_tokens
            kept.insert(0, msg)

        result = system + kept + task_msg
        truncation_count = len(history) - len(kept)
        return result, truncation_count


class ReactAgent:
    """ReAct (Reason + Act) agent — v0.4.0 frontier-hardened.

    v0.4.0 additions:
    - Tool parameter schemas in prompt (fixes critical bug)
    - Context window management (token counting, truncation)
    - Usage limits (token/cost caps)
    - Retry with exponential backoff
    - Deep interpretability (reasoning trace, decision logs)
    - Structured observability (metrics)
    """

    def __init__(
        self,
        model: Any,
        tools: Any,
        tracer: Any = None,
        audit: Any = None,
        verifier: Any = None,
        loop_guard: LoopGuard | None = None,
        max_tokens: int = 32_000,
        max_cost_usd: float = 1.0,
        max_retries: int = 3,
        sandbox_dir: str | None = None,
        verify_command: str | None = None,
        auto_verify: bool = True,
        verify_timeout_seconds: float = 120.0,
    ) -> None:
        self._model = model
        self._tools = tools
        self._tracer = tracer
        self._audit = audit
        self._verifier = verifier
        self._guard = loop_guard or LoopGuard()
        self._max_retries = max_retries
        self._context = ContextManager(max_tokens=max_tokens)
        self._limiter = UsageLimiter(max_tokens=max_tokens * 10, max_cost_usd=max_cost_usd)
        self._sandbox_dir = sandbox_dir  # Restrict file writes to this directory
        # Issue #20: a configurable build/test command that gates the
        # terminal SUCCESS verdict. If not given explicitly, auto-detected
        # by project type (Cargo.toml -> cargo build, edited .py files ->
        # py_compile) when auto_verify is True. None means no gate is
        # available for this project — SUCCESS is then NOT empirically
        # verified and the result says so explicitly (see arun()).
        self._verify_command = verify_command
        self._auto_verify = auto_verify
        self._verify_timeout_seconds = verify_timeout_seconds

    def _build_system_prompt(self) -> str:
        """AI-native system prompt with full tool schemas."""
        tool_descriptions = []
        for t in self._tools.available():
            # CRITICAL FIX: Include parameter schemas so model knows what to pass
            params_str = json.dumps(t.input_schema, indent=2)
            tool_descriptions.append(
                f"- {t.name}: {t.description}\n"
                f"  Parameters: {params_str}"
            )
        tools_block = "\n\n".join(tool_descriptions)

        sandbox_note = ""
        if self._sandbox_dir:
            sandbox_note = (
                f"\n## Sandbox\n"
                f"All file operations are restricted to: {self._sandbox_dir}\n"
                f"Writing outside this directory will be blocked.\n"
            )

        return (
            "You are an expert coding agent. You solve tasks by reasoning step-by-step "
            "and using tools to gather information and make changes.\n\n"
            "## How to respond\n\n"
            "For each step, respond with EXACTLY one JSON object (no other text):\n"
            '{"thought": "your reasoning about what to do next",'
            ' "action": "tool_name",'
            ' "action_input": {"param": "value"}}\n\n'
            "When the task is complete, respond with:\n"
            '{"thought": "summary of what was accomplished",'
            ' "action": "finish",'
            ' "action_input": {"output": "your final answer or summary"}}\n\n'
            "## Available tools\n\n"
            f"{tools_block}\n"
            f"{sandbox_note}\n"
            "## Rules\n\n"
            "- Always think before acting — explain your reasoning in 'thought'.\n"
            "- Read AT MOST 3 files before acting. Do not over-research.\n"
            "- If the task requires writing a file, write it within your FIRST 5 steps.\n"
            "- If a tool fails, read the error message carefully and try a different approach.\n"
            "- Do NOT repeat the same tool call with the same arguments — it will be blocked.\n"
            "- When you have enough information, finish with a clear, complete output.\n"
            "- Keep responses concise — the output is consumed by other AI systems.\n"
            "- Use the EXACT tool name from the list above (not the id).\n"
            "- Prefer ACTION over investigation. Write first, verify second.\n"
        )

    def _parse_response(self, content: str) -> dict[str, Any]:
        """Parse model response into action dict.

        Uses a strategy registry (OKF S3-safe — no nested if/elif chains).
        Each strategy has a stable ID, applies() predicate, and execute() method.
        First successful strategy wins. Debug logging traces which strategy matched.
        """
        content = content.strip()
        for strategy in _PARSE_STRATEGIES:
            if strategy.applies(content):
                result = strategy.execute(content)
                if result is not None:
                    log.debug("PARSE: strategy=%s matched", strategy.id)
                    return result
        log.debug("PARSE: no strategy matched, fallback to finish")
        return {"thought": content, "action": "finish", "action_input": {"output": content}}

    def _resolve_cwd(self, action: str, action_input: dict[str, Any], cwd: str) -> dict[str, Any]:
        """Issue #23: scope every tool call to context.cwd at this single
        dispatch choke point, instead of relying on each tool handler to
        resolve paths correctly on its own (they don't — they resolve
        against os.getcwd()).
        """
        if cwd in (".", "", None):
            return action_input
        base = Path(cwd).expanduser()
        resolved = dict(action_input)

        for key in _CWD_RELATIVE_KEYS:
            value = resolved.get(key)
            if isinstance(value, str) and value and not Path(value).expanduser().is_absolute():
                resolved[key] = str((base / value).resolve())

        default_param = _CWD_DEFAULT_PARAM.get(action)
        if default_param and default_param not in resolved:
            resolved[default_param] = str(base.resolve())

        return resolved

    async def _execute_tool(
        self, action: str, action_input: dict[str, Any], context: AgentContext | None = None
    ) -> str:
        """Execute a tool with retry and structured output."""
        tool = self._tools.get_by_name(action)
        if tool is None:
            available = [t.name for t in self._tools.available()]
            return (
                f"Error: Unknown tool '{action}'. "
                f"Available tools: {available}. "
                f"Use the exact tool name from the list."
            )
        if context is not None:
            action_input = self._resolve_cwd(action, action_input, context.cwd)
        try:
            result = await tool.handler(**action_input)
            return result.as_message
        except Exception as e:
            # Sanitize error — don't leak internals
            error_type = type(e).__name__
            return f"Error executing {action}: {error_type}. Try a different approach."

    def _build_messages(self, context: AgentContext) -> list[dict[str, Any]]:
        messages = [{"role": "system", "content": self._build_system_prompt()}]
        messages.extend(context.messages)
        messages.append({"role": "user", "content": context.task})
        return messages

    def _extract_edits_from_observation(
        self, action: str, action_input: dict, observation: str
    ) -> list[str]:
        """Extract file paths modified by a tool call from its observation."""
        edits: list[str] = []
        write_tools = {"write_file", "create_file"}
        shell_tools = {"shell", "run_command"}

        if action in write_tools:
            path = action_input.get("path", "")
            if path:
                edits.append(path)
        elif action in shell_tools:
            cmd = action_input.get("command", "")
            write_patterns = [
                r">\s*(\S+)",
                r"tee\s+(\S+)",
                r"cp\s+\S+\s+(\S+)",
                r"mv\s+\S+\s+(\S+)",
                r"mkdir\s+.*",
                r"touch\s+(\S+)",
                r"sed\s+.*\s*>\s*(\S+)",
            ]
            for pattern in write_patterns:
                matches = re.findall(pattern, cmd)
                edits.extend(matches)
        return edits

    def _task_implies_edits(self, task: str) -> bool:
        """Heuristic: does the task prompt imply code/file changes are expected?

        Issue #24: explicit negation ("read-only", "do not edit") wins over
        any positive keyword match — without this, an explicitly read-only
        audit/research task gets a false success:false just because its
        description happens to mention a word like "bug" or "security".
        """
        if _READ_ONLY_MARKERS.search(task):
            return False
        if _ACTION_VERBS.search(task):
            return True
        if _ERROR_KEYWORDS.search(task):
            return True
        return False

    def _detect_verify_command(self, cwd: str, edited_files: list[str]) -> str | None:
        """Issue #20: pick a real build/test command for whatever project
        type lives at cwd, so SUCCESS is never asserted on code nobody
        compiled. Deliberately narrow — only the two cases this repo has
        real evidence for (lgwks's Rust TUI work, forge's own Python code).
        Returns None (no gate) rather than guessing a command that might not
        exist; an absent gate is reported honestly, not silently assumed.
        """
        base = Path(cwd).expanduser()
        if (base / "Cargo.toml").is_file():
            return "cargo build --quiet"
        if any(f.endswith(".py") for f in edited_files) and (
            (base / "pyproject.toml").is_file() or (base / "setup.py").is_file()
        ):
            py_files = [f for f in edited_files if f.endswith(".py")]
            quoted = " ".join(f'"{f}"' for f in py_files)
            return f"python3 -m py_compile {quoted}"
        return None

    async def _run_verify_command(self, command: str, cwd: str) -> VerificationEvidence:
        """Run the build/test command and turn its exit code into evidence.
        A real subprocess run, not a heuristic — this is the actual gate
        issue #20 asked for.
        """
        start = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=self._verify_timeout_seconds
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return VerificationEvidence(
                    gate_name="build_verify",
                    status=VerificationStatus.ERROR,
                    message=f"Verify command timed out after {self._verify_timeout_seconds}s: {command}",
                    duration_ms=(time.monotonic() - start) * 1000,
                )
            output = (stdout.decode(errors="replace") + stderr.decode(errors="replace"))[-2000:]
            status = VerificationStatus.PASSED if proc.returncode == 0 else VerificationStatus.FAILED
            return VerificationEvidence(
                gate_name="build_verify",
                status=status,
                message=(
                    f"`{command}` exited {proc.returncode}"
                    + (f"\n{output}" if status is VerificationStatus.FAILED else "")
                ),
                details={"command": command, "returncode": proc.returncode},
                duration_ms=(time.monotonic() - start) * 1000,
            )
        except Exception as e:
            return VerificationEvidence(
                gate_name="build_verify",
                status=VerificationStatus.ERROR,
                message=f"Could not run verify command `{command}`: {type(e).__name__}: {e}",
                duration_ms=(time.monotonic() - start) * 1000,
            )

    def _check_sandbox(self, action: str, action_input: dict) -> str | None:
        """F4 fix: Check ALL tools against sandbox, not just write_file.

        L1 PERIMETER: every tool that touches the filesystem routes through
        the centralized _check_path_safety() in forge_sdk.security.
        """
        if not self._sandbox_dir:
            return None

        # Tools that touch the filesystem — ALL must be sandbox-checked
        FILE_TOOLS = {
            "write_file", "create_file", "read_file", "list_dir",
            "patch_line", "patch_symbol", "insert_at", "rename_symbol",
            "multi_edit", "code_structure",
        }

        if action in FILE_TOOLS:
            path = action_input.get("path", "") or action_input.get("file_path", "")
            if path:
                from forge_sdk.security import _check_path_safety
                check_writes = action in {"write_file", "create_file", "patch_line",
                                          "patch_symbol", "insert_at", "multi_edit"}
                violation = _check_path_safety(
                    path, self._sandbox_dir, self._sandbox_dir, check_writes
                )
                if violation:
                    return violation

        # Shell tool — check cwd is within sandbox
        if action == "shell":
            cwd = action_input.get("cwd", ".")
            from forge_sdk.security import _check_path_safety
            violation = _check_path_safety(cwd, self._sandbox_dir, self._sandbox_dir)
            if violation:
                return violation

        return None

    async def _call_model_with_retry(
        self, messages: list[dict], temperature: float = 0.0
    ) -> Any:
        """Call model with exponential backoff retry."""
        last_error = None
        for attempt in range(self._max_retries):
            try:
                return self._model.complete(messages, temperature=temperature)
            except Exception as e:
                last_error = e
                error_type = type(e).__name__
                if "rate" in error_type.lower() or "429" in str(e):
                    wait = (2 ** attempt) * 1.0
                    log.warning("Rate limited, retrying in %.1fs (attempt %d)", wait, attempt + 1)
                    await asyncio.sleep(wait)
                elif "timeout" in error_type.lower() or "connection" in error_type.lower():
                    wait = (2 ** attempt) * 0.5
                    log.warning("Connection error, retrying in %.1fs (attempt %d)", wait, attempt + 1)
                    await asyncio.sleep(wait)
                else:
                    raise
        raise last_error

    async def arun(self, context: AgentContext) -> AgentResult:
        """Async core — the canonical execution loop with observability."""
        run_start = time.monotonic()
        guard = LoopGuard(max_repeats=self._guard.max_repeats)
        trace = ReasoningTrace(task=context.task)
        metrics = AgentMetrics(
            run_id=hashlib.sha256(f"{context.task}{time.time()}".encode()).hexdigest()[:12],
            model=getattr(self._model, "name", "unknown"),
            provider=getattr(self._model, "provider", "unknown"),
        )
        steps: list[AgentStep] = []
        all_edits: list[str] = []

        # Convergence tracking: detect stalled agents
        steps_since_edit = 0
        max_steps_without_edit = 5  # Nudge after 5 steps with no file changes
        convergence_nudges = 0
        max_nudges = 2  # Force finish after 2 ignored nudges

        messages = self._build_messages(context)

        for step_num in range(1, context.max_steps + 1):
            step_start = time.monotonic()

            # Convergence check: force finish if agent is spinning
            if steps_since_edit >= max_steps_without_edit:
                convergence_nudges += 1
                if convergence_nudges > max_nudges:
                    log.warning("Convergence: %d nudges ignored, force-finishing", convergence_nudges - 1)
                    break
                log.warning("Convergence: %d steps without edit, nudging (nudge %d/%d)", steps_since_edit, convergence_nudges, max_nudges)
                # Inject a stronger nudge into the conversation
                nudge_msg = (
                    f"URGENT: You have taken {steps_since_edit} steps without making any file changes. "
                    f"This is nudge {convergence_nudges} of {max_nudges}. "
                )
                if convergence_nudges == 1:
                    nudge_msg += (
                        "STOP reading files. You have enough information. "
                        "Write the output file NOW using write_file, then call finish. "
                        "If you cannot write, call finish immediately with a summary of what you found."
                    )
                else:
                    nudge_msg += (
                        "FINAL WARNING. Call finish NOW with your best summary of findings. "
                        "Do NOT attempt any more tool calls."
                    )
                messages.append({
                    "role": "user",
                    "content": nudge_msg,
                })
                steps_since_edit = 0  # Reset after nudge

            # Context management: truncate if too long
            messages, trunc_count = self._context.fit(messages, self._build_system_prompt())
            metrics.context_truncations += trunc_count

            # Check usage limits
            if self._limiter.check():
                log.warning("Usage limit exceeded at step %d", step_num)
                break

            # Call model with retry
            try:
                response = await self._call_model_with_retry(messages)
            except Exception as e:
                log.error("Model call failed after retries: %s", e)
                break

            # Track tokens
            if hasattr(response, "usage"):
                usage = response.usage
                self._limiter.check(usage.total_tokens)
                metrics.prompt_tokens += usage.prompt_tokens
                metrics.completion_tokens += usage.completion_tokens
                metrics.total_tokens += usage.total_tokens

            # TRACER: emit LLM call span
            if self._tracer:
                self._tracer.llm_call(
                    model=getattr(self._model, "name", "unknown"),
                    provider=getattr(self._model, "provider", "unknown"),
                    messages=messages[-2:],  # Last 2 messages for context
                    response_content=response.content[:500],
                    reasoning=getattr(response, "reasoning", None),
                    usage={
                        "gen_ai.usage.prompt_tokens": getattr(usage, "prompt_tokens", 0),
                        "gen_ai.usage.completion_tokens": getattr(usage, "completion_tokens", 0),
                        "gen_ai.usage.total_tokens": getattr(usage, "total_tokens", 0),
                    } if hasattr(response, "usage") else {},
                    **({"step": step_num, "run_id": metrics.run_id}),
                )

            # Parse response
            try:
                parsed = self._parse_response(response.content)
            except (json.JSONDecodeError, ValueError):
                parsed = {
                    "thought": response.content,
                    "action": "finish",
                    "action_input": {"output": response.content},
                }

            thought = parsed.get("thought", "")
            action = parsed.get("action", "finish")
            action_input = parsed.get("action_input", {})

            # Execute tool if not finish
            observation = ""
            is_final = action == "finish"
            loop_guard_triggered = False
            decision_rationale = ""

            if not is_final:
                metrics.tool_calls += 1

                # Sandbox check
                sandbox_error = self._check_sandbox(action, action_input)
                if sandbox_error:
                    observation = sandbox_error
                    decision_rationale = "Sandbox blocked file write outside allowed directory"
                # LoopGuard check
                elif guard.check(action, action_input):
                    observation = (
                        f"BLOCKED: You have called '{action}' with the same arguments "
                        f"{guard.max_repeats} times. This indicates you are stuck. "
                        f"Try a completely different approach or finish if possible."
                    )
                    loop_guard_triggered = True
                    metrics.loop_guard_triggers += 1
                    decision_rationale = f"LoopGuard blocked repeated identical call (count={guard._counts.get(guard._hash(action, action_input), 0)})"
                else:
                    observation = await self._execute_tool(action, action_input, context)
                    if observation.startswith("Error"):
                        metrics.tool_errors += 1
                        decision_rationale = f"Tool '{action}' returned error"
                    else:
                        decision_rationale = f"Tool '{action}' succeeded"

                # TRACER: emit tool call span
                if self._tracer:
                    self._tracer.tool_call(
                        tool_name=action,
                        input_data=action_input,
                        output=observation[:500],
                        success=not observation.startswith("Error"),
                        **{"step": step_num, "run_id": metrics.run_id},
                    )

                # AUDIT: emit tool execution entry
                if self._audit:
                    self._audit.append(
                        entry_type="tool_call",
                        trace_id=self._tracer.trace_id if self._tracer else metrics.run_id,
                        payload={
                            "tool": action,
                            "input": action_input,
                            "output_preview": observation[:200],
                            "success": not observation.startswith("Error"),
                            "step": step_num,
                            "model": metrics.model,
                        },
                    )

            step_duration = (time.monotonic() - step_start) * 1000

            # Convergence: track steps since last edit
            if not is_final and not loop_guard_triggered:
                new_edits = self._extract_edits_from_observation(action, action_input, observation)
                if new_edits:
                    steps_since_edit = 0
                else:
                    steps_since_edit += 1

            # Record interpretability trace
            trace.steps.append(ReasoningStep(
                step=step_num,
                thought=thought,
                action=action,
                action_input=action_input,
                observation=observation[:500],
                is_final=is_final,
                loop_guard_triggered=loop_guard_triggered,
                duration_ms=step_duration,
                decision_rationale=decision_rationale,
            ))

            step = AgentStep(
                step_number=step_num,
                thought=thought,
                action=action,
                action_input=action_input,
                observation=observation,
                is_final=is_final,
                loop_guard_triggered=loop_guard_triggered,
            )
            steps.append(step)

            # Track file edits
            if not is_final and not loop_guard_triggered and not sandbox_error:
                all_edits.extend(
                    self._extract_edits_from_observation(action, action_input, observation)
                )

            # Add to messages for next iteration
            messages.append({"role": "assistant", "content": response.content})
            if observation:
                messages.append({"role": "user", "content": f"Tool output:\n{observation}"})

            # Emit structured log for observability
            log.info(
                "agent.step",
                extra={
                    "run_id": metrics.run_id,
                    "step": step_num,
                    "action": action,
                    "is_final": is_final,
                    "duration_ms": step_duration,
                    "tokens": response.usage.total_tokens if hasattr(response, "usage") else 0,
                },
            )

            if is_final:
                output = action_input.get("output", response.content)

                # INV-201: run verification pipeline
                verification: list[VerificationEvidence] = []
                if self._verifier and output.strip():
                    # Only run verification on code-like output (skip for plain text)
                    looks_like_code = (
                        "def " in output or "class " in output or "import " in output
                        or "function " in output or "const " in output or "var " in output
                        or output.strip().startswith("{") or output.strip().startswith("[")
                    )
                    if looks_like_code:
                        verification = self._verifier.verify(output, context.cwd)

                # Issue #20: the gates above only ever inspected the final
                # message TEXT, never the actual files written to disk —
                # a Rust file with a real compile error still passed every
                # existing gate because nothing in the pipeline ran a build.
                # Run the project's real build/test command against
                # context.cwd whenever files were actually edited.
                build_gate_ran = False
                if all_edits:
                    verify_cmd = self._verify_command
                    if verify_cmd is None and self._auto_verify:
                        verify_cmd = self._detect_verify_command(context.cwd, all_edits)
                    if verify_cmd:
                        build_gate_ran = True
                        verification.append(await self._run_verify_command(verify_cmd, context.cwd))

                verification_passed = all(
                    v.status == VerificationStatus.PASSED for v in verification
                ) if verification else True

                metrics.verification_passed = verification_passed
                metrics.edits_made = len(all_edits)

                # False-green check
                success = verification_passed
                failure_reason = ""

                if not verification_passed and build_gate_ran:
                    success = False
                    failure_reason = "Build/verify command failed on the files written — see verification evidence."
                elif not verification_passed and self._task_implies_edits(context.task):
                    success = False
                    failure_reason = "Verification failed for a task that requires code changes."
                elif len(all_edits) == 0 and self._task_implies_edits(context.task):
                    success = False
                    failure_reason = (
                        "Agent completed without modifying any files. "
                        "Task implies code changes were expected."
                    )
                elif all_edits and not build_gate_ran:
                    # Honest about the gap (CLAUDE.md: unknowns stay labeled
                    # unknown) -- files changed but no build/test command was
                    # available for this project type, so this SUCCESS was
                    # never empirically verified against the files on disk.
                    output = (
                        f"{output}\n\n[Note: {len(all_edits)} file(s) changed but no build/verify "
                        f"command was available for this project type — SUCCESS reflects the agent's "
                        f"own report, not an empirical check.]"
                    )

                if not success and failure_reason:
                    output = f"{output}\n\n[Failure reason: {failure_reason}]"

                # Finalize trace and metrics
                trace.success = success
                trace.failure_reason = failure_reason
                trace.total_duration_ms = (time.monotonic() - run_start) * 1000
                trace.total_tokens = metrics.total_tokens
                trace.total_cost_usd = metrics.total_cost_usd
                metrics.total_steps = step_num
                metrics.duration_ms = trace.total_duration_ms

                log.info("agent.run.complete", extra=metrics.to_dict())

                return AgentResult(
                    success=success,
                    output=output,
                    steps=steps,
                    trace_id=self._tracer.trace_id if self._tracer else "",
                    total_tokens=metrics.total_tokens,
                    total_cost_usd=metrics.total_cost_usd,
                    verification=verification,
                    edits_made=all_edits,
                )

        # Max steps reached
        metrics.total_steps = context.max_steps
        metrics.duration_ms = (time.monotonic() - run_start) * 1000
        trace.total_duration_ms = metrics.duration_ms
        trace.failure_reason = "Max steps reached"
        log.warning("agent.run.max_steps", extra=metrics.to_dict())

        return AgentResult(
            success=False,
            output="Max steps reached without finishing. Try increasing max_steps or simplifying the task.",
            steps=steps,
            trace_id=self._tracer.trace_id if self._tracer else "",
            total_tokens=metrics.total_tokens,
            total_cost_usd=metrics.total_cost_usd,
            edits_made=all_edits,
        )

    def run(self, context: AgentContext) -> AgentResult:
        """Sync wrapper — Python 3.14+ compatible (fixes #2)."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running loop — safe to use asyncio.run
            return asyncio.run(self.arun(context))
        else:
            # Running loop exists — run in a new thread with its own event loop
            import concurrent.futures

            def _run_in_new_loop():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    return new_loop.run_until_complete(self.arun(context))
                finally:
                    new_loop.close()

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(_run_in_new_loop)
                return future.result(timeout=120)
