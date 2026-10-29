"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api, errorDetail, type ApiAgent, type ModelProfile } from "@/lib/api";

const ACCESS_LABEL: Record<string, string> = {
  api: "API",
  subscription: "subscription",
  local: "local",
};

type Gate = "default" | "always" | "never";

function gateOf(v: boolean | null): Gate {
  return v === null ? "default" : v ? "always" : "never";
}

const field =
  "w-full rounded-lg border border-stone-300 bg-white px-2.5 py-1.5 text-xs text-stone-800 focus:border-stone-500 focus:outline-none";

/** Per-agent setup: which model does the work, who reviews it, and what
 *  extra instructions it follows. Saved as one PATCH; every change is audited. */
export function AgentConfig({
  projectId,
  agent,
  agents,
  profiles,
  onSaved,
}: {
  projectId: string;
  agent: ApiAgent;
  agents: ApiAgent[];
  profiles: ModelProfile[];
  onSaved: () => void;
}) {
  const [modelId, setModelId] = useState(agent.model_profile_id ?? "");
  const [supervisorId, setSupervisorId] = useState(agent.supervisor_id ?? "");
  const [instructions, setInstructions] = useState(agent.instructions);
  const [revisions, setRevisions] = useState(agent.max_revisions);
  const [gate, setGate] = useState<Gate>(gateOf(agent.requires_approval));
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    setModelId(agent.model_profile_id ?? "");
    setSupervisorId(agent.supervisor_id ?? "");
    setInstructions(agent.instructions);
    setRevisions(agent.max_revisions);
    setGate(gateOf(agent.requires_approval));
    setMessage(null);
  }, [agent]);

  const candidates = agents.filter(
    (a) => a.id !== agent.id && !["archived", "rejected"].includes(a.status)
  );
  const dirty =
    modelId !== (agent.model_profile_id ?? "") ||
    supervisorId !== (agent.supervisor_id ?? "") ||
    instructions !== agent.instructions ||
    revisions !== agent.max_revisions ||
    gate !== gateOf(agent.requires_approval);

  async function save() {
    setSaving(true);
    setMessage(null);
    try {
      await api.configureAgent(agent.id, {
        model_profile_id: modelId || null,
        supervisor_id: supervisorId || null,
        instructions,
        max_revisions: revisions,
        requires_approval: gate === "default" ? null : gate === "always",
      });
      setMessage({ ok: true, text: "Saved." });
      onSaved();
    } catch (e) {
      setMessage({ ok: false, text: errorDetail(e, "Could not save this setup.") });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="p-4 border-b border-stone-200 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-xs uppercase tracking-wide text-stone-500">Setup</h3>
        <Link
          href={`/projects/${projectId}/trace?agent=${agent.slug}`}
          className="text-xs text-stone-500 hover:text-stone-900"
        >
          Full trace →
        </Link>
      </div>

      <label className="block">
        <span className="text-xs text-stone-600">Model</span>
        <select value={modelId} onChange={(e) => setModelId(e.target.value)} className={`${field} mt-1`}>
          <option value="">Automatic (best model for the task)</option>
          {profiles.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name} · {ACCESS_LABEL[p.access]}
            </option>
          ))}
        </select>
        {profiles.length === 0 && (
          <span className="mt-1 block text-xs text-stone-500">
            <Link href="/settings/models" className="underline hover:text-stone-900">
              Add models
            </Link>{" "}
            to run this agent locally or on a subscription.
          </span>
        )}
      </label>

      <label className="block">
        <span className="text-xs text-stone-600">Reports to</span>
        <select
          value={supervisorId}
          onChange={(e) => setSupervisorId(e.target.value)}
          className={`${field} mt-1`}
        >
          <option value="">You (no review before it reaches the team)</option>
          {candidates.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name}
            </option>
          ))}
        </select>
        <span className="mt-1 block text-xs text-stone-500">
          The supervisor reviews every draft, sends weak work back, and escalates only what it
          can&apos;t settle.
        </span>
      </label>

      <div className="flex gap-3">
        <label className="block flex-1">
          <span className="text-xs text-stone-600">Send-backs allowed</span>
          <input
            type="number"
            min={0}
            max={5}
            value={revisions}
            onChange={(e) => setRevisions(Math.max(0, Math.min(5, Number(e.target.value) || 0)))}
            className={`${field} mt-1`}
          />
        </label>
        <label className="block flex-1">
          <span className="text-xs text-stone-600">Your sign-off</span>
          <select
            value={gate}
            onChange={(e) => setGate(e.target.value as Gate)}
            className={`${field} mt-1`}
          >
            <option value="default">Default for this role</option>
            <option value="always">Always ask me</option>
            <option value="never">Only if escalated</option>
          </select>
        </label>
      </div>

      <label className="block">
        <span className="text-xs text-stone-600">Extra instructions</span>
        <textarea
          value={instructions}
          onChange={(e) => setInstructions(e.target.value)}
          rows={4}
          maxLength={8000}
          placeholder="e.g. Prices in USD. Assume a 2-person team. Cite a source for every number."
          className={`${field} mt-1 resize-y`}
        />
      </label>

      <div className="flex items-center gap-2">
        <button
          onClick={save}
          disabled={!dirty || saving}
          className="rounded-lg bg-stone-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-stone-700 disabled:opacity-40"
        >
          {saving ? "Saving…" : "Save setup"}
        </button>
        {message && (
          <span className={`text-xs ${message.ok ? "text-emerald-600" : "text-rose-600"}`}>
            {message.text}
          </span>
        )}
      </div>
    </div>
  );
}
