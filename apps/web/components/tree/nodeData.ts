import type { NodeKind, NodeSummary } from "./build";
import type { TreeAgent } from "./types";

// Shared data payload for both React Flow node types (group + agent).
export interface TreeNodeData {
  nodeId: string;
  kind: NodeKind;
  label: string;
  team: string;
  initials?: string;
  agent?: TreeAgent;
  selected: boolean;
  hasChildren: boolean;
  collapsed: boolean;
  summary: NodeSummary;
  onToggle: (id: string) => void;
  [key: string]: unknown;
}
