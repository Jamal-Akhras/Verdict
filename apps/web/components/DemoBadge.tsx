"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export function DemoBadge() {
  const [demo, setDemo] = useState(false);
  useEffect(() => {
    api.health().then((h) => setDemo(h.demo_mode)).catch(() => {});
  }, []);
  if (!demo) return null;
  return (
    <span className="rounded-full bg-violet-50 border border-violet-200 px-2.5 py-0.5 text-xs text-violet-700">
      Demo mode · simulated agents · $0 spend
    </span>
  );
}
