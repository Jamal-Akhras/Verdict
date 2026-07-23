"""Demo provider: the full product at zero AI spend.

Implements the same ModelProvider protocol; picks a canned output by the
agent marker in the system prompt. Costs logged by the router are labeled
via provider name 'demo' so nothing pretends to be real spend.
"""
import json
import time

from app.providers.base import ModelResponse
from app.providers.demo_data import MARKERS


class DemoProvider:
    name = "demo"

    def complete(
        self, *, model: str, system_prompt: str, user_prompt: str,
        json_output: bool, max_tokens: int, json_schema: dict | None = None,
    ) -> ModelResponse:
        del json_schema  # canned fixtures already match the schemas
        time.sleep(0.8)  # visible progression in the live tree
        payload: dict = {"note": "no demo fixture matched"}
        for marker, fixture in MARKERS:
            if marker in system_prompt:
                payload = fixture
                break
        text = json.dumps(payload)
        return ModelResponse(
            provider=self.name,
            model=model,
            text=text,
            tokens_in=(len(system_prompt) + len(user_prompt)) // 4,
            tokens_out=len(text) // 4,
            latency_ms=800,
        )
