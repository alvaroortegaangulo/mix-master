// frontend/src/app/studio/[jobId]/page.tsx
"use client";

import { useEffect, useState, use } from "react";
import { useRouter } from "next/navigation";
import { StudioInterface } from "@/components/studio/StudioInterface";
import { fetchJobReport, MixResult } from "@/lib/mixApi";

export default function StudioPage(props: { params: Promise<{ jobId: string }> }) {
  const params = use(props.params);
  const { jobId } = params;
  const [result, setResult] = useState<MixResult | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    async function load() {
        if(!jobId) return;
      try {
        const data = await fetchJobReport(jobId);
        setResult(data);
      } catch (e) {
        console.error("Failed to load job", e);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [jobId]);

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-950 text-emerald-500">
        Loading Studio...
      </div>
    );
  }

  if (!result) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-950 text-red-400">
        Job not found.
      </div>
    );
  }

  return (
    <div className="h-screen w-screen overflow-hidden bg-slate-950">
      <StudioInterface job={result} />
    </div>
  );
}
