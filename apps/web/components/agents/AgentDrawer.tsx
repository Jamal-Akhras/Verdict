"use client";
import { useEffect, useRef } from "react";
import { authorityLabel, statusChip, taskStatusColor } from "@/lib/status";
import { teamColor, type TreeAgent } from "@/components/tree/types";

export type AgentAction = "approve" | "deny" | "pause" | "resume" | "archive";

const actionsByStatus: Record<string, AgentAction[]> = {
  proposed: ["approve", "deny"],
  approved: ["pause", "archive"],
  active: ["pause", "archive"],
  paused: ["resume", "archive"],
  blocked: ["resume", "archive"],
  completed: ["archive"],
};

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4 text-xs py-1">
      <span className="text-stone-500">{label}</span>
      <span className="text-right capitalize text-stone-700">{value}</span>
    </div>
  );
}

export function AgentDrawer({
  agent,
  onClose,
  onAction,
  busy,
  children,
}: {
  agent: TreeAgent;
  onClose: () => void;
  onAction?: (action: AgentAction) => void;
  busy?: boolean;
  /** Extra sections (e.g. hierarchy setup) rendered under the summary. */
  children?: React.ReactNode;
}) {
  const tc = teamColor(agent.team);
  const actions = actionsByStatus[agent.status] ?? [];
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeRef.current?.focus();
  }, [agent.id]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`${agent.name} details`}
      className="flex h-full flex-col overflow-y-auto"
    >
      <div className="p-4 border-b border-stone-200 flex items-start gap-3">
        <div
          className={`h-9 w-9 shrink-0 rounded-full ${tc.bg} ${tc.text} flex items-center justify-center text-xs font-semibold`}
        >
          {agent.initials}
        </div>
        <div className="min-w-0 flex-1">
          <h2 className="font-semibold text-sm text-stone-900">{agent.name}</h2>
          <p className="text-xs text-stone-500 mt-0.5">{agent.role ?? agent.team}</p>
        </div>
        <button
          ref={closeRef}
          onClick={onClose}
          aria-label="Close agent details"
          className="rounded-lg border border-stone-300 px-2 py-1 text-xs text-stone-600 hover:border-stone-500 hover:text-stone-900"
        >
          Close
        </button>
      </div>

      <div className="p-4 border-b border-stone-200">
        <Row
          label="Status"
          value={
            <span className={`rounded-full px-1.5 py-0.5 ${statusChip(agent.status)}`}>
              {agent.status}
            </span>
          }
        />
        <Row label="Team" value={agent.team} />
        {agent.authority && <Row label="What it can do" value={authorityLabel(agent.authority)} />}
        {agent.model && <Row label="Model" value={agent.model} />}
        {agent.riskLevel && <Row label="Risk level" value={agent.riskLevel} />}
        <Row
          label="Budget"
          value={`$${agent.costUsedUsd.toFixed(2)} used of $${agent.budgetMaxUsd.toFixed(2)}`}
        />
      </div>

      {children}

      {agent.tasks !== undefined && (
        <Section title="Tasks">
          {agent.tasks.length === 0 && <Empty text="No tasks yet - orchestration lands in Milestone 3." />}
          {agent.tasks.map((t) => (
            <div key={t.title} className="flex justify-between text-xs py-1">
              <span className="text-stone-700">{t.title}</span>
              <span className="text-stone-500">
                <span className={taskStatusColor(t.status)}>{t.status}</span> · $
                {t.costUsd.toFixed(2)}
              </span>
            </div>
          ))}
        </Section>
      )}

      {agent.outputs !== undefined && (
        <Section title="Documents">
          {agent.outputs.length === 0 && <Empty text="No documents yet." />}
          {agent.outputs.map((o) => (
            <div key={o} className="text-xs py-1 text-stone-800">
              {o}
            </div>
          ))}
        </Section>
      )}

      {agent.log !== undefined && (
        <Section title="Activity log">
          {agent.log.length === 0 && <Empty text="Nothing logged yet." />}
          {agent.log.map((l) => (
            <div key={l} className="text-xs py-1 text-stone-500">
              · {l}
            </div>
          ))}
        </Section>
      )}

      {actions.length > 0 && (
        <div className="p-4 flex gap-2 flex-wrap">
          {actions.map((a) => (
            <button
              key={a}
              disabled={!onAction || busy}
              onClick={() => onAction?.(a)}
              className={`rounded-lg px-3 py-1.5 text-xs capitalize disabled:opacity-40 ${
                a === "approve"
                  ? "bg-stone-900 text-white hover:bg-stone-700"
                  : "border border-stone-300 text-stone-600 hover:border-stone-500 hover:text-stone-900"
              }`}
            >
              {a}
            </button>
          ))}
        </div>
      )}
      <p className="px-4 pb-4 text-xs text-stone-500">
        Every action writes an audit event.
      </p>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="p-4 border-b border-stone-200">
      <h3 className="text-xs uppercase tracking-wide text-stone-500 mb-2">{title}</h3>
      {children}
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return <div className="text-xs text-stone-500">{text}</div>;
}
