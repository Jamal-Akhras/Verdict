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
        )


settings = Settings()
# force-sync marker
