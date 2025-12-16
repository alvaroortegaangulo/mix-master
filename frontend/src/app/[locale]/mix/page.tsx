"use client";

import { Suspense } from "react";
import dynamic from "next/dynamic";
import { useSearchParams } from "next/navigation";

const MixTool = dynamic(
  () => import("../../../components/MixTool").then((mod) => mod.MixTool),
  {
    ssr: false,
    loading: () => (
      <div className="flex min-h-[60vh] items-center justify-center text-slate-300">
        Loading studio...
      </div>
    ),
  }
);

function MixPageContent() {
  const searchParams = useSearchParams();
  const jobIdParam = searchParams.get("jobId");

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans selection:bg-teal-500/30 pt-16">
      <div className="flex flex-col">
        <MixTool resumeJobId={jobIdParam || undefined} />
      </div>
    </div>
  );
}

export default function MixPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-slate-950" />}>
      <MixPageContent />
    </Suspense>
  );
}
