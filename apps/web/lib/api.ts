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
  // hierarchy configuration (null supervisor = reports to the founder,
  // null model profile = routed by task type)
  model_profile_id: string | null;
  supervisor_id: string | null;
  instructions: string;
  max_revisions: number;
  requires_approval: boolean | null;
}

export interface ApiProject {
  id: string;
  name: string;
  status: string;
  stage: string;
  budget_total_usd: number;
  budget_used_usd: number;
  instructions: string;
  created_at: string;
}

export type ProviderKind = "anthropic" | "openai" | "gemini" | "local" | "claude_code" | "codex";
export type ModelTier = "high" | "cheap" | "local";

export interface ModelProfile {
  id: string;
  name: string;
  provider: ProviderKind;
  access: "api" | "subscription" | "local";
  model: string;
  base_url: string;
  tier: ModelTier;
  price_in: number;
  price_out: number;
  created_at: string;
}

export interface ModelProfileIn {
  name: string;
  provider: ProviderKind;
  model: string;
  base_url?: string;
  tier?: ModelTier;
  price_in?: number;
  price_out?: number;
}

export interface ModelCatalog {
  demo_mode: boolean;
  providers: Record<ProviderKind, { enabled: boolean; access: string; reason: string }>;
  api_models: { model: string; provider: ProviderKind; tier: ModelTier; price_in: number; price_out: number }[];
  suggested: { name: string; provider: ProviderKind; model: string; tier: ModelTier }[];
  local_base_url: string;
}

export interface AgentConfigIn {
  model_profile_id?: string | null;
  supervisor_id?: string | null;
  instructions?: string;
  max_revisions?: number;
  requires_approval?: boolean | null;
}

export interface HierarchyPresetIn {
  shape: "flat" | "teams";
  worker_profile_id: string | null;
  lead_profile_id: string | null;
  director_profile_id: string | null;
}

export interface FlagHop {
  agent_id: string | null;
  agent_name: string;
  model: string;
  decision: string;
  rationale: string;
  at: string;
}

export interface ApiFlag {
  id: string;
  task_id: string;
  artifact_id: string | null;
  raised_by_agent_id: string;
  holder_agent_id: string | null;
  severity: string;
  title: string;
  detail: string;
  status: "open" | "resolved" | "raised" | "approved" | "denied" | "revised";
  chain: FlagHop[];
  resolution: string;
  approval_request_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface TraceCall {
  id: string;
  task_id: string | null;
  agent_slug: string | null;
  call_role: "work" | "review" | "triage" | string;
  task_type: string;
  provider: string;
  model: string;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
  latency_ms: number;
  created_at: string;
  system_prompt: string;
  user_prompt: string;
  response_text: string;
  parse_ok: boolean;
  router_decision: Record<string, unknown>;
}

export interface TraceReview {
  id: string;
  task_id: string;
  worker_agent_id: string;
  reviewer_agent_id: string;
  attempt: number;
  decision: "accept" | "revise" | "escalate";
  summary: string;
  feedback: string;
  issues: { severity: string; issue: string; where: string }[];
  reviewed_output: Record<string, unknown>;
  created_at: string;
}

export interface Trace {
  calls: TraceCall[];
  reviews: TraceReview[];
  flags: ApiFlag[];
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
  status: "pending" | "approved" | "denied" | "revise";
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
  requestChanges: (requestId: string, note: string) =>
    req<ApiApproval>(`/approvals/${requestId}/revise`, {
      method: "POST",
      body: JSON.stringify({ note }),
    }),
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
  modelCatalog: () => req<ModelCatalog>("/models/catalog"),
  discoverLocalModels: (baseUrl: string) =>
    req<{ base_url: string; models: string[] }>(
      `/models/local?base_url=${encodeURIComponent(baseUrl)}`
    ),
  listModelProfiles: () => req<ModelProfile[]>("/model-profiles"),
  createModelProfile: (body: ModelProfileIn) =>
    req<ModelProfile>("/model-profiles", { method: "POST", body: JSON.stringify(body) }),
  updateModelProfile: (profileId: string, body: ModelProfileIn) =>
    req<ModelProfile>(`/model-profiles/${profileId}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  deleteModelProfile: async (profileId: string) => {
    const res = await fetch(`${API_URL}/model-profiles/${profileId}`, {
      method: "DELETE",
      headers: await authHeader(),
    });
    if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  },
  configureAgent: (agentId: string, body: AgentConfigIn) =>
    req<ApiAgent>(`/agents/${agentId}/config`, { method: "PATCH", body: JSON.stringify(body) }),
  configureProject: (projectId: string, instructions: string) =>
    req<ApiProject>(`/projects/${projectId}/config`, {
      method: "PATCH",
      body: JSON.stringify({ instructions }),
    }),
  applyHierarchyPreset: (projectId: string, body: HierarchyPresetIn) =>
    req<ApiAgent[]>(`/projects/${projectId}/hierarchy/preset`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listFlags: (projectId: string) => req<ApiFlag[]>(`/projects/${projectId}/flags`),
  trace: (projectId: string, taskId?: string) =>
    req<Trace>(`/projects/${projectId}/trace${taskId ? `?task_id=${taskId}` : ""}`),
};

/** FastAPI error bodies look like `422: {"detail": "..."}`; show the detail. */
export function errorDetail(e: unknown, fallback: string): string {
  if (!(e instanceof Error)) return fallback;
  const body = e.message.replace(/^\d+: /, "");
  try {
    const detail = JSON.parse(body).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map((d) => d.msg).join("; ");
  } catch {
    /* not JSON */
  }
  return fallback;
}
