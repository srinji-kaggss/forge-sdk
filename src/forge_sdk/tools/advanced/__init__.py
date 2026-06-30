"""Advanced tool suite — world-class tools for the forge agent.

Design principle: The LLM plays a markov chain puzzle. It makes discrete
choices (read this, edit that, verify this). The tools do the heavy lifting:
parsing, diffing, graphing, embedding, crawling. The LLM spends its tokens on
REASONING about what to do next, not on DOING it.

Every tool returns structured, machine-readable output. No prose. No padding.
The agent sees exact data and decides the next action.

Tool categories:
  - Code Intelligence: AST-aware codebase graph, impact analysis, symbol search
  - Edit Intelligence: Structured diff/patch, multi-file edit, rename refactoring
  - Verify Intelligence: Test runner, syntax check, type check, security scan
  - Knowledge Intelligence: Web crawl, document extraction, semantic search
  - Memory Intelligence: Episodic recall, context compression, relevance scoring
"""

from forge_sdk.tools.advanced.code_intel import CODE_INTEL_TOOLS
from forge_sdk.tools.advanced.edit_intel import EDIT_INTEL_TOOLS
from forge_sdk.tools.advanced.verify_intel import VERIFY_INTEL_TOOLS
from forge_sdk.tools.advanced.knowledge_intel import KNOWLEDGE_INTEL_TOOLS
from forge_sdk.tools.advanced.memory_intel import MEMORY_INTEL_TOOLS

ADVANCED_TOOLS = (
    CODE_INTEL_TOOLS
    + EDIT_INTEL_TOOLS
    + VERIFY_INTEL_TOOLS
    + KNOWLEDGE_INTEL_TOOLS
    + MEMORY_INTEL_TOOLS
)

__all__ = [
    "ADVANCED_TOOLS",
    "CODE_INTEL_TOOLS",
    "EDIT_INTEL_TOOLS",
    "VERIFY_INTEL_TOOLS",
    "KNOWLEDGE_INTEL_TOOLS",
    "MEMORY_INTEL_TOOLS",
]