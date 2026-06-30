"""Tracer — orchestrates span creation, context, and export."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from forge_sdk.tracing.span import Span, SpanKind, SpanStatus


class Tracer:
    """Manages spans for a single agent session."""

    def __init__(self, trace_id: str | None = None, session_id: str | None = None) -> None:
        self.trace_id = trace_id or uuid.uuid4().hex
        self.session_id = session_id or uuid.uuid4().hex
        self._spans: list[Span] = []
        self._span_stack: list[Span] = []
        self._export_path: Path | None = None

    def set_export_path(self, path: Path) -> None:
        self._export_path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    def start_span(
        self,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: dict[str, Any] | None = None,
    ) -> Span:
        parent_id = self._span_stack[-1].span_id if self._span_stack else None
        span = Span(
            trace_id=self.trace_id,
            parent_span_id=parent_id,
            name=name,
            kind=kind,
            attributes=attributes or {},
        )
        self._spans.append(span)
        self._span_stack.append(span)
        return span

    def finish_span(self, span: Span, status: SpanStatus = SpanStatus.OK) -> None:
        span.finish(status)
        if self._span_stack and self._span_stack[-1].span_id == span.span_id:
            self._span_stack.pop()

    def current_span(self) -> Span | None:
        return self._span_stack[-1] if self._span_stack else None

    def llm_call(
        self,
        model: str,
        provider: str,
        messages: list[dict],
        response_content: str,
        reasoning: str | None = None,
        usage: dict[str, int] | None = None,
        **attributes: Any,
    ) -> Span:
        """Convenience: create and finish an LLM span."""
        span = self.start_span(
            name="llm.complete",
            kind=SpanKind.LLM,
            attributes={
                "gen_ai.system": provider,
                "gen_ai.request.model": model,
                "gen_ai.response.model": attributes.get("response_model", model),
                "gen_ai.request.messages": json.dumps(messages, default=str),
                "gen_ai.response.content": response_content,
                **({"gen_ai.response.reasoning": reasoning} if reasoning else {}),
                **(usage or {}),
                **attributes,
            },
        )
        span.finish(SpanStatus.OK)
        return span

    def tool_call(
        self,
        tool_name: str,
        input_data: dict,
        output: str,
        success: bool,
        **attributes: Any,
    ) -> Span:
        """Convenience: create and finish a tool span."""
        span = self.start_span(
            name=f"tool.{tool_name}",
            kind=SpanKind.TOOL,
            attributes={
                "tool.name": tool_name,
                "tool.input": json.dumps(input_data, default=str),
                "tool.output": output,
                "tool.success": success,
                **attributes,
            },
        )
        span.finish(SpanStatus.OK if success else SpanStatus.ERROR)
        return span

    def export_jsonl(self, path: Path | None = None) -> Path:
        target = path or self._export_path
        if target is None:
            raise ValueError("No export path set")
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w") as f:
            for span in self._spans:
                f.write(json.dumps(span.to_dict(), default=str) + "\n")
        return target

    @property
    def spans(self) -> list[Span]:
        return list(self._spans)

    @property
    def total_tokens(self) -> int:
        total = 0
        for span in self._spans:
            if span.kind == SpanKind.LLM:
                total += span.attributes.get("gen_ai.usage.total_tokens", 0)
        return total

    @property
    def total_cost_usd(self) -> float:
        """Estimate cost from span attributes. Requires pricing in attributes."""
        cost = 0.0
        for span in self._spans:
            if span.kind == SpanKind.LLM:
                cost += span.attributes.get("gen_ai.cost_usd", 0.0)
        return cost
