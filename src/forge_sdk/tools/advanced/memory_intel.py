"""Memory intelligence tools — episodic recall, context compression, relevance scoring.

The agent has a memory of past actions. It can:
  - recall: search past episodes for similar tasks
  - compress_context: summarize a long conversation into key points
  - relevance_score: score how relevant a file/section is to the current task

These tools make the agent stateful across steps within a task, and
across tasks within a session. The harness manages the memory store;
the agent queries it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from forge_sdk.tools.types import ToolResult, ToolSpec

_episode_store: list[dict[str, Any]] = []


def register_episode(episode: dict[str, Any]) -> None:
    """Register an episode in the in-memory store (called by the harness)."""
    _episode_store.append(episode)


async def recall(query: str, limit: int = 5) -> ToolResult:
    """Search past episodes for tasks similar to the current query."""
    query_words = set(query.lower().split())
    results: list[dict[str, Any]] = []

    for ep in _episode_store:
        task = ep.get("task", "")
        task_words = set(task.lower().split())
        overlap = len(query_words & task_words)
        if overlap == 0:
            continue
        score = overlap / max(len(query_words), 1)
        results.append(
            {
                "task": task,
                "outcome": ep.get("outcome", "unknown"),
                "score": round(score, 3),
                "output": (ep.get("output") or "")[:200],
            }
        )

    results.sort(key=lambda x: x["score"], reverse=True)
    return ToolResult(
        success=True,
        output=json.dumps(
            {"query": query, "episodes_searched": len(_episode_store), "results": results[:limit]},
            indent=2,
        ),
    )


async def compress_context(text: str, max_words: int = 100) -> ToolResult:
    """Compress a long text into key points (extractive summarization, no API needed)."""
    sentences = re.split(r"[.!?]+", text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]

    if not sentences:
        return ToolResult(
            success=True, output=json.dumps({"compressed": "", "method": "no_sentences"}, indent=2)
        )

    word_freq: dict[str, int] = {}
    for word in text.lower().split():
        word = re.sub(r"[^a-z0-9]", "", word)
        if len(word) > 3:
            word_freq[word] = word_freq.get(word, 0) + 1

    scored = []
    for i, sent in enumerate(sentences):
        words = sent.lower().split()
        score = sum(word_freq.get(re.sub(r"[^a-z0-9]", "", w), 0) for w in words) / max(
            len(words), 1
        )
        scored.append((score, i, sent))

    scored.sort(reverse=True)
    top = sorted(scored[: max_words // 15], key=lambda x: x[1])
    compressed = ". ".join(s[2] for s in top)

    return ToolResult(
        success=True,
        output=json.dumps(
            {
                "original_words": len(text.split()),
                "compressed_words": len(compressed.split()),
                "compression_ratio": round(len(compressed.split()) / max(len(text.split()), 1), 2),
                "compressed": compressed,
            },
            indent=2,
        ),
    )


async def relevance_score(file_path: str, task: str) -> ToolResult:
    """Score how relevant a file is to the current task (keyword overlap + symbol matching)."""
    path = Path(file_path)
    if not path.exists():
        return ToolResult(success=False, output=f"Error: {file_path} not found")

    try:
        content = path.read_text(errors="replace")
    except Exception as exc:
        return ToolResult(success=False, output=f"Error: {exc}")

    task_words = set(task.lower().split())
    content_words = set(content.lower().split())

    word_overlap = len(task_words & content_words) / max(len(task_words), 1)

    symbol_matches = 0
    for word in task_words:
        if word in content:
            symbol_matches += content.lower().count(word)

    total_score = word_overlap * 0.6 + min(symbol_matches / 20, 1.0) * 0.4

    matching_lines = []
    for i, line in enumerate(content.splitlines(), 1):
        if any(word in line.lower() for word in task_words if len(word) > 3):
            matching_lines.append({"line": i, "content": line.strip()[:80]})
            if len(matching_lines) >= 5:
                break

    return ToolResult(
        success=True,
        output=json.dumps(
            {
                "file": file_path,
                "task": task,
                "relevance_score": round(total_score, 3),
                "word_overlap": round(word_overlap, 3),
                "symbol_matches": symbol_matches,
                "matching_lines": matching_lines,
            },
            indent=2,
        ),
    )


RECALL_TOOL = ToolSpec(
    name="recall",
    description=(
        "Search past episodes for tasks similar to the current query. "
        "Returns matching past tasks with their outcome and output. "
        "Use when you're stuck — a similar task may have been solved before."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Task description to search for"},
            "limit": {"type": "integer", "description": "Max results (default: 5)"},
        },
        "required": ["query"],
    },
    output_schema={"type": "string", "description": "JSON result"},
    stable_id="TOOL-MEM-001",
    handler=recall,
)

COMPRESS_CONTEXT_TOOL = ToolSpec(
    name="compress_context",
    description=(
        "Compress a long text into key points using extractive summarization (no API needed). "
        "Use when a file or output is too long to process — compress it first, then reason over the summary."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text to compress"},
            "max_words": {"type": "integer", "description": "Target word count (default: 100)"},
        },
        "required": ["text"],
    },
    output_schema={"type": "string", "description": "JSON result"},
    stable_id="TOOL-MEM-002",
    handler=compress_context,
)

RELEVANCE_SCORE_TOOL = ToolSpec(
    name="relevance_score",
    description=(
        "Score how relevant a file is to the current task. Returns relevance score (0-1), "
        "word overlap, symbol matches, and matching lines. "
        "Use to prioritize which files to read next in a large codebase."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "Path to the file"},
            "task": {"type": "string", "description": "Current task description"},
        },
        "required": ["file_path", "task"],
    },
    output_schema={"type": "string", "description": "JSON result"},
    stable_id="TOOL-MEM-003",
    handler=relevance_score,
)

MEMORY_INTEL_TOOLS = [RECALL_TOOL, COMPRESS_CONTEXT_TOOL, RELEVANCE_SCORE_TOOL]
