"""Google Cloud Vertex AI (Gemini) provider — satisfies ModelPort protocol.

Auth is Application Default Credentials, resolved by shelling out to
`gcloud auth application-default print-access-token` — zero new dependency
(no google-auth / google-cloud-aiplatform SDK). The token lives only in this
process's memory for its TTL window; it is never printed, logged, traced, or
written to disk by this module.

Region defaults to northamerica-northeast1 (Montreal) per the standing
Canada-data-residency requirement. northamerica-northeast2 (Toronto) was
verified 2026-06-30 to return 400 FAILED_PRECONDITION for generateContent —
do not switch the default without re-verifying that region works.
"""

from __future__ import annotations

import os
import subprocess
import time
from typing import Any

import httpx

from forge_sdk.models.types import ModelChunk, ModelResponse, Usage

_TOKEN_TTL_SECONDS = 45 * 60  # ADC access tokens last ~1h; refresh before expiry
_DEFAULT_LOCATION = "northamerica-northeast1"


class VertexAuthError(RuntimeError):
    """Raised when an ADC access token or required config cannot be resolved."""


def _fetch_access_token() -> str:
    try:
        result = subprocess.run(
            ["gcloud", "auth", "application-default", "print-access-token"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise VertexAuthError(f"gcloud invocation failed: {exc}") from exc
    if result.returncode != 0:
        raise VertexAuthError(
            "gcloud auth application-default print-access-token failed "
            f"(exit {result.returncode}): {result.stderr.strip()}"
        )
    token = result.stdout.strip()
    if not token:
        raise VertexAuthError("gcloud returned an empty access token")
    return token


class VertexProvider:
    """Vertex AI Gemini provider."""

    def __init__(
        self,
        api_key: str | None = None,  # unused (ADC-only); accepted for ForgeConfig.create_model() compat
        base_url: str = "",
        model: str = "gemini-2.5-flash",
        project: str | None = None,
        location: str | None = None,
    ) -> None:
        del api_key  # ADC-only; accepted for ForgeConfig.create_model() kwarg compatibility
        self._model = model
        self._project = project or os.environ.get("GOOGLE_CLOUD_PROJECT", "")
        self._location = location or os.environ.get("GOOGLE_CLOUD_LOCATION", _DEFAULT_LOCATION)
        if not self._project:
            raise VertexAuthError(
                "GOOGLE_CLOUD_PROJECT is not set — the vertex provider requires an explicit project"
            )
        host = f"{self._location}-aiplatform.googleapis.com"
        self._base_url = base_url.rstrip("/") or (
            f"https://{host}/v1/projects/{self._project}/locations/{self._location}"
            f"/publishers/google/models/{self._model}"
        )
        self._client = httpx.Client(timeout=120.0)
        self._token = ""
        self._token_fetched_at = 0.0

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

    def _access_token(self) -> str:
        now = time.monotonic()
        if not self._token or (now - self._token_fetched_at) > _TOKEN_TTL_SECONDS:
            self._token = _fetch_access_token()
            self._token_fetched_at = now
        return self._token

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token()}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _to_gemini_contents(messages: list[dict]) -> tuple[dict | None, list[dict]]:
        """Translate OpenAI-style messages into Gemini contents + systemInstruction.

        Gemini has no "system" role in `contents`; system turns are collected
        into a separate systemInstruction block instead.
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
        system_instruction = (
            {"parts": [{"text": "\n\n".join(system_parts)}]} if system_parts else None
        )
        return system_instruction, contents

    def _build_payload(
        self,
        messages: list[dict],
        *,
        temperature: float,
        max_tokens: int | None,
        stop: list[str] | None,
    ) -> dict[str, Any]:
        system_instruction, contents = self._to_gemini_contents(messages)
        generation_config: dict[str, Any] = {"temperature": temperature}
        if max_tokens is not None:
            generation_config["maxOutputTokens"] = max_tokens
        if stop:
            generation_config["stopSequences"] = stop
        payload: dict[str, Any] = {"contents": contents, "generationConfig": generation_config}
        if system_instruction is not None:
            payload["systemInstruction"] = system_instruction
        return payload

    def _parse_response(self, data: dict[str, Any]) -> ModelResponse:
        candidates = data.get("candidates") or []
        candidate = candidates[0] if candidates else {}
        parts = candidate.get("content", {}).get("parts", [])
        content = "".join(p.get("text", "") for p in parts)
        usage_data = data.get("usageMetadata", {})
        return ModelResponse(
            content=content,
            reasoning=None,
            model=self._model,
            provider="vertex",
            usage=Usage(
                prompt_tokens=usage_data.get("promptTokenCount", 0),
                completion_tokens=usage_data.get("candidatesTokenCount", 0),
                total_tokens=usage_data.get("totalTokenCount", 0),
            ),
            finish_reason=candidate.get("finishReason", ""),
            raw=data,
        )

    def complete(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
    ) -> ModelResponse:
        payload = self._build_payload(
            messages, temperature=temperature, max_tokens=max_tokens, stop=stop
        )
        resp = self._client.post(
            f"{self._base_url}:generateContent",
            headers=self._headers(),
            json=payload,
        )
        resp.raise_for_status()
        return self._parse_response(resp.json())

    def complete_stream(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
    ) -> list[ModelChunk]:
        # No caller in the ReactAgent loop uses complete_stream today (only
        # mesh.py delegates to it); satisfy the protocol via one complete()
        # call wrapped as a single chunk instead of adding an unused SSE parser.
        response = self.complete(
            messages, temperature=temperature, max_tokens=max_tokens, stop=stop
        )
        return [
            ModelChunk(
                delta=response.content,
                reasoning_delta="",
                finish_reason=response.finish_reason,
                usage=response.usage,
            )
        ]
