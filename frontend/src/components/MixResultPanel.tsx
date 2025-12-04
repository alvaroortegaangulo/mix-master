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
  const [isReportOpen, setIsReportOpen] = useState(false);

  const { originalFullSongUrl, fullSongUrl, jobId } = result;

  // Fetch report automatically when component mounts or jobId changes
  useEffect(() => {
    if (!jobId) return;

    let active = true;
    setLoadingReport(true);

    fetchJobReport(jobId)
      .then((data) => {
        if (active) {
          setReport(data);
          // Auto-open report when loaded
          setIsReportOpen(true);
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
      {/* Header + Main Player */}
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

        <div className="mt-2 flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
          <button
            type="button"
            onClick={() => setShowOriginal((v) => !v)}
            className="inline-flex min-w-[200px] items-center justify-center rounded-full bg-emerald-400 px-6 py-2 text-sm font-semibold text-emerald-950 shadow-md shadow-emerald-900/40 transition hover:bg-emerald-300"
          >
            {showOriginal ? "Back to Result" : "Listen to Original"}
          </button>

          <button
            type="button"
            onClick={() => setIsReportOpen(true)}
            className="inline-flex min-w-[200px] items-center justify-center rounded-full border border-emerald-500/50 bg-emerald-900/50 px-6 py-2 text-sm font-semibold text-emerald-100 shadow-md shadow-emerald-900/40 transition hover:bg-emerald-800 hover:text-white disabled:opacity-50"
            disabled={loadingReport || !report}
          >
            {loadingReport ? "Loading Report..." : "View Full Report"}
          </button>
        </div>
      </div>

      {/* Pipeline Panel (Stages + Player per stage) */}
      <MixPipelinePanel
        result={result}
        enabledPipelineStageKeys={enabledPipelineStageKeys}
      />

      {/* Report Modal */}
      {isReportOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 overflow-hidden">
          <div className="relative flex max-h-[90vh] w-full max-w-4xl flex-col rounded-2xl border border-emerald-500/30 bg-slate-950 shadow-2xl shadow-emerald-900/50">

            {/* Modal Header */}
            <div className="flex items-center justify-between border-b border-emerald-500/20 bg-emerald-950/30 px-6 py-4">
               <h3 className="text-xl font-bold text-emerald-100">Final Mix Report</h3>
               <button
                 onClick={() => setIsReportOpen(false)}
                 className="rounded-full bg-emerald-900/50 p-2 text-emerald-400 transition hover:bg-emerald-500 hover:text-emerald-950"
               >
                 <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                   <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                 </svg>
               </button>
            </div>

            {/* Modal Content - Scrollable */}
            <div className="flex-1 overflow-y-auto p-6 scrollbar-thin scrollbar-thumb-emerald-700 scrollbar-track-slate-900">
               {loadingReport && (
                 <div className="flex h-40 items-center justify-center space-x-2">
                    <div className="h-3 w-3 animate-bounce rounded-full bg-emerald-500 delay-75"></div>
                    <div className="h-3 w-3 animate-bounce rounded-full bg-emerald-500 delay-150"></div>
                    <div className="h-3 w-3 animate-bounce rounded-full bg-emerald-500 delay-300"></div>
                 </div>
               )}

               {!loadingReport && report && (
                 <ReportViewer report={report} jobId={jobId} />
               )}

               {!loadingReport && !report && (
                 <div className="py-10 text-center text-slate-500">
                    Report data is not available.
                 </div>
               )}
            </div>

            {/* Modal Footer */}
            <div className="border-t border-emerald-500/20 bg-emerald-950/30 px-6 py-4 flex justify-end">
               <button
                  onClick={() => setIsReportOpen(false)}
                  className="rounded-lg bg-emerald-600 px-5 py-2 text-sm font-bold text-white shadow-lg transition hover:bg-emerald-500"
               >
                  Close
               </button>
            </div>

          </div>
        </div>
      )}

    </section>
  );
}
