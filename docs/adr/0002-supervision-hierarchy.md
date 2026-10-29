# ADR 0002: Supervision hierarchy with local workers and frontier supervisors

Date: 2026-10-27 · Status: Accepted

## Context

Every agent called a frontier model through the task-type routing table.
Output volume was bounded by API spend and rate limits. Most tokens a
run produces are drafts: research memos, PRDs, backlogs. A capable local
model can write a decent draft. Checking that draft is where frontier
quality pays off.

## Decision

Split production from judgement and make the split configurable:

- **Model profiles** (user-owned rows): a model plus how it's reached.
  That is an API key, a subscription via the official CLI (`claude -p`,
  `codex exec`), or a local OpenAI-compatible server (Ollama, LM Studio,
  vLLM, llama.cpp). Local and subscription calls are recorded at $0.
- **Hierarchy on the agents table**: `supervisor_id` (null = the founder),
  `model_profile_id` (null = the routing table, i.e. the old behavior),
  founder `instructions`, `max_revisions`, and a `requires_approval`
  override. Projects carry instructions for every agent.
- **Supervision loop** (`services/supervision.py`): the worker drafts and
  its supervisor accepts, revises (feedback goes back to the worker), or
  escalates. A send-back past `max_revisions` becomes an escalation. An
  escalation is a `Flag` that climbs the supervisor chain. Each level
  resolves it, with binding guidance that travels with the artifact to
  downstream agents, or passes it up. Only a flag that leaves the top of
  the chain becomes a blocking approval on the founder's desk.
- **Trace**: every call is tagged with its task and role (work, review, or
  triage). Each review stores the exact draft it judged, and each flag
  stores every hop. `GET /projects/{id}/trace` returns all of it,
  including full prompts.

## Policy

- **No silent fallback for pinned models.** If the local server is down,
  the task fails visibly. It does not quietly retry on a paid model.
- **High-risk work** (e.g. Security Review) may run on a non-frontier model
  only under a high-tier supervisor. This is enforced at configuration
  time, so the router can trust a pinned model at run time.
- **Default founder gates stay.** The PRD and tech plan still need the
  founder unless the founder overrides per agent.
- **Subscription CLIs are operator opt-in** (`CLAUDE_CODE_ENABLED`,
  `CODEX_ENABLED`). Local and subscription profiles are disabled by default
  when Clerk multi-tenant auth is on, because a user-supplied base URL is
  an SSRF vector and a CLI profile spends the operator's plan.
- **CLI hardening:** no shell, model names validated against flag
  injection, user text only in a temp file or on stdin (the Windows
  `.cmd` shims re-parse argv), an empty working directory, and API keys
  stripped from the child env so the subscription is what pays.

## Consequences

- Unconfigured projects behave exactly as before (all prior tests pass
  unchanged).
- A supervised task costs one frontier review per draft. The trace page
  reports the share of output written on $0 models.
- Subscription plans have their own rate limits. Supervisors, not
  workers, belong there.
- The founder has a third answer to any blocking desk item (a default gate
  or an escalation): **request changes**. The note becomes binding
  directions in the agent's system prompt for every attempt, including
  supervisor send-backs. The supervisor reviews against those directions,
  and the new artifact supersedes the old one (`supersedes_id`). Finished
  work that read the old version, such as QA's review of the PRD, is
  queued again, so nothing downstream acts on a stale draft.
