# ADR 0001: Custom orchestrator instead of LangGraph (v0)

Date: 2026-07-07 · Status: Accepted

## Context

The v0 workflow is a small DAG (~7-9 agents) with human approval pauses between
stages. Transparency is the product: users must see exactly why each agent ran,
what it cost, and what state everything is in.

## Decision

Build a custom Postgres-backed orchestrator (task table + state machine +
sequential async execution) instead of adopting LangGraph/CrewAI/Temporal.

## Rationale

- The whole orchestrator is a few hundred lines and fully inspectable —
  an inspectable orchestrator IS the product.
- No framework types leak into product logic (see quality rule: provider isolation).
- Approval pauses are first-class rows (ApprovalRequest), not framework interrupts.
- Easier to debug and CV-stronger than gluing a framework.

## Consequences

- We own retries/timeouts ourselves (acceptable at v0 scale).
- Revisit at Milestone 7 if we need parallel branches, replay, or durable
  execution at scale; the Task/DAG schema is framework-portable by design.
