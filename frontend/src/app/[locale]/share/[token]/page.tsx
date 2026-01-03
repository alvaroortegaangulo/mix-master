"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { useRouter } from "@/i18n/routing";
import { WaveformPlayer } from "../../../../components/WaveformPlayer";
import { getSharedJob } from "../../../../lib/mixApi";
import { ShareIcon, ArrowDownTrayIcon } from "@heroicons/react/24/solid";
import { useTranslations } from "next-intl";
import { useAuth } from "@/context/AuthContext";
import { useModal } from "@/context/ModalContext";

export default function SharePage() {
  const { token } = useParams();
  const router = useRouter();
  const [jobData, setJobData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showOriginal, setShowOriginal] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [isSharing, setIsSharing] = useState(false);
  const { user } = useAuth();
  const { openAuthModal } = useModal();
  const t = useTranslations("MixTool.share");
  const tStudio = useTranslations("Studio");

  useEffect(() => {
    async function loadSharedJob() {
      if (!token) return;
      try {
        const data = await getSharedJob(token as string);
        setJobData(data);
      } catch (err) {
        setError(t('invalidLink'));
      } finally {
        setLoading(false);
      }
    }
    void loadSharedJob();
  }, [token, t]);

  useEffect(() => {
    if (!jobData?.original_url && showOriginal) {
      setShowOriginal(false);
    }
  }, [jobData?.original_url, showOriginal]);

  const handleDownload = async () => {
    if (!user) {
      openAuthModal();
      return;
    }
    if (isDownloading || !jobData?.audio_url) return;
    setIsDownloading(true);
    try {
      const response = await fetch(jobData.audio_url);
      if (!response.ok) {
        throw new Error(`Download failed: ${response.status}`);
      }
      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = jobData?.jobId ? `${jobData.jobId}_mixdown.wav` : "mixdown.wav";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(objectUrl);
    } catch (err) {
      console.error("Download failed", err);
    } finally {
      setIsDownloading(false);
    }
  };

  const handleShare = async () => {
    if (isSharing) return;
    const shareUrl = typeof window !== "undefined" ? window.location.href : "";
    if (!shareUrl) return;
    setIsSharing(true);
    try {
      if (navigator.share) {
        await navigator.share({ url: shareUrl, title: "Piroola" });
      } else {
        await navigator.clipboard.writeText(shareUrl);
      }
    } catch (err) {
      console.error("Share failed", err);
    } finally {
      setIsSharing(false);
    }
  };

  const handleViewReport = () => {
    if (!jobData?.jobId) return;
    router.push(`/mix/result/${jobData.jobId}`);
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 text-emerald-500">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-current border-t-transparent" />
      </div>
    );
  }

  if (error || !jobData) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 text-center">
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-8">
          <p className="text-xl text-red-200">{error || t('notFound')}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-slate-950 px-4 py-12">
      <div className="w-full max-w-5xl">
        <div className="text-center mb-6">
          <h1 className="text-2xl md:text-3xl font-bold text-white tracking-wide">
            MEZCLA / MASTERIZACI\u00d3N DE PIROOLA
          </h1>
        </div>

        <div className="bg-slate-950 rounded-3xl border border-slate-800 shadow-2xl overflow-hidden">
          <div className="p-6 md:p-8">
            <div className="flex flex-col items-center justify-center mb-8">
              <div className="inline-flex bg-slate-900 p-1 rounded-full border border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowOriginal(true)}
                  disabled={!jobData?.original_url}
                  className={`px-6 py-1.5 rounded-full text-xs font-bold transition-all ${
                    showOriginal
                      ? "bg-slate-800 text-white shadow-sm"
                      : "text-slate-500 hover:text-slate-300"
                  } ${!jobData?.original_url ? "opacity-50 cursor-not-allowed" : ""}`}
                >
                  Original
                </button>
                <button
                  type="button"
                  onClick={() => setShowOriginal(false)}
                  className={`px-6 py-1.5 rounded-full text-xs font-bold transition-all ${
                    !showOriginal
                      ? "bg-amber-500 text-slate-950 shadow-lg shadow-amber-500/20"
                      : "text-slate-500 hover:text-slate-300"
                  }`}
                >
                  Master AI
                </button>
              </div>
            </div>

            <div className="mb-8">
              {jobData?.audio_url ? (
                <div className="relative z-0">
                  <WaveformPlayer
                    src={jobData.audio_url}
                    compareSrc={jobData.original_url || undefined}
                    isCompareActive={showOriginal && !!jobData.original_url}
                    accentColor={showOriginal ? "#64748b" : "#f59e0b"}
                    className="bg-transparent shadow-none border-none p-0 !gap-0 h-32 md:h-40 overflow-hidden"
                    canvasClassName="h-full"
                    hideDownload={true}
                  />
                </div>
              ) : (
                <div className="text-center text-sm text-slate-500">
                  Audio no disponible.
                </div>
              )}
            </div>

            <div className="flex flex-col md:flex-row items-center justify-between gap-6 pt-6 border-t border-slate-900">
              <div className="flex w-full md:w-auto items-center gap-4 justify-start">
                <button
                  type="button"
                  onClick={handleViewReport}
                  className="flex w-full md:w-auto items-center justify-center gap-2 rounded-xl border border-teal-500/40 bg-teal-500/10 px-6 py-3 text-sm font-bold text-teal-100 transition hover:bg-teal-500/20"
                >
                  Ver informe completo
                </button>
              </div>

              <div className="flex items-center gap-4 w-full md:w-auto">
                <button
                  type="button"
                  onClick={handleShare}
                  disabled={isSharing}
                  className="flex-1 md:flex-none flex items-center justify-center gap-2 px-6 py-3 rounded-xl border border-emerald-500/40 bg-emerald-500/10 text-emerald-100 text-sm font-bold hover:bg-emerald-500/20 transition disabled:opacity-60"
                >
                  <ShareIcon className="w-4 h-4 text-emerald-200" />
                  Compartir
                </button>
                <button
                  type="button"
                  onClick={handleDownload}
                  disabled={isDownloading}
                  className="flex-1 md:flex-none flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-amber-500 text-slate-950 text-sm font-bold hover:bg-amber-400 transition shadow-[0_0_18px_rgba(251,191,36,0.45)] disabled:opacity-60"
                >
                  <ArrowDownTrayIcon className="w-4 h-4" />
                  {isDownloading ? tStudio("downloading") : "Descargar Master"}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
