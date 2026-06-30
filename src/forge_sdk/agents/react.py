"""ReAct agent — thought-action-observation loop.

AI-native design:
- System prompt optimized for AI consumption (not human reading)
- Structured JSON output with recovery guidance
- Tool errors include candidates and suggestions
- LoopGuard prevents repeated identical calls
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from typing import Any

from forge_sdk.agents.types import AgentContext, AgentResult, AgentStep
from forge_sdk.verifiers import VerificationEvidence, VerificationStatus

# Verbs that imply the task requires code/file changes
_ACTION_VERBS = re.compile(
    r"\b(implement|fix|create|write|add|modify|update|build|refactor|"
    r"patch|repair|construct|generate|develop|compose|insert|append|"
    r"edit|change|convert|migrate|rewrite|set up|setup)\b",
    re.IGNORECASE,
)

log = logging.getLogger(__name__)


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


class ReactAgent:
    """ReAct (Reason + Act) agent — v1 with async core, LoopGuard, AI-native prompts."""

    def __init__(
        self,
        model: Any,
        tools: Any,
        tracer: Any = None,
        audit: Any = None,
        verifier: Any = None,
        loop_guard: LoopGuard | None = None,
    ) -> None:
        self._model = model
        self._tools = tools
        self._tracer = tracer
        self._audit = audit
        self._verifier = verifier
        self._guard = loop_guard or LoopGuard()

    def _build_system_prompt(self) -> str:
        """AI-native system prompt — designed for the model, not a human reader."""
        tool_descriptions = []
        for t in self._tools.available():
            tool_descriptions.append(
                f"- {t.name} (id: {t.stable_id}): {t.description}"
            )
        tools_block = "\n\n".join(tool_descriptions)

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
            f"{tools_block}\n\n"
            "## Rules\n\n"
            "- Always think before acting — explain your reasoning in 'thought'.\n"
            "- Use tools to gather information before making changes.\n"
            "- If a tool fails, read the error message carefully and try a different approach.\n"
            "- Do NOT repeat the same tool call with the same arguments — it will be blocked.\n"
            "- When you have enough information, finish with a clear, complete output.\n"
            "- Keep responses concise — the output is consumed by other AI systems.\n"
        )

    def _parse_response(self, content: str) -> dict[str, Any]:
        """Parse model response into action dict. Handles markdown code blocks."""
        content = content.strip()
        # Handle markdown code blocks
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        # Find JSON object
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(content[start:end])
        # Fallback: treat entire response as finish
        return {"thought": content, "action": "finish", "action_input": {"output": content}}

    async def _execute_tool(self, action: str, action_input: dict[str, Any]) -> str:
        """Execute a tool and return structured output for AI consumption."""
        tool = self._tools.get_by_name(action)
        if tool is None:
            available = [t.name for t in self._tools.available()]
            return (
                f"Error: Unknown tool '{action}'. "
                f"Available tools: {available}. "
                f"Check the tool name and try again."
            )
        try:
            result = await tool.handler(**action_input)
            return result.as_message
        except Exception as e:
            return f"Error executing {action}: {type(e).__name__}: {e}. Try a different approach."

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
        # Tools that write/create files
        write_tools = {"write_file", "create_file"}
        # Tools that could modify files via shell
        shell_tools = {"shell", "run_command"}

        if action in write_tools:
            path = action_input.get("path", "")
            if path:
                edits.append(path)
        elif action in shell_tools:
            cmd = action_input.get("command", "")
            # Common patterns that indicate file writes
            write_patterns = [
                r">\s*(\S+)",  # echo > file
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
            # If the shell command succeeded and looks write-like, be conservative
            # and trust the observation (don't false-positive on echo/ls)
        elif action == "finish":
            pass  # finish doesn't write files

        return edits

    def _task_implies_edits(self, task: str) -> bool:
        """Heuristic: does the task prompt imply code/file changes are expected?"""
        return bool(_ACTION_VERBS.search(task))

    async def arun(self, context: AgentContext) -> AgentResult:
        """Async core — the canonical execution loop."""
        steps: list[AgentStep] = []
        messages = self._build_messages(context)
        self._guard.reset()
        all_edits: list[str] = []

        for step_num in range(1, context.max_steps + 1):
            # Get model response
            response = self._model.complete(messages, temperature=0.0)

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

            if not is_final:
                # LoopGuard check — INV-204
                if self._guard.check(action, action_input):
                    observation = (
                        f"BLOCKED: You have called '{action}' with the same arguments "
                        f"{self._guard.max_repeats} times. This indicates you are stuck. "
                        f"Try a completely different approach or finish if possible."
                    )
                    loop_guard_triggered = True
                    log.warning("LoopGuard triggered on %s (step %d)", action, step_num)
                else:
                    observation = await self._execute_tool(action, action_input)

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
            if not is_final and not loop_guard_triggered:
                all_edits.extend(
                    self._extract_edits_from_observation(action, action_input, observation)
                )

            # Add to messages for next iteration
            messages.append({"role": "assistant", "content": response.content})
            if observation:
                messages.append({"role": "user", "content": f"Tool output:\n{observation}"})

            if is_final:
                output = action_input.get("output", response.content)

                # INV-201: run verification pipeline on final output
                verification: list[VerificationEvidence] = []
                if self._verifier and output.strip():
                    verification = self._verifier.verify(output, context.cwd)

                # INV-202: success = verification passed, not self-rated confidence
                verification_passed = all(
                    v.status == VerificationStatus.PASSED for v in verification
                ) if verification else True  # no verifier = pass (backwards compat)

                # False-green check (issue #12):
                # success must be False if:
                #   1. verification failed AND task requires code changes
                #   2. zero edits made AND task implies edits were expected
                success = verification_passed
                failure_reason = ""

                if not verification_passed and self._task_implies_edits(context.task):
                    success = False
                    failure_reason = "Verification failed for a task that requires code changes."
                elif len(all_edits) == 0 and self._task_implies_edits(context.task):
                    success = False
                    failure_reason = (
                        "Agent completed without modifying any files. "
                        "Task implies code changes were expected."
                    )

                if not success and failure_reason:
                    output = f"{output}\n\n[Failure reason: {failure_reason}]"

                return AgentResult(
                    success=success,
                    output=output,
                    steps=steps,
                    trace_id=self._tracer.trace_id if self._tracer else "",
                    total_tokens=self._tracer.total_tokens if self._tracer else 0,
                    total_cost_usd=self._tracer.total_cost_usd if self._tracer else 0.0,
                    verification=verification,
                    edits_made=all_edits,
                )

        # Max steps reached
        return AgentResult(
            success=False,
            output="Max steps reached without finishing. Try increasing max_steps or simplifying the task.",
            steps=steps,
            trace_id=self._tracer.trace_id if self._tracer else "",
            total_tokens=self._tracer.total_tokens if self._tracer else 0,
            total_cost_usd=self._tracer.total_cost_usd if self._tracer else 0.0,
            edits_made=all_edits,
        )

    def run(self, context: AgentContext) -> AgentResult:
        """Sync wrapper — Python 3.14+ compatible (fixes #2)."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.arun(context))
        else:
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, self.arun(context)).result(timeout=120)
