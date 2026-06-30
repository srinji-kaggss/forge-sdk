"""Basic example: run an agent with default tools.

Usage:
    source .venv/bin/activate
    python examples/basic.py
"""

from forge_sdk import ReactAgent, OllamaProvider, ToolRegistry, AgentContext
from forge_sdk.tools import get_default_tools

# 1. Create model (local Ollama by default)
model = OllamaProvider(model="gemma3:4b")

# 2. Register default tools (filesystem + search + shell)
tools = ToolRegistry()
for tool in get_default_tools():
    tools.register(tool)

# 3. Create agent
agent = ReactAgent(model=model, tools=tools)

# 4. Run a task
result = agent.run(AgentContext(
    task="Read the file pyproject.toml and tell me the version",
    cwd=".",
    max_steps=10,
))

# 5. Print results
print(f"Success: {result.success}")
print(f"Steps: {len(result.steps)}")
print(f"Tokens: {result.total_tokens}")
print(f"Output: {result.output}")
if result.edits_made:
    print(f"Files modified: {result.edits_made}")
