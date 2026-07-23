"use client";
import { Handle, Position, type NodeProps, type Node } from "@xyflow/react";
import { STATUS_DOT } from "./build";
import { teamColor } from "./types";
import type { TreeNodeData } from "./nodeData";

export type GroupNodeType = Node<TreeNodeData, "group">;

function Chevron({ collapsed }: { collapsed: boolean }) {
  return (
    <span className="text-stone-400 text-xs leading-none select-none">
      {collapsed ? "▸" : "▾"}
    </span>
  );
}

export function GroupNode({ data }: NodeProps<GroupNodeType>) {
  const { kind, label, team, initials, selected, hasChildren, collapsed, summary, onToggle } =
    data;
  const tc = teamColor(team);
  const isFounder = kind === "founder";

  return (
    <div
      className={`rounded-xl border bg-white px-3 py-2 shadow-sm transition-colors ${
        selected ? "border-stone-900" : "border-stone-200"
      } ${isFounder ? "w-52" : "w-48 cursor-pointer hover:border-stone-400"}`}
    >
      <Handle type="target" position={Position.Top} className="!bg-stone-300" />
      <div className="flex items-center gap-2.5">
        {isFounder ? (
          <div
            className={`h-7 w-7 shrink-0 rounded-full ${tc.bg} ${tc.text} flex items-center justify-center text-xs font-semibold`}
          >
            {initials ?? "You"}
          </div>
        ) : (
          <span className={`h-6 w-1.5 shrink-0 rounded-full ${tc.bg}`} />
        )}
        <div className="min-w-0 flex-1">
          <div className="text-xs font-semibold text-stone-900 truncate">{label}</div>
          {!isFounder && (
            <div className="text-[11px] text-stone-500">
              {summary.count} {summary.count === 1 ? "agent" : "agents"}
            </div>
          )}
        </div>
        {hasChildren && !isFounder && (
          <button
            aria-label={collapsed ? "Expand" : "Collapse"}
            onClick={(e) => {
              e.stopPropagation();
              onToggle(data.nodeId);
            }}
            className="shrink-0 rounded p-0.5 hover:bg-stone-100"
          >
            <Chevron collapsed={collapsed} />
          </button>
        )}
      </div>
      {collapsed && !isFounder && (
        <div className="mt-1.5 flex items-center gap-1.5">
          <span className={`h-2 w-2 rounded-full ${STATUS_DOT[summary.worst] ?? "bg-stone-300"}`} />
          <span className="text-[11px] text-stone-500">folded · click to expand</span>
        </div>
      )}
      <Handle type="source" position={Position.Bottom} className="!bg-stone-300" />
    </div>
  );
}
