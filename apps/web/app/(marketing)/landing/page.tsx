import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Verdict — the AI CTO that tells you if your idea is worth building",
  description:
    "Get a real feasibility verdict, a reviewed build plan, and exact prompts for Lovable, Cursor, or Claude Code. One free verdict, then $29 per project run.",
};

const steps = [
  {
    n: "1",
    title: "Verdict",
    body: "Describe your idea in plain language. Verdict scores it against a weighted rubric and gives you an honest call — kill, park, validate, prototype, or build — with the reasoning behind every score.",
  },
  {
    n: "2",
    title: "Reviewed plan",
    body: "A governed agent team drafts the product spec, tech plan, and build plan. QA and a security reviewer check the work. Nothing advances without your approval, and every action is costed and logged.",
  },
  {
    n: "3",
    title: "Build-ready prompts",
    body: "You get an exact, sequenced prompt pack to paste into Lovable, Cursor, or Claude Code — scoped tickets with acceptance criteria, not a vague wishlist.",
  },
];

const trustItems = [
  {
    title: "Every action costed and audited",
    body: "Write-ahead cost logging and an append-only audit ledger. You can see what each agent did, what it cost, and why — down to the model call.",
  },
  {
    title: "Approval gates, always",
    body: "Agents propose; you decide. The product spec and tech plan pause the run until you approve. Nothing spends your money without asking first.",
  },
  {
    title: "Security review built in",
    body: "A dedicated security agent audits the tech plan before you build. High-risk findings require your explicit acknowledgement.",
  },
];

export default function LandingPage() {
  return (
    <div className="max-w-4xl mx-auto px-6">
      {/* Hero */}
      <section className="py-16 text-center">
        <p className="text-xs uppercase tracking-wide text-stone-500 mb-4">
          Verdict — your AI CTO
        </p>
        <h1 className="text-3xl sm:text-4xl font-semibold text-stone-900 leading-tight max-w-2xl mx-auto">
          The AI CTO that tells you if your idea is worth building — then hands your AI tools an
          exact, reviewed plan to build it.
        </h1>
        <p className="mt-4 text-sm text-stone-600 max-w-xl mx-auto">
          Lovable, Cursor, and Claude Code will build anything you ask. Verdict tells you what to
          ask for — and whether to ask at all.
        </p>
        <div className="mt-8 flex items-center justify-center gap-3">
          <Link
            href="/intake"
            className="rounded-lg bg-stone-900 hover:bg-stone-700 px-5 py-2.5 text-sm font-medium text-white"
          >
            Get your free verdict
          </Link>
          <Link
            href="/projects/demo"
            className="rounded-lg border border-stone-300 px-5 py-2.5 text-sm text-stone-600 hover:border-stone-500"
          >
            See an example project
          </Link>
        </div>
        <p className="mt-3 text-xs text-stone-500">
          One real verdict, free. No credit card.
        </p>
      </section>

      {/* How it works */}
      <section className="py-12 border-t border-stone-200">
        <h2 className="text-lg font-semibold text-stone-900 mb-6 text-center">How it works</h2>
        <div className="grid gap-4 sm:grid-cols-3">
          {steps.map((s) => (
            <div key={s.n} className="rounded-xl border border-stone-200 bg-white p-5">
              <div className="flex items-center gap-2 mb-2">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-stone-900 text-xs font-medium text-white">
                  {s.n}
                </span>
                <h3 className="text-sm font-semibold text-stone-900">{s.title}</h3>
              </div>
              <p className="text-xs text-stone-600 leading-relaxed">{s.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Honesty block */}
      <section className="py-12 border-t border-stone-200">
        <div className="rounded-xl border border-stone-200 bg-stone-50 p-8 text-center">
          <h2 className="text-xl font-semibold text-stone-900 mb-3">
            We&apos;ll tell you no.
          </h2>
          <p className="text-sm text-stone-600 max-w-xl mx-auto leading-relaxed">
            Generation tools are built to say yes. Ask Lovable to build a bad idea and it will
            build it beautifully. Verdict kills bad ideas before you spend a month on them — with a
            scored rubric, a &quot;do not build&quot; list, and the cheapest possible validation
            tests instead. Kill and park are real verdicts here, and we hand them out. That
            honesty is the product.
          </p>
        </div>
      </section>

      {/* Pricing */}
      <section className="py-12 border-t border-stone-200">
        <h2 className="text-lg font-semibold text-stone-900 mb-2 text-center">Pricing</h2>
        <p className="text-sm text-stone-600 text-center max-w-xl mx-auto mb-8">
          A wasted month building the wrong thing costs $1,000+ in tool subscriptions, API
          credits, and your time. Knowing before you build costs $29.
        </p>
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="rounded-xl border border-stone-200 bg-white p-6">
            <div className="text-xs uppercase tracking-wide text-stone-500 mb-1">Free</div>
            <div className="text-2xl font-semibold text-stone-900">$0</div>
            <p className="mt-2 text-xs text-stone-600 leading-relaxed">
              One real feasibility verdict on your idea. Full rubric, honest reasoning, cost
              forecast. Explore the rest of the product in demo mode.
            </p>
          </div>
          <div className="rounded-xl border-2 border-stone-900 bg-white p-6">
            <div className="text-xs uppercase tracking-wide text-stone-500 mb-1">
              Project run
            </div>
            <div className="text-2xl font-semibold text-stone-900">
              $29 <span className="text-sm font-normal text-stone-500">per run</span>
            </div>
            <p className="mt-2 text-xs text-stone-600 leading-relaxed">
              Everything, once: verdict, reviewed product spec, tech plan with security review,
              build plan, and the full prompt pack for your AI tools. Pay per idea, own the
              output.
            </p>
          </div>
          <div className="rounded-xl border border-stone-200 bg-white p-6">
            <div className="text-xs uppercase tracking-wide text-stone-500 mb-1">Builder</div>
            <div className="text-2xl font-semibold text-stone-900">
              $49 <span className="text-sm font-normal text-stone-500">per month</span>
            </div>
            <p className="mt-2 text-xs text-stone-600 leading-relaxed">
              Three full project runs a month plus re-runs as your idea evolves. For people
              shipping more than one thing.
            </p>
          </div>
        </div>
        <div className="mt-8 text-center">
          <Link
            href="/intake"
            className="rounded-lg bg-stone-900 hover:bg-stone-700 px-5 py-2.5 text-sm font-medium text-white"
          >
            Start with the free verdict
          </Link>
        </div>
      </section>

      {/* Trust strip */}
      <section className="py-12 border-t border-stone-200">
        <div className="grid gap-4 sm:grid-cols-3">
          {trustItems.map((t) => (
            <div key={t.title} className="rounded-xl border border-stone-200 bg-white p-5">
              <h3 className="text-sm font-semibold text-stone-900 mb-1.5">{t.title}</h3>
              <p className="text-xs text-stone-600 leading-relaxed">{t.body}</p>
            </div>
          ))}
        </div>
        <p className="mt-6 text-center text-xs text-stone-500">
          You hold final say. Every action, cost, and decision is auditable.
        </p>
      </section>
    </div>
  );
}
