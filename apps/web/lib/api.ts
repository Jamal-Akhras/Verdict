const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
// Shared-secret API auth (stopgap until per-user auth lands). Matches the
// API's API_AUTH_TOKEN; leave unset for local/demo dev.
const API_TOKEN = process.env.NEXT_PUBLIC_API_TOKEN ?? "";

export interface IntakeResult {
  project_id: string;
  submission_id: string;
  normalized_brief: string;
  target_user: string;
  problem: string;
  assumptions: string[];
  missing_info: string[];
  follow_up_questions: string[];
}

export interface RubricScore {
  category: string;
  score: number;
  weight: number;
  reasoning: string;
}

export interface FeasibilityReport {
  id: string;
  project_id: string;
  version: number;
  verdict: "kill" | "park" | "research" | "validate" | "prototype" | "build";
  confidence: number;
  scores: RubricScore[];
  mvp_scope: string[];
  do_not_build: string[];
  assumptions: string[];
  validation_plan: string[];
  reasoning: string;
  cost_estimate: {
    complexity_factor: number;
    mvp_feature_count: number;
    stages: Record<string, { low_usd: number; high_usd: number }>;
    method: string;
  };
  created_at: string;
}


export interface ApiAgent {
  id: string;
  project_id: string;
  slug: string;
  name: string;
  initials: string;
  team: string;
  role: string;
  status: string;
  authority: string;
  risk_level: string;
  budget_max_usd: number;
  cost_used_usd: number;
  created_by: string;
  created_at: string;
}

export interface ApiProject {
  id: string;
  name: string;
  status: string;
  stage: string;
  budget_total_usd: number;
  budget_used_usd: number;
  created_at: string;
}

export type Stage = "kill" | "park" | "research" | "validate" | "prototype" | "build";


export interface ApiTask {
  id: string;
  project_id: string;
  agent_id: string;
  agent_slug: string;
  title: string;
  task_type: string;
  status: "queued" | "running" | "review" | "done" | "failed" | "cancelled";
  depends_on: string[];
  cost_used_usd: number;
  error: string;
  created_at: string;
  updated_at: string;
}

export interface ApiArtifact {
  id: string;
  project_id: string;
  task_id: string;
  agent_id: string;
  agent_slug: string;
  artifact_type: string;
  title: string;
  content: Record<string, unknown>;
  version: number;
  review_status: string;
  model_used: string;
  cost_usd: number;
  created_at: string;
}

export interface ApiAuditEvent {
  id: string;
  actor_type: string;
  event_type: string;
  summary: string;
  subject_type: string | null;
  subject_id: string | null;
  payload: Record<string, unknown>;
  created_at: string;
}


export interface ApiApproval {
  id: string;
  project_id: string;
  subject_type: string;
  subject_id: string;
  requested_by_slug: string;
  title: string;
  summary: string;
  context: Record<string, unknown>;
  blocking: boolean;
  status: "pending" | "approved" | "denied";
  resolution_note: string;
  created_at: string;
}

export interface CostSummary {
  total_usd: number;
  by_agent: { agent_slug: string; cost_usd: number; calls: number; budget_usd: number | null }[];
  by_model: {
    provider: string;
    model: string;
    cost_usd: number;
    calls: number;
    tokens_in: number;
    tokens_out: number;
  }[];
}


export interface ApiTemplate {
  id: string;
  slug: string;
  version: number;
  name: string;
  initials: string;
  team: string;
  role: string;
  scope: string;
  checks: string[];
  output_types: string[];
  default_budget_usd: number;
  risk_level: string;
  authority_default: string;
  approval_requirement: string;
}

export interface CustomAgentIn {
  name: string;
  role: string;
  team: string;
  scope?: string;
  budget_max_usd: number;
  risk_level: string;
  authority: "observe" | "suggest";
}

declare global {
  interface Window {
    Clerk?: { session?: { getToken(): Promise<string | null> } };
  }
}

async function authHeader(): Promise<Record<string, string>> {
  // Clerk session JWT wins (per-user auth); the shared API token is the
  // single-operator fallback; neither = open demo mode.
  if (typeof window !== "undefined" && window.Clerk?.session) {
    const token = await window.Clerk.session.getToken();
    if (token) return { Authorization: `Bearer ${token}` };
  }
  return API_TOKEN ? { Authorization: `Bearer ${API_TOKEN}` } : {};
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(await authHeader()),
    },
    ...init,
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json();
}

export const api = {
  submitIdea: (name: string, raw_text: string) =>
    req<IntakeResult>("/ideas", { method: "POST", body: JSON.stringify({ name, raw_text }) }),
  submitAnswers: (projectId: string, answers: Record<string, string>) =>
    req<IntakeResult>(`/projects/${projectId}/answers`, {
      method: "POST",
      body: JSON.stringify({ answers }),
    }),
  evaluate: (projectId: string) =>
    req<FeasibilityReport>(`/projects/${projectId}/evaluate`, { method: "POST" }),
  getReport: (projectId: string) => req<FeasibilityReport>(`/projects/${projectId}/report`),
  getProject: (projectId: string) => req<ApiProject>(`/projects/${projectId}`),
  listProjects: () => req<ApiProject[]>("/projects"),
  setStage: (projectId: string, stage: Stage) =>
    req<ApiAgent[]>(`/projects/${projectId}/stage`, {
      method: "POST",
      body: JSON.stringify({ stage }),
    }),
  listAgents: (projectId: string) => req<ApiAgent[]>(`/projects/${projectId}/agents`),
  agentAction: (agentId: string, action: string) =>
    req<ApiAgent>(`/agents/${agentId}/${action}`, { method: "POST" }),
  approveAllAgents: (projectId: string) =>
    req<ApiAgent[]>(`/projects/${projectId}/agents/approve-all`, { method: "POST" }),
  startRun: (projectId: string) =>
    req<ApiTask[]>(`/projects/${projectId}/run`, { method: "POST" }),
  resetRuns: (projectId: string) =>
    req<unknown>(`/projects/${projectId}/runs/reset`, { method: "POST" }),
  listTasks: (projectId: string) => req<ApiTask[]>(`/projects/${projectId}/tasks`),
  listArtifacts: (projectId: string) => req<ApiArtifact[]>(`/projects/${projectId}/artifacts`),
  getArtifact: (artifactId: string) => req<ApiArtifact>(`/artifacts/${artifactId}`),
  listAudit: (projectId: string) => req<ApiAuditEvent[]>(`/projects/${projectId}/audit`),
  listApprovals: (projectId: string, status?: string) =>
    req<ApiApproval[]>(`/projects/${projectId}/approvals${status ? `?status=${status}` : ""}`),
  resolveApproval: (requestId: string, decision: "approve" | "deny", note = "") =>
    req<ApiApproval>(`/approvals/${requestId}/${decision}`, {
      method: "POST",
      body: JSON.stringify({ note }),
    }),
  costSummary: (projectId: string) => req<CostSummary>(`/projects/${projectId}/costs/summary`),
  health: () => req<{ status: string; demo_mode: boolean }>("/health"),
  shareReport: (projectId: string) =>
    req<{ token: string; path: string }>(`/projects/${projectId}/report/share`, {
      method: "POST",
    }),
  listTemplates: () => req<ApiTemplate[]>("/templates"),
  staffAgent: (projectId: string, templateSlug: string) =>
    req<ApiAgent>(`/projects/${projectId}/agents/staff`, {
      method: "POST",
      body: JSON.stringify({ template_slug: templateSlug }),
    }),
  createCustomAgent: (projectId: string, body: CustomAgentIn) =>
    req<ApiAgent>(`/projects/${projectId}/agents/custom`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
