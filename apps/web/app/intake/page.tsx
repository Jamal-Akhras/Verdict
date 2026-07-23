"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, type IntakeResult } from "@/lib/api";

type Step = "idea" | "questions" | "brief";

export default function IntakePage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("idea");
  const [name, setName] = useState("");
  const [rawText, setRawText] = useState("");
  const [intake, setIntake] = useState<IntakeResult | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(fn: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  const submitIdea = () =>
    run(async () => {
      const result = await api.submitIdea(name || "Untitled idea", rawText);
      setIntake(result);
      setStep(result.follow_up_questions.length > 0 ? "questions" : "brief");
    });

  const submitAnswers = () =>
    run(async () => {
      if (!intake) return;
      const filled = Object.fromEntries(
        Object.entries(answers).filter(([, v]) => v.trim().length > 0)
      );
      const result =
        Object.keys(filled).length > 0
          ? await api.submitAnswers(intake.project_id, filled)
          : intake;
      setIntake(result);
      setStep("brief");
    });

  const evaluate = () =>
    run(async () => {
      if (!intake) return;
      await api.evaluate(intake.project_id);
      router.push(`/projects/${intake.project_id}/report`);
    });

  return (
    <div className="max-w-2xl mx-auto px-6 py-10">
      <h1 className="text-2xl font-semibold text-stone-900 mb-1">New idea</h1>
      <p className="text-sm text-stone-500 mb-8">
        The Intake Agent turns your idea into a structured brief. You confirm it before
        the evaluation spends anything.
      </p>

      {error && (
        <div className="mb-6 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </div>
      )}

      {step === "idea" && (
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-stone-600 mb-1.5">Project name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Gym booking MVP"
              className="w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm focus:border-stone-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-stone-600 mb-1.5">
              Describe your idea in plain words
            </label>
            <textarea
              value={rawText}
              onChange={(e) => setRawText(e.target.value)}
              rows={6}
              placeholder="I want to build an app that helps local gyms manage class bookings, trainer schedules, and member payments."
              className="w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm focus:border-stone-500 focus:outline-none"
            />
          </div>
          <button
            onClick={submitIdea}
            disabled={busy || rawText.trim().length < 10}
            className="rounded-lg bg-stone-900 px-4 py-2 text-sm font-medium text-white hover:bg-stone-700 disabled:opacity-40"
          >
            {busy ? "Intake Agent is reading…" : "Submit idea"}
          </button>
        </div>
      )}

      {step === "questions" && intake && (
        <div className="space-y-4">
          <div className="rounded-xl border border-stone-200 bg-white p-4">
            <div className="text-xs uppercase tracking-wide text-stone-500 mb-1">
              What the Intake Agent understood
            </div>
            <p className="text-sm text-stone-700">{intake.normalized_brief}</p>
          </div>
          <p className="text-sm text-stone-600">
            A few follow-ups sharpen the evaluation. Skip any you don&apos;t know.
          </p>
          {intake.follow_up_questions.map((q) => (
            <div key={q}>
              <label className="block text-xs font-medium text-stone-600 mb-1.5">{q}</label>
              <input
                value={answers[q] ?? ""}
                onChange={(e) => setAnswers((a) => ({ ...a, [q]: e.target.value }))}
                className="w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm focus:border-stone-500 focus:outline-none"
              />
            </div>
          ))}
          <button
            onClick={submitAnswers}
            disabled={busy}
            className="rounded-lg bg-stone-900 px-4 py-2 text-sm font-medium text-white hover:bg-stone-700 disabled:opacity-40"
          >
            {busy ? "Updating brief…" : "Continue"}
          </button>
        </div>
      )}

      {step === "brief" && intake && (
        <div className="space-y-4">
          <div className="rounded-xl border border-stone-200 bg-white p-4 space-y-3">
            <div>
              <div className="text-xs uppercase tracking-wide text-stone-500 mb-1">Brief</div>
              <p className="text-sm text-stone-700">{intake.normalized_brief}</p>
            </div>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <div className="text-xs uppercase tracking-wide text-stone-500 mb-1">
                  Target user
                </div>
                <p className="text-stone-700">{intake.target_user}</p>
              </div>
              <div>
                <div className="text-xs uppercase tracking-wide text-stone-500 mb-1">
                  Problem
                </div>
                <p className="text-stone-700">{intake.problem}</p>
              </div>
            </div>
            {intake.assumptions.length > 0 && (
              <div>
                <div className="text-xs uppercase tracking-wide text-stone-500 mb-1">
                  Assumptions to confirm
                </div>
                <ul className="text-sm text-stone-600 space-y-0.5">
                  {intake.assumptions.map((a) => (
                    <li key={a}>· {a}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
          <div className="rounded-xl border border-stone-200 bg-stone-100 px-4 py-3 text-xs text-stone-500">
            Evaluation runs the Feasibility Analyst (~$1–2 of AI spend). Every model call is
            cost-logged and inspectable.
          </div>
          <button
            onClick={evaluate}
            disabled={busy}
            className="rounded-lg bg-stone-900 px-4 py-2 text-sm font-medium text-white hover:bg-stone-700 disabled:opacity-40"
          >
            {busy ? "Feasibility Analyst is working…" : "Evaluate feasibility"}
          </button>
        </div>
      )}
    </div>
  );
}
