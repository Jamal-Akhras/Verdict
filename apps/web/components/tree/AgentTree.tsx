"use client";
import { useCallback, useMemo, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  Panel,
  type Edge,
  type Node,
} from "@xyflow/react";
import { AgentNode } from "./AgentNode";
import { GroupNode } from "./GroupNode";
import {
  buildTree,
  collapsibleIds,
  layoutTree,
  summarize,
} from "./build";
import type { TreeNodeData } from "./nodeData";
import type { TreeAgent } from "./types";

const nodeTypes = { agent: AgentNode, group: GroupNode };

export function AgentTree({
  agents,
  selectedId,
  onSelect,
}: {
  agents: TreeAgent[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  // default: fully expanded (empty collapsed set)
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  const tree = useMemo(() => buildTree(agents), [agents]);

  const onToggle = useCallback((id: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const expandAll = useCallback(() => setCollapsed(new Set()), []);
  const collapseAll = useCallback(
    () => setCollapsed(new Set(collapsibleIds(tree))),
    [tree]
  );

  const { nodes, edges } = useMemo(() => {
    const { positions, visible } = layoutTree(tree, collapsed);
    const rfNodes: Node<TreeNodeData>[] = [];
    const rfEdges: Edge[] = [];

    for (const id of visible) {
      const node = tree.nodes.get(id);
      if (!node) continue;
      const hasChildren = node.childIds.length > 0 && node.kind !== "founder";
      const data: TreeNodeData = {
        nodeId: id,
        kind: node.kind,
        label: node.label,
        team: node.team,
        initials: node.initials,
        agent: node.agent,
        selected: node.kind === "agent" && id === selectedId,
        hasChildren,
        collapsed: collapsed.has(id),
        summary: summarize(tree.nodes, id),
        onToggle,
      };
      rfNodes.push({
        id,
        type: node.kind === "agent" ? "agent" : "group",
        position: positions[id] ?? { x: 0, y: 0 },
        data,
      });
      if (node.parentId && visible.has(node.parentId)) {
        rfEdges.push({
          id: `${node.parentId}-${id}`,
          source: node.parentId,
          target: id,
          type: "smoothstep",
          style: { stroke: "#d6d3d1" },
        });
      }
    }
    return { nodes: rfNodes, edges: rfEdges };
  }, [tree, collapsed, selectedId, onToggle]);

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      onNodeClick={(_, node) => {
        const kind = (node.data as TreeNodeData).kind;
        if (kind === "agent") onSelect(node.id);
        else if (kind === "department") onToggle(node.id);
        // founder: no action
      }}
      fitView
      proOptions={{ hideAttribution: true }}
      colorMode="light"
    >
      <Panel position="top-right">
        <div className="flex gap-1.5">
          <button
            onClick={expandAll}
            className="rounded-lg border border-stone-300 bg-white px-2.5 py-1 text-xs text-stone-600 hover:border-stone-500"
          >
            Expand all
          </button>
          <button
            onClick={collapseAll}
            className="rounded-lg border border-stone-300 bg-white px-2.5 py-1 text-xs text-stone-600 hover:border-stone-500"
          >
            Collapse all
          </button>
        </div>
      </Panel>
      <Background color="#e7e5e4" />
      <Controls />
    </ReactFlow>
  );
}
