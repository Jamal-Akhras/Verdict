"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { actorChip, budgetBarColor } from "@/lib/status";
import { api, type ApiAuditEvent, type CostSummary } from "@/lib/api";

function csvField(value: string): string {
  // Formula-injection guard: Excel/Sheets execute cells starting with
  // = + - @, and audit summaries contain agent-authored text. Prefix with
  // ' to force plain text, and quote every field.
  const guarded = /^[=+\-@]/.test(value) ? `'${value}` : value;
  return `"${guarded.replaceAll('"', '""')}"`;
}

function toCsv(events: ApiAuditEvent[]): string {
  const header = "created_at,actor_type,event_type,summary";
  const rows = events.map((e) =>
    [e.created_at, e.actor_type, e.event_type, e.summary].map(csvField).join(",")
  );
  return [header, ...rows].join("\n");
}

export default function ActivityPage() {
  const { id } = useParams<{ id: string }>();
  const [events, setEvents] = useState<ApiAuditEvent[]>([]);
  const [costs, setCosts] = useState<CostSummary | null>(null);
  const [filter, setFilter] = useState<string>("all");

  useEffect(() => {
    api.listAudit(id).then(setEvents).catch(() => {});
    api.costSummary(id).then(setCosts).catch(() => {});
  }, [id]);

  const filtered = filter === "all" ? events : events.filter((e) => e.actor_type === filter);

  function exportCsv() {
    const blob = new Blob([toCsv(filtered)], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "verdict-audit.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="max-w-3xl mx-auto px-6 py-10">
      <Link href={`/projects/${id}`} className="text-xs text-stone-500 hover:text-stone-700">
        ← Back to command center
      </Link>
      <h1 className="text-2xl font-semibold text-stone-900 mt-2 mb-6">Activity & costs</h1>

      {costs && (
        <>
          <h2 className="text-sm font-semibold text-stone-900 mb-2">
            Spend: ${costs.total_usd.toFixed(2)}
          </h2>
          <div className="grid grid-cols-2 gap-4 mb-8">
            <div className="rounded-xl border border-stone-200 bg-white p-4">
              <div className="text-xs uppercase tracking-wide text-stone-500 mb-2">
                By agent
              </div>
              {costs.by_agent.length === 0 && (
                <p className="text-xs text-stone-500">No spend yet.</p>
              )}
              {costs.by_agent.map((a) => (
                <div key={a.agent_slug} className="py-1">
                  <div className="flex justify-between text-xs">
                    <span className="text-stone-700">{a.agent_slug}</span>
                    <span className="text-stone-500">
                      ${a.cost_usd.toFixed(2)}
                      {a.budget_usd != null && ` / $${a.budget_usd.toFixed(2)}`}
                    </span>
                  </div>
                  {a.budget_usd != null && a.budget_usd > 0 && (
                    <div className="mt-1 h-1 rounded bg-stone-100">
                      <div
                        className={`h-1 rounded ${budgetBarColor((a.cost_usd / a.budget_usd) * 100)}`}
                        style={{ width: `${Math.min(100, (a.cost_usd / a.budget_usd) * 100)}%` }}
                      />
                    </div>
                  )}
                </div>
              ))}
            </div>
            <div className="rounded-xl border border-stone-200 bg-white p-4">
              <div className="text-xs uppercase tracking-wide text-stone-500 mb-2">
                By model
              </div>
              {costs.by_model.length === 0 && (
                <p className="text-xs text-stone-500">No model calls yet.</p>
              )}
              {costs.by_model.map((m) => (
                <div key={m.model} className="flex justify-between text-xs py-1">
                  <span className="text-stone-700">
                    {m.model} <span className="text-stone-500">({m.provider})</span>
                  </span>
                  <span className="text-stone-500">
                    {m.calls} calls · ${m.cost_usd.toFixed(2)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      <div className="flex items-center justify-between mb-2">
        <h2 className="text-sm font-semibold text-stone-900">Audit timeline</h2>
        <div className="flex gap-1.5 items-center">
          {["all", "user", "agent", "system"].map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`rounded-lg px-2.5 py-1 text-xs capitalize border ${
                filter === f
                  ? "bg-stone-900 text-white border-stone-900"
                  : "border-stone-300 text-stone-500 hover:border-stone-500"
              }`}
            >
              {f}
            </button>
          ))}
          <button
            onClick={exportCsv}
            className="rounded-lg border border-stone-300 px-2.5 py-1 text-xs text-stone-500 hover:border-stone-500"
          >
            Export CSV
          </button>
        </div>
      </div>
      <div className="rounded-xl border border-stone-200 bg-white divide-y divide-stone-100">
        {filtered.length === 0 && (
          <p className="p-4 text-xs text-stone-500">No events yet.</p>
        )}
        {filtered.map((e) => (
          <div key={e.id} className="px-4 py-2.5 flex items-start gap-3">
            <span
              className={`mt-0.5 shrink-0 rounded-full px-2 py-0.5 text-xs ${actorChip[e.actor_type] ?? actorChip.system}`}
            >
              {e.actor_type}
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-xs text-stone-700">{e.summary}</p>
              <p className="text-xs text-stone-400 mt-0.5">
                {e.event_type} · {new Date(e.created_at).toLocaleString()}
              </p>
            </div>
          </div>
        ))}
      </div>
      <p className="mt-3 text-xs text-stone-500">
        Append-only: this timeline includes failures, denials, and warnings - not just wins.
      </p>
    </div>
  );
}
