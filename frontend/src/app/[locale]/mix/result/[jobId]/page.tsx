"use client";

import { Suspense, use } from "react";
import { MixResultPageContent } from "../../../../../components/MixResultPageContent";

export default function MixResultPage({ params }: { params: Promise<{ jobId: string }> }) {
  const resolvedParams = use(params);
  return (
    <div className="min-h-screen bg-slate-950 pt-20">
      <Suspense fallback={<div className="text-center text-slate-500 pt-20">Loading result...</div>}>
        <MixResultPageContent jobId={resolvedParams.jobId} />
      </Suspense>
    </div>
  );
}
