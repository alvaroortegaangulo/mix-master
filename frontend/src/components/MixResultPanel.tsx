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
import { useTranslations } from "next-intl";

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
  const [processedStageKeys, setProcessedStageKeys] = useState<string[] | undefined>(enabledPipelineStageKeys);
  const [showOriginal, setShowOriginal] = useState(false);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [report, setReport] = useState<any>(null);
  const [loadingReport, setLoadingReport] = useState(false);
  const [isReportOpen, setIsReportOpen] = useState(false);
  const [isShareModalOpen, setIsShareModalOpen] = useState(false);
  const [shareLink, setShareLink] = useState("");
  const [loadingShare, setLoadingShare] = useState(false);
  const t = useTranslations('MixTool.result');

  const { originalFullSongUrl, fullSongUrl, jobId } = result;
  const [signedOriginalUrl, setSignedOriginalUrl] = useState(originalFullSongUrl);
  const [signedFullUrl, setSignedFullUrl] = useState(fullSongUrl);

  const deriveProcessedStageKeys = (reportData: any): string[] => {
    if (!reportData) return [];

    const stageList = Array.isArray(reportData.stages) ? reportData.stages : [];
    const fromStages = stageList
      .map((s: any) => s?.contract_id || s?.stage_id)
      .filter((v: any): v is string => typeof v === "string" && v.length > 0);
    if (fromStages.length) {
      return Array.from(new Set(fromStages));
    }

    const timingStages = reportData?.pipeline_durations?.stages;
    if (Array.isArray(timingStages)) {
      const keys = timingStages
        .map((s: any) => s?.contract_id)
        .filter((v: any): v is string => typeof v === "string" && v.length > 0);
      if (keys.length) {
        return Array.from(new Set(keys));
      }
    }

    return [];
  };

  // Keep processed stage keys in sync when parent resets (e.g. new job)
  useEffect(() => {
    setProcessedStageKeys(enabledPipelineStageKeys);
  }, [enabledPipelineStageKeys, jobId]);

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

  // Cargar reporte (con reintento manual)
  const loadReport = async () => {
    if (!jobId) return;
    setLoadingReport(true);
    setIsReportOpen(true);
    try {
      const data = await fetchJobReport(jobId);
      setReport(data);
      setProcessedStageKeys(deriveProcessedStageKeys(data));
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

  const handleShare = async () => {
    setLoadingShare(true);
    try {
       const { createShareLink } = await import("../lib/mixApi");
       const token = await createShareLink(jobId);
       const link = `${window.location.origin}/share/${token}`;
       setShareLink(link);
       setIsShareModalOpen(true);
    } catch (e) {
       console.error("Share error", e);
    } finally {
       setLoadingShare(false);
    }
  };

  const copyToClipboard = () => {
    navigator.clipboard.writeText(shareLink);
  };

  return (
    <section className="mt-6 rounded-3xl border border-emerald-500/40 bg-emerald-500/10 p-6 text-emerald-50 shadow-lg shadow-emerald-500/20">

      {/* Header + Main Player */}
      <div className="space-y-3">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-emerald-100">
            {showOriginal ? t('originalMix') : t('aiMix')}
          </h2>
          <p className="mt-1 text-xs text-emerald-200/90">
            {showOriginal
              ? t('originalDesc')
              : t('aiDesc')}
          </p>
        </div>

        <WaveformPlayer
          src={signedFullUrl}
          compareSrc={signedOriginalUrl}
          isCompareActive={showOriginal}
          requireAuthForDownload
        />

        <div className="mt-2 flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
          <button
            type="button"
            onClick={() => setShowOriginal((v) => !v)}
            className="inline-flex min-w-[200px] items-center justify-center rounded-full bg-emerald-400 px-6 py-2 text-sm font-semibold text-emerald-950 shadow-md shadow-emerald-900/40 transition hover:bg-emerald-300"
          >
            {showOriginal ? t('backToResult') : t('listenOriginal')}
          </button>

          <button
            type="button"
            onClick={() => setIsReportOpen(true)}
            className="inline-flex min-w-[200px] items-center justify-center rounded-full border border-emerald-500/50 bg-emerald-900/50 px-6 py-2 text-sm font-semibold text-emerald-100 shadow-md shadow-emerald-900/40 transition hover:bg-emerald-800 hover:text-white disabled:opacity-50"
            disabled={loadingReport}
          >
            {loadingReport ? t('loadingReport') : t('viewReport')}
          </button>
        </div>
      </div>

      {/* Pipeline Panel (Stages + Player per stage) */}
      <MixPipelinePanel
        result={result}
        enabledPipelineStageKeys={processedStageKeys}
      />

      {/* Share Button (Below and to the right) */}
      <div className="mt-4 flex justify-end">
        <button
           onClick={handleShare}
           className="flex items-center gap-2 rounded-full bg-emerald-600 px-5 py-2 text-sm font-bold text-white transition hover:bg-emerald-500 shadow-lg shadow-emerald-900/40"
           disabled={loadingShare}
        >
           {loadingShare ? (
             <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></span>
           ) : (
             <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
               <path d="M15 8a3 3 0 10-2.977-2.63l-4.94 2.47a3 3 0 100 4.319l4.94 2.47a3 3 0 10.895-1.789l-4.94-2.47a3.027 3.027 0 000-.74l4.94-2.47C13.456 7.68 14.19 8 15 8z" />
             </svg>
           )}
           <span>{t('share')}</span>
        </button>
      </div>

      {/* Share Modal */}
      {isShareModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
           <div className="w-full max-w-md rounded-2xl border border-emerald-500/30 bg-slate-950 p-6 shadow-2xl">
              <h3 className="text-xl font-bold text-emerald-100 mb-2">{t('shareMix')}</h3>
              <p className="text-sm text-emerald-200/60 mb-4">{t('shareMixDesc')}</p>

              <div className="mb-4 flex gap-2">
                 <input
                   type="text"
                   value={shareLink}
                   readOnly
                   className="flex-1 rounded-lg border border-emerald-500/20 bg-slate-900 px-3 py-2 text-sm text-emerald-100 focus:outline-none"
                 />
                 <button
                   onClick={copyToClipboard}
                   className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-500"
                 >
                   {t('copy')}
                 </button>
              </div>

              <div className="flex gap-4 justify-center py-2">
                  <a href={`https://wa.me/?text=${encodeURIComponent(shareLink)}`} target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:text-emerald-300">WhatsApp</a>
                  <a href={`mailto:?body=${encodeURIComponent(shareLink)}`} className="text-emerald-400 hover:text-emerald-300">Email</a>
                  <a href={`https://twitter.com/intent/tweet?url=${encodeURIComponent(shareLink)}`} target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:text-emerald-300">X / Twitter</a>
                  <a href={`https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(shareLink)}`} target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:text-emerald-300">Facebook</a>
              </div>

              <div className="mt-4 flex justify-end">
                 <button onClick={() => setIsShareModalOpen(false)} className="text-sm text-slate-400 hover:text-white">Close</button>
              </div>
           </div>
        </div>
      )}

      {/* Report Modal */}
      {isReportOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 overflow-hidden">
          <div className="relative flex max-h-[90vh] w-full max-w-4xl flex-col rounded-2xl border border-emerald-500/30 bg-slate-950 shadow-2xl shadow-emerald-900/50">

            {/* Modal Header */}
            <div className="flex items-center justify-between border-b border-emerald-500/20 bg-emerald-950/30 px-6 py-4">
               <h3 className="text-xl font-bold text-emerald-100">{t('finalReport')}</h3>
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
                    {t('unavailable')}
                    <div className="mt-3">
                      <button
                        type="button"
                        onClick={loadReport}
                        className="rounded-full border border-emerald-600 px-4 py-2 text-xs font-semibold text-emerald-100 hover:bg-emerald-800"
                      >
                        {t('retry')}
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
                  {t('close')}
               </button>
            </div>

          </div>
        </div>
      )}

    </section>
  );
}
