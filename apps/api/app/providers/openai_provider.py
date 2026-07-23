import copy
import time

from app.config import settings
from app.providers.base import ModelResponse, ProviderError


def strict_json_schema(schema: dict) -> dict:
    """Adapt a Pydantic model_json_schema for OpenAI strict mode.

    Strict mode requires every object node to declare
    additionalProperties=false and list ALL properties as required
    (fields with defaults are otherwise omitted from `required`).
    Walks nested nodes and $defs pragmatically.
    """
    schema = copy.deepcopy(schema)

    def walk(node) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object" or "properties" in node:
                props = node.get("properties", {})
                node["additionalProperties"] = False
                node["required"] = list(props.keys())
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(schema)
    return schema


class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or settings.openai_api_key
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI  # lazy: keeps SDK out of test paths

            self._client = OpenAI(api_key=self._api_key)
        return self._client

    def complete(
        self, *, model: str, system_prompt: str, user_prompt: str,
        json_output: bool, max_tokens: int, json_schema: dict | None = None,
    ) -> ModelResponse:
        start = time.monotonic()
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        def create(response_format: dict | None):
            kwargs: dict = {}
            if response_format is not None:
                kwargs["response_format"] = response_format
            return self._get_client().chat.completions.create(
                model=model, messages=messages, max_tokens=max_tokens, **kwargs
            )

        try:
            if json_schema is not None:
                try:
                    resp = create({
                        "type": "json_schema",
                        "json_schema": {
                            "name": json_schema.get("title", "output"),
                            "schema": strict_json_schema(json_schema),
                            "strict": True,
                        },
                    })
                except Exception:
                    # Strict schemas reject some valid Pydantic constructs
                    # (formats, unions). Degrade to json_object: the router's
                    # _extract_json + schema validation still guard the result.
                    resp = create({"type": "json_object"})
            elif json_output:
                resp = create({"type": "json_object"})
            else:
                resp = create(None)
        except Exception as exc:  # normalize all SDK errors
            # class name only: SDK exception text can echo request URLs,
            # org ids, or keys into owner-visible ModelCall records.
            raise ProviderError(f"openai/{model}: {type(exc).__name__}") from exc
        usage = resp.usage
        return ModelResponse(
            provider=self.name,
            model=model,
            text=resp.choices[0].message.content or "",
            tokens_in=usage.prompt_tokens if usage else 0,
            tokens_out=usage.completion_tokens if usage else 0,
            latency_ms=int((time.monotonic() - start) * 1000),
        )
