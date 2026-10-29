"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  api,
  errorDetail,
  type ModelCatalog,
  type ModelProfile,
  type ModelProfileIn,
  type ModelTier,
  type ProviderKind,
} from "@/lib/api";

const PROVIDERS: { kind: ProviderKind; label: string }[] = [
  { kind: "local", label: "Local server (Ollama, LM Studio, vLLM…)" },
  { kind: "claude_code", label: "Claude subscription (Claude Code CLI)" },
  { kind: "codex", label: "ChatGPT subscription (Codex CLI)" },
  { kind: "anthropic", label: "Anthropic API" },
  { kind: "openai", label: "OpenAI API" },
  { kind: "gemini", label: "Gemini API" },
];

const ACCESS_CHIP: Record<string, string> = {
  local: "bg-emerald-50 text-emerald-700",
  subscription: "bg-violet-50 text-violet-700",
  api: "bg-sky-50 text-sky-700",
};

const TIER_LABEL: Record<ModelTier, string> = {
  high: "Frontier: can supervise high-risk work",
  cheap: "Cheap",
  local: "Local",
};

const field =
  "w-full rounded-lg border border-stone-300 bg-white px-2.5 py-1.5 text-xs text-stone-800 focus:border-stone-500 focus:outline-none";

const EMPTY: ModelProfileIn = { name: "", provider: "local", model: "", base_url: "" };

export default function ModelsPage() {
  const [catalog, setCatalog] = useState<ModelCatalog | null>(null);
  const [profiles, setProfiles] = useState<ModelProfile[]>([]);
  const [form, setForm] = useState<ModelProfileIn>(EMPTY);
  const [editing, setEditing] = useState<string | null>(null);
  const [installed, setInstalled] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  const load = useCallback(async () => {
    try {
      const [c, p] = await Promise.all([api.modelCatalog(), api.listModelProfiles()]);
      setCatalog(c);
      setProfiles(p);
    } catch (e) {
      setMessage({ ok: false, text: errorDetail(e, "Could not reach the API.") });
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const access = catalog?.providers[form.provider]?.access ?? "api";
  const suggestions = useMemo(() => {
    if (!catalog) return [];
    const fromCatalog =
      form.provider === "local"
        ? installed
        : catalog.api_models.filter((m) => m.provider === form.provider).map((m) => m.model);
    const fromSuggested = catalog.suggested
      .filter((s) => s.provider === form.provider)
      .map((s) => s.model);
    return [...new Set([...fromCatalog, ...fromSuggested])];
  }, [catalog, form.provider, installed]);

  function set<K extends keyof ModelProfileIn>(key: K, value: ModelProfileIn[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function discover() {
    setBusy(true);
    setMessage(null);
    try {
      const res = await api.discoverLocalModels(form.base_url || catalog?.local_base_url || "");
      setInstalled(res.models);
      setMessage({ ok: true, text: `Found ${res.models.length} installed model(s).` });
    } catch (e) {
      setMessage({ ok: false, text: errorDetail(e, "Could not reach that server.") });
    } finally {
      setBusy(false);
    }
  }

  async function save() {
    setBusy(true);
    setMessage(null);
    const body: ModelProfileIn = { ...form };
    if (access !== "api") {
      delete body.price_in;
      delete body.price_out;
    }
    try {
      if (editing) await api.updateModelProfile(editing, body);
      else await api.createModelProfile(body);
      setForm(EMPTY);
      setEditing(null);
      setMessage({ ok: true, text: "Saved." });
      await load();
    } catch (e) {
      setMessage({ ok: false, text: errorDetail(e, "Could not save this model.") });
    } finally {
      setBusy(false);
    }
  }

  async function remove(p: ModelProfile) {
    setBusy(true);
    setMessage(null);
    try {
      await api.deleteModelProfile(p.id);
      await load();
    } catch (e) {
      setMessage({ ok: false, text: errorDetail(e, "Could not delete this model.") });
    } finally {
      setBusy(false);
    }
  }

  function edit(p: ModelProfile) {
    setEditing(p.id);
    setForm({
      name: p.name,
      provider: p.provider,
      model: p.model,
      base_url: p.base_url,
      tier: p.tier,
      price_in: p.price_in,
      price_out: p.price_out,
    });
  }

  return (
    <div className="max-w-4xl mx-auto px-6 py-8 space-y-6">
      <div>
        <h1 className="text-lg font-semibold text-stone-900">Models</h1>
        <p className="mt-1 text-sm text-stone-500 max-w-2xl">
          Choose which models your agents can use. Put the high-volume worker agents on local
          models with no per-token cost or rate limit, and keep frontier models (subscription or
          API) for the supervisors who review their work.
        </p>
      </div>

      {catalog?.demo_mode && (
        <div className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-xs text-amber-800">
          Demo mode: every call returns canned output. To go live, set LOCAL_LLM_BASE_URL, an API
          key, or CLAUDE_CODE_ENABLED / CODEX_ENABLED on the API server.
        </div>
      )}

      <section className="rounded-xl border border-stone-200 bg-white">
        <h2 className="px-4 py-3 border-b border-stone-200 text-xs uppercase tracking-wide text-stone-500">
          Your models
        </h2>
        {profiles.length === 0 ? (
          <p className="px-4 py-4 text-xs text-stone-500">
            None yet. Agents use the built-in routing table until you add one.
          </p>
        ) : (
          <table className="w-full text-xs">
            <thead className="text-left text-stone-500">
              <tr>
                <th className="px-4 py-2 font-normal">Name</th>
                <th className="px-4 py-2 font-normal">Access</th>
                <th className="px-4 py-2 font-normal">Model</th>
                <th className="px-4 py-2 font-normal">Tier</th>
                <th className="px-4 py-2 font-normal">Price / 1M (in, out)</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody>
              {profiles.map((p) => (
                <tr key={p.id} className="border-t border-stone-100">
                  <td className="px-4 py-2 text-stone-900">{p.name}</td>
                  <td className="px-4 py-2">
                    <span className={`rounded-full px-2 py-0.5 ${ACCESS_CHIP[p.access]}`}>
                      {p.access}
                    </span>
                  </td>
                  <td className="px-4 py-2 font-mono text-stone-700">{p.model}</td>
                  <td className="px-4 py-2 text-stone-600">{p.tier}</td>
                  <td className="px-4 py-2 text-stone-600">
                    {p.access === "api" ? `$${p.price_in} / $${p.price_out}` : "free"}
                  </td>
                  <td className="px-4 py-2 text-right whitespace-nowrap">
                    <button onClick={() => edit(p)} className="text-stone-500 hover:text-stone-900">
                      Edit
                    </button>
                    <button
                      onClick={() => remove(p)}
                      disabled={busy}
                      className="ml-3 text-rose-600 hover:text-rose-800 disabled:opacity-40"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="rounded-xl border border-stone-200 bg-white p-4 space-y-3">
        <h2 className="text-xs uppercase tracking-wide text-stone-500">
          {editing ? "Edit model" : "Add a model"}
        </h2>
        {catalog && !editing && (
          <div className="flex flex-wrap gap-1.5">
            {catalog.suggested
              .filter((s) => catalog.providers[s.provider]?.enabled)
              .map((s) => (
                <button
                  key={s.name}
                  onClick={() =>
                    setForm({
                      ...EMPTY,
                      ...s,
                      base_url: s.provider === "local" ? catalog.local_base_url : "",
                    })
                  }
                  className="rounded-full border border-stone-300 px-2.5 py-1 text-xs text-stone-600 hover:border-stone-500"
                >
                  + {s.name}
                </button>
              ))}
          </div>
        )}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <label className="block">
            <span className="text-xs text-stone-600">How it&apos;s reached</span>
            <select
              value={form.provider}
              onChange={(e) => {
                set("provider", e.target.value as ProviderKind);
                setInstalled([]);
              }}
              className={`${field} mt-1`}
            >
              {PROVIDERS.map((p) => {
                const status = catalog?.providers[p.kind];
                return (
                  <option key={p.kind} value={p.kind} disabled={status ? !status.enabled : false}>
                    {p.label}
                    {status && !status.enabled ? " (unavailable)" : ""}
                  </option>
                );
              })}
            </select>
            {catalog && !catalog.providers[form.provider]?.enabled && (
              <span className="mt-1 block text-xs text-amber-700">
                {catalog.providers[form.provider]?.reason}
              </span>
            )}
          </label>
          <label className="block">
            <span className="text-xs text-stone-600">Display name</span>
            <input
              value={form.name}
              onChange={(e) => set("name", e.target.value)}
              placeholder="e.g. Qwen3 32B on my GPU"
              className={`${field} mt-1`}
            />
          </label>
          <label className="block">
            <span className="text-xs text-stone-600">Model</span>
            <input
              value={form.model}
              onChange={(e) => set("model", e.target.value)}
              list="model-suggestions"
              placeholder={form.provider === "local" ? "qwen3:32b" : "model id"}
              className={`${field} mt-1 font-mono`}
            />
            <datalist id="model-suggestions">
              {suggestions.map((m) => (
                <option key={m} value={m} />
              ))}
            </datalist>
          </label>
          <label className="block">
            <span className="text-xs text-stone-600">Tier</span>
            <select
              value={form.tier ?? ""}
              onChange={(e) => set("tier", (e.target.value || undefined) as ModelTier | undefined)}
              className={`${field} mt-1`}
            >
              <option value="">Automatic</option>
              {(Object.keys(TIER_LABEL) as ModelTier[]).map((t) => (
                <option key={t} value={t}>
                  {TIER_LABEL[t]}
                </option>
              ))}
            </select>
          </label>
          {form.provider === "local" && (
            <label className="block sm:col-span-2">
              <span className="text-xs text-stone-600">Server URL (OpenAI-compatible)</span>
              <div className="mt-1 flex gap-2">
                <input
                  value={form.base_url ?? ""}
                  onChange={(e) => set("base_url", e.target.value)}
                  placeholder={catalog?.local_base_url || "http://localhost:11434/v1"}
                  className={`${field} font-mono`}
                />
                <button
                  onClick={discover}
                  disabled={busy}
                  className="shrink-0 rounded-lg border border-stone-300 px-3 text-xs text-stone-600 hover:border-stone-500 disabled:opacity-40"
                >
                  Find installed models
                </button>
              </div>
            </label>
          )}
          {access === "api" && (
            <>
              <label className="block">
                <span className="text-xs text-stone-600">Input price, USD per 1M tokens</span>
                <input
                  type="number"
                  min={0}
                  step="0.01"
                  value={form.price_in ?? ""}
                  onChange={(e) =>
                    set("price_in", e.target.value === "" ? undefined : Number(e.target.value))
                  }
                  placeholder="from catalog"
                  className={`${field} mt-1`}
                />
              </label>
              <label className="block">
                <span className="text-xs text-stone-600">Output price, USD per 1M tokens</span>
                <input
                  type="number"
                  min={0}
                  step="0.01"
                  value={form.price_out ?? ""}
                  onChange={(e) =>
                    set("price_out", e.target.value === "" ? undefined : Number(e.target.value))
                  }
                  placeholder="from catalog"
                  className={`${field} mt-1`}
                />
              </label>
            </>
          )}
        </div>
        {access === "subscription" && (
          <p className="text-xs text-stone-500">
            Runs through the official CLI on the API server, using the plan it&apos;s logged into.
            No per-token charge, but plan rate limits apply, so use subscriptions for supervisors,
            not workers. Keep this for your own self-hosted install.
          </p>
        )}
        <div className="flex items-center gap-2">
          <button
            onClick={save}
            disabled={busy || !form.name || !form.model}
            className="rounded-lg bg-stone-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-stone-700 disabled:opacity-40"
          >
            {editing ? "Save changes" : "Add model"}
          </button>
          {editing && (
            <button
              onClick={() => {
                setEditing(null);
                setForm(EMPTY);
              }}
              className="rounded-lg border border-stone-300 px-3 py-1.5 text-xs text-stone-600 hover:border-stone-500"
            >
              Cancel
            </button>
          )}
          {message && (
            <span className={`text-xs ${message.ok ? "text-emerald-600" : "text-rose-600"}`}>
              {message.text}
            </span>
          )}
        </div>
      </section>
    </div>
  );
}
