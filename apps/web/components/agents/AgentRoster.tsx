"use client";
import { authorityLabel, budgetBarColor, statusChip } from "@/lib/status";
import { teamColor, type TreeAgent } from "@/components/tree/types";

const TEAM_ORDER = ["Strategy", "Product", "Engineering", "Quality"];

/** Agents that need the founder's attention float to the top of each team. */
function sortWeight(a: TreeAgent): number {
  if (a.status === "proposed" || a.status === "blocked") return 0; // needs you
  if (a.status === "active") return 1; // working
  if (a.status === "paused") return 2;
  if (a.status === "approved") return 3;
  if (a.status === "completed") return 4;
  return 5; // archived / rejected
}

function StatusStrip({ agents }: { agents: TreeAgent[] }) {
  const working = agents.filter((a) => a.status === "active").length;
  const blocked = agents.filter((a) => a.status === "blocked").length;
  const waiting = agents.filter((a) => a.status === "proposed").length;
  const parts: string[] = [];
  if (working > 0) parts.push(`${working} working`);
  if (blocked > 0) parts.push(`${blocked} blocked`);
  if (waiting > 0) parts.push(`${waiting} waiting on you`);
  return (
    <div className="flex items-center gap-2 text-xs text-stone-600">
      {working > 0 && (
        <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" aria-hidden />
      )}
      <span>{parts.length > 0 ? parts.join(" · ") : "Nothing in motion right now"}</span>
    </div>
  );
}

function RosterCard({
  agent,
  selected,
  onSelect,
}: {
  agent: TreeAgent;
  selected: boolean;
  onSelect: (id: string) => void;
}) {
  const pct =
    agent.budgetMaxUsd > 0 ? Math.min(100, (agent.costUsedUsd / agent.budgetMaxUsd) * 100) : 0;
  const tc = teamColor(agent.team);
  const dimmed = agent.status === "rejected" || agent.status === "archived";
  return (
    <button
      onClick={() => onSelect(agent.id)}
      className={`w-full rounded-xl border bg-white px-3 py-2.5 text-left shadow-sm transition-colors ${
        selected
          ? "border-stone-900 ring-1 ring-stone-900"
          : "border-stone-200 hover:border-stone-400"
      } ${dimmed ? "opacity-70" : ""}`}
    >
      <div className="flex items-center gap-2.5">
        <div
          className={`h-8 w-8 shrink-0 rounded-full ${tc.bg} ${tc.text} flex items-center justify-center text-xs font-semibold`}
        >
          {agent.initials}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs font-semibold text-stone-900 truncate">{agent.name}</span>
            <span className={`text-xs px-1.5 py-0.5 rounded-full ${statusChip(agent.status)}`}>
              {agent.status}
            </span>
          </div>
          <div className="text-xs text-stone-500 truncate">
            {agent.currentTask ?? agent.role ?? agent.team}
          </div>
        </div>
      </div>
      <div className="mt-2 flex items-center justify-between text-xs text-stone-500">
        <span>{agent.model ?? authorityLabel(agent.authority)}</span>
        <span>
          ${agent.costUsedUsd.toFixed(2)}
          {agent.budgetMaxUsd > 0 && ` of $${agent.budgetMaxUsd.toFixed(2)}`}
        </span>
      </div>
      {agent.budgetMaxUsd > 0 && (
        <div className="mt-1 h-1 rounded bg-stone-100">
          <div className={`h-1 rounded ${budgetBarColor(pct)}`} style={{ width: `${pct}%` }} />
        </div>
      )}
    </button>
  );
}

export function AgentRoster({
  agents,
  selectedId,
  onSelect,
}: {
  agents: TreeAgent[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  // The founder root ("You") lives in the right rail, not on the roster.
  const staff = agents.filter((a) => a.parentId !== null);
  const teams = [
    ...TEAM_ORDER,
    ...Array.from(new Set(staff.map((a) => a.team))).filter((t) => !TEAM_ORDER.includes(t)),
  ];

  return (
    <div className="h-full overflow-y-auto bg-stone-50">
      <div className="mx-auto max-w-4xl px-6 py-5">
        <StatusStrip agents={staff} />
        {teams.map((team) => {
          const members = staff
            .filter((a) => a.team === team)
            .sort((a, b) => sortWeight(a) - sortWeight(b));
          if (members.length === 0) return null;
          const tc = teamColor(team);
          return (
            <section key={team} className="mt-5">
              <h3 className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-stone-500">
                <span className={`h-2 w-2 rounded-full ${tc.bg}`} aria-hidden />
                {team}
              </h3>
              <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 xl:grid-cols-3">
                {members.map((agent) => (
                  <RosterCard
                    key={agent.id}
                    agent={agent}
                    selected={agent.id === selectedId}
                    onSelect={onSelect}
                  />
                ))}
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}

/** Small two-tab switch between the roster and the structure (tree) view. */
export function RosterTreeToggle({
  view,
  onChange,
}: {
  view: "roster" | "tree";
  onChange: (view: "roster" | "tree") => void;
}) {
  return (
    <div
      className="inline-flex items-center rounded-lg border border-stone-200 bg-stone-100 p-0.5"
      role="tablist"
      aria-label="Team view"
    >
      {(["roster", "tree"] as const).map((v) => (
        <button
          key={v}
          role="tab"
          aria-selected={view === v}
          onClick={() => onChange(v)}
          className={`rounded-md px-2.5 py-1 text-xs ${
            view === v
              ? "bg-white text-stone-900 shadow-sm font-medium"
              : "text-stone-500 hover:text-stone-900"
          }`}
        >
          {v === "roster" ? "Roster" : "Tree"}
        </button>
      ))}
    </div>
  );
}
