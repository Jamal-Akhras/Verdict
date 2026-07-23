"use client";
import { useState } from "react";
import { AgentTree } from "@/components/tree/AgentTree";
import { AgentRoster, RosterTreeToggle } from "@/components/agents/AgentRoster";
import { AgentDrawer } from "@/components/agents/AgentDrawer";
import { NeedsYou } from "@/components/approvals/NeedsYou";
import { demoAgents, demoApprovals, demoProject } from "@/lib/mock-data";

export default function DemoProjectPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [view, setView] = useState<"roster" | "tree">("roster");
  const selected = demoAgents.find((a) => a.id === selectedId) ?? null;
  const p = demoProject;
  const pct = Math.round((p.budgetUsedUsd / p.budgetTotalUsd) * 100);

  return (
    <div className="flex h-[calc(100vh-53px)]">
      <div className="flex-1 flex flex-col">
        <div className="bg-white px-6 py-3 border-b border-stone-200 flex items-center gap-5 text-sm">
          <span className="font-semibold text-stone-900">{p.name}</span>
          <span className="rounded-full bg-blue-50 px-2.5 py-0.5 text-xs text-blue-700 capitalize">
            {p.stage}
          </span>
          <RosterTreeToggle view={view} onChange={setView} />
          <span className="text-stone-500 text-xs">
            Demo data · your company of {demoAgents.length - 1} agents
          </span>
          <div className="ml-auto flex items-center gap-3">
            <span className="text-xs text-stone-500">
              ${p.budgetUsedUsd.toFixed(2)} of ${p.budgetTotalUsd.toFixed(2)}
            </span>
            <div className="h-1.5 w-24 rounded bg-stone-100">
              <div className="h-1.5 rounded bg-stone-800" style={{ width: `${pct}%` }} />
            </div>
          </div>
        </div>
        <div className="flex-1 min-h-0">
          {view === "roster" ? (
            <AgentRoster agents={demoAgents} selectedId={selectedId} onSelect={setSelectedId} />
          ) : (
            <AgentTree agents={demoAgents} selectedId={selectedId} onSelect={setSelectedId} />
          )}
        </div>
      </div>
      <aside className="w-96 shrink-0 border-l border-stone-200 bg-stone-50 flex flex-col">
        <div className="flex items-center gap-2 border-b border-stone-200 bg-white px-4 py-2">
          {selected && (
            <button
              onClick={() => setSelectedId(null)}
              aria-label="Back to On your desk"
              className="rounded px-1 text-sm text-stone-500 hover:text-stone-900"
            >
              ←
            </button>
          )}
          <span className="text-xs font-semibold text-stone-900">On your desk</span>
          {demoApprovals.length > 0 && (
            <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
              {demoApprovals.length} waiting
            </span>
          )}
        </div>
        <div className="min-h-0 flex-1">
          {selected ? (
            <AgentDrawer agent={selected} onClose={() => setSelectedId(null)} />
          ) : (
            <NeedsYou />
          )}
        </div>
      </aside>
    </div>
  );
}
