"use client";
import { Handle, Position, type NodeProps, type Node } from "@xyflow/react";
import { authorityLabel, budgetBarColor, statusChip } from "@/lib/status";
import { STATUS_DOT } from "./build";
import { teamColor } from "./types";
import type { TreeNodeData } from "./nodeData";

export type AgentNodeType = Node<TreeNodeData, "agent">;

export function AgentNode({ data }: NodeProps<AgentNodeType>) {
  const { agent, selected, hasChildren, collapsed, summary, onToggle } = data;
  if (!agent) return null;
  const pct =
    agent.budgetMaxUsd > 0 ? Math.min(100, (agent.costUsedUsd / agent.budgetMaxUsd) * 100) : 0;
  const tc = teamColor(agent.team);
  const dimmed = agent.status === "proposed" || agent.status === "rejected";
  return (
    <div
      className={`w-60 rounded-xl border bg-white px-3 py-2.5 text-left shadow-sm transition-colors ${
        selected ? "border-stone-900 ring-1 ring-stone-900" : "border-stone-200 hover:border-stone-400"
      } ${dimmed ? "opacity-70" : ""}`}
    >
      <Handle type="target" position={Position.Top} className="!bg-stone-300" />
      <div className="flex items-center gap-2.5">
        <div
          className={`h-8 w-8 shrink-0 rounded-full ${tc.bg} ${tc.text} flex items-center justify-center text-xs font-semibold`}
        >
          {agent.initials}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs font-semibold text-stone-900 truncate">{agent.name}</span>
            <div className="flex items-center gap-1 shrink-0">
              <span className={`text-xs px-1.5 py-0.5 rounded-full ${statusChip(agent.status)}`}>
                {agent.status}
              </span>
              {hasChildren && (
                <button
                  aria-label={collapsed ? "Expand reports" : "Collapse reports"}
                  onClick={(e) => {
                    e.stopPropagation();
                    onToggle(data.nodeId);
                  }}
                  className="rounded p-0.5 hover:bg-stone-100 text-stone-400 text-xs leading-none"
                >
                  {collapsed ? "▸" : "▾"}
                </button>
              )}
            </div>
          </div>
          <div className="text-xs text-stone-500 truncate">
            {agent.currentTask ?? agent.team}
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
      {hasChildren && collapsed && (
        <div className="mt-1.5 flex items-center gap-1.5">
          <span className={`h-2 w-2 rounded-full ${STATUS_DOT[summary.worst] ?? "bg-stone-300"}`} />
          <span className="text-[11px] text-stone-500">
            {summary.count} {summary.count === 1 ? "report" : "reports"} folded in
          </span>
        </div>
      )}
      <Handle type="source" position={Position.Bottom} className="!bg-stone-300" />
    </div>
  );
}
