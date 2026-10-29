"use client";
import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import {
  api,
  type ApiAgent,
  type ApiFlag,
  type ApiTask,
  type Trace,
  type TraceCall,
  type TraceReview,
} from "@/lib/api";

const ROLE_CHIP: Record<string, string> = {
  work: "bg-stone-100 text-stone-700",
  review: "bg-sky-50 text-sky-700",
  triage: "bg-violet-50 text-violet-700",
};

const DECISION_CHIP: Record<string, string> = {
  accept: "bg-emerald-50 text-emerald-700",
  revise: "bg-amber-50 text-amber-700",
  escalate: "bg-rose-50 text-rose-700",
  resolved: "bg-emerald-50 text-emerald-700",
  raised: "bg-amber-50 text-amber-700",
  approved: "bg-emerald-50 text-emerald-700",
  denied: "bg-rose-50 text-rose-700",
  revised: "bg-sky-50 text-sky-700",
  open: "bg-stone-100 text-stone-600",
};

type Entry =
  | { kind: "call"; at: string; call: TraceCall }
  | { kind: "review"; at: string; review: TraceReview }
  | { kind: "flag"; at: string; flag: ApiFlag };

function Prompt({ label, text }: { label: string; text: string }) {
  return (
    <details className="mt-1.5">
      <summary className="cursor-pointer text-xs text-stone-500 hover:text-stone-800">
        {label} <span className="text-stone-400">({text.length.toLocaleString()} chars)</span>
      </summary>
      <pre className="mt-1 max-h-96 overflow-auto whitespace-pre-wrap rounded-lg bg-stone-50 p-2.5 font-mono text-xs text-stone-700">
        {text}
      </pre>
    </details>
  );
}

function CallRow({ call, agentName }: { call: TraceCall; agentName: string }) {
  return (
    <div className="rounded-xl border border-stone-200 bg-white p-3">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className={`rounded-full px-2 py-0.5 ${ROLE_CHIP[call.call_role] ?? ROLE_CHIP.work}`}>
          {call.call_role}
        </span>
        <span className="font-medium text-stone-900">{agentName}</span>
        <span className="font-mono text-stone-600">
          {call.provider}/{call.model}
        </span>
        {!call.parse_ok && (
          <span className="rounded-full bg-rose-50 px-2 py-0.5 text-rose-700">invalid output</span>
        )}
        <span className="ml-auto text-stone-500">
          {call.tokens_in.toLocaleString()} in · {call.tokens_out.toLocaleString()} out ·{" "}
          {(call.latency_ms / 1000).toFixed(1)}s ·{" "}
          {call.cost_usd > 0 ? `$${call.cost_usd.toFixed(4)}` : "free"}
        </span>
      </div>
      <Prompt label="System prompt" text={call.system_prompt} />
      <Prompt label="User prompt" text={call.user_prompt} />
      <Prompt label="Response" text={call.response_text} />
      <Prompt label="Why this model" text={JSON.stringify(call.router_decision, null, 2)} />
    </div>
  );
}

function ReviewRow({ review, name }: { review: TraceReview; name: (id: string) => string }) {
  return (
    <div className="rounded-xl border border-sky-200 bg-sky-50/40 p-3 text-xs">
      <div className="flex flex-wrap items-center gap-2">
        <span className={`rounded-full px-2 py-0.5 ${DECISION_CHIP[review.decision]}`}>
          {review.decision}
        </span>
        <span className="font-medium text-stone-900">{name(review.reviewer_agent_id)}</span>
        <span className="text-stone-500">
          reviewed {name(review.worker_agent_id)}&apos;s draft #{review.attempt}
        </span>
      </div>
      <p className="mt-1.5 text-stone-700">{review.summary}</p>
      {review.feedback && (
        <p className="mt-1.5 whitespace-pre-wrap text-stone-600">
          <span className="font-medium text-stone-800">Feedback: </span>
          {review.feedback}
        </p>
      )}
      {review.issues.length > 0 && (
        <ul className="mt-1.5 space-y-0.5 text-stone-600">
          {review.issues.map((i, n) => (
            <li key={n}>
              · <span className="text-stone-500">[{i.severity}]</span> {i.issue}
              {i.where && <span className="text-stone-400"> ({i.where})</span>}
            </li>
          ))}
        </ul>
      )}
      <Prompt label="The draft it reviewed" text={JSON.stringify(review.reviewed_output, null, 2)} />
    </div>
  );
}

function FlagRow({ flag }: { flag: ApiFlag }) {
  return (
    <div className="rounded-xl border border-amber-300 bg-amber-50/40 p-3 text-xs">
      <div className="flex flex-wrap items-center gap-2">
        <span className={`rounded-full px-2 py-0.5 ${DECISION_CHIP[flag.status]}`}>
          {flag.status === "raised" ? "on your desk" : flag.status}
        </span>
        <span className="font-medium text-stone-900">{flag.title}</span>
        <span className="text-stone-500">severity {flag.severity}</span>
      </div>
      <p className="mt-1.5 whitespace-pre-wrap text-stone-700">{flag.detail}</p>
      <ol className="mt-2 space-y-1 border-l border-amber-300 pl-2.5">
        {flag.chain.map((h, i) => (
          <li key={i}>
            <span className="font-medium text-stone-800">{h.agent_name}</span>{" "}
            <span className="text-stone-500">
              {h.decision} · {h.model}
            </span>
            {h.rationale && <p className="text-stone-600">{h.rationale}</p>}
          </li>
        ))}
      </ol>
      {flag.resolution && (
        <p className="mt-1.5 text-stone-700">
          <span className="font-medium">Resolution: </span>
          {flag.resolution}
        </p>
      )}
    </div>
  );
}

function TraceView() {
  const { id } = useParams<{ id: string }>();
  const params = useSearchParams();
  const [trace, setTrace] = useState<Trace | null>(null);
  const [tasks, setTasks] = useState<ApiTask[]>([]);
  const [agents, setAgents] = useState<ApiAgent[]>([]);
  const [agentFilter, setAgentFilter] = useState(params.get("agent") ?? "all");
  const [roleFilter, setRoleFilter] = useState("all");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.trace(id), api.listTasks(id), api.listAgents(id)])
      .then(([t, ts, as]) => {
        setTrace(t);
        setTasks(ts);
        setAgents(as);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load the trace"));
  }, [id]);

  const byId = useMemo(() => new Map(agents.map((a) => [a.id, a])), [agents]);
  const bySlug = useMemo(() => new Map(agents.map((a) => [a.slug, a])), [agents]);
  const name = (agentId: string) => byId.get(agentId)?.name ?? "unknown agent";

  const stats = useMemo(() => {
    const calls = trace?.calls ?? [];
    const out = (role: string) =>
      calls.filter((c) => c.call_role === role).reduce((s, c) => s + c.tokens_out, 0);
    const freeOut = calls.filter((c) => c.cost_usd === 0).reduce((s, c) => s + c.tokens_out, 0);
    const allOut = calls.reduce((s, c) => s + c.tokens_out, 0);
    return {
      calls: calls.length,
      cost: calls.reduce((s, c) => s + c.cost_usd, 0),
      workOut: out("work"),
      reviewOut: out("review") + out("triage"),
      freeShare: allOut ? Math.round((freeOut / allOut) * 100) : 0,
    };
  }, [trace]);

  const groups = useMemo(() => {
    if (!trace) return [];
    const keep = (slug: string | null | undefined, agentId?: string) => {
      if (agentFilter === "all") return true;
      const target = bySlug.get(agentFilter);
      return slug === agentFilter || (target !== undefined && agentId === target.id);
    };
    const entries: (Entry & { task: string | null })[] = [
      ...trace.calls
        .filter((c) => roleFilter === "all" || c.call_role === roleFilter)
        .map((c) => ({ kind: "call" as const, at: c.created_at, call: c, task: c.task_id })),
      ...(roleFilter === "all" || roleFilter === "review"
        ? trace.reviews.map((r) => ({
            kind: "review" as const,
            at: r.created_at,
            review: r,
            task: r.task_id,
          }))
        : []),
      ...(roleFilter === "all" || roleFilter === "triage"
        ? trace.flags.map((f) => ({ kind: "flag" as const, at: f.created_at, flag: f, task: f.task_id }))
        : []),
    ];
    // Filtering by agent keeps the whole task thread that agent touched.
    const touched = new Set(
      entries
        .filter((e) =>
          e.kind === "call"
            ? keep(e.call.agent_slug)
            : e.kind === "review"
              ? keep(null, e.review.worker_agent_id) || keep(null, e.review.reviewer_agent_id)
              : keep(null, e.flag.raised_by_agent_id)
        )
        .map((e) => e.task)
    );
    const order = [null, ...tasks.map((t) => t.id)];
    return order
      .filter((tid) => touched.has(tid))
      .map((tid) => ({
        task: tasks.find((t) => t.id === tid) ?? null,
        entries: entries.filter((e) => e.task === tid).sort((a, b) => a.at.localeCompare(b.at)),
      }))
      .filter((g) => g.entries.length > 0);
  }, [trace, tasks, agentFilter, roleFilter, bySlug]);

  if (error)
    return <div className="max-w-4xl mx-auto px-6 py-10 text-sm text-rose-700">{error}</div>;
  if (!trace)
    return <div className="max-w-4xl mx-auto px-6 py-10 text-sm text-stone-500">Loading…</div>;

  return (
    <div className="max-w-5xl mx-auto px-6 py-8 space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <Link href={`/projects/${id}`} className="text-xs text-stone-500 hover:text-stone-900">
            ← Back to project
          </Link>
          <h1 className="mt-1 text-lg font-semibold text-stone-900">Trace</h1>
          <p className="text-sm text-stone-500">
            Every prompt, response, review, and escalation, in order. Nothing is summarised away.
          </p>
        </div>
        <div className="flex gap-2">
          <select
            value={agentFilter}
            onChange={(e) => setAgentFilter(e.target.value)}
            aria-label="Filter by agent"
            className="rounded-lg border border-stone-300 bg-white px-2.5 py-1.5 text-xs"
          >
            <option value="all">All agents</option>
            {agents.map((a) => (
              <option key={a.id} value={a.slug}>
                {a.name}
              </option>
            ))}
          </select>
          <select
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value)}
            aria-label="Filter by role"
            className="rounded-lg border border-stone-300 bg-white px-2.5 py-1.5 text-xs"
          >
            <option value="all">All activity</option>
            <option value="work">Drafting</option>
            <option value="review">Reviews</option>
            <option value="triage">Escalations</option>
          </select>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          ["Model calls", stats.calls.toLocaleString()],
          ["Spend", `$${stats.cost.toFixed(4)}`],
          ["Tokens written: drafts / reviews", `${stats.workOut.toLocaleString()} / ${stats.reviewOut.toLocaleString()}`],
          ["Output on $0 models", `${stats.freeShare}%`],
        ].map(([label, value]) => (
          <div key={label} className="rounded-xl border border-stone-200 bg-white p-3">
            <div className="text-xs text-stone-500">{label}</div>
            <div className="mt-1 text-sm font-semibold text-stone-900">{value}</div>
          </div>
        ))}
      </div>

      {groups.length === 0 && (
        <p className="text-sm text-stone-500">No activity yet. Start a run to see the trace.</p>
      )}
      {groups.map((g) => (
        <section key={g.task?.id ?? "project"} className="space-y-2">
          <h2 className="text-xs uppercase tracking-wide text-stone-500">
            {g.task ? `${g.task.title} · ${g.task.status}` : "Intake & feasibility"}
          </h2>
          {g.entries.map((e) =>
            e.kind === "call" ? (
              <CallRow
                key={e.call.id}
                call={e.call}
                agentName={bySlug.get(e.call.agent_slug ?? "")?.name ?? e.call.agent_slug ?? "system"}
              />
            ) : e.kind === "review" ? (
              <ReviewRow key={e.review.id} review={e.review} name={name} />
            ) : (
              <FlagRow key={e.flag.id} flag={e.flag} />
            )
          )}
        </section>
      ))}
    </div>
  );
}

export default function TracePage() {
  return (
    <Suspense
      fallback={<div className="max-w-4xl mx-auto px-6 py-10 text-sm text-stone-500">Loading…</div>}
    >
      <TraceView />
    </Suspense>
  );
}
