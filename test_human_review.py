"""Human review test of forge-sdk ReactAgent with OllamaProvider.

Tests: Read pyproject.toml -> extract version -> write report -> verify.
"""

import time
import os

t_start = time.time()

from forge_sdk.models.ollama import OllamaProvider
from forge_sdk.agents.react import ReactAgent
from forge_sdk.agents.types import AgentContext
from forge_sdk.tools.registry import ToolRegistry
from forge_sdk.tools.filesystem import FILE_TOOLS

# 1. Set up model — local Ollama
model = OllamaProvider(
    base_url="http://localhost:11434",
    model="gemma3:4b",
)

# 2. Set up tools
registry = ToolRegistry()
for tool in FILE_TOOLS:
    registry.register(tool)

# 3. Create agent
agent = ReactAgent(
    model=model,
    tools=registry,
    max_tokens=32_000,
    max_retries=3,
)

# 4. Define task
task = (
    "Read the file /Users/srinji/forge/pyproject.toml, find the version number "
    "under [project], then write a file /tmp/forge_version_report.txt containing exactly:\n"
    "Forge SDK version: X.Y.Z\n"
    "Tested by: human reviewer\n"
    "where X.Y.Z is the version you found. After writing, read the file back to verify "
    "it was written correctly."
)

context = AgentContext(
    task=task,
    cwd="/Users/srinji/forge",
    max_steps=15,
)

# 5. Run
print(f"Starting agent run at {time.strftime('%H:%M:%S')}...")
result = agent.run(context)
elapsed = time.time() - t_start

# 6. Report
print(f"\n{'='*60}")
print(f"COMPLETED IN: {elapsed:.1f}s")
print(f"SUCCESS: {result.success}")
print(f"STEPS: {len(result.steps)}")
print(f"TOKENS: {result.total_tokens}")
print(f"EDITS: {result.edits_made}")
print(f"OUTPUT: {result.output[:300]}")
print(f"{'='*60}")

# 7. Step-by-step trace
for s in result.steps:
    flag = " [FINAL]" if s.is_final else ""
    flag += " [GUARD]" if s.loop_guard_triggered else ""
    print(f"\nStep {s.step_number}: {s.action}{flag}")
    if s.thought:
        print(f"  Thought: {s.thought[:150]}")
    if s.observation:
        print(f"  Obs: {s.observation[:200]}")

# 8. Verify output file
print(f"\n{'='*60}")
print("VERIFICATION:")
report_path = "/tmp/forge_version_report.txt"
if os.path.exists(report_path):
    with open(report_path) as f:
        content = f.read()
    print(f"File exists: YES")
    print(f"Content:\n{content}")
    expected = "Forge SDK version: 0.4.0"
    if expected in content:
        print("PASS: Version number matches!")
    else:
        print(f"FAIL: Expected '{expected}' in file")
else:
    print("File exists: NO — agent failed to write the file")

print(f"\nTotal wall time: {elapsed:.1f}s")
