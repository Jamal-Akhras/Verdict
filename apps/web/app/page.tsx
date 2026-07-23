"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api, type ApiProject } from "@/lib/api";

export default function Dashboard() {
  const [projects, setProjects] = useState<ApiProject[] | null>(null);
  const [apiDown, setApiDown] = useState(false);

  useEffect(() => {
    api.listProjects().then(setProjects).catch(() => setApiDown(true));
  }, []);

  return (
    <div className="max-w-4xl mx-auto px-6 py-10">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold text-stone-900">Your projects</h1>
        <Link
          href="/intake"
          className="rounded-lg bg-stone-900 hover:bg-stone-700 px-4 py-2 text-sm font-medium text-white"
        >
          New idea
        </Link>
      </div>

      {apiDown && (
        <div className="mb-4 rounded-xl border border-stone-200 bg-white px-4 py-3 text-xs text-stone-500">
          We couldn&apos;t reach the workshop. It may be waking up — try again in a minute. You can
          still explore the <Link href="/projects/demo" className="underline">example project</Link>.
        </div>
      )}

      <div className="space-y-3">
        {projects?.map((p) => (
          <Link
            key={p.id}
            href={`/projects/${p.id}`}
            className="block rounded-xl border border-stone-200 bg-white p-5 shadow-sm hover:border-stone-400 transition-colors"
          >
            <div className="flex items-center justify-between">
              <div>
                <div className="font-semibold text-stone-900">{p.name}</div>
                <div className="text-xs text-stone-500 mt-1 capitalize">
                  {p.status.replaceAll("_", " ")}
                  {p.stage !== "none" && ` · stage: ${p.stage}`}
                </div>
              </div>
              <div className="text-right text-xs text-stone-500">
                ${p.budget_used_usd.toFixed(2)} spent
              </div>
            </div>
          </Link>
        ))}
        {projects && projects.length === 0 && (
          <div className="rounded-xl border border-dashed border-stone-300 p-8 text-center">
            <p className="text-sm text-stone-600 mb-1">
              Find out if your idea is worth building - free
            </p>
            <p className="text-xs text-stone-500 mb-4">
              Submit an idea and get an honest feasibility verdict with scored reasoning. You
              approve before anything runs.
            </p>
            <Link
              href="/intake"
              className="rounded-lg bg-stone-900 px-4 py-2 text-xs font-medium text-white hover:bg-stone-700"
            >
              New idea
            </Link>
          </div>
        )}
      </div>

      <p className="mt-8 text-sm text-stone-500">
        Every action, cost, and decision is auditable. Explore the{" "}
        <Link href="/projects/demo" className="underline hover:text-stone-600">
          example project
        </Link>{" "}
        to see the command center with sample data.
      </p>
    </div>
  );
}
