"use client";
import { approvalBorder } from "@/lib/status";
import { demoApprovals } from "@/lib/mock-data";

export function NeedsYou() {
  return (
    <div className="flex h-full flex-col overflow-y-auto">
      <div className="p-4 border-b border-stone-200">
        <p className="text-xs text-stone-500">
          Nothing spends or proceeds without you.
        </p>
      </div>
      <div className="p-4 space-y-3">
        {demoApprovals.map((a) => (
          <div
            key={a.id}
            className={`rounded-xl border bg-white p-3.5 ${approvalBorder(a.risk === "high")}`}
          >
            <div className="text-xs font-semibold text-stone-900">{a.title}</div>
            <div className="text-xs text-stone-500 mt-1">
              {a.requestedBy} · {a.detail}
            </div>
            <div className="mt-2.5 flex gap-1.5">
              <button className="rounded-lg bg-stone-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-stone-700">
                Approve
              </button>
              <button className="rounded-lg border border-stone-300 px-3 py-1.5 text-xs text-stone-600 hover:border-stone-500">
                Request changes
              </button>
              <button className="rounded-lg border border-stone-300 px-3 py-1.5 text-xs text-stone-600 hover:border-stone-500">
                Ask why
              </button>
            </div>
          </div>
        ))}
        {demoApprovals.length === 0 && (
          <p className="text-xs text-stone-500">
            Nothing needs you — agents are working or done.
          </p>
        )}
      </div>
      <div className="mt-auto p-4 border-t border-stone-200">
        <h3 className="text-xs uppercase tracking-wide text-stone-500 mb-1.5">Dissent log</h3>
        <p className="text-xs text-stone-500 leading-relaxed">
          CTO Agent preferred <span className="text-stone-800">prototype</span> over validate —
          reasoning attached to the verdict.
        </p>
      </div>
    </div>
  );
}
