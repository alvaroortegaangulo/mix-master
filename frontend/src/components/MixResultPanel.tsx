// frontend/src/components/MixResultPanel.tsx
"use client";

import { useEffect, useState } from "react";
import { type MixResult, fetchJobReport } from "../lib/mixApi";
import { MixPipelinePanel } from "./MixPipelinePanel";
import { WaveformPlayer } from "./WaveformPlayer";
import { ReportViewer } from "./ReportViewer";

type Props = {
  result: MixResult;
  /**
   * List of keys of pipeline stages that were executed for THIS job.
   */
  enabledPipelineStageKeys?: string[];
};

export function MixResultPanel({
  result,
  enabledPipelineStageKeys,
}: Props) {
  const [showOriginal, setShowOriginal] = useState(false);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [report, setReport] = useState<any>(null);
  const [loadingReport, setLoadingReport] = useState(false);

  const { originalFullSongUrl, fullSongUrl, jobId } = result;

  // Fetch report automatically when component mounts or jobId changes
  useEffect(() => {
    if (!jobId) return;

    let active = true;

    // Using a microtask or internal state management to avoid sync setState warning if strictly needed,
    // but typically just setting loading in effect is fine.
    // However, if the linter insists, we can fetch first then set, but that delays the 'loading' feedback.
    // Instead we can just wrap in setTimeout to push it to next tick if we really want to silence it without disabling rule.
    // Or just disable the specific rule for the line.

    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoadingReport(true);

    fetchJobReport(jobId)
      .then((data) => {
        if (active) {
          setReport(data);
        }
      })
      .catch((err) => {
        console.error("Failed to load report", err);
      })
      .finally(() => {
        if (active) setLoadingReport(false);
      });

    return () => {
      active = false;
    };
  }, [jobId]);

  const currentSrc = showOriginal ? originalFullSongUrl : fullSongUrl;

  return (
    <section className="mt-6 rounded-3xl border border-emerald-500/40 bg-emerald-900/30 p-6 text-emerald-50 shadow-xl shadow-emerald-900/40">
      {/* Cabecera + reproductor principal */}
      <div className="space-y-3">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-emerald-100">
            {showOriginal ? "Original mix" : "AI mix & mastering (result)"}
          </h2>
          <p className="mt-1 text-xs text-emerald-200/90">
            {showOriginal
              ? "Original mix (before processing)."
              : "AI mix & mastering (result). Listen to the final mix after processing."}
          </p>
        </div>

        <WaveformPlayer src={currentSrc} />

        <div className="mt-2 flex justify-center">
          <button
            type="button"
            onClick={() => setShowOriginal((v) => !v)}
            className="inline-flex min-w-[220px] items-center justify-center rounded-full bg-emerald-400 px-6 py-2 text-sm font-semibold text-emerald-950 shadow-md shadow-emerald-900/40 transition hover:bg-emerald-300"
          >
            {showOriginal ? "AI Mix & Mastering" : "Original Mix"}
          </button>
        </div>
      </div>

      {/* Panel de pipeline (stages + reproductor por fase) */}
      <MixPipelinePanel
        result={result}
        enabledPipelineStageKeys={enabledPipelineStageKeys}
      />

      {/* Report Viewer Section */}
      <div className="mt-8 border-t border-emerald-500/30 pt-8">
        <h3 className="text-xl font-bold mb-4 text-emerald-100 text-center">Final Mix Report</h3>
        {loadingReport && (
            <p className="text-center text-emerald-200/50 animate-pulse">Loading detailed report...</p>
        )}

        {!loadingReport && report && (
            <ReportViewer report={report} jobId={jobId} />
        )}

        {!loadingReport && !report && (
             <p className="text-center text-emerald-200/50">Report not available.</p>
        )}
      </div>

    </section>
  );
}
