import json
import time

from app.config import settings
from app.providers.base import ModelResponse, ProviderError


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or settings.anthropic_api_key
        self._client = None

    def _get_client(self):
        if self._client is None:
            from anthropic import Anthropic  # lazy: keeps SDK out of test paths

            self._client = Anthropic(api_key=self._api_key)
        return self._client

    def complete(
        self, *, model: str, system_prompt: str, user_prompt: str,
        json_output: bool, max_tokens: int, json_schema: dict | None = None,
    ) -> ModelResponse:
        start = time.monotonic()
        system = system_prompt
        kwargs: dict = {}
        if json_schema is not None:
            # Native structured output via forced tool use: the model must
            # call `emit` with input matching the schema.
            kwargs["tools"] = [{
                "name": "emit",
                "description": "Emit the structured output for this task.",
                "input_schema": json_schema,
            }]
            kwargs["tool_choice"] = {"type": "tool", "name": "emit"}
        elif json_output:
            system += "\n\nRespond with a single valid JSON object and nothing else."
        try:
            resp = self._get_client().messages.create(
                model=model,
                system=system,
                messages=[{"role": "user", "content": user_prompt}],
                max_tokens=max_tokens,
                **kwargs,
            )
        except Exception as exc:
            # class name only: SDK exception text can echo request URLs,
            # org ids, or keys into owner-visible ModelCall records.
            raise ProviderError(f"anthropic/{model}: {type(exc).__name__}") from exc
        text = ""
        if json_schema is not None:
            for block in resp.content:
                if block.type == "tool_use" and block.name == "emit":
                    text = json.dumps(block.input)
                    break
        if not text:
            text = "".join(block.text for block in resp.content if block.type == "text")
        return ModelResponse(
            provider=self.name,
            model=model,
            text=text,
            tokens_in=resp.usage.input_tokens,
            tokens_out=resp.usage.output_tokens,
            latency_ms=int((time.monotonic() - start) * 1000),
        )
