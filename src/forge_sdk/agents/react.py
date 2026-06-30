"""ReAct agent — thought-action-observation loop."""

from __future__ import annotations

import json
from typing import Any

from forge_sdk.agents.types import AgentContext, AgentResult, AgentStep
from forge_sdk.audit import AuditLog
from forge_sdk.models.port import ModelPort
from forge_sdk.tools.registry import ToolRegistry
from forge_sdk.tracing.span import SpanKind
from forge_sdk.tracing.tracer import Tracer


class ReactAgent:
    """ReAct (Reason + Act) agent implementation."""

    def __init__(
        self,
        model: ModelPort,
        tools: ToolRegistry,
        tracer: Tracer | None = None,
        audit: AuditLog | None = None,
    ) -> None:
        self._model = model
        self._tools = tools
        self._tracer = tracer or Tracer()
        self._audit = audit

    def _build_system_prompt(self) -> str:
        self._tools.to_prompt_schemas()
        tool_descriptions = "\n".join(
            f"- {t.name}: {t.description} (id: {t.stable_id})" for t in self._tools.available()
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
        """Parse model response into action dict."""
        # Try to find JSON in the response
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

    def run(self, context: AgentContext) -> AgentResult:
        """Run the ReAct loop."""
        steps: list[AgentStep] = []
        messages = self._build_messages(context)

        for step_num in range(1, context.max_steps + 1):
            # Get model response
            span = self._tracer.start_span(
                name="llm.complete",
                kind=SpanKind.LLM,
                attributes={
                    "gen_ai.system": self._model.provider,
                    "gen_ai.request.model": self._model.name,
                    "gen_ai.request.messages": json.dumps(messages, default=str),
                },
            )

            response = self._model.complete(messages, temperature=0.0)
            span.attributes["gen_ai.response.content"] = response.content
            if response.reasoning:
                span.attributes["gen_ai.response.reasoning"] = response.reasoning
            span.attributes["gen_ai.usage.prompt_tokens"] = response.usage.prompt_tokens
            span.attributes["gen_ai.usage.completion_tokens"] = response.usage.completion_tokens
            span.attributes["gen_ai.usage.total_tokens"] = response.usage.total_tokens
            self._tracer.finish_span(span)

            # Audit the LLM call
            if self._audit:
                self._audit.append(
                    trace_id=self._tracer.trace_id,
                    entry_type="llm_call",
                    payload={
                        "model": self._model.name,
                        "provider": self._model.provider,
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "step": step_num,
                    },
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
            if not is_final:
                tool_span = self._tracer.start_span(
                    name=f"tool.{action}",
                    kind=SpanKind.TOOL,
                    attributes={
                        "tool.name": action,
                        "tool.input": json.dumps(action_input, default=str),
                    },
                )
                observation = self._execute_tool_sync(action, action_input)
                tool_span.attributes["tool.output"] = observation
                self._tracer.finish_span(tool_span)

                if self._audit:
                    self._audit.append(
                        trace_id=self._tracer.trace_id,
                        entry_type="tool_use",
                        payload={
                            "tool": action,
                            "input": action_input,
                            "output": observation[:500],
                        },
                    )

            step = AgentStep(
                step_number=step_num,
                thought=thought,
                action=action,
                action_input=action_input,
                observation=observation,
                is_final=is_final,
            )
            steps.append(step)

            # Add to messages for next iteration
            messages.append({"role": "assistant", "content": response.content})
            if observation:
                messages.append({"role": "user", "content": f"Tool output:\n{observation}"})

            if is_final:
                output = action_input.get("output", response.content)
                return AgentResult(
                    success=True,
                    output=output,
                    steps=steps,
                    trace_id=self._tracer.trace_id,
                    total_tokens=self._tracer.total_tokens,
                    total_cost_usd=self._tracer.total_cost_usd,
                )

        # Max steps reached
        return AgentResult(
            success=False,
            output="Max steps reached without finishing",
            steps=steps,
            trace_id=self._tracer.trace_id,
            total_tokens=self._tracer.total_tokens,
            total_cost_usd=self._tracer.total_cost_usd,
        )

    def _execute_tool_sync(self, action: str, action_input: dict[str, Any]) -> str:
        """Synchronous tool execution for the sync run() method."""
        import asyncio

        tool = self._tools.get_by_name(action)
        if tool is None:
            return f"Error: Unknown tool '{action}'"
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're inside an async context, use nest_asyncio or run_sync
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, tool.handler(**action_input))
                    result = future.result(timeout=60)
            else:
                result = loop.run_until_complete(tool.handler(**action_input))
            return result.output if result.success else f"Error: {result.error}"
        except Exception as e:
            return f"Error executing {action}: {e}"
