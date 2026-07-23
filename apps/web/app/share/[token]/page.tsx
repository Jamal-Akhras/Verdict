import Link from "next/link";
import type { Metadata } from "next";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface SharedScore {
  category: string;
  score: number;
  weight: number;
  reasoning: string;
}

interface SharedVerdict {
  project_name: string;
  verdict: string;
  confidence: number;
  scores: SharedScore[];
  reasoning: string;
  mvp_scope: string[];
  do_not_build: string[];
  created_at: string;
}

async function getShared(token: string): Promise<SharedVerdict | null> {
  try {
    const res = await fetch(`${API_URL}/share/${token}`, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as SharedVerdict;
  } catch {
    return null;
  }
}

function confidenceLabel(c: number): string {
  return c >= 75 ? "high" : c >= 50 ? "moderate" : "low";
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ token: string }>;
}): Promise<Metadata> {
  const { token } = await params;
  const data = await getShared(token);
  if (!data) return { title: "Verdict" };
  return {
    title: `${data.verdict.toUpperCase()} — ${data.project_name} · Verdict`,
    description: data.reasoning.slice(0, 160),
  };
}

export default async function SharePage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  const data = await getShared(token);

  if (!data) {
    return (
      <div className="max-w-xl mx-auto px-6 py-20 text-center">
        <p className="text-sm text-stone-600">This shared verdict doesn&apos;t exist or was revoked.</p>
        <Link
          href="/intake"
          className="mt-4 inline-block rounded-lg bg-stone-900 px-4 py-2 text-sm font-medium text-white hover:bg-stone-700"
        >
          Get your own verdict — free
        </Link>
      </div>
    );
  }

  const weighted = data.scores.reduce((acc, s) => acc + (s.score * s.weight) / 10, 0);

  return (
    <div className="max-w-2xl mx-auto px-6 py-12">
      <p className="text-xs uppercase tracking-wide text-stone-500 mb-3">
        Verdict · shared feasibility report
      </p>
      <h1 className="text-3xl font-semibold text-stone-900 capitalize">
        {data.verdict}
        <span className="text-stone-400 font-normal text-xl"> — {data.project_name}</span>
      </h1>
      <p className="mt-1 text-sm text-stone-500">
        Confidence: {confidenceLabel(data.confidence)} · weighted score {Math.round(weighted)}/100 ·{" "}
        {new Date(data.created_at).toLocaleDateString()}
      </p>

      <div className="mt-6 rounded-xl border border-stone-200 bg-white p-5">
        <div className="text-xs uppercase tracking-wide text-stone-500 mb-2">The honest story</div>
        <p className="text-sm text-stone-700 leading-relaxed">{data.reasoning}</p>
      </div>

      <div className="mt-4 rounded-xl border border-stone-200 bg-white p-5">
        <div className="text-xs uppercase tracking-wide text-stone-500 mb-3">Scores</div>
        {data.scores.map((s) => (
          <div key={s.category} className="flex items-center gap-3 py-1.5">
            <span className="w-44 text-xs text-stone-600 capitalize">
              {s.category.replaceAll("_", " ")}
            </span>
            <div className="flex-1 h-1.5 rounded bg-stone-100">
              <div
                className={`h-1.5 rounded ${
                  s.score >= 7 ? "bg-emerald-500" : s.score >= 4 ? "bg-amber-500" : "bg-rose-500"
                }`}
                style={{ width: `${s.score * 10}%` }}
              />
            </div>
            <span className="w-10 text-right text-xs text-stone-500">{s.score}/10</span>
          </div>
        ))}
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <div className="rounded-xl border border-stone-200 bg-white p-5">
          <div className="text-xs uppercase tracking-wide text-stone-500 mb-2">
            Recommended scope
          </div>
          <ul className="space-y-1.5">
            {data.mvp_scope.map((item) => (
              <li key={item} className="flex gap-2 text-xs text-stone-700">
                <span className="text-emerald-600">·</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="rounded-xl border border-stone-200 bg-white p-5">
          <div className="text-xs uppercase tracking-wide text-stone-500 mb-2">
            Do not build yet
          </div>
          <ul className="space-y-1.5">
            {data.do_not_build.map((item) => (
              <li key={item} className="flex gap-2 text-xs text-stone-700">
                <span className="text-rose-500">·</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="mt-8 rounded-xl border border-stone-200 bg-stone-50 p-6 text-center">
        <p className="text-sm text-stone-700 font-medium">
          Wondering if your idea is worth building?
        </p>
        <p className="mt-1 text-xs text-stone-500">
          Verdict scores it honestly — kill and park are real answers here.
        </p>
        <Link
          href="/intake"
          className="mt-4 inline-block rounded-lg bg-stone-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-stone-700"
        >
          Get your own verdict — free
        </Link>
      </div>
    </div>
  );
}
