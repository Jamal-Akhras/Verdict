from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App configuration. Reads .env; every value overridable via env vars."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://verdict:verdict@localhost:5432/verdict"
    # Comma-separated list of origins allowed by CORS (FRONTEND_ORIGINS env).
    frontend_origins: str = "http://localhost:3000"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    # Local models: any OpenAI-compatible server (Ollama, LM Studio, vLLM,
    # llama.cpp server). Default base URL for local model profiles, e.g.
    # http://localhost:11434/v1 for Ollama. Setting it leaves demo mode.
    local_llm_base_url: str = ""
    # Most local servers ignore the key; some (vLLM --api-key) require one.
    local_llm_api_key: str = ""
    # Local inference is slow on consumer hardware; be generous.
    local_llm_timeout_seconds: int = 600
    # Subscription access to frontier models via their official CLIs, which
    # bill against the plan you are logged into (`claude login`, `codex
    # login`) instead of an API key. Operator opt-in: these run a subprocess
    # on the API host using the host's login, so never enable them on a
    # deployment other people can reach.
    claude_code_enabled: bool = False
    claude_code_command: str = "claude"
    codex_enabled: bool = False
    codex_command: str = "codex"
    cli_timeout_seconds: int = 600
    # Whether users may create local/subscription model profiles. Unset =
    # allowed only when per-user auth (Clerk) is off, i.e. self-hosted single
    # operator: in a multi-tenant deploy a user-supplied base_url is an SSRF
    # vector and a CLI profile would spend the operator's subscription.
    allow_local_providers: bool | None = None
    # Demo mode: run the entire product with canned agent outputs and zero AI
    # spend. Auto-enabled when no provider key is configured.
    demo_mode: bool = False
    # Per-user auth: the Clerk instance issuer, e.g.
    # https://your-app.clerk.accounts.dev (CLERK_ISSUER env). When set, every
    # route requires a Clerk session JWT and data is scoped per user.
    clerk_issuer: str = ""
    # Shared-secret API auth (API_AUTH_TOKEN): single-operator stopgap used
    # only when clerk_issuer is empty. Empty too = open local/demo dev mode.
    api_auth_token: str = ""
    # In-memory per-IP rate limit for mutating endpoints (cost-bomb defense).
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 30
    # Number of trusted reverse proxies in front of the app. Behind Render/
    # Vercel/Fly this is 1: the real client IP is the Nth-from-last hop in
    # X-Forwarded-For. 0 = no proxy, trust the socket peer only (never trust
    # a client-supplied XFF header when 0).
    trusted_proxy_count: int = 0
    # Hard ceiling on total AI spend per UTC day; <= 0 disables the check.
    daily_spend_limit_usd: float = 25.0
    # Web search for the Research agent. Either key enables it; both empty =
    # the agent honestly discloses it has no web access (old behavior).
    # Brave: https://api-dashboard.search.brave.com (free tier ~2k/mo)
    brave_api_key: str = ""
    # Tavily: https://tavily.com (free tier ~1k credits/mo)
    tavily_api_key: str = ""
    # Observability (all optional; free tiers)
    sentry_dsn: str = ""
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    @property
    def effective_demo_mode(self) -> bool:
        return self.demo_mode or not (
            self.openai_api_key or self.anthropic_api_key or self.gemini_api_key
            or self.local_llm_base_url or self.claude_code_enabled or self.codex_enabled
        )

    @property
    def local_providers_allowed(self) -> bool:
        if self.allow_local_providers is not None:
            return self.allow_local_providers
        return not self.clerk_issuer


settings = Settings()
