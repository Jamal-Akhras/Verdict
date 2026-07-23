"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArtifactView } from "@/components/artifacts/ArtifactView";
import { api, type ApiArtifact } from "@/lib/api";
import { buildPromptPack } from "@/lib/prompt-pack";

export default function ArtifactPage() {
  const { id, artifactId } = useParams<{ id: string; artifactId: string }>();
  const [artifact, setArtifact] = useState<ApiArtifact | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    api.getArtifact(artifactId).then(setArtifact).catch(() => setError(true));
  }, [artifactId]);

  if (error)
    return <div className="max-w-3xl mx-auto px-6 py-10 text-sm text-stone-500">Document not found.</div>;
  if (!artifact)
    return <div className="max-w-3xl mx-auto px-6 py-10 text-sm text-stone-500">Loading…</div>;

  return (
    <div className="max-w-3xl mx-auto px-6 py-10">
      <Link href={`/projects/${id}`} className="text-xs text-stone-500 hover:text-stone-700">
        ← Back to command center
      </Link>
      <div className="flex items-center justify-between mt-2 mb-4">
        <h1 className="text-2xl font-semibold text-stone-900">{artifact.title}</h1>
        {artifact.artifact_type === "task_backlog" && (
          <button
            onClick={() => {
              const md = buildPromptPack(artifact, "Project");
              const blob = new Blob([md], { type: "text/markdown" });
              const url = URL.createObjectURL(blob);
              const a = document.createElement("a");
              a.href = url;
              a.download = "prompt-pack.md";
              a.click();
              URL.revokeObjectURL(url);
            }}
            className="rounded-lg bg-stone-900 px-3.5 py-1.5 text-xs font-medium text-white hover:bg-stone-700"
          >
            Download prompt pack
          </button>
        )}
      </div>
      <ArtifactView artifact={artifact} />
    </div>
  );
}
