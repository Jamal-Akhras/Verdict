// Milestone 0 mock data. Replaced by the real API in Milestone 2.
export type AgentStatus =
  | "proposed" | "approved" | "active" | "paused"
  | "blocked" | "completed" | "archived";

export type Authority = "observe" | "suggest" | "draft";
export type Team = "Governance" | "Strategy" | "Product" | "Engineering" | "Quality";

export interface MockTask {
  title: string;
  status: "queued" | "running" | "review" | "done";
  costUsd: number;
}

export interface MockAgent {
  id: string;
  slug: string;
  name: string;
  initials: string;
  role: string;
  team: Team;
  parentId: string | null;
  status: AgentStatus;
  authority: Authority;
  model: string;
  riskLevel: "low" | "medium" | "high";
  budgetMaxUsd: number;
  costUsedUsd: number;
  currentTask: string | null;
  tasks: MockTask[];
  outputs: string[];
  log: string[];
}

export interface MockApproval {
  id: string;
  title: string;
  requestedBy: string;
  detail: string;
  risk: "low" | "medium" | "high";
}

export const teamColors: Record<Team, { bg: string; text: string }> = {
  Governance: { bg: "bg-stone-200", text: "text-stone-700" },
  Strategy: { bg: "bg-violet-100", text: "text-violet-800" },
  Product: { bg: "bg-orange-100", text: "text-orange-800" },
  Engineering: { bg: "bg-blue-100", text: "text-blue-800" },
  Quality: { bg: "bg-teal-100", text: "text-teal-800" },
};

export const demoProject = {
  id: "demo",
  name: "Gym Booking MVP",
  status: "active",
  stage: "prototype",
  budgetTotalUsd: 25,
  budgetUsedUsd: 6.13,
  pendingApprovals: 2,
};

export const demoApprovals: MockApproval[] = [
  {
    id: "ap1",
    title: "Approve Product spec (PRD) v1",
    requestedBy: "Product Agent",
    detail: "QA passed · unlocks the CTO Agent ($2.00 budget)",
    risk: "low",
  },
  {
    id: "ap2",
    title: "Security finding: Stripe webhooks",
    requestedBy: "Security Review Agent",
    detail: "High severity · webhook signatures unverified · blocks launch-ready status",
    risk: "high",
  },
];

export const demoAgents: MockAgent[] = [
  {
    id: "founder", slug: "founder", name: "You", initials: "You",
    role: "Approves scope, budget, stage changes, and risky actions.",
    team: "Governance", parentId: null, status: "active", authority: "draft", model: "human",
    riskLevel: "low", budgetMaxUsd: 0, costUsedUsd: 0, currentTask: "2 decisions on your desk",
    tasks: [], outputs: ["Approved budget: $25", "Approved scope: Feasibility + prototype plan"],
    log: ["Approved agent team (7 agents)", "Set project budget to $25"],
  },
  {
    id: "intake", slug: "founder-intake", name: "Founder Intake Agent", initials: "IN",
    role: "Normalizes the raw idea, asks follow-ups, flags missing info.",
    team: "Strategy", parentId: "founder", status: "completed", authority: "observe", model: "gpt-4o-mini",
    riskLevel: "low", budgetMaxUsd: 0.5, costUsedUsd: 0.08, currentTask: null,
    tasks: [{ title: "Normalize idea brief", status: "done", costUsd: 0.08 }],
    outputs: ["Normalized idea brief v1", "Assumptions list (6 items)"],
    log: ["Asked 5 follow-up questions", "Brief confirmed by founder"],
  },
  {
    id: "research", slug: "market-research", name: "Market Research Agent", initials: "MR",
    role: "Finds competitors, pricing, and demand signals. Read-only web.",
    team: "Strategy", parentId: "founder", status: "completed", authority: "observe", model: "gpt-4o + web",
    riskLevel: "medium", budgetMaxUsd: 1.5, costUsedUsd: 1.12, currentTask: null,
    tasks: [{ title: "Competitor scan", status: "done", costUsd: 0.74 }, { title: "Pricing comparison", status: "done", costUsd: 0.38 }],
    outputs: ["Competitor matrix (6 found)", "Market memo v1"],
    log: ["Cited 11 sources", "Flagged crowded mid-market segment"],
  },
  {
    id: "feasibility", slug: "feasibility-analyst", name: "Feasibility Analyst", initials: "FA",
    role: "Scores the idea against the rubric and renders the verdict.",
    team: "Strategy", parentId: "founder", status: "completed", authority: "suggest", model: "gpt-4o",
    riskLevel: "medium", budgetMaxUsd: 1.5, costUsedUsd: 0.91, currentTask: null,
    tasks: [{ title: "Feasibility report v1", status: "done", costUsd: 0.91 }],
    outputs: ["Verdict: Validate before build (confidence: moderate)", "MVP scope + do-not-build list"],
    log: ["Cited research + finance documents", "Dissent: CTO Agent preferred 'prototype'"],
  },
  {
    id: "finance", slug: "finance-roi", name: "Finance / ROI Agent", initials: "FI",
    role: "Cost forecast, pricing model, break-even. Math is deterministic, not LLM.",
    team: "Strategy", parentId: "founder", status: "completed", authority: "suggest", model: "gpt-4o-mini + calc",
    riskLevel: "medium", budgetMaxUsd: 1, costUsedUsd: 0.42, currentTask: null,
    tasks: [{ title: "AI cost forecast", status: "done", costUsd: 0.22 }, { title: "Break-even model", status: "done", costUsd: 0.2 }],
    outputs: ["Cost forecast: $48-$140 to MVP plan", "Break-even memo (base case: 9 gyms)"],
    log: ["Arithmetic verified by calculator tool"],
  },
  {
    id: "product", slug: "product", name: "Product Agent", initials: "PA",
    role: "Product spec (PRD), user stories, prioritization, non-goals.",
    team: "Product", parentId: "founder", status: "active", authority: "draft", model: "claude-sonnet",
    riskLevel: "low", budgetMaxUsd: 2, costUsedUsd: 1.35, currentTask: "Writing product spec v1",
    tasks: [{ title: "Product spec v1", status: "running", costUsd: 1.35 }, { title: "Story map", status: "queued", costUsd: 0 }],
    outputs: ["MVP scope draft"],
    log: ["Scope locked to approved MVP scope", "Product spec requires your approval before the Planner runs"],
  },
  {
    id: "cto", slug: "cto-architecture", name: "CTO / Architecture Agent", initials: "CT",
    role: "Stack choice, architecture, data model, API contract, ADRs.",
    team: "Engineering", parentId: "founder", status: "approved", authority: "draft", model: "claude-sonnet",
    riskLevel: "medium", budgetMaxUsd: 2, costUsedUsd: 0, currentTask: "Waiting on product spec approval",
    tasks: [{ title: "Technical plan", status: "queued", costUsd: 0 }],
    outputs: [],
    log: ["Blocked by approval gate: Product spec v1"],
  },
  {
    id: "planner", slug: "engineering-planner", name: "Engineering Planner", initials: "EP",
    role: "Converts the product spec + technical plan into a single-responsibility build plan.",
    team: "Engineering", parentId: "cto", status: "approved", authority: "suggest", model: "claude-sonnet",
    riskLevel: "low", budgetMaxUsd: 1.5, costUsedUsd: 0, currentTask: null,
    tasks: [], outputs: [], log: ["Waiting on tech plan"],
  },
  {
    id: "qa", slug: "qa", name: "QA Agent", initials: "QA",
    role: "Adversarial review of other agents' documents. Tries to break the work.",
    team: "Quality", parentId: "founder", status: "active", authority: "suggest", model: "gpt-4o",
    riskLevel: "low", budgetMaxUsd: 1, costUsedUsd: 0.6, currentTask: "Reviewing MVP scope draft",
    tasks: [{ title: "Review MVP scope", status: "running", costUsd: 0.6 }],
    outputs: ["QA report: research memo (passed)"],
    log: ["Found 2 contradictions in scope draft, sent back"],
  },
  {
    id: "security", slug: "security-review", name: "Security Review Agent", initials: "SR",
    role: "Reviews the plan for auth/data/payment risk. Produces launch checklist.",
    team: "Quality", parentId: "founder", status: "active", authority: "suggest", model: "claude-sonnet",
    riskLevel: "high", budgetMaxUsd: 1, costUsedUsd: 0.55, currentTask: "Reviewing payment flow in the product spec",
    tasks: [{ title: "Plan risk review", status: "running", costUsd: 0.55 }],
    outputs: ["RiskAssessment: Stripe webhooks need signature verification (high)"],
    log: ["High finding auto-created an approval request"],
  },
  {
    id: "governance", slug: "governance", name: "Governance / Audit", initials: "GA",
    role: "Deterministic service: audit ledger, state machines, budget + sprawl guards.",
    team: "Governance", parentId: "founder", status: "active", authority: "observe", model: "service + haiku",
    riskLevel: "low", budgetMaxUsd: 0.25, costUsedUsd: 0.02, currentTask: "Watching budget (25% used)",
    tasks: [], outputs: ["Audit timeline (34 events)"],
    log: ["All transitions recorded"],
  },
];
