"""Provider abstraction. The ONLY place vendor SDKs may be imported is the
concrete provider modules. Product logic never sees a vendor type.
"""
from dataclasses import dataclass
from typing import Protocol


@dataclass
class ModelResponse:
    provider: str
    model: str
    text: str
    tokens_in: int
    tokens_out: int
    latency_ms: int


class ModelProvider(Protocol):
    name: str

    def complete(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        json_output: bool,
        max_tokens: int,
        json_schema: dict | None = None,
    ) -> ModelResponse: ...


class ProviderError(Exception):
    """Raised by providers on API failure; triggers router fallback."""
