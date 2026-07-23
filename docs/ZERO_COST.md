# Running Verdict at $0

Every layer has a free path. This is the order to climb as the product earns
its costs.

## Tier 0: demo mode (no accounts, no keys, works offline)

Leave every API key empty in `apps/api/.env` (or set `DEMO_MODE=true`).
The router swaps in the DemoProvider: the ENTIRE product flow runs -
intake, feasibility verdict, agent team, approval gates, QA + security
reviews, artifacts, prompt pack - with realistic canned outputs. Costs are
simulated and labeled `provider: demo` in the cost dashboard; the header
shows a "Demo mode" badge. Use this for UI work, demos, and screenshots.

## Tier 1: real AI, still $0

Get a free Gemini key at https://aistudio.google.com (no card required) and
set `GEMINI_API_KEY`. The router's fallback chain routes every task type to
Gemini when it is the only configured provider:
- gemini-2.0-flash: cheap-tier tasks (intake, ROI, summaries)
- gemini-2.5-pro: high-tier tasks (feasibility, architecture, security)
Free-tier daily quotas comfortably cover several full project runs.

## Tier 2: free infrastructure

| Need | Free option |
|---|---|
| Postgres | Neon free tier (0.5GB) or the docker-compose local DB |
| Web hosting | Vercel Hobby |
| API hosting | Render free web service, or Fly.io free allowance |
| Auth (when added) | Clerk free tier (10k MAU) |
| Web search for the Research Agent (when added) | Brave Search API free tier (2k queries/mo) or Tavily free tier (1k credits/mo) |
| Error tracking | Sentry free tier |
| LLM tracing | Langfuse cloud free tier |

## Tier 3: paid keys, only when needed

Add `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` when output quality starts to
matter commercially. The routing table (`app/providers/routing.yaml`) already
prefers them; Gemini stays as the fallback. A full project run costs roughly
$1-3 at current prices, and every cent is visible per agent, per model, per
task in the cost dashboard.

## Principle

Same code path at every tier - demo mode and Gemini go through the same
router, gates, budgets, and audit trail as paid providers. Nothing is
mocked except the model's brain.
