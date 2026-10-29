"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api, errorDetail, type ApiProject, type ModelProfile } from "@/lib/api";

const field =
  "w-full rounded-lg border border-stone-300 bg-white px-2.5 py-1.5 text-xs text-stone-800 focus:border-stone-500 focus:outline-none";

function ProfileSelect({
  label,
  hint,
  value,
  onChange,
  profiles,
}: {
  label: string;
  hint: string;
  value: string;
  onChange: (v: string) => void;
  profiles: ModelProfile[];
}) {
  return (
    <label className="block">
      <span className="text-xs text-stone-600">{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)} className={`${field} mt-1`}>
        <option value="">Automatic (routing table)</option>
        {profiles.map((p) => (
          <option key={p.id} value={p.id}>
            {p.name} · {p.access}
          </option>
        ))}
      </select>
      <span className="mt-1 block text-xs text-stone-500">{hint}</span>
    </label>
  );
}

/** Team-wide setup: a one-click supervision hierarchy plus instructions
 *  every agent follows. Fine-tuning per agent lives in the agent drawer. */
export function TeamSetup({
  project,
  profiles,
  onChanged,
}: {
  project: ApiProject;
  profiles: ModelProfile[];
  onChanged: () => void;
}) {
  const local = profiles.find((p) => p.access === "local");
  const frontier = profiles.find((p) => p.tier === "high");
  const [shape, setShape] = useState<"flat" | "teams">("teams");
  const [worker, setWorker] = useState(local?.id ?? "");
  const [lead, setLead] = useState(frontier?.id ?? "");
  const [director, setDirector] = useState(frontier?.id ?? "");
  const [instructions, setInstructions] = useState(project.instructions);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => setInstructions(project.instructions), [project.instructions]);

  async function run(action: () => Promise<unknown>, ok: string, fail: string) {
    setBusy(true);
    setMessage(null);
    try {
      await action();
      setMessage({ ok: true, text: ok });
      onChanged();
    } catch (e) {
      setMessage({ ok: false, text: errorDetail(e, fail) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-full flex-col overflow-y-auto">
      <div className="p-4 border-b border-stone-200 space-y-3">
        <div>
          <h3 className="text-xs uppercase tracking-wide text-stone-500">Supervision hierarchy</h3>
          <p className="mt-1 text-xs text-stone-500 leading-relaxed">
            Workers draft on cheap or local models; supervisors on frontier models review every
            draft, send weak work back, and escalate upward. You only see what the top of the
            chain can&apos;t settle.
          </p>
        </div>
        <div className="flex gap-1.5" role="radiogroup" aria-label="Hierarchy shape">
          {(
            [
              ["teams", "Director + team leads"],
              ["flat", "Director only"],
            ] as const
          ).map(([value, label]) => (
            <button
              key={value}
              role="radio"
              aria-checked={shape === value}
              onClick={() => setShape(value)}
              className={`rounded-lg px-2.5 py-1.5 text-xs ${
                shape === value
                  ? "bg-stone-900 text-white"
                  : "border border-stone-300 text-stone-600 hover:border-stone-500"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
        <ProfileSelect
          label="Workers"
          hint="Does the bulk of the writing. A local model costs nothing per token."
          value={worker}
          onChange={setWorker}
          profiles={profiles}
        />
        {shape === "teams" && (
          <ProfileSelect
            label="Team leads"
            hint="Reviews each draft from its team."
            value={lead}
            onChange={setLead}
            profiles={profiles}
          />
        )}
        <ProfileSelect
          label="Director"
          hint="Settles escalations; the last stop before you."
          value={director}
          onChange={setDirector}
          profiles={profiles}
        />
        {profiles.length === 0 && (
          <p className="text-xs text-amber-700">
            No models set up yet.{" "}
            <Link href="/settings/models" className="underline">
              Add a local or subscription model
            </Link>{" "}
            first.
          </p>
        )}
        <button
          disabled={busy}
          onClick={() =>
            run(
              () =>
                api.applyHierarchyPreset(project.id, {
                  shape,
                  worker_profile_id: worker || null,
                  lead_profile_id: shape === "teams" ? lead || null : null,
                  director_profile_id: director || null,
                }),
              "Hierarchy applied. Fine-tune any agent from its card.",
              "Could not apply the hierarchy."
            )
          }
          className="rounded-lg bg-stone-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-stone-700 disabled:opacity-40"
        >
          Apply hierarchy
        </button>
      </div>

      <div className="p-4 border-b border-stone-200 space-y-2">
        <h3 className="text-xs uppercase tracking-wide text-stone-500">
          Instructions for every agent
        </h3>
        <textarea
          value={instructions}
          onChange={(e) => setInstructions(e.target.value)}
          rows={5}
          maxLength={8000}
          placeholder="e.g. Target market is Lebanon; price in USD. Prefer boring, proven tech."
          className={`${field} resize-y`}
        />
        <button
          disabled={busy || instructions === project.instructions}
          onClick={() =>
            run(
              () => api.configureProject(project.id, instructions),
              "Instructions saved.",
              "Could not save instructions."
            )
          }
          className="rounded-lg border border-stone-300 px-3 py-1.5 text-xs text-stone-700 hover:border-stone-500 disabled:opacity-40"
        >
          Save instructions
        </button>
      </div>

      {message && (
        <p className={`px-4 pt-3 text-xs ${message.ok ? "text-emerald-600" : "text-rose-600"}`}>
          {message.text}
        </p>
      )}
      <div className="mt-auto p-4 border-t border-stone-200 flex justify-between">
        <Link href="/settings/models" className="text-xs text-stone-500 hover:text-stone-900">
          Manage models →
        </Link>
        <Link
          href={`/projects/${project.id}/trace`}
          className="text-xs text-stone-500 hover:text-stone-900"
        >
          Full trace →
        </Link>
      </div>
    </div>
  );
}
