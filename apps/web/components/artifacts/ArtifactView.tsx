"use client";
import type { ApiArtifact } from "@/lib/api";

function isObjArray(v: unknown): v is Record<string, unknown>[] {
  return Array.isArray(v) && v.length > 0 && typeof v[0] === "object" && v[0] !== null;
}

function Value({ value }: { value: unknown }) {
  if (typeof value === "string" || typeof value === "number")
    return <p className="text-sm text-stone-700 leading-relaxed">{String(value)}</p>;
  if (Array.isArray(value) && value.every((v) => typeof v === "string"))
    return (
      <ul className="space-y-1">
        {(value as string[]).map((v) => (
          <li key={v} className="flex gap-2 text-sm text-stone-700">
            <span className="text-stone-400">·</span>
            <span>{v}</span>
          </li>
        ))}
      </ul>
    );
  if (isObjArray(value))
    return (
      <div className="space-y-2">
        {value.map((item, i) => (
          <div key={i} className="rounded-lg border border-stone-200 bg-stone-50 p-3">
            {Object.entries(item).map(([k, v]) => (
              <div key={k} className="flex gap-2 text-xs py-0.5">
                <span className="w-40 shrink-0 text-stone-500">{k.replaceAll("_", " ")}</span>
                <span className="text-stone-700">
                  {Array.isArray(v) ? (v as unknown[]).map(String).join(" · ") : String(v)}
                </span>
              </div>
            ))}
          </div>
        ))}
      </div>
    );
  if (typeof value === "object" && value !== null)
    return (
      <div className="rounded-lg border border-stone-200 bg-stone-50 p-3">
        {Object.entries(value as Record<string, unknown>).map(([k, v]) => (
          <div key={k} className="flex gap-2 text-xs py-0.5">
            <span className="w-40 shrink-0 text-stone-500">{k.replaceAll("_", " ")}</span>
            <span className="text-stone-700">{String(v)}</span>
          </div>
        ))}
      </div>
    );
  return null;
}

export function ArtifactView({ artifact }: { artifact: ApiArtifact }) {
  return (
    <div>
      <div className="rounded-xl border border-stone-200 bg-stone-100 px-4 py-3 mb-6 flex flex-wrap gap-x-5 gap-y-1 text-xs text-stone-500">
        <span>
          Produced by <span className="text-stone-800">{artifact.agent_slug}</span>
        </span>
        <span>
          model <span className="text-stone-800">{artifact.model_used || "n/a"}</span>
        </span>
        <span>
          cost <span className="text-stone-800">${artifact.cost_usd.toFixed(2)}</span>
        </span>
        <span>v{artifact.version}</span>
        <span>{new Date(artifact.created_at).toLocaleString()}</span>
        <span className="capitalize">{artifact.review_status}</span>
      </div>
      <div className="space-y-6">
        {Object.entries(artifact.content).map(([key, value]) => (
          <section key={key}>
            <h3 className="text-xs uppercase tracking-wide text-stone-500 mb-2">
              {key.replaceAll("_", " ")}
            </h3>
            <Value value={value} />
          </section>
        ))}
      </div>
    </div>
  );
}
