"""Model profiles -> providers, plus the catalog the UI offers.

A ModelProfile is the founder's choice of "this model, reached this way":
an API key, a subscription CLI, or a local server. This module is the one
place that turns that choice into a ModelProvider.
"""
from app.config import settings
from app.models.hierarchy import ModelProfile, ModelTier, ProviderKind
from app.providers.base import ModelProvider


def build_provider(profile: ModelProfile) -> ModelProvider:
    if settings.effective_demo_mode:
        from app.providers.demo_provider import DemoProvider

        return DemoProvider()
    kind = profile.provider
    if kind == ProviderKind.openai:
        from app.providers.openai_provider import OpenAIProvider

        return OpenAIProvider()
    if kind == ProviderKind.anthropic:
        from app.providers.anthropic_provider import AnthropicProvider

        return AnthropicProvider()
    if kind == ProviderKind.gemini:
        from app.providers.gemini_provider import GeminiProvider

        return GeminiProvider()
    if kind == ProviderKind.local:
        from app.providers.local_provider import LocalProvider

        return LocalProvider(base_url=profile.base_url or None)
    if kind == ProviderKind.claude_code:
        from app.providers.cli_provider import ClaudeCodeProvider

        return ClaudeCodeProvider()
    if kind == ProviderKind.codex:
        from app.providers.cli_provider import CodexProvider

        return CodexProvider()
    raise ValueError(f"unknown provider kind: {kind}")


def provider_status() -> dict[str, dict]:
    """Which provider kinds this deployment can actually use, and why not.
    Drives the model-profile form so users only pick what will work."""
    local_ok = settings.local_providers_allowed

    def entry(enabled: bool, access: str, reason: str = "") -> dict:
        return {"enabled": enabled, "access": access, "reason": "" if enabled else reason}

    return {
        ProviderKind.anthropic.value: entry(
            bool(settings.anthropic_api_key), "api", "ANTHROPIC_API_KEY not set"),
        ProviderKind.openai.value: entry(
            bool(settings.openai_api_key), "api", "OPENAI_API_KEY not set"),
        ProviderKind.gemini.value: entry(
            bool(settings.gemini_api_key), "api", "GEMINI_API_KEY not set"),
        ProviderKind.local.value: entry(
            local_ok, "local", "local providers are disabled on this deployment"),
        ProviderKind.claude_code.value: entry(
            local_ok and settings.claude_code_enabled, "subscription",
            "set CLAUDE_CODE_ENABLED=true and run `claude login` on the API host"),
        ProviderKind.codex.value: entry(
            local_ok and settings.codex_enabled, "subscription",
            "set CODEX_ENABLED=true and run `codex login` on the API host"),
    }


# Starting points for the "add model" form. Prices are the routing table's
# for API models; subscription and local models cost nothing per token.
# Model names are suggestions - every field is editable.
SUGGESTED_PROFILES: list[dict] = [
    {"name": "Claude Opus (subscription)", "provider": "claude_code", "model": "opus",
     "tier": ModelTier.high.value},
    {"name": "Claude Sonnet (subscription)", "provider": "claude_code", "model": "sonnet",
     "tier": ModelTier.high.value},
    {"name": "Codex (ChatGPT subscription)", "provider": "codex", "model": "gpt-5-codex",
     "tier": ModelTier.high.value},
    {"name": "Qwen3 32B (Ollama)", "provider": "local", "model": "qwen3:32b",
     "tier": ModelTier.local.value},
    {"name": "Llama 3.3 70B (Ollama)", "provider": "local", "model": "llama3.3:70b",
     "tier": ModelTier.local.value},
    {"name": "Gemma 3 27B (Ollama)", "provider": "local", "model": "gemma3:27b",
     "tier": ModelTier.local.value},
]
