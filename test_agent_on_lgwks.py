"""Test the forge ReactAgent on a real lgwks issue (#349).

Goal: Use the agent to write tests for lgwks_redact and lgwks_proc,
then remove them from the EXCLUDED list in test_module_coverage.py.
"""
import asyncio
import sys
import os

# Add paths
sys.path.insert(0, "/Users/srinji/forge/src")
sys.path.insert(0, "/Users/srinji/logicalworks-")

from forge_sdk.agents.react import ReactAgent
from forge_sdk.agents.types import AgentContext, AgentResult
from forge_sdk.tools import ToolSpec, ToolResult
from forge_sdk.tools.registry import ToolRegistry
from forge_sdk.models.ollama import OllamaProvider

# Define the tools the agent needs

async def read_file(path: str) -> ToolResult:
    """Read a file's contents."""
    try:
        with open(path, 'r') as f:
            content = f.read()
        return ToolResult(success=True, output=content, metadata={"path": path, "size": len(content)})
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))

async def write_file(path: str, content: str) -> ToolResult:
    """Write content to a file."""
    try:
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else '.', exist_ok=True)
        with open(path, 'w') as f:
            f.write(content)
        return ToolResult(success=True, output=f"Written {len(content)} bytes to {path}")
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))

async def list_dir(path: str = ".") -> ToolResult:
    """List directory contents."""
    try:
        entries = sorted(os.listdir(path))
        return ToolResult(success=True, output="\n".join(entries))
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))

async def run_command(command: str) -> ToolResult:
    """Run a shell command."""
    import subprocess
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        output = result.stdout
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}"
        return ToolResult(
            success=result.returncode == 0,
            output=output.strip(),
            error=f"Exit code {result.returncode}" if result.returncode != 0 else None
        )
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))

# Create tool registry
output_schema = {"type": "object", "properties": {"success": {"type": "boolean"}, "output": {"type": "string"}}}
registry = ToolRegistry()

registry.register(ToolSpec(
    name="read_file",
    stable_id="FILE-READ-001",
    description="Read a file's contents. Use this to examine source code or test files.",
    input_schema={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    output_schema=output_schema,
    handler=read_file,
))
registry.register(ToolSpec(
    name="write_file",
    stable_id="FILE-WRITE-001",
    description="Write content to a file. Use this to create or update test files.",
    input_schema={"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]},
    output_schema=output_schema,
    handler=write_file,
))
registry.register(ToolSpec(
    name="list_dir",
    stable_id="DIR-LIST-001",
    description="List directory contents.",
    input_schema={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    output_schema=output_schema,
    handler=list_dir,
))
registry.register(ToolSpec(
    name="run_command",
    stable_id="CMD-RUN-001",
    description="Run a shell command. Use this to run tests.",
    input_schema={"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]},
    output_schema=output_schema,
    handler=run_command,
))

async def main():
    # Create the agent — pass API key from env (Bug #3 fix)
    api_key = os.environ.get("OLLAMA_API_KEY", "92e6ca23cee645b793375d92ba1ea5e0.XBrqcpxJ3WmtRnNn3pcwGGXq")
    provider = OllamaProvider(api_key=api_key, model="gemma3:4b")
    agent = ReactAgent(
        model=provider,
        tools=registry,
        max_tokens=8000,
    )

    # The task for the agent
    task = """You are working on lgwks issue #349: backfill tests for untested modules.

Your job is to:
1. Read lgwks_redact.py at /Users/srinji/logicalworks-/lgwks_redact.py
2. Read lgwks_proc.py at /Users/srinji/logicalworks-/lgwks_proc.py
3. Look at an existing test file for pattern reference: /Users/srinji/logicalworks-/tests/test_algorithms.py
4. Create /Users/srinji/logicalworks-/tests/test_lgwks_redact.py with tests for lgwks_redact
5. Create /Users/srinji/logicalworks-/tests/test_lgwks_proc.py with tests for lgwks_proc
6. Run: cd /Users/srinji/logicalworks- && python -m pytest tests/test_lgwks_redact.py tests/test_lgwks_proc.py -v

Start by reading the source files."""

    print("=" * 60)
    print("FORGE AGENT TEST: lgwks issue #349")
    print("=" * 60)
    print(f"Task: Write tests for lgwks_redact and lgwks_proc")
    print(f"Provider: Ollama Cloud (gemma3:4b)")
    print("=" * 60)

    # Run the agent
    context = AgentContext(
        task=task,
        cwd="/Users/srinji/logicalworks-",
        max_steps=25,
    )
    result = agent.run(context)

    print("\n" + "=" * 60)
    print("AGENT RESULT")
    print("=" * 60)
    print(f"Success: {result.success}")
    print(f"Steps: {len(result.steps)}")
    print(f"Output:\n{result.output}")
    print(f"Edits made: {result.edits_made}")
    print("\nSteps taken:")
    for i, step in enumerate(result.steps):
        print(f"\n--- Step {i+1} ---")
        print(f"Thought: {step.thought[:200]}...")
        print(f"Action: {step.action}({step.action_input})")
        print(f"Observation: {step.observation[:200] if step.observation else 'None'}...")

if __name__ == "__main__":
    asyncio.run(main())
