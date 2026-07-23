"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { AgentTree } from "@/components/tree/AgentTree";
import { AgentRoster, RosterTreeToggle } from "@/components/agents/AgentRoster";
import { AgentDrawer, type AgentAction } from "@/components/agents/AgentDrawer";
import { AgentBuilder } from "@/components/agents/AgentBuilder";
import type { TreeAgent } from "@/components/tree/types";
import { approvalBorder, taskStatusColor } from "@/lib/status";
import {
  api,
  type ApiAgent,
  type ApiApproval,
  type ApiArtifact,
  type ApiProject,
  type ApiTask,
} from "@/lib/api";

const FOUNDER_ID = "founder";
const FRIENDLY_DOWN =
  "We couldn't reach the workshop. It may be waking up — try again in a minute.";

function toTree(
  agents: ApiAgent[],
  tasks: ApiTask[],
  artifacts: ApiArtifact[]
): TreeAgent[] {
  const founder: TreeAgent = {
    id: FOUNDER_ID,
    name: "You",
    initials: "You",
    team: "Governance",
    parentId: null,
    status: "active",
    budgetMaxUsd: 0,
    costUsedUsd: 0,
    currentTask: `${agents.filter((a) => a.status === "proposed").length} proposals waiting`,
    role: "Approves scope, budget, stage changes, and risky actions.",
  };
  return [
    founder,
    ...agents.map((a) => {
      const mine = tasks.filter((t) => t.agent_slug === a.slug);
      const running = mine.find((t) => t.status === "running");
      const failed = mine.find((t) => t.status === "failed");
      return {
        id: a.id,
        slug: a.slug,
        name: a.name,
        initials: a.initials,
        team: a.team,
        parentId: FOUNDER_ID,
        status: a.status,
        authority: a.authority,
        riskLevel: a.risk_level,
        budgetMaxUsd: a.budget_max_usd,
        costUsedUsd: a.cost_used_usd,
        currentTask: running
          ? `Working: ${running.title}`
          : failed
            ? `Failed: ${failed.title}`
            : undefined,
        role: a.role,
        tasks: mine.map((t) => ({ title: t.title, status: t.status, costUsd: t.cost_used_usd })),
        outputs: artifacts.filter((ar) => ar.agent_slug === a.slug).map((ar) => ar.title),
      };
    }),
  ];
}

export default function ProjectPage() {
  const { id } = useParams<{ id: string }>();
  const [project, setProject] = useState<ApiProject | null>(null);
  const [agents, setAgents] = useState<ApiAgent[]>([]);
  const [tasks, setTasks] = useState<ApiTask[]>([]);
  const [artifacts, setArtifacts] = useState<ApiArtifact[]>([]);
  const [approvals, setApprovals] = useState<ApiApproval[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [builderOpen, setBuilderOpen] = useState(false);
  const [view, setView] = useState<"roster" | "tree">("roster");
  const [reviewHint, setReviewHint] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [p, a, t, ar, ap] = await Promise.all([
        api.getProject(id),
        api.listAgents(id),
        api.listTasks(id),
        api.listArtifacts(id),
        api.listApprovals(id, "pending"),
      ]);
      setProject(p);
      setAgents(a);
      setTasks(t);
      setArtifacts(ar);
      setApprovals(ap);
      setError(null);
      return t;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load project");
      return [];
    }
  }, [id]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const blockingPending = approvals.some((a) => a.blocking && a.status === "pending");
  const runActive =
    tasks.some((t) => t.status === "running") ||
    (tasks.some((t) => t.status === "queued") && !blockingPending);
  const runPaused = tasks.some((t) => t.status === "queued") && blockingPending;

  const shouldPoll = runActive;
  useEffect(() => {
    if (shouldPoll && !pollRef.current) {
      pollRef.current = setInterval(refresh, 2500);
    }
    if (!shouldPoll && pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = null;
    };
  }, [shouldPoll, refresh]);

  async function act(agentId: string, action: AgentAction) {
    setBusy(true);
    try {
      await api.agentAction(agentId, action);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Action failed");
    } finally {
      setBusy(false);
    }
  }

  async function approveAll() {
    setBusy(true);
    try {
      await api.approveAllAgents(id);
      await refresh();
    } finally {
      setBusy(false);
    }
  }

  async function resolveApproval(requestId: string, decision: "approve" | "deny") {
    setBusy(true);
    try {
      await api.resolveApproval(requestId, decision);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not resolve");
    } finally {
      setBusy(false);
    }
  }

  async function startRun() {
    setBusy(true);
    try {
      await api.startRun(id);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start the run");
    } finally {
      setBusy(false);
    }
  }

  async function retryRun() {
    setBusy(true);
    try {
      await api.resetRuns(id);
      await api.startRun(id);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not retry the run");
    } finally {
      setBusy(false);
    }
  }

  if (error && !project)
    return (
      <div className="max-w-2xl mx-auto px-6 py-10">
        <p className="text-sm text-stone-600">{FRIENDLY_DOWN}</p>
        <button
          onClick={refresh}
          className="mt-4 rounded-lg bg-stone-900 px-4 py-2 text-xs font-medium text-white hover:bg-stone-700"
        >
          Try again
        </button>
      </div>
    );
  if (!project)
    return <div className="max-w-2xl mx-auto px-6 py-10 text-sm text-stone-500">Loading…</div>;

  const treeAgents = toTree(agents, tasks, artifacts);
  const selected = treeAgents.find((a) => a.id === selectedId && a.id !== FOUNDER_ID) ?? null;
  const proposed = agents.filter((a) => a.status === "proposed");
  const approved = agents.filter((a) => a.status === "approved");
  const doneTasks = tasks.filter((t) => t.status === "done").length;
  const canRun = !runActive && tasks.length === 0 && approved.length > 0 && proposed.length === 0;
  const workBudget = agents
    .filter((a) => ["approved", "active"].includes(a.status))
    .reduce((acc, a) => acc + a.budget_max_usd, 0);
  const proposedBudget = proposed.reduce((acc, a) => acc + a.budget_max_usd, 0);
  const runCost = tasks.reduce((acc, t) => acc + t.cost_used_usd, 0);
  const hasFailures = !runActive && tasks.some((t) => t.status === "failed");
  const runComplete = tasks.length > 0 && tasks.every((t) => t.status === "done");
  const buildPlan = artifacts.find((a) => a.artifact_type === "task_backlog");
  const panelOpen = builderOpen || selected !== null;

  return (
    <div className="flex h-[calc(100vh-53px)]">
      <div className="flex-1 flex flex-col">
        <div className="bg-white px-6 py-3 border-b border-stone-200 flex items-center gap-5 text-sm">
          <span className="font-semibold text-stone-900">{project.name}</span>
          <span className="rounded-full bg-blue-50 px-2.5 py-0.5 text-xs text-blue-700 capitalize">
            {project.stage === "none" ? project.status : project.stage}
          </span>
          {agents.length > 0 && <RosterTreeToggle view={view} onChange={setView} />}
          {runActive && (
            <span className="text-xs text-emerald-600">
              Run in progress · {doneTasks}/{tasks.length} tasks done
            </span>
          )}
          {runPaused && (
            <span className="text-xs text-amber-600">
              Run paused · waiting for your approval
            </span>
          )}
          <div className="ml-auto flex items-center gap-3">
            <Link
              href={`/projects/${id}/activity`}
              className="text-xs text-stone-500 hover:text-stone-700"
            >
              Activity & costs
            </Link>
            <span className="text-xs text-stone-500">
              ${project.budget_used_usd.toFixed(2)} spent
            </span>
          </div>
        </div>
        <div className="flex-1 min-h-0">
          {agents.length > 0 ? (
            view === "roster" ? (
              <AgentRoster agents={treeAgents} selectedId={selectedId} onSelect={setSelectedId} />
            ) : (
              <AgentTree agents={treeAgents} selectedId={selectedId} onSelect={setSelectedId} />
            )
          ) : (
            <div className="h-full flex items-center justify-center">
              <div className="text-center max-w-sm">
                <p className="text-sm text-stone-600 mb-1">No agent team yet.</p>
                <p className="text-xs text-stone-500 mb-4">
                  Choose a stage on the feasibility report to propose a team.
                </p>
                <Link
                  href={`/projects/${id}/report`}
                  className="rounded-lg bg-stone-900 px-4 py-2 text-xs font-medium text-white hover:bg-stone-700"
                >
                  View feasibility report
                </Link>
              </div>
            </div>
          )}
        </div>
      </div>
      <aside className="w-96 shrink-0 border-l border-stone-200 bg-stone-50 flex flex-col">
        <div className="flex items-center gap-2 border-b border-stone-200 bg-white px-4 py-2">
          {panelOpen && (
            <button
              onClick={() => {
                setBuilderOpen(false);
                setSelectedId(null);
              }}
              aria-label="Back to On your desk"
              className="rounded px-1 text-sm text-stone-500 hover:text-stone-900"
            >
              ←
            </button>
          )}
          <span className="text-xs font-semibold text-stone-900">On your desk</span>
          {approvals.length > 0 && (
            <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
              {approvals.length} waiting
            </span>
          )}
        </div>
        <div className="min-h-0 flex-1">
          {builderOpen ? (
            <AgentBuilder
              projectId={id}
              staffedSlugs={agents
                .filter((a) => !["archived", "rejected"].includes(a.status))
                .map((a) => a.slug)}
              onAdded={() => {
                setBuilderOpen(false);
                refresh();
              }}
              onClose={() => setBuilderOpen(false)}
            />
          ) : selected ? (
            <AgentDrawer
              agent={selected}
              busy={busy}
              onClose={() => setSelectedId(null)}
              onAction={(action) => act(selected.id, action)}
            />
          ) : (
            <div className="flex h-full flex-col overflow-y-auto">
              <div className="p-4 border-b border-stone-200 flex items-start justify-between">
                <p className="text-xs text-stone-500">
                  Nothing spends or proceeds without you.
                </p>
                {agents.length > 0 && (
                  <button
                    onClick={() => setBuilderOpen(true)}
                    className="shrink-0 rounded-lg border border-stone-300 px-2.5 py-1.5 text-xs text-stone-600 hover:border-stone-500"
                  >
                    + Add agent
                  </button>
                )}
              </div>
              <div className="p-4 space-y-3">
                {error && (
                  <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
                    {error.includes("Failed to fetch") || error.includes("NetworkError")
                      ? FRIENDLY_DOWN
                      : "That didn't go through. Try again in a moment — nothing was lost."}
                  </div>
                )}
                {runComplete && buildPlan && (
                  <div className="rounded-xl bg-stone-900 p-4 text-white shadow-sm">
                    <div className="text-sm font-semibold">Build it</div>
                    <p className="mt-1 text-xs leading-relaxed text-stone-300">
                      Your build plan is ready. Download the prompt pack and paste it
                      ticket-by-ticket into Lovable, Cursor, or Claude Code.
                    </p>
                    <Link
                      href={`/projects/${id}/artifacts/${buildPlan.id}`}
                      className="mt-3 inline-block rounded-lg bg-white px-3.5 py-1.5 text-xs font-medium text-stone-900 hover:bg-stone-200"
                    >
                      Get the prompt pack →
                    </Link>
                  </div>
                )}
                {approvals.map((ap) => (
                  <div
                    key={ap.id}
                    className={`rounded-xl border bg-white p-3.5 ${approvalBorder(ap.blocking)}`}
                  >
                    <div className="text-xs font-semibold text-stone-900">{ap.title}</div>
                    <div className="text-xs text-stone-500 mt-1">
                      {ap.requested_by_slug} · {ap.summary || (ap.blocking ? "Blocks downstream work until resolved." : "For your awareness.")}
                    </div>
                    <div className="mt-2.5 flex flex-wrap gap-1.5">
                      <button
                        onClick={() => resolveApproval(ap.id, "approve")}
                        disabled={busy}
                        className="rounded-lg bg-stone-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-stone-700 disabled:opacity-40"
                      >
                        {ap.blocking ? "Approve" : "Acknowledge"}
                      </button>
                      {ap.blocking && (
                        <button
                          onClick={() => resolveApproval(ap.id, "deny")}
                          disabled={busy}
                          className="rounded-lg border border-stone-300 px-3 py-1.5 text-xs text-stone-600 hover:border-stone-500 disabled:opacity-40"
                        >
                          Reject
                        </button>
                      )}
                      {ap.subject_type === "artifact" && (
                        <Link
                          href={`/projects/${id}/artifacts/${ap.subject_id}`}
                          className="rounded-lg border border-stone-300 px-3 py-1.5 text-xs text-stone-600 hover:border-stone-500"
                        >
                          Read it first
                        </Link>
                      )}
                    </div>
                  </div>
                ))}
                {proposed.length > 0 && (
                  <div className="rounded-xl border border-stone-200 bg-white p-3.5">
                    <div className="text-xs font-semibold text-stone-900">
                      Approve this phase
                    </div>
                    <div className="text-xs text-stone-500 mt-1">
                      This phase: ~${proposedBudget.toFixed(2)} budget · produces a Product spec
                      (PRD), technical plan, build plan, and QA + security review.
                    </div>
                    <div className="mt-2.5 flex flex-wrap gap-1.5">
                      <button
                        onClick={approveAll}
                        disabled={busy}
                        className="rounded-lg bg-stone-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-stone-700 disabled:opacity-40"
                      >
                        Approve team & budget
                      </button>
                      <button
                        onClick={() => setReviewHint((h) => !h)}
                        className="rounded-lg border border-stone-300 px-3 py-1.5 text-xs text-stone-600 hover:border-stone-500"
                      >
                        Review individually
                      </button>
                    </div>
                    {reviewHint && (
                      <p className="mt-2 text-xs text-stone-500">
                        Click any agent card on the left to review, approve, or deny that team
                        member on its own.
                      </p>
                    )}
                  </div>
                )}
                {canRun && (
                  <div className="rounded-xl border border-stone-200 bg-white p-3.5">
                    <div className="text-xs font-semibold text-stone-900">Start the work</div>
                    <div className="text-xs text-stone-500 mt-1">
                      Runs research → ROI model → product spec → technical plan → build plan in
                      dependency order. Hard cap: ${workBudget.toFixed(2)} across the team. Each
                      agent stops at its own budget.
                    </div>
                    <button
                      onClick={startRun}
                      disabled={busy}
                      className="mt-2.5 rounded-lg bg-stone-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-stone-700 disabled:opacity-40"
                    >
                      Start work
                    </button>
                  </div>
                )}
                {runActive && (
                  <div className="rounded-xl border border-emerald-200 bg-white p-3.5">
                    <div className="flex items-center justify-between">
                      <div className="text-xs font-semibold text-stone-900">
                        Agents are working
                      </div>
                      <span className="text-xs text-stone-500">
                        ${runCost.toFixed(2)} so far
                      </span>
                    </div>
                    <div className="mt-2 space-y-1.5">
                      {tasks.map((t) => (
                        <div key={t.id} className="flex items-center justify-between gap-2 text-xs">
                          <span className="flex min-w-0 items-center gap-1.5">
                            {t.status === "running" && (
                              <span
                                className="h-1.5 w-1.5 shrink-0 animate-pulse rounded-full bg-blue-500"
                                aria-hidden
                              />
                            )}
                            <span className="truncate text-stone-600">{t.title}</span>
                          </span>
                          <span className="flex shrink-0 items-center gap-2">
                            {t.cost_used_usd > 0 && (
                              <span className="text-stone-500">
                                ${t.cost_used_usd.toFixed(2)}
                              </span>
                            )}
                            <span className={taskStatusColor(t.status)}>{t.status}</span>
                            {t.status === "failed" && (
                              <button
                                onClick={retryRun}
                                disabled={busy}
                                className="rounded border border-stone-300 px-1.5 py-0.5 text-xs text-stone-600 hover:border-stone-500 disabled:opacity-40"
                              >
                                Retry
                              </button>
                            )}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {artifacts.length > 0 && (
                  <div className="rounded-xl border border-stone-200 bg-white p-3.5">
                    <div className="text-xs font-semibold text-stone-900 mb-2">
                      Documents ({artifacts.length})
                    </div>
                    <div className="space-y-1.5">
                      {artifacts.map((a) => (
                        <Link
                          key={a.id}
                          href={`/projects/${id}/artifacts/${a.id}`}
                          className="flex items-center justify-between text-xs text-stone-600 hover:text-stone-900"
                        >
                          <span className="truncate">{a.title}</span>
                          <span className="text-stone-500">${a.cost_usd.toFixed(2)}</span>
                        </Link>
                      ))}
                    </div>
                  </div>
                )}
                {hasFailures && (
                  <div className="rounded-xl border border-amber-300 bg-white p-3.5">
                    <div className="text-xs font-semibold text-stone-900">
                      Some work didn&apos;t finish
                    </div>
                    <div className="text-xs text-stone-500 mt-1">
                      A step failed along the way. Retry sends the failed steps back to the team
                      — finished work is kept.
                    </div>
                    <button
                      onClick={retryRun}
                      disabled={busy}
                      className="mt-2.5 rounded-lg bg-stone-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-stone-700 disabled:opacity-40"
                    >
                      Retry failed steps
                    </button>
                  </div>
                )}
                {proposed.length === 0 && !canRun && !runActive && artifacts.length === 0 &&
                  approvals.length === 0 && (
                    <p className="text-xs text-stone-500">Nothing needs you right now.</p>
                  )}
              </div>
              <div className="mt-auto p-4 border-t border-stone-200">
                <Link
                  href={`/projects/${id}/report`}
                  className="text-xs text-stone-500 hover:text-stone-900"
                >
                  View feasibility report →
                </Link>
              </div>
            </div>
          )}
        </div>
      </aside>
    </div>
  );
}
