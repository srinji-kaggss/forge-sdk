"""ReAct agent — v2 thought-action-observation loop.

Fixes #2: async-native execution (no get_event_loop()).
Implements INV-204: LoopGuard halts on repeated identical calls.
Implements INV-201: verification pipeline after final action.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from forge_v2.agent_loop.loop_guard import LoopGuard
from forge_v2.agents.types import AgentContext, AgentResult, AgentStep

log = logging.getLogger(__name__)


class ReactAgent:
    """ReAct (Reason + Act) agent — v2 with async core and LoopGuard."""

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
        tool_descriptions = "\n".join(
            f"- {t.name}: {t.description} (id: {t.stable_id})"
            for t in self._tools.available()
        )
        return (
            "You are a coding agent. You solve tasks by reasoning step-by-step "
            "and using tools.\n\n"
            "Available tools:\n"
            f"{tool_descriptions}\n\n"
            "For each step, respond with a JSON object:\n"
            '{"thought": "your reasoning", "action": "tool_name", "action_input": {...}}\n\n'
            "When you are done, respond with:\n"
            '{"thought": "final reasoning", "action": "finish",'
            ' "action_input": {"output": "your answer"}}\n\n'
            "Rules:\n"
            "- Always think before acting.\n"
            "- Use tools to gather information before writing code.\n"
            "- If a tool fails, reason about why and try a different approach.\n"
            "- When you have enough information, finish with a clear output.\n"
        )

    def _parse_response(self, content: str) -> dict[str, Any]:
        content = content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(content[start:end])
        return {"thought": content, "action": "finish", "action_input": {"output": content}}

    async def _execute_tool(self, action: str, action_input: dict[str, Any]) -> str:
        tool = self._tools.get_by_name(action)
        if tool is None:
            return f"Error: Unknown tool '{action}'"
        try:
            result = await tool.handler(**action_input)
            return result.output if result.success else f"Error: {result.error}"
        except Exception as e:
            return f"Error executing {action}: {e}"

    def _build_messages(self, context: AgentContext) -> list[dict[str, Any]]:
        messages = [{"role": "system", "content": self._build_system_prompt()}]
        messages.extend(context.messages)
        messages.append({"role": "user", "content": context.task})
        return messages

    async def arun(self, context: AgentContext) -> AgentResult:
        """Async core — the canonical execution loop."""
        steps: list[AgentStep] = []
        messages = self._build_messages(context)
        self._guard.reset()

        for step_num in range(1, context.max_steps + 1):
            response = self._model.complete(messages, temperature=0.0)

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

            observation = ""
            is_final = action == "finish"
            loop_guard_triggered = False

            if not is_final:
                # INV-204: LoopGuard check
                if self._guard.check(action, action_input):
                    observation = (
                        f"BLOCKED by LoopGuard: repeated identical call to '{action}' "
                        f"({self._guard.max_repeats} times). Try a different approach."
                    )
                    loop_guard_triggered = True
                    log.warning("LoopGuard triggered on %s", action)
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

            messages.append({"role": "assistant", "content": response.content})
            if observation:
                messages.append({"role": "user", "content": f"Tool output:\n{observation}"})

            if is_final:
                output = action_input.get("output", response.content)
                result = AgentResult(
                    success=True,
                    output=output,
                    steps=steps,
                    trace_id="",
                    total_tokens=0,
                    total_cost_usd=0.0,
                )

                # INV-201: run verification pipeline
                if self._verifier:
                    result.verification = self._verifier.verify(output, context.cwd)
                    result.success = result.verification_passed

                return result

        return AgentResult(
            success=False,
            output="Max steps reached without finishing",
            steps=steps,
            trace_id="",
        )

    def run(self, context: AgentContext) -> AgentResult:
        """Sync wrapper — fixes #2 by using asyncio.run() directly."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.arun(context))
        else:
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, self.arun(context)).result(timeout=120)
