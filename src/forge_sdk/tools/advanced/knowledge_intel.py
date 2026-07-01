"""Knowledge intelligence tools — web crawling, document extraction, semantic search.

The agent doesn't just read local files. It can:
  - web_search: search the web (free DuckDuckGo, no API key)
  - web_fetch: fetch a URL and extract clean text
  - extract_document: parse PDF, DOCX, HTML → text
  - semantic_search: search local files by meaning (not just regex)

These are the agent's eyes to the outside world. The harness provides
the degradation chain: free first, paid fallback, honest on failure.
"""

from __future__ import annotations

import asyncio
import json
import re
import urllib.parse
from pathlib import Path
from typing import Any

from forge_sdk.tools.types import ToolResult, ToolSpec


async def web_search(query: str, limit: int = 5) -> ToolResult:
    """Search the web using DuckDuckGo HTML (free, no API key)."""
    encoded = urllib.parse.quote(query)
    url = f"https://html.duckduckgo.com/html/?q={encoded}"

    try:
        proc = await asyncio.create_subprocess_shell(
            f"curl -sL '{url}' -H 'User-Agent: Mozilla/5.0'",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        html = stdout.decode(errors="replace")

        results: list[dict[str, str]] = []
        for match in re.finditer(
            r'<a[^>]+class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?'
            r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
            html, re.DOTALL
        ):
            link = match.group(1)
            title = re.sub(r"<[^>]+>", "", match.group(2)).strip()
            snippet = re.sub(r"<[^>]+>", "", match.group(3)).strip()

            if link.startswith("//duckduckgo.com/l/?uddg="):
                link = urllib.parse.unquote(link.split("uddg=")[1].split("&")[0])

            results.append({"title": title, "url": link, "snippet": snippet})
            if len(results) >= limit:
                break

        if not results:
            return ToolResult(success=False, output=f"No results found for: {query}")

        return ToolResult(success=True, output=json.dumps({"query": query, "results": results}, indent=2))
    except Exception as exc:
        return ToolResult(success=False, output=f"Search failed: {exc}")


async def web_fetch(url: str, max_chars: int = 5000) -> ToolResult:
    """Fetch a URL and extract clean text (strip HTML tags)."""
    try:
        proc = await asyncio.create_subprocess_shell(
            f"curl -sL '{url}' -H 'User-Agent: Mozilla/5.0' --max-time 15",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        html = stdout.decode(errors="replace")

        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()

        return ToolResult(
            success=len(text) > 0,
            output=json.dumps({
                "url": url,
                "chars": len(text),
                "content": text[:max_chars],
            }, indent=2),
        )
    except Exception as exc:
        return ToolResult(success=False, output=f"Fetch failed: {exc}")


async def extract_document(file_path: str, max_chars: int = 10000) -> ToolResult:
    """Extract text from PDF, DOCX, HTML, or any file. Picks the best available extractor."""
    path = Path(file_path)
    if not path.exists():
        return ToolResult(success=False, output=f"Error: {file_path} not found")

    suffix = path.suffix.lower()
    text = ""

    if suffix == ".pdf":
        for extractor in ["pdftotext", "python3 -c 'import fitz; print(fitz.open(\"{}\")[0].get_text())'"]:
            try:
                proc = await asyncio.create_subprocess_shell(
                    f'{extractor} "{file_path}"',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await proc.communicate()
                text = stdout.decode(errors="replace").strip()
                if text:
                    break
            except Exception:
                continue
    elif suffix in (".docx", ".doc", ".xlsx", ".pptx"):
        try:
            proc = await asyncio.create_subprocess_shell(
                f'python3 -c "from markitdown import MarkItDown; print(MarkItDown().convert(\\"{file_path}\\").text_content)"',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            text = stdout.decode(errors="replace").strip()
        except Exception:
            pass
    elif suffix in (".html", ".htm"):
        raw = path.read_text(errors="replace")
        text = re.sub(r"<[^>]+>", " ", raw)
        text = re.sub(r"\s+", " ", text).strip()
    else:
        text = path.read_text(errors="replace")

    if not text:
        return ToolResult(success=False, output=f"Could not extract text from {file_path}")

    return ToolResult(
        success=True,
        output=json.dumps({
            "file": file_path,
            "type": suffix,
            "chars": len(text),
            "content": text[:max_chars],
        }, indent=2),
    )


async def semantic_search(query: str, path: str = ".", limit: int = 10) -> ToolResult:
    """Search files by semantic similarity (keyword overlap scoring, no API needed)."""
    # L1: Path safety check
    from forge_sdk.security import _check_path_safety
    violation = _check_path_safety(path, ".", check_writes=False)
    if violation:
        return ToolResult(success=False, output="", error=violation,
                          metadata={"blocked": True})

    root = Path(path)
    query_words = set(query.lower().split())
    results: list[dict[str, Any]] = []

    for pyf in root.rglob("*"):
        if any(skip in str(pyf) for skip in [".venv", "__pycache__", ".git", "site-packages", "node_modules"]):
            continue
        if not pyf.is_file():
            continue
        if pyf.stat().st_size > 100_000:
            continue

        try:
            content = pyf.read_text(errors="replace")
        except Exception:
            continue

        content_words = set(content.lower().split())
        overlap = len(query_words & content_words)
        if overlap == 0:
            continue

        score = overlap / len(query_words) if query_words else 0
        if score > 0.1:
            results.append({
                "file": str(pyf.relative_to(root)),
                "score": round(score, 3),
                "matching_words": list(query_words & content_words)[:10],
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    return ToolResult(
        success=True,
        output=json.dumps({"query": query, "matches": len(results), "results": results[:limit]}, indent=2),
    )


WEB_SEARCH_TOOL = ToolSpec(
    name="web_search",
    description=(
        "Search the web using DuckDuckGo (free, no API key). Returns title, url, snippet for each result. "
        "Use for finding documentation, examples, error solutions, or current information. "
        "Limit: 5 results by default. Degrades honestly: returns error if search fails."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "limit": {"type": "integer", "description": "Max results (default: 5)"},
        },
        "required": ["query"],
    },
    output_schema={"type": "string", "description": "JSON result"},
        stable_id="TOOL-KNOW-001",
        handler=web_search,
)

WEB_FETCH_TOOL = ToolSpec(
    name="web_fetch",
    description=(
        "Fetch a URL and extract clean text (HTML tags stripped). "
        "Use after web_search to read the full content of a result. "
        "max_chars: truncate output (default: 5000). 15s timeout."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to fetch"},
            "max_chars": {"type": "integer", "description": "Max chars to return (default: 5000)"},
        },
        "required": ["url"],
    },
    output_schema={"type": "string", "description": "JSON result"},
        stable_id="TOOL-KNOW-002",
        handler=web_fetch,
)

EXTRACT_DOCUMENT_TOOL = ToolSpec(
    name="extract_document",
    description=(
        "Extract text from PDF, DOCX, XLSX, PPTX, HTML, or any file. "
        "Picks the best available extractor (pdftotext, pymupdf, markitdown, raw read). "
        "Use for reading non-code files: documentation, specs, reports."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "Path to the document"},
            "max_chars": {"type": "integer", "description": "Max chars (default: 10000)"},
        },
        "required": ["file_path"],
    },
    output_schema={"type": "string", "description": "JSON result"},
        stable_id="TOOL-KNOW-003",
        handler=extract_document,
)

SEMANTIC_SEARCH_TOOL = ToolSpec(
    name="semantic_search",
    description=(
        "Search files by semantic similarity (keyword overlap scoring). No API needed. "
        "Returns files ranked by relevance to the query. "
        "Use when grep is too literal — this finds files that 'talk about' your topic."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Natural language query"},
            "path": {"type": "string", "description": "Root directory (default: '.')"},
            "limit": {"type": "integer", "description": "Max results (default: 10)"},
        },
        "required": ["query"],
    },
    output_schema={"type": "string", "description": "JSON result"},
        stable_id="TOOL-KNOW-004",
        handler=semantic_search,
)

KNOWLEDGE_INTEL_TOOLS = [WEB_SEARCH_TOOL, WEB_FETCH_TOOL, EXTRACT_DOCUMENT_TOOL, SEMANTIC_SEARCH_TOOL]