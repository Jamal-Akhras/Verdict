"""Local models via any OpenAI-compatible server (no SDK dependency).

Ollama (http://localhost:11434/v1), LM Studio (http://localhost:1234/v1),
vLLM, and llama.cpp's server all expose /chat/completions. Local calls have
no per-token price and no rate limits, which is what makes them the right
default for high-volume worker agents: a frontier supervisor reviews their
output instead of producing it.
"""
import time

import httpx

from app.config import settings
from app.providers.base import ModelResponse, ProviderError


class LocalProvider:
    name = "local"

    def __init__(self, base_url: str | None = None, api_key: str | None = None,
                 timeout: float | None = None):
        self._base_url = (base_url or settings.local_llm_base_url).rstrip("/")
        self._api_key = api_key if api_key is not None else settings.local_llm_api_key
        self._timeout = timeout or settings.local_llm_timeout_seconds

    def _post(self, body: dict) -> dict:
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        resp = httpx.post(
            f"{self._base_url}/chat/completions", json=body, headers=headers,
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def complete(
        self, *, model: str, system_prompt: str, user_prompt: str,
        json_output: bool, max_tokens: int, json_schema: dict | None = None,
    ) -> ModelResponse:
        if not self._base_url:
            raise ProviderError("local: no base URL configured (LOCAL_LLM_BASE_URL)")
        body: dict = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "stream": False,
        }
        start = time.monotonic()
        try:
            if json_schema is not None:
                # Grammar-constrained decoding where the server supports it
                # (Ollama >= 0.5, vLLM, llama.cpp). Small models benefit most.
                try:
                    data = self._post({**body, "response_format": {
                        "type": "json_schema",
                        "json_schema": {
                            "name": json_schema.get("title", "output"),
                            "schema": json_schema,
                        },
                    }})
                except httpx.HTTPStatusError:
                    # Older servers reject json_schema; the router's
                    # extraction + validation + repair still guard the result.
                    data = self._post({**body, "response_format": {"type": "json_object"}})
            elif json_output:
                data = self._post({**body, "response_format": {"type": "json_object"}})
            else:
                data = self._post(body)
        except Exception as exc:
            # Class name only, matching the hosted providers.
            raise ProviderError(f"local/{model}: {type(exc).__name__}") from exc
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"local/{model}: unexpected response shape") from exc
        usage = data.get("usage") or {}
        return ModelResponse(
            provider=self.name,
            model=model,
            text=text,
            tokens_in=usage.get("prompt_tokens", 0),
            tokens_out=usage.get("completion_tokens", 0),
            latency_ms=int((time.monotonic() - start) * 1000),
        )

    def list_models(self) -> list[str]:
        """Models the server has available (GET /models). Used by the UI to
        offer installed models instead of making the user type tags."""
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        try:
            resp = httpx.get(f"{self._base_url}/models", headers=headers, timeout=10)
            resp.raise_for_status()
            return sorted(m["id"] for m in resp.json().get("data", []))
        except Exception as exc:
            raise ProviderError(f"local: {type(exc).__name__}") from exc
