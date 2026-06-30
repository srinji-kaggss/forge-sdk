"""Test script: forge-sdk ReactAgent with calculator tool + file write."""

from __future__ import annotations

import asyncio
import json

from forge_sdk.agents.react import ReactAgent
from forge_sdk.agents.types import AgentContext
from forge_sdk.models.ollama import OllamaProvider
from forge_sdk.tools.filesystem import FILE_TOOLS
from forge_sdk.tools.registry import ToolRegistry
from forge_sdk.tools.types import ToolResult, ToolSpec


# ── 1. Define the calculator tool ──────────────────────────────────────────
async def calculator_handler(expression: str) -> ToolResult:
    """Evaluate a math expression and return the result."""
    try:
        result = eval(expression)  # noqa: S307 — intentional sandbox eval
        return ToolResult(success=True, output=str(result))
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))


calculator_spec = ToolSpec(
    name="calculator",
    description="Evaluate a mathematical expression and return the result.",
    input_schema={
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "A Python expression to evaluate (e.g. '2+2', '10*5')",
            }
        },
        "required": ["expression"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "result": {"type": "string", "description": "The evaluated result"},
        },
    },
    stable_id="TOOL-CALC-001",
    handler=calculator_handler,
)


# ── 2. Register tools ──────────────────────────────────────────────────────
registry = ToolRegistry()
registry.register(calculator_spec)

# Also register the built-in write_file tool so the agent can write results
write_file_tool = next(t for t in FILE_TOOLS if t.name == "write_file")
registry.register(write_file_tool)

# ── 3. Create model provider ────────────────────────────────────────────────
model = OllamaProvider(model="gemma3:4b", base_url="http://localhost:11434")

# ── 4. Create agent ─────────────────────────────────────────────────────────
agent = ReactAgent(model=model, tools=registry)

# ── 5. Build context and run ────────────────────────────────────────────────
context = AgentContext(
    task=(
        "Calculate 2+2, then 10*5, then write both results to /tmp/calc_results.txt. "
        "The file should contain one result per line."
    ),
    cwd="/Users/srinji/forge",
    max_steps=15,
)

print("Running agent...")
result = agent.run(context)

print(f"\n{'='*60}")
print(f"Success:  {result.success}")
print(f"Steps:    {len(result.steps)}")
print(f"Tokens:   {result.total_tokens}")
print(f"Edits:    {result.edits_made}")
print(f"Output:   {result.output[:300]}")
print(f"{'='*60}")

# Print step trace
for step in result.steps:
    flag = " [GUARD]" if step.loop_guard_triggered else ""
    flag += " [FINAL]" if step.is_final else ""
    print(f"  Step {step.step_number}: {step.action}{flag}")
    if step.thought:
        print(f"    Thought: {step.thought[:120]}")
    if step.observation:
        print(f"    Obs: {step.observation[:120]}")

# Verify the output file
print(f"\n--- /tmp/calc_results.txt ---")
try:
    with open("/tmp/calc_results.txt") as f:
        print(f.read())
except FileNotFoundError:
    print("(file not found)")
