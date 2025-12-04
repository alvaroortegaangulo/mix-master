// frontend/src/components/MixResultPanel.tsx
"use client";

import { useEffect, useState } from "react";
import type { MixResult } from "../lib/mixApi";
import { MixPipelinePanel } from "./MixPipelinePanel";
import { FinalReportModal } from "./FinalReportModal";
import { WaveformPlayer } from "./WaveformPlayer";

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
  const [isReportModalOpen, setIsReportModalOpen] = useState(false);
  const [showOriginal, setShowOriginal] = useState(false);

  const { originalFullSongUrl, fullSongUrl, jobId } = result;

  // Abrir informe automáticamente cuando termina el pipeline
  useEffect(() => {
    if (!jobId) return;
    setIsReportModalOpen(true);
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

      {/* Botón informe final */}
      <div className="mt-4 flex justify-center">
        <button
          type="button"
          onClick={() => setIsReportModalOpen(true)}
          className="inline-flex min-w-[220px] items-center justify-center rounded-full bg-emerald-400 px-6 py-2 text-sm font-semibold text-emerald-950 shadow-md shadow-emerald-900/40 transition hover:bg-emerald-300"
        >
          View Report
        </button>
      </div>

      <FinalReportModal
        jobId={jobId}
        isOpen={isReportModalOpen}
        onClose={() => setIsReportModalOpen(false)}
      />
    </section>
  );
}
