// One source of truth for status colors and plain-language labels.
// Tokens follow DESIGN.md: active emerald, completed violet, approved sky,
// paused/warning amber, blocked rose, proposed/archived stone.

/** Agent status → chip classes (nodes, roster cards, drawer). */
export const agentStatusChip: Record<string, string> = {
  proposed: "bg-stone-100 text-stone-600",
  approved: "bg-sky-50 text-sky-700",
  active: "bg-emerald-50 text-emerald-700",
  paused: "bg-amber-50 text-amber-700",
  blocked: "bg-rose-50 text-rose-700",
  completed: "bg-violet-50 text-violet-700",
  archived: "bg-stone-100 text-stone-500",
  rejected: "bg-rose-50 text-rose-500",
};

export function statusChip(status: string): string {
  return agentStatusChip[status] ?? "bg-stone-100 text-stone-600";
}

/** Task status → text color (task lists, run progress rows). */
export const taskStatusText: Record<string, string> = {
  queued: "text-stone-500",
  running: "text-blue-600",
  review: "text-amber-600",
  done: "text-emerald-600",
  failed: "text-rose-600",
  cancelled: "text-stone-500",
};

export function taskStatusColor(status: string): string {
  return taskStatusText[status] ?? "text-stone-500";
}

/** Audit timeline actor → chip classes. */
export const actorChip: Record<string, string> = {
  user: "bg-blue-50 text-blue-700",
  agent: "bg-violet-50 text-violet-700",
  system: "bg-stone-100 text-stone-600",
};

/**
 * Approval / decision cards: things that BLOCK progress get the amber
 * (urgent) border; non-blocking FYIs stay calm stone.
 */
export function approvalBorder(blocking: boolean): string {
  return blocking ? "border-amber-300" : "border-stone-200";
}

/** Budget bar fill: amber once 80% of budget is used. */
export function budgetBarColor(pct: number): string {
  return pct >= 80 ? "bg-amber-500" : "bg-stone-800";
}

/** Plain-language authority labels (no "observe/suggest" jargon). */
export const authorityLabels: Record<string, string> = {
  observe: "advice only",
  suggest: "can draft",
  draft: "can draft",
};

export function authorityLabel(authority?: string | null): string {
  return authorityLabels[authority ?? "observe"] ?? "advice only";
}
