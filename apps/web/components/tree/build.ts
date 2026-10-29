import type { TreeAgent } from "./types";

// Hybrid hierarchy:  You (founder) -> Department -> lead agent -> report agent.
// Departments come from the agent's `team`; lead->report nesting is defined
// by slug below. Once the founder configures supervisors, the real chain of
// command (agent.parentId = its supervisor) replaces the departments. Departments and leads can collapse; when collapsed, their
// descendants' status bubbles up as a summary chip on the folded node.

export type NodeKind = "founder" | "department" | "agent";

export interface BuiltNode {
  id: string;
  kind: NodeKind;
  label: string;
  team: string;
  initials?: string;
  agent?: TreeAgent;
  parentId: string | null;
  childIds: string[];
}

const DEPT_ORDER = ["Strategy", "Product", "Engineering", "Quality", "Governance"];

// Senior agent slug -> the report slugs that fold into it.
export const LEAD_REPORTS: Record<string, string[]> = {
  "cto-architecture": ["engineering-planner"],
};

function slugOf(a: TreeAgent): string {
  return a.slug ?? a.id;
}

export interface BuiltTree {
  nodes: Map<string, BuiltNode>;
  rootId: string | null;
}

export function buildTree(agents: TreeAgent[]): BuiltTree {
  const nodes = new Map<string, BuiltNode>();
  const founder = agents.find((a) => a.parentId === null) ?? null;
  const rootId = founder ? founder.id : null;

  if (founder) {
    nodes.set(founder.id, {
      id: founder.id,
      kind: "founder",
      label: founder.name,
      team: founder.team,
      initials: founder.initials,
      agent: founder,
      parentId: null,
      childIds: [],
    });
  }

  const others = agents.filter((a) => a.id !== rootId);

  // A configured supervision hierarchy wins over department grouping: the
  // tree then shows who reviews whom and which way escalations climb.
  const ids = new Set(others.map((a) => a.id));
  if (others.some((a) => a.parentId !== null && ids.has(a.parentId))) {
    for (const a of others) {
      nodes.set(a.id, {
        id: a.id,
        kind: "agent",
        label: a.name,
        team: a.team,
        initials: a.initials,
        agent: a,
        parentId: a.parentId !== null && ids.has(a.parentId) ? a.parentId : rootId,
        childIds: [],
      });
    }
    for (const a of others) {
      const parent = nodes.get(nodes.get(a.id)!.parentId ?? "");
      if (parent) parent.childIds.push(a.id);
    }
    return { nodes, rootId };
  }

  const teams = new Map<string, TreeAgent[]>();
  for (const a of others) {
    const list = teams.get(a.team) ?? [];
    list.push(a);
    teams.set(a.team, list);
  }
  const orderedTeams = [
    ...DEPT_ORDER.filter((t) => teams.has(t)),
    ...[...teams.keys()].filter((t) => !DEPT_ORDER.includes(t)),
  ];

  for (const team of orderedTeams) {
    const members = teams.get(team) ?? [];
    const deptId = `dept:${team}`;
    nodes.set(deptId, {
      id: deptId,
      kind: "department",
      label: team,
      team,
      parentId: rootId,
      childIds: [],
    });
    if (rootId) nodes.get(rootId)!.childIds.push(deptId);

    // create agent nodes, initially parented to the department
    for (const a of members) {
      nodes.set(a.id, {
        id: a.id,
        kind: "agent",
        label: a.name,
        team: a.team,
        initials: a.initials,
        agent: a,
        parentId: deptId,
        childIds: [],
      });
    }

    // re-parent reports under their lead (same department only)
    const bySlug = new Map(members.map((m) => [slugOf(m), m]));
    for (const a of members) {
      for (const reportSlug of LEAD_REPORTS[slugOf(a)] ?? []) {
        const report = bySlug.get(reportSlug);
        if (report) nodes.get(report.id)!.parentId = a.id;
      }
    }

    // wire childIds now that all parentIds are final
    for (const a of members) {
      const node = nodes.get(a.id)!;
      const parent = nodes.get(node.parentId!);
      if (parent) parent.childIds.push(a.id);
    }
  }

  return { nodes, rootId };
}

// --- status rollup for collapsed-node summary chips -------------------------

// Higher rank = more attention-worthy; the worst descendant wins the dot color.
const STATUS_RANK: Record<string, number> = {
  blocked: 6,
  paused: 5,
  proposed: 4,
  review: 3,
  active: 2,
  approved: 1,
  completed: 0,
  archived: -1,
  rejected: -1,
};

export const STATUS_DOT: Record<string, string> = {
  blocked: "bg-rose-500",
  paused: "bg-amber-500",
  proposed: "bg-stone-400",
  review: "bg-amber-500",
  active: "bg-emerald-500",
  approved: "bg-sky-500",
  completed: "bg-violet-500",
  archived: "bg-stone-300",
  rejected: "bg-rose-300",
};

export interface NodeSummary {
  count: number;
  worst: string;
}

export function summarize(nodes: Map<string, BuiltNode>, id: string): NodeSummary {
  let count = 0;
  let worst = "completed";
  let worstRank = -Infinity;
  const walk = (nid: string) => {
    const n = nodes.get(nid);
    if (!n) return;
    if (n.kind === "agent") {
      count += 1;
      const st = n.agent?.status ?? "completed";
      const rank = STATUS_RANK[st] ?? 0;
      if (rank > worstRank) {
        worstRank = rank;
        worst = st;
      }
    }
    n.childIds.forEach(walk);
  };
  nodes.get(id)?.childIds.forEach(walk);
  return { count, worst };
}

// --- tidy layout (respects the collapsed set) ------------------------------

const X_STEP = 250;
const Y_STEP = 165;

export interface LayoutResult {
  positions: Record<string, { x: number; y: number }>;
  visible: Set<string>;
}

export function layoutTree(
  tree: BuiltTree,
  collapsed: Set<string>
): LayoutResult {
  const positions: Record<string, { x: number; y: number }> = {};
  const visible = new Set<string>();
  let cursor = 0;

  const place = (id: string, depth: number): number => {
    visible.add(id);
    const node = tree.nodes.get(id);
    const kids =
      node && !collapsed.has(id)
        ? node.childIds.filter((k) => tree.nodes.has(k))
        : [];
    if (kids.length === 0) {
      const x = cursor * X_STEP;
      cursor += 1;
      positions[id] = { x, y: depth * Y_STEP };
      return x;
    }
    const xs = kids.map((k) => place(k, depth + 1));
    const x = (xs[0] + xs[xs.length - 1]) / 2;
    positions[id] = { x, y: depth * Y_STEP };
    return x;
  };

  if (tree.rootId) place(tree.rootId, 0);
  return { positions, visible };
}

// nodes that CAN collapse (have children and aren't the root founder)
export function collapsibleIds(tree: BuiltTree): string[] {
  const out: string[] = [];
  for (const n of tree.nodes.values()) {
    if (n.kind !== "founder" && n.childIds.length > 0) out.push(n.id);
  }
  return out;
}
