// frontend/src/components/MixResultPanel.tsx
"use client";

import { useEffect, useState } from "react";
import {
  type MixResult,
  fetchJobReport,
  signFileUrl,
  getBackendBaseUrl,
} from "../lib/mixApi";
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
  const [signedOriginalUrl, setSignedOriginalUrl] = useState(originalFullSongUrl);
  const [signedFullUrl, setSignedFullUrl] = useState(fullSongUrl);

  // Prepara URLs firmadas para reproducir (en caso de que lleguen sin firmar o con host interno)
  useEffect(() => {
    let cancelled = false;

    async function prepareUrls() {
      try {
        const signUrl = async (rawUrl: string): Promise<string> => {
          if (!rawUrl) return "";
          try {
            const parsed = new URL(rawUrl, window.location.href);
            const hasSig = parsed.searchParams.has("sig") && parsed.searchParams.has("exp");
            const path = parsed.pathname.startsWith(`/files/${jobId}/`)
              ? parsed.pathname.slice(`/files/${jobId}/`.length)
              : parsed.pathname.replace(/^\/files\//, "");
            if (hasSig) {
              // Ya viene firmada: solo normalizamos al host del backend (no al host público)
              const backend = new URL(getBackendBaseUrl());
              parsed.protocol = backend.protocol;
              parsed.host = backend.host;
              parsed.port = backend.port;
              return parsed.toString();
            }
            return await signFileUrl(jobId, path);
          } catch (err) {
            console.warn("Could not normalize URL, returning raw", err);
            return rawUrl;
          }
        };

        const [orig, full] = await Promise.all([
          signUrl(originalFullSongUrl),
          signUrl(fullSongUrl),
        ]);

        if (!cancelled) {
          setSignedOriginalUrl(orig);
          setSignedFullUrl(full);
        }
      } catch (err) {
        console.warn("Could not prepare playback URLs", err);
        if (!cancelled) {
          setSignedOriginalUrl(originalFullSongUrl);
          setSignedFullUrl(fullSongUrl);
        }
      }
    }

    void prepareUrls();
    return () => {
      cancelled = true;
    };
  }, [jobId, originalFullSongUrl, fullSongUrl]);

  const currentSrc = showOriginal ? signedOriginalUrl : signedFullUrl;

  // Cargar reporte (con reintento manual)
  const loadReport = async () => {
    if (!jobId) return;
    setLoadingReport(true);
    try {
      const data = await fetchJobReport(jobId);
      setReport(data);
      setIsReportOpen(true);
    } catch (err) {
      console.error("Failed to load report", err);
    } finally {
      setLoadingReport(false);
    }
  };

  useEffect(() => {
    void loadReport();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  return (
    <section className="mt-6 rounded-3xl border border-emerald-500/40 bg-emerald-500/10 p-6 text-emerald-50 shadow-lg shadow-emerald-500/20">
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
            disabled={loadingReport}
          >
            {loadingReport ? "Loading Report..." : "View Full Report"}
          </button>

          {hasStems && (
            <div className="flex w-full flex-col items-center pt-4">
                <button
                    onClick={() => router.push(`/studio/${jobId}`)}
                    className="group relative inline-flex items-center justify-center overflow-hidden rounded-full bg-gradient-to-r from-emerald-600 to-teal-500 px-8 py-3 font-bold text-white shadow-lg transition-all hover:from-emerald-500 hover:to-teal-400 hover:shadow-emerald-500/50 focus:outline-none focus:ring-4 focus:ring-emerald-500/30"
                >
                    <span className="relative flex items-center gap-2">
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="h-5 w-5">
                            <path d="M11.645 20.91l-.007-.003-.022-.012a15.247 15.247 0 01-.383-.218 25.18 25.18 0 01-4.244-3.17C4.688 15.36 2.25 12.174 2.25 8.25 2.25 5.322 4.714 3 7.688 3A5.5 5.5 0 0112 5.052 5.5 5.5 0 0116.313 3c2.973 0 5.437 2.322 5.437 5.25 0 3.925-2.438 7.111-4.739 9.256a25.175 25.175 0 01-4.244 3.17 15.247 15.247 0 01-.383.219l-.022.012-.007.004-.003.001a.752.752 0 01-.704 0l-.003-.001z" />
                        </svg>
                        PIROOLA STUDIO
                    </span>
                    <div className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/20 to-transparent transition-transform duration-1000 group-hover:translate-x-full" />
                </button>
                <p className="mt-2 text-xs text-emerald-300/70">Manual correction & Remixing</p>
            </div>
          )}
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
                    <div className="mt-3">
                      <button
                        type="button"
                        onClick={loadReport}
                        className="rounded-full border border-emerald-600 px-4 py-2 text-xs font-semibold text-emerald-100 hover:bg-emerald-800"
                      >
                        Retry loading report
                      </button>
                    </div>
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
