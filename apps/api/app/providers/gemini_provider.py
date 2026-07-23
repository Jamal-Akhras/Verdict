"""Gemini provider via the REST API (no SDK dependency).

Google AI Studio issues free-tier keys (https://aistudio.google.com) with
generous daily quotas on the flash models - real AI at zero cost while
validating the product.
"""
import time

import httpx

from app.config import settings
from app.providers.base import ModelResponse, ProviderError

BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or settings.gemini_api_key

    def complete(
        self, *, model: str, system_prompt: str, user_prompt: str,
        json_output: bool, max_tokens: int,
    ) -> ModelResponse:
        if not self._api_key:
            raise ProviderError("gemini: no API key configured")
        body = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens},
        }
        if json_output:
            body["generationConfig"]["responseMimeType"] = "application/json"
        start = time.monotonic()
        try:
            # Key travels in a header, never the URL: query strings end up in
            # server logs, proxies, and exception messages.
            resp = httpx.post(
                f"{BASE}/{model}:generateContent",
                headers={"x-goog-api-key": self._api_key},
                json=body,
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            # Class name only: httpx exception text can echo the request
            # (and with it, credentials) into DB/UI-visible error fields.
            raise ProviderError(f"gemini/{model}: {type(exc).__name__}") from exc
        try:
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts)
        except (KeyError, IndexError) as exc:
            raise ProviderError(f"gemini/{model}: unexpected response shape") from exc
        usage = data.get("usageMetadata", {})
        return ModelResponse(
            provider=self.name,
            model=model,
            text=text,
            tokens_in=usage.get("promptTokenCount", 0),
            tokens_out=usage.get("candidatesTokenCount", 0),
            latency_ms=int((time.monotonic() - start) * 1000),
        )
