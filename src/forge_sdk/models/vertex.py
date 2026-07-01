"""Google Cloud Vertex AI (Gemini) provider — satisfies ModelPort protocol.

Built on the official `google-genai` SDK (https://pypi.org/project/google-genai/)
rather than hand-rolled REST calls. The SDK's `vertexai=True` client mode
resolves Application Default Credentials itself (via `google-auth`, already
a transitive dependency of google-genai) — no manual `gcloud`
subprocess/token-TTL bookkeeping needed.

Region defaults to northamerica-northeast1 (Montreal) per the standing
Canada-data-residency requirement. northamerica-northeast2 (Toronto) was
verified 2026-06-30 to return 400 FAILED_PRECONDITION for generateContent —
do not switch the default without re-verifying that region works.
"""

from __future__ import annotations

import os

from google import genai
from google.genai import types as genai_types

from forge_sdk.models.types import ModelChunk, ModelResponse, Usage

_DEFAULT_LOCATION = "northamerica-northeast1"


class VertexAuthError(RuntimeError):
    """Raised when required Vertex config (project) is missing."""


class VertexProvider:
    """Vertex AI Gemini provider."""

    def __init__(
        self,
        api_key: str | None = None,  # unused (ADC-only); accepted for ForgeConfig.create_model() compat
        base_url: str = "",  # unused; accepted for ForgeConfig.create_model() compat
        model: str = "gemini-2.5-flash",
        project: str | None = None,
        location: str | None = None,
    ) -> None:
        del api_key, base_url
        self._model = model
        self._project = project or os.environ.get("GOOGLE_CLOUD_PROJECT", "")
        self._location = location or os.environ.get("GOOGLE_CLOUD_LOCATION", _DEFAULT_LOCATION)
        if not self._project:
            raise VertexAuthError(
                "GOOGLE_CLOUD_PROJECT is not set — the vertex provider requires an explicit project"
            )
        self._client = genai.Client(vertexai=True, project=self._project, location=self._location)

    @property
    def name(self) -> str:
        return self._model

    @property
    def provider(self) -> str:
        return "vertex"

    @property
    def context_window(self) -> int:
        return 1_048_576

    @property
    def max_output(self) -> int:
        return 65_536

    @property
    def supports_reasoning(self) -> bool:
        return False

    @staticmethod
    def _to_gemini_contents(messages: list[dict]) -> tuple[str | None, list[dict]]:
        """Translate OpenAI-style messages into Gemini contents + system instruction.

        Gemini has no "system" role in `contents`; system turns are collected
        into a separate system_instruction string instead. Returns plain
        dicts (ContentDict) — the SDK accepts these directly, no need to
        construct typed genai_types.Content objects.
        """
        system_parts: list[str] = []
        contents: list[dict] = []
        role_map = {"assistant": "model", "user": "user"}
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_parts.append(content)
                continue
            contents.append({"role": role_map.get(role, "user"), "parts": [{"text": content}]})
        system_instruction = "\n\n".join(system_parts) if system_parts else None
        return system_instruction, contents

    @staticmethod
    def _openai_tools_to_gemini_tool(tools: list[dict]) -> genai_types.Tool:
        """Convert forge's canonical OpenAI-shaped tool schemas
        (ToolSpec.to_prompt_schema()) into one genai_types.Tool holding all
        function declarations — the SDK validates/normalizes the JSON
        Schema itself rather than forge hand-building the request dict.
        """
        declarations = []
        for tool in tools:
            function = tool.get("function", tool)  # tolerate a bare function dict too
            declarations.append(
                genai_types.FunctionDeclaration(
                    name=function.get("name", ""),
                    description=function.get("description", ""),
                    parameters=function.get("parameters", {"type": "object", "properties": {}}),
                )
            )
        return genai_types.Tool(function_declarations=declarations)

    def _build_config(
        self,
        *,
        temperature: float,
        max_tokens: int | None,
        stop: list[str] | None,
        tools: list[dict] | None,
        system_instruction: str | None,
    ) -> genai_types.GenerateContentConfig:
        return genai_types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            stop_sequences=stop or None,
            tools=[self._openai_tools_to_gemini_tool(tools)] if tools else None,
            system_instruction=system_instruction,
        )

    def _parse_response(self, response: genai_types.GenerateContentResponse) -> ModelResponse:
        candidates = response.candidates or []
        candidate = candidates[0] if candidates else None
        parts = candidate.content.parts if candidate and candidate.content and candidate.content.parts else []
        content = "".join(p.text for p in parts if p.text)
        tool_calls = [
            {"id": p.function_call.id or "", "name": p.function_call.name or "", "arguments": p.function_call.args or {}}
            for p in parts
            if p.function_call
        ]
        usage = response.usage_metadata
        finish_reason = candidate.finish_reason.value if candidate and candidate.finish_reason else ""
        return ModelResponse(
            content=content,
            reasoning=None,
            model=self._model,
            provider="vertex",
            usage=Usage(
                prompt_tokens=usage.prompt_token_count or 0 if usage else 0,
                completion_tokens=usage.candidates_token_count or 0 if usage else 0,
                total_tokens=usage.total_token_count or 0 if usage else 0,
            ),
            finish_reason=finish_reason,
            raw=response.model_dump() if hasattr(response, "model_dump") else {},
            tool_calls=tool_calls,
        )

    def complete(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
        tools: list[dict] | None = None,
    ) -> ModelResponse:
        system_instruction, contents = self._to_gemini_contents(messages)
        config = self._build_config(
            temperature=temperature,
            max_tokens=max_tokens,
            stop=stop,
            tools=tools,
            system_instruction=system_instruction,
        )
        response = self._client.models.generate_content(model=self._model, contents=contents, config=config)
        return self._parse_response(response)

    def complete_stream(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
        tools: list[dict] | None = None,
    ) -> list[ModelChunk]:
        # No caller in the ReactAgent loop uses complete_stream today (only
        # mesh.py delegates to it); satisfy the protocol via one complete()
        # call wrapped as a single chunk instead of adding an unused
        # streaming consumer.
        response = self.complete(
            messages, temperature=temperature, max_tokens=max_tokens, stop=stop, tools=tools
        )
        return [
            ModelChunk(
                delta=response.content,
                reasoning_delta="",
                finish_reason=response.finish_reason,
                usage=response.usage,
            )
        ]
