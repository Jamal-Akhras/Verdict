import { ImageResponse } from "next/og";

export const runtime = "edge";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const alt = "Verdict — feasibility report";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const verdictColors: Record<string, string> = {
  kill: "#e11d48",
  park: "#78716c",
  research: "#0284c7",
  validate: "#d97706",
  prototype: "#7c3aed",
  build: "#059669",
};

export default async function Image({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  let name = "an idea";
  let verdict = "verdict";
  let weighted = 0;
  try {
    const res = await fetch(`${API_URL}/share/${token}`, { next: { revalidate: 600 } });
    if (res.ok) {
      const data = await res.json();
      name = data.project_name;
      verdict = data.verdict;
      weighted = Math.round(
        (data.scores as { score: number; weight: number }[]).reduce(
          (acc, s) => acc + (s.score * s.weight) / 10,
          0
        )
      );
    }
  } catch {
    // fall through to the generic card
  }
  const color = verdictColors[verdict] ?? "#1c1917";

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          background: "#fafaf9",
          padding: "64px",
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ display: "flex", color: "#78716c", fontSize: 28, letterSpacing: 2 }}>
          VERDICT · FEASIBILITY REPORT
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div
            style={{
              display: "flex",
              fontSize: 96,
              fontWeight: 700,
              color,
              textTransform: "uppercase",
            }}
          >
            {verdict}
          </div>
          <div style={{ display: "flex", fontSize: 40, color: "#1c1917" }}>{name}</div>
        </div>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            color: "#57534e",
            fontSize: 28,
          }}
        >
          <div style={{ display: "flex" }}>Weighted score: {weighted}/100</div>
          <div style={{ display: "flex" }}>The AI CTO that says no</div>
        </div>
      </div>
    ),
    size
  );
}
