"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { api, type FeasibilityReport, type Stage } from "@/lib/api";

const verdictStyles: Record<string, { chip: string; label: string }> = {
  kill: { chip: "bg-rose-50 text-rose-700 border-rose-200", label: "Not worth pursuing on current evidence" },
  park: { chip: "bg-stone-100 text-stone-600 border-stone-200", label: "Interesting, but not ready" },
  research: { chip: "bg-sky-50 text-sky-700 border-sky-200", label: "More information needed first" },
  validate: { chip: "bg-amber-50 text-amber-700 border-amber-200", label: "Test demand before building" },
  prototype: { chip: "bg-violet-50 text-violet-700 border-violet-200", label: "Build a lightweight demo" },
  build: { chip: "bg-emerald-50 text-emerald-700 border-emerald-200", label: "Create a proper MVP plan" },
};

const stageLabels: Record<string, string> = {
  evaluate: "Evaluate",
  validate: "Validate",
  prototype_plan: "Prototype plan",
  build_plan: "Build plan",
  monthly_after_launch: "Monthly after launch",
};

function confidenceLabel(confidence: number): string {
  if (confidence >= 75) return "high";
  if (confidence >= 50) return "moderate";
  return "low";
}

export default function ReportPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [report, setReport] = useState<FeasibilityReport | null>(null);
  const [error, setError] = useState<"none" | "not_found" | "other">("none");
  const [openScore, setOpenScore] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [projectName, setProjectName] = useState("");

  const load = useCallback(() => {
    setError("none");
    api
      .getReport(id)
      .then(setReport)
      .catch((e) => {
        const message = e instanceof Error ? e.message : String(e);
        setError(message.startsWith("404") ? "not_found" : "other");
      });
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    api
      .getProject(id)
      .then((p) => setProjectName(p.name))
      .catch(() => {});
  }, [id]);

  if (error === "not_found")
    return (
      <div className="max-w-2xl mx-auto px-6 py-10">
        <p className="text-sm text-stone-600">
          No report yet. Run an evaluation from the intake page first.
        </p>
        <Link
          href="/intake"
          className="mt-4 inline-block rounded-lg bg-stone-900 px-4 py-2 text-xs font-medium text-white hover:bg-stone-700"
        >
          Start with an idea
        </Link>
      </div>
    );
  if (error === "other")
    return (
      <div className="max-w-2xl mx-auto px-6 py-10">
        <p className="text-sm text-stone-600">
          We couldn&apos;t load the report just now. It may be waking up — try again in a minute.
        </p>
        <button
          onClick={load}
          className="mt-4 rounded-lg bg-stone-900 px-4 py-2 text-xs font-medium text-white hover:bg-stone-700"
        >
          Try again
        </button>
      </div>
    );
  if (!report)
    return (
      <div className="max-w-2xl mx-auto px-6 py-10 text-sm text-stone-500">Loading report…</div>
    );

  const v = verdictStyles[report.verdict];
  const weighted = report.scores.reduce((acc, s) => acc + (s.score * s.weight) / 10, 0);

  const shareVerdict = async () => {
    const lowestScore = [...report.scores].sort((a, b) => a.score - b.score)[0];
    const topRisk = report.do_not_build[0] ?? lowestScore?.reasoning ?? "none identified";
    // Mint (or reuse) the public share page so the copied text carries a real
    // link with an OG card, not just the homepage.
    let link = window.location.origin;
    try {
      const share = await api.shareReport(id);
      link = `${window.location.origin}${share.path}`;
    } catch {
      // Share endpoint unavailable — fall back to the homepage link.
    }
    const text = `Verdict on '${projectName || "my idea"}': ${report.verdict.toUpperCase()} (confidence: ${confidenceLabel(report.confidence)}). Weighted ${Math.round(weighted)}/100. Top risk: ${topRisk}. Full verdict: ${link}`;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard unavailable (permissions/insecure context) — leave button state unchanged.
    }
  };

  return (
    <div className="max-w-3xl mx-auto px-6 py-10">
      <div className="flex items-center gap-3 mb-1">
        <h1 className="text-2xl font-semibold text-stone-900 capitalize">
          Verdict: {report.verdict}
        </h1>
        <span
          className={`rounded-full border px-3 py-0.5 text-xs ${v.chip}`}
          title={`Model-reported confidence: ${report.confidence}%`}
        >
          confidence: {confidenceLabel(report.confidence)}
        </span>
        <button
          onClick={shareVerdict}
          className="ml-auto rounded-lg border border-stone-300 px-3 py-1.5 text-xs text-stone-600 hover:border-stone-500"
        >
          {copied ? "Copied" : "Share this verdict"}
        </button>
      </div>
      <p className="text-sm text-stone-500 mb-6">
        {v.label} · weighted score {Math.round(weighted)}/100 · report v{report.version} · produced
        by the Feasibility Analyst
      </p>

      <div className="rounded-xl border border-stone-200 bg-white p-4 mb-6">
        <div className="text-xs uppercase tracking-wide text-stone-500 mb-1.5">
          The honest story
        </div>
        <p className="text-sm text-stone-700 leading-relaxed">{report.reasoning}</p>
      </div>

      <h2 className="text-sm font-semibold text-stone-900 mb-2">
        Rubric scores <span className="text-stone-500 font-normal">(click a row for reasoning)</span>
      </h2>
      <div className="rounded-xl border border-stone-200 bg-white divide-y divide-stone-100 mb-6">
        {report.scores.map((s) => (
          <button
            key={s.category}
            onClick={() => setOpenScore(openScore === s.category ? null : s.category)}
            className="w-full px-4 py-2.5 text-left hover:bg-stone-50"
          >
            <div className="flex items-center gap-3">
              <span className="w-44 text-xs text-stone-600 capitalize">
                {s.category.replaceAll("_", " ")}
              </span>
              <div className="flex-1 h-1.5 rounded bg-stone-100">
                <div
                  className={`h-1.5 rounded ${s.score >= 7 ? "bg-emerald-500" : s.score >= 4 ? "bg-amber-500" : "bg-rose-500"}`}
                  style={{ width: `${s.score * 10}%` }}
                />
              </div>
              <span className="w-14 text-right text-xs text-stone-500">
                {s.score}/10 · w{s.weight}
              </span>
            </div>
            {openScore === s.category && (
              <p className="mt-2 text-xs text-stone-500">{s.reasoning}</p>
            )}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-4 mb-6">
        <ListCard title="Recommended MVP scope" items={report.mvp_scope} tone="positive" />
        <ListCard title="Do not build yet" items={report.do_not_build} tone="negative" />
        <ListCard title="What must be true" items={report.assumptions} />
        <ListCard title="Cheapest validation tests" items={report.validation_plan} ordered />
      </div>

      <h2 className="text-sm font-semibold text-stone-900 mb-2">AI cost forecast</h2>
      <div className="rounded-xl border border-stone-200 bg-white p-4 mb-2">
        <div className="grid grid-cols-5 gap-2">
          {Object.entries(report.cost_estimate.stages).map(([stage, r]) => (
            <div key={stage} className="rounded-lg bg-stone-50 p-2.5">
              <div className="text-xs text-stone-500">{stageLabels[stage] ?? stage}</div>
              <div className="text-xs font-medium text-stone-800 mt-0.5">
                ${r.low_usd}–${r.high_usd}
              </div>
            </div>
          ))}
        </div>
      </div>
      <p className="text-xs text-stone-500 mb-1">{report.cost_estimate.method}</p>
      <p className="text-xs text-stone-500 mb-8">
        Estimates from a deterministic model — treat as ranges, not promises.
      </p>

      <div className="rounded-xl border border-stone-200 bg-white p-4">
        <div className="text-sm font-semibold text-stone-900 mb-1">Your decision</div>
        <p className="text-xs text-stone-500 mb-3">
          Nothing proceeds without you. Approving a stage creates a proposed agent team you
          review before any further spend.
        </p>
        <div className="flex flex-wrap gap-2">
          {(["kill", "park", "research", "validate", "prototype", "build"] as Stage[]).map((d) => (
            <button
              key={d}
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  await api.setStage(id, d);
                  router.push(`/projects/${id}`);
                } finally {
                  setBusy(false);
                }
              }}
              className={`rounded-lg px-3.5 py-1.5 text-xs capitalize border disabled:opacity-40 ${
                d === report.verdict
                  ? "bg-stone-900 text-white border-stone-900"
                  : "border-stone-300 text-stone-600 hover:border-stone-500"
              }`}
            >
              {d}
              {d === report.verdict && " (recommended)"}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function ListCard({
  title,
  items,
  tone,
  ordered,
}: {
  title: string;
  items: string[];
  tone?: "positive" | "negative";
  ordered?: boolean;
}) {
  const mark = tone === "positive" ? "text-emerald-600" : tone === "negative" ? "text-rose-500" : "text-stone-400";
  return (
    <div className="rounded-xl border border-stone-200 bg-white p-4">
      <div className="text-xs uppercase tracking-wide text-stone-500 mb-2">{title}</div>
      <ul className="space-y-1.5">
        {items.map((item, i) => (
          <li key={item} className="flex gap-2 text-xs text-stone-700">
            <span className={mark}>{ordered ? `${i + 1}.` : "·"}</span>
            <span>{item}</span>
          </li>
        ))}
        {items.length === 0 && <li className="text-xs text-stone-500">None listed.</li>}
      </ul>
    </div>
  );
}
