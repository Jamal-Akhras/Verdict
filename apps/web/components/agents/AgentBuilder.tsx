"use client";
import { useEffect, useState } from "react";
import { authorityLabel } from "@/lib/status";
import { teamColor } from "@/components/tree/types";
import { api, type ApiAgent, type ApiTemplate } from "@/lib/api";

export function AgentBuilder({
  projectId,
  staffedSlugs,
  onAdded,
  onClose,
}: {
  projectId: string;
  staffedSlugs: string[];
  onAdded: () => void;
  onClose: () => void;
}) {
  const [templates, setTemplates] = useState<ApiTemplate[]>([]);
  const [tab, setTab] = useState<"gallery" | "custom">("gallery");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    name: "",
    role: "",
    team: "Quality",
    budget_max_usd: 5,
    risk_level: "medium",
  });

  useEffect(() => {
    api.listTemplates().then(setTemplates).catch(() => {});
  }, []);

  const available = templates.filter(
    (t) => !staffedSlugs.includes(t.slug) && t.slug !== "founder-intake" && t.slug !== "feasibility-analyst"
  );

  async function run(fn: () => Promise<ApiAgent>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      onAdded();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-full flex-col overflow-y-auto">
      <div className="p-4 border-b border-stone-200 flex items-start justify-between">
        <div>
          <h2 className="text-sm font-semibold text-stone-900">Add an agent</h2>
          <p className="text-xs text-stone-500 mt-0.5">
            New agents start as proposed - nothing runs until you approve.
          </p>
        </div>
        <button
          onClick={onClose}
          aria-label="Close agent builder"
          className="rounded-lg border border-stone-300 px-2 py-1 text-xs text-stone-600 hover:border-stone-500 hover:text-stone-900"
        >
          Close
        </button>
      </div>

      <div className="px-4 pt-3 flex gap-1.5">
        {(["gallery", "custom"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`rounded-lg px-3 py-1.5 text-xs capitalize border ${
              tab === t
                ? "bg-stone-900 text-white border-stone-900"
                : "border-stone-300 text-stone-500 hover:border-stone-500"
            }`}
          >
            {t === "gallery" ? "From template" : "Custom specialist"}
          </button>
        ))}
      </div>

      {error && (
        <div className="mx-4 mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
          {error}
        </div>
      )}

      {tab === "gallery" && (
        <div className="p-4 space-y-2.5">
          {available.length === 0 && (
            <p className="text-xs text-stone-500">Every template is already on this project.</p>
          )}
          {available.map((t) => {
            const tc = teamColor(t.team);
            return (
              <div key={t.slug} className="rounded-xl border border-stone-200 bg-white p-3">
                <div className="flex items-center gap-2.5">
                  <div
                    className={`h-7 w-7 shrink-0 rounded-full ${tc.bg} ${tc.text} flex items-center justify-center text-xs font-semibold`}
                  >
                    {t.initials}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-xs font-semibold text-stone-900">{t.name}</div>
                    <div className="text-xs text-stone-500">
                      {t.team} · ${t.default_budget_usd.toFixed(2)} budget · {t.risk_level} risk ·{" "}
                      {authorityLabel(t.authority_default)}
                    </div>
                  </div>
                  <button
                    onClick={() => run(() => api.staffAgent(projectId, t.slug))}
                    disabled={busy}
                    className="rounded-lg border border-stone-300 px-2.5 py-1 text-xs text-stone-600 hover:border-stone-500 disabled:opacity-40"
                  >
                    Propose
                  </button>
                </div>
                <p className="text-xs text-stone-500 mt-2">{t.role}</p>
              </div>
            );
          })}
        </div>
      )}

      {tab === "custom" && (
        <div className="p-4 space-y-3">
          <div>
            <label className="block text-xs font-medium text-stone-600 mb-1">Agent name</label>
            <input
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              placeholder="Supabase RLS Specialist"
              className="w-full rounded-lg border border-stone-300 bg-white px-2.5 py-1.5 text-xs focus:border-stone-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-stone-600 mb-1">
              Role - what should it review or produce?
            </label>
            <textarea
              value={form.role}
              onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}
              rows={3}
              placeholder="Review database access policies and detect unsafe row-level security setup."
              className="w-full rounded-lg border border-stone-300 bg-white px-2.5 py-1.5 text-xs focus:border-stone-500 focus:outline-none"
            />
          </div>
          <div className="grid grid-cols-3 gap-2">
            <div>
              <label className="block text-xs font-medium text-stone-600 mb-1">Team</label>
              <select
                value={form.team}
                onChange={(e) => setForm((f) => ({ ...f, team: e.target.value }))}
                className="w-full rounded-lg border border-stone-300 bg-white px-2 py-1.5 text-xs"
              >
                {["Strategy", "Product", "Engineering", "Quality"].map((t) => (
                  <option key={t}>{t}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-stone-600 mb-1">Budget $</label>
              <input
                type="number"
                min={0.5}
                max={25}
                step={0.5}
                value={form.budget_max_usd}
                onChange={(e) => setForm((f) => ({ ...f, budget_max_usd: Number(e.target.value) }))}
                className="w-full rounded-lg border border-stone-300 bg-white px-2 py-1.5 text-xs"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-stone-600 mb-1">Risk</label>
              <select
                value={form.risk_level}
                onChange={(e) => setForm((f) => ({ ...f, risk_level: e.target.value }))}
                className="w-full rounded-lg border border-stone-300 bg-white px-2 py-1.5 text-xs"
              >
                {["low", "medium", "high"].map((r) => (
                  <option key={r}>{r}</option>
                ))}
              </select>
            </div>
          </div>
          <p className="text-xs text-stone-500">
            Custom agents give advice only: they can inspect, draft, and report — never change
            anything on their own. Automated tasks for custom agents land in a later milestone -
            for now they join the team as reviewable advisors.
          </p>
          <button
            onClick={() =>
              run(() =>
                api.createCustomAgent(projectId, {
                  ...form,
                  authority: "suggest",
                })
              )
            }
            disabled={busy || form.name.length < 3 || form.role.length < 10}
            className="rounded-lg bg-stone-900 px-3.5 py-1.5 text-xs font-medium text-white hover:bg-stone-700 disabled:opacity-40"
          >
            Create proposed agent
          </button>
        </div>
      )}
    </div>
  );
}
