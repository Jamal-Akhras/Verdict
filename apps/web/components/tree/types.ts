export interface TreeAgent {
  id: string;
  name: string;
  initials: string;
  team: string;
  parentId: string | null;
  // template slug (stable across demo + API); drives lead->report nesting
  slug?: string;
  status: string;
  authority?: string;
  model?: string;
  riskLevel?: string;
  budgetMaxUsd: number;
  costUsedUsd: number;
  currentTask?: string | null;
  role?: string;
  tasks?: { title: string; status: string; costUsd: number }[];
  outputs?: string[];
  log?: string[];
}

const palette: Record<string, { bg: string; text: string }> = {
  Governance: { bg: "bg-stone-200", text: "text-stone-700" },
  Strategy: { bg: "bg-violet-100", text: "text-violet-800" },
  Product: { bg: "bg-orange-100", text: "text-orange-800" },
  Engineering: { bg: "bg-blue-100", text: "text-blue-800" },
  Quality: { bg: "bg-teal-100", text: "text-teal-800" },
};

export function teamColor(team: string): { bg: string; text: string } {
  return palette[team] ?? { bg: "bg-stone-200", text: "text-stone-700" };
}
