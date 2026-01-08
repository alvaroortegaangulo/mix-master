"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "@/i18n/routing";
import {
  fetchJobStatus,
  fetchJobReport,
  type JobStatus,
  type MixResult,
  signFileUrl,
  getBackendBaseUrl,
  fetchPipelineStages,
  type PipelineStage,
  createShareLink,
} from "@/lib/mixApi";
import { WaveformPlayer } from "./WaveformPlayer";
import {
  PlayIcon,
  BackwardIcon,
  ForwardIcon,
  ArrowPathRoundedSquareIcon,
  ShareIcon,
  ArrowDownTrayIcon,
  CheckCircleIcon,
  ChevronDownIcon,
  ChevronUpIcon
} from "@heroicons/react/24/solid";
import { ReportViewer } from "./ReportViewer";
import { useTranslations } from "next-intl";
import { useAuth } from "@/context/AuthContext";
import { useModal } from "@/context/ModalContext";

type Props = {
  jobId: string;
};

// --- Pipeline Phase Mapping (reused) ---
const PHASE_KEY_MAP: Record<string, string> = {
  "Input & Metadata": "inputMetadata",
  "Technical Preparation": "technicalPreparation",
  "Phase & Polarity Alignment": "phasePolarityAlignment",
  "Static Mix & Routing": "staticMixRouting",
  "Spectral Cleanup": "spectralCleanup",
  "Dynamics & Level Automation": "dynamicsLevelAutomation",
  "Space / Depth by Buses": "spaceDepthByBuses",
  "Multiband EQ / Tonal Balance": "multibandEqTonalBalance",
  "Mix Bus Color": "mixBusColor",
  "Mastering": "mastering",
  "Master Stereo QC": "masterStereoQc",
  "Reporting": "reporting"
};

const STATUS_POLL_INTERVAL_MS = 2000;
const MAX_FINALIZING_RETRIES = 15;

const formatDuration = (totalSeconds?: number | null) => {
  if (typeof totalSeconds !== "number" || !Number.isFinite(totalSeconds)) {
    return null;
  }
  const safeSeconds = Math.max(0, Math.round(totalSeconds));
  const hours = Math.floor(safeSeconds / 3600);
  const minutes = Math.floor((safeSeconds % 3600) / 60);
  const seconds = safeSeconds % 60;

  if (hours > 0) {
    return `${hours}h ${minutes}m ${seconds}s`;
  }
  if (minutes > 0) {
    return `${minutes}m ${seconds}s`;
  }
  return `${seconds}s`;
};

export function MixResultPageContent({ jobId }: Props) {
  const router = useRouter();
  const t = useTranslations('MixTool.result');
  const tStudio = useTranslations('Studio');
  const tPhases = useTranslations("PipelinePhases");
  const tPanel = useTranslations("MixPipelinePanel");
  const tStages = useTranslations("MixTool.stage");
  const { user } = useAuth();
  const { openAuthModal } = useModal();
  const finalizingRetriesRef = useRef(0);
  const hasStatusRef = useRef(false);

  // State
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [report, setReport] = useState<any>(null);
  const [loadingReport, setLoadingReport] = useState(false);
  const [isReportOpen, setIsReportOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMessage, setLoadingMessage] = useState("Cargando resultados...");
  const [error, setError] = useState<string | null>(null);
  const [isDownloading, setIsDownloading] = useState(false);

  // Player State
  const [showOriginal, setShowOriginal] = useState(false);
  const [signedFullUrl, setSignedFullUrl] = useState("");
  const [signedOriginalUrl, setSignedOriginalUrl] = useState("");
  const [stagePreviewUrl, setStagePreviewUrl] = useState("");
  const [stagePreviewLoading, setStagePreviewLoading] = useState(false);
  const [isStageDownloading, setIsStageDownloading] = useState(false);
  const [isStageSharing, setIsStageSharing] = useState(false);

  // Pipeline State
  const [stages, setStages] = useState<PipelineStage[]>([]);
  const [processedStageKeys, setProcessedStageKeys] = useState<string[]>([]);
  const [activeStageKey, setActiveStageKey] = useState<string | null>(null);
  const [isPipelineExpanded, setIsPipelineExpanded] = useState(true);

  // Share State
  const [isShareModalOpen, setIsShareModalOpen] = useState(false);
  const [shareLink, setShareLink] = useState("");
  const [loadingShare, setLoadingShare] = useState(false);

  // --- Pipeline Stages Load ---
  useEffect(() => {
    let cancelled = false;

    async function loadStages() {
      try {
        const allStages = await fetchPipelineStages();
        if (!cancelled) setStages(allStages);
      } catch (e) {
        console.warn("Could not fetch stages", e);
      }
    }

    loadStages();
    return () => { cancelled = true; };
  }, []);

  // --- Job Status Polling ---
  useEffect(() => {
    let cancelled = false;
    let timeoutId: ReturnType<typeof setTimeout> | null = null;
    let finished = false;
    let consecutiveErrors = 0;
    const startedAt = Date.now();
    const STATUS_TIMEOUT_MS = 12000;
    const MAX_INITIAL_WAIT_MS = 30000;
    const MAX_ERROR_DELAY_MS = 8000;

    finalizingRetriesRef.current = 0;
    hasStatusRef.current = false;
    setError(null);
    setLoading(true);
    setLoadingMessage("Cargando resultados...");

    if (!jobId) {
      setError("Job ID missing");
      setLoading(false);
      return () => {};
    }

    const scheduleNext = (delayMs: number) => {
      if (cancelled || finished) return;
      timeoutId = setTimeout(pollStatus, delayMs);
    };

    const applyStatus = (status: JobStatus) => {
      hasStatusRef.current = true;
      setJobStatus(status);
      setError(null);

      if (status.status === "error") {
        setError(status.error || status.message || "Error loading result");
        setLoading(false);
        finished = true;
        return;
      }

      const hasResult = status.status === "done" && !!status.result;
      if (hasResult) {
        setLoading(false);
        finished = true;
        return;
      }

      if (status.status === "done" && !status.result) {
        finalizingRetriesRef.current += 1;
        if (finalizingRetriesRef.current >= MAX_FINALIZING_RETRIES) {
          setError("Resultados no disponibles. Intenta nuevamente.");
          setLoading(false);
          finished = true;
          return;
        }
      } else {
        finalizingRetriesRef.current = 0;
      }

      setLoading(false);
    };

    const pollStatus = async () => {
      if (cancelled || finished) return;
      try {
        const status = await fetchJobStatus(jobId, { timeoutMs: STATUS_TIMEOUT_MS, skipSigning: true });
        if (cancelled || finished) return;
        consecutiveErrors = 0;
        applyStatus(status);
        if (!finished) {
          scheduleNext(STATUS_POLL_INTERVAL_MS);
        }
      } catch (err: any) {
        if (cancelled || finished) return;
        consecutiveErrors += 1;
        const hasStatus = hasStatusRef.current;
        const elapsedMs = Date.now() - startedAt;

        if (!hasStatus && elapsedMs > MAX_INITIAL_WAIT_MS) {
          setLoadingMessage("La conexión tarda más de lo habitual. Reintentando...");
          setLoading(true);
        } else if (!hasStatus) {
          setLoading(true);
        }

        const delayMs = Math.min(
          MAX_ERROR_DELAY_MS,
          STATUS_POLL_INTERVAL_MS * (consecutiveErrors + 1),
        );
        scheduleNext(delayMs);
      }
    };

    pollStatus();
    return () => {
      cancelled = true;
      finished = true;
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, [jobId]);

  // --- Fetch Report (after job completes) ---
  const loadReport = useCallback(async () => {
    if (!jobId) return;
    setLoadingReport(true);
    try {
      const rep = await fetchJobReport(jobId);
      setReport(rep);
    } catch (e) {
      console.warn("Could not fetch report", e);
    } finally {
      setLoadingReport(false);
    }
  }, [jobId]);

  useEffect(() => {
    if (!jobStatus || jobStatus.status !== "done") return;
    void loadReport();
  }, [jobId, jobStatus?.status, loadReport]);

  // --- Derive Processed Keys from Report ---
  useEffect(() => {
    if (!report) return;

    // Logic from MixResultPanel
    const deriveKeys = (reportData: any): string[] => {
        const stageList = Array.isArray(reportData.stages) ? reportData.stages : [];
        const fromStages = stageList
          .map((s: any) => s?.contract_id || s?.stage_id)
          .filter((v: any): v is string => typeof v === "string" && v.length > 0);

        if (fromStages.length) return Array.from(new Set(fromStages));

        const timingStages = reportData?.pipeline_durations?.stages;
        if (Array.isArray(timingStages)) {
          const keys = timingStages
            .map((s: any) => s?.contract_id)
            .filter((v: any): v is string => typeof v === "string" && v.length > 0);
          if (keys.length) return Array.from(new Set(keys));
        }
        return [];
    };

    const keys = deriveKeys(report);
    setProcessedStageKeys(keys);

    // Set active stage to the last processed one by default
    if (keys.length > 0) {
        setActiveStageKey(keys[keys.length - 1]);
    }
  }, [report]);

  // --- Prepare URLs ---
  useEffect(() => {
    if (!jobStatus?.result) return;
    const { fullSongUrl, originalFullSongUrl } = jobStatus.result;

    let cancelled = false;
    async function sign() {
        // Helper to sign
        const signUrl = async (raw: string) => {
            if (!raw) return "";
            try {
                // Same logic as MixResultPanel to reuse existing signatures or sign new
                const parsed = new URL(raw, window.location.href);
                const hasSig = parsed.searchParams.has("sig");
                if (hasSig) {
                     const backend = new URL(getBackendBaseUrl());
                     parsed.protocol = backend.protocol;
                     parsed.host = backend.host;
                     parsed.port = backend.port;
                     return parsed.toString();
                }
                return await signFileUrl(jobId, parsed.pathname); // simplified, assumes normalize happens inside
            } catch {
                return raw;
            }
        };

        const [sFull, sOrig] = await Promise.all([
            signUrl(fullSongUrl),
            signUrl(originalFullSongUrl)
        ]);

        if (!cancelled) {
            setSignedFullUrl(sFull);
            setSignedOriginalUrl(sOrig);
        }
    }
    sign();
    return () => { cancelled = true; };
  }, [jobStatus, jobId]);

  // --- Computed Metrics ---
  const metrics = useMemo(() => {
      const m = {
          pipelineTime: "N/A",
          lufs: "N/A",
          tp: "N/A",
          lra: "N/A",
      };

      if (report) {
         const durationLabel = formatDuration(report.pipeline_durations?.total_duration_sec);
         if (durationLabel) m.pipelineTime = durationLabel;

         const sourceMetrics = showOriginal ? (report.original_metrics || {}) : (report.final_metrics || {});

         if (typeof sourceMetrics.lufs_integrated === "number") {
           m.lufs = sourceMetrics.lufs_integrated.toFixed(2);
         } else if (showOriginal) {
            m.lufs = "N/A";
         }

         if (typeof sourceMetrics.true_peak_dbtp === "number") {
           m.tp = sourceMetrics.true_peak_dbtp.toFixed(2);
         } else if (showOriginal) {
            m.tp = "N/A";
         }

         if (typeof sourceMetrics.lra === "number") {
           m.lra = sourceMetrics.lra.toFixed(2);
         } else if (showOriginal) {
            m.lra = "N/A";
         }
      }

      return m;
  }, [report, showOriginal]);

  // --- Active Stage Details ---
  const processedStages = useMemo(() => {
      if (!stages.length || !processedStageKeys.length) return [];
      const stageByKey = new Map(stages.map((stage) => [stage.key, stage]));
      const ordered = processedStageKeys
        .map((key) => stageByKey.get(key))
        .filter((stage): stage is PipelineStage => Boolean(stage));
      if (ordered.length) return ordered;
      return stages.filter((stage) => processedStageKeys.includes(stage.key));
  }, [stages, processedStageKeys]);

  const stageSelectOptions = useMemo(() => {
      if (processedStages.length) return processedStages;
      if (activeStageKey) {
        const stage = stages.find((s) => s.key === activeStageKey);
        return stage ? [stage] : [];
      }
      return [];
  }, [processedStages, activeStageKey, stages]);

  const activeStageInfo = useMemo(() => {
      if (!activeStageKey || !stages.length) return null;
      const stage = stages.find(s => s.key === activeStageKey);
      if (!stage) return null;

      const key = stage.description;
      const mappedKey = PHASE_KEY_MAP[key];

      return {
          id: stage.key,
          index: stage.index,
          title: mappedKey ? tPhases(`${mappedKey}.title`) : stage.description,
          description: mappedKey ? tPhases(`${mappedKey}.body`) : "Processing stage applied."
      };
  }, [activeStageKey, stages, tPhases]);

  const activeStageTitle = useMemo(() => {
      if (!activeStageInfo?.id) return null;
      const key = `${activeStageInfo.id}.title` as any;
      return tStages.has(key) ? tStages(key) : activeStageInfo.id;
  }, [activeStageInfo?.id, tStages]);

  // --- Active Stage Preview Audio ---
  useEffect(() => {
    let cancelled = false;

    if (!activeStageKey || !stages.length || !jobStatus?.result) {
      setStagePreviewUrl("");
      setStagePreviewLoading(false);
      return () => {};
    }

    const stage = stages.find(s => s.key === activeStageKey);
    const relPath = stage?.previewMixRelPath || "";

    if (!relPath) {
      setStagePreviewUrl("");
      setStagePreviewLoading(false);
      return () => {};
    }

    async function signStagePreview() {
      setStagePreviewLoading(true);
      setStagePreviewUrl("");
      try {
        const signed = await signFileUrl(jobId, relPath);
        if (!cancelled) {
          setStagePreviewUrl(signed || "");
        }
      } catch (err) {
        console.warn("Could not sign stage preview", err);
        if (!cancelled) {
          setStagePreviewUrl("");
        }
      } finally {
        if (!cancelled) {
          setStagePreviewLoading(false);
        }
      }
    }

    signStagePreview();
    return () => {
      cancelled = true;
    };
  }, [activeStageKey, stages, jobStatus?.result, jobId]);

  // --- Handlers ---
  const handleOpenReport = () => {
    setIsReportOpen(true);
    if (!report && !loadingReport) {
      void loadReport();
    }
  };

  const handleShare = async () => {
    setLoadingShare(true);
    try {
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

  const buildAuthHeaders = useCallback((): HeadersInit => {
    const headers: Record<string, string> = {};
    if (typeof window !== "undefined") {
      const token = localStorage.getItem("access_token");
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }
    }
    return headers;
  }, []);

  const handleDownload = useCallback(async () => {
    if (!user) {
      openAuthModal(`/mix/result/${jobId}`);
      return;
    }
    if (isDownloading) return;
    const activeUrl = showOriginal
      ? (signedOriginalUrl || jobStatus?.result?.originalFullSongUrl || "")
      : (signedFullUrl || jobStatus?.result?.fullSongUrl || "");
    if (!activeUrl) return;
    setIsDownloading(true);
    try {
      let response = await fetch(activeUrl);
      if (!response.ok) {
        response = await fetch(activeUrl, { headers: buildAuthHeaders() });
      }
      if (!response.ok) {
        throw new Error(`Download failed: ${response.status}`);
      }
      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = showOriginal ? `${jobId}_original.wav` : `${jobId}_mixdown.wav`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(objectUrl);
    } catch (err) {
      console.error("Download failed", err);
    } finally {
      setIsDownloading(false);
    }
  }, [
    buildAuthHeaders,
    isDownloading,
    jobId,
    jobStatus?.result?.fullSongUrl,
    jobStatus?.result?.originalFullSongUrl,
    openAuthModal,
    showOriginal,
    signedFullUrl,
    signedOriginalUrl,
    user,
  ]);

  const copyToClipboard = () => {
    navigator.clipboard.writeText(shareLink);
  };

  const handleStageDownload = useCallback(async () => {
    if (!user) {
      openAuthModal(`/mix/result/${jobId}`);
      return;
    }
    if (!stagePreviewUrl || !activeStageKey || isStageDownloading) return;
    setIsStageDownloading(true);
    try {
      const response = await fetch(stagePreviewUrl);
      if (!response.ok) {
        throw new Error(`Download failed: ${response.status}`);
      }
      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = `${jobId}_${activeStageKey}_preview.wav`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(objectUrl);
    } catch (err) {
      console.error("Stage download failed", err);
    } finally {
      setIsStageDownloading(false);
    }
  }, [activeStageKey, isStageDownloading, jobId, openAuthModal, stagePreviewUrl, user]);

  const handleStageShare = useCallback(async () => {
    if (!stagePreviewUrl || !activeStageKey || isStageSharing) return;
    setIsStageSharing(true);
    try {
      await navigator.clipboard.writeText(stagePreviewUrl);
    } catch (err) {
      console.error("Stage share failed", err);
    } finally {
      setIsStageSharing(false);
    }
  }, [activeStageKey, isStageSharing, stagePreviewUrl]);

  if (loading) {
      return (
          <div className="flex items-center justify-center min-h-[60vh] text-slate-400">
              <div className="flex flex-col items-center gap-4">
                  <div className="w-8 h-8 border-4 border-amber-500 border-t-transparent rounded-full animate-spin"></div>
                  <p>{loadingMessage}</p>
              </div>
          </div>
      );
  }

  if (error) {
      return (
        <div className="flex flex-col items-center justify-center min-h-[60vh] text-slate-400 gap-4">
            <p className="text-red-400">{error}</p>
            <button onClick={() => router.push('/mix')} className="text-amber-500 underline">Volver al inicio</button>
        </div>
      );
  }

  const isFinalizing = jobStatus?.status === "done" && !jobStatus?.result;
  const isProcessing = jobStatus && jobStatus.status !== "done" && jobStatus.status !== "error";
  const progressValue = Math.min(100, Math.max(0, jobStatus?.progress ?? 0));

  if (isProcessing || isFinalizing) {
      return (
          <div className="flex items-center justify-center min-h-[60vh] text-slate-400">
              <div className="flex w-full max-w-md flex-col items-center gap-4 px-4 text-center">
                  <div className="w-8 h-8 border-4 border-amber-500 border-t-transparent rounded-full animate-spin"></div>
                  <div>
                      <p className="text-slate-200">
                        {isFinalizing ? "Preparando archivos finales..." : "Procesando mezcla..."}
                      </p>
                      <p className="text-xs text-slate-500 mt-2">{jobStatus?.message || "Esperando actualizacion del estado..."}</p>
                  </div>
                  <div className="w-full">
                      <div className="h-2 w-full rounded-full bg-slate-800 overflow-hidden">
                          <div
                              className="h-2 bg-amber-500 transition-all"
                              style={{ width: `${progressValue}%` }}
                          />
                      </div>
                      <p className="mt-2 text-xs text-slate-500">{Math.round(progressValue)}%</p>
                  </div>
              </div>
          </div>
      );
  }

  if (!jobStatus || !jobStatus.result) {
      return (
        <div className="flex flex-col items-center justify-center min-h-[60vh] text-slate-400 gap-4">
            <p className="text-red-400">No se encontraron resultados</p>
            <button onClick={() => router.push('/mix')} className="text-amber-500 underline">Volver al inicio</button>
        </div>
      );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
        {/* HEADER */}
        <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4">
            <div>
                <div className="flex items-center gap-3 mb-1">
                    <CheckCircleIcon className="w-6 h-6 text-emerald-500" />
                    <h1 className="text-2xl font-bold text-white">Mezcla Finalizada</h1>
                </div>
                <p className="text-slate-400 text-sm flex items-center gap-2">
                    <span className="opacity-60">Sesión #{jobId.slice(0, 8)}</span>
                    <span className="w-1 h-1 rounded-full bg-slate-600"></span>
                    <span className="text-slate-300">"{jobStatus.result.fullSongUrl.split('/').pop()?.split('?')[0] || 'Unknown'}"</span>
                </p>
            </div>
            <div className="flex items-center gap-3">
                <button
                    onClick={() => router.push('/profile')}
                    className="px-4 py-2 rounded-lg bg-slate-900 border border-slate-700 text-slate-300 text-sm font-medium hover:text-white hover:border-slate-600 transition"
                >
                    Historial
                </button>
                  <button
                      onClick={() => router.push('/mix')}
                      className="px-4 py-2 rounded-lg bg-teal-600 border border-teal-500/40 text-white text-sm font-medium hover:bg-teal-500 transition"
                  >
                      Nueva Carga
                  </button>
            </div>
        </div>

        {/* METRICS BAR */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            <div className="bg-slate-900/50 rounded-2xl p-4 border border-slate-800 text-center relative overflow-hidden group">
                <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-amber-500/50 to-transparent opacity-0 group-hover:opacity-100 transition-opacity"></div>
                <p className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">TIEMPO PIPELINE</p>
                <div className="text-xl font-bold text-white">
                    {metrics.pipelineTime}
                </div>
            </div>
            <div className="bg-slate-900/50 rounded-2xl p-4 border border-slate-800 text-center relative overflow-hidden group">
                <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-amber-500/50 to-transparent opacity-0 group-hover:opacity-100 transition-opacity"></div>
                <p className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">LUFS INTEGRADO</p>
                <div className="text-xl font-bold text-white">
                    {metrics.lufs} <span className="text-xs text-slate-500 font-normal">LUFS</span>
                </div>
            </div>
            <div className="bg-slate-900/50 rounded-2xl p-4 border border-slate-800 text-center relative overflow-hidden group">
                <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-amber-500/50 to-transparent opacity-0 group-hover:opacity-100 transition-opacity"></div>
                <p className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">TRUE PEAK</p>
                <div className="text-xl font-bold text-white">
                    {metrics.tp} <span className="text-xs text-slate-500 font-normal">dBTP</span>
                </div>
            </div>
            <div className="bg-slate-900/50 rounded-2xl p-4 border border-slate-800 text-center relative overflow-hidden group">
                <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-amber-500/50 to-transparent opacity-0 group-hover:opacity-100 transition-opacity"></div>
                <p className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">LRA</p>
                <div className="text-xl font-bold text-white">
                    {metrics.lra} <span className="text-xs text-slate-500 font-normal">LU</span>
                </div>
            </div>
        </div>

        {/* MAIN PLAYER CARD */}
        <div className="bg-slate-950 rounded-3xl border border-slate-800 shadow-2xl overflow-hidden mb-8">
            <div className="p-6 md:p-8">
                {/* Toggle & Title */}
                <div className="flex flex-col items-center justify-center mb-8 relative">
                    <div className="inline-flex bg-slate-900 p-1 rounded-full border border-slate-800">
                        <button
                            onClick={() => setShowOriginal(true)}
                            className={`px-6 py-1.5 rounded-full text-xs font-bold transition-all ${showOriginal ? 'bg-slate-800 text-white shadow-sm' : 'text-slate-500 hover:text-slate-300'}`}
                        >
                            Original
                        </button>
                        <button
                            onClick={() => setShowOriginal(false)}
                            className={`px-6 py-1.5 rounded-full text-xs font-bold transition-all ${!showOriginal ? 'bg-amber-500 text-slate-950 shadow-lg shadow-amber-500/20' : 'text-slate-500 hover:text-slate-300'}`}
                        >
                            Master AI
                        </button>
                    </div>
                </div>

                {/* Waveform */}
                <div className="mb-8">
                <div className="relative z-0">
                  <WaveformPlayer
                    src={signedFullUrl}
                    compareSrc={signedOriginalUrl}
                    isCompareActive={showOriginal}
                    accentColor={showOriginal ? "#64748b" : "#f59e0b"} // Slate for original, Amber for Master
                    className="bg-transparent shadow-none border-none p-0 !gap-0 h-32 md:h-40 overflow-hidden"
                    canvasClassName="h-full"
                    hideDownload={true}
                    authRedirectPath={`/mix/result/${jobId}`}
                  />
                </div>
              </div>

                {/* Controls & Actions */}
                <div className="flex flex-col md:flex-row items-center justify-between gap-6 pt-6 border-t border-slate-900">

                    {/* Transport (Visual only mostly, WaveformPlayer handles play/pause internally but we can't easily control it from outside without ref hoisting.
                        The requested image shows external controls.
                        WaveformPlayer currently has internal Play button.
                        I will hide WaveformPlayer's button via CSS or modify component if I could, but strictly I should use what's available.
                        However, the user said "estilo de Waveform como el que hay actualmente".
                        The current WaveformPlayer HAS a play button. I'll stick to WaveformPlayer's built-in controls to avoid breaking functionality.
                        I will just add the Extra buttons (Share, Download) on the right.
                    */}
                    <div className="flex w-full md:w-auto items-center gap-4 justify-start">
                        <button
                            type="button"
                            onClick={handleOpenReport}
                            className="flex w-full md:w-auto items-center justify-center gap-2 rounded-xl border border-teal-500/40 bg-teal-500/10 px-6 py-3 text-sm font-bold text-teal-100 transition hover:bg-teal-500/20"
                        >
                            {t('viewReport')}
                        </button>
                    </div>

                    <div className="flex items-center gap-4 w-full md:w-auto">
                        <button
                            onClick={handleShare}
                            className="flex-1 md:flex-none flex items-center justify-center gap-2 px-6 py-3 rounded-xl border border-emerald-500/40 bg-emerald-500/10 text-emerald-100 text-sm font-bold hover:bg-emerald-500/20 transition"
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
                            {isDownloading ? tStudio('downloading') : "Descargar Master"}
                        </button>
                    </div>
                </div>
            </div>

            {/* PIPELINE SECTION */}
            <div className="border-t border-slate-900 bg-slate-950 relative z-20">
                <button
                    onClick={() => setIsPipelineExpanded(!isPipelineExpanded)}
                    className="w-full flex items-center justify-between p-6 hover:bg-slate-900/50 transition"
                >
                    <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center text-emerald-500">
                           <ArrowPathRoundedSquareIcon className="w-5 h-5" />
                        </div>
                        <div className="text-left">
                            <h3 className="text-white font-bold text-sm">Pipeline de Procesamiento</h3>
                            <p className="text-slate-500 text-xs">{processedStageKeys.length} módulos aplicados</p>
                        </div>
                    </div>
                    {isPipelineExpanded ? <ChevronUpIcon className="w-5 h-5 text-slate-500" /> : <ChevronDownIcon className="w-5 h-5 text-slate-500" />}
                </button>

                {isPipelineExpanded && (
                    <div className="border-t border-slate-900">
                        <div className="p-8 bg-slate-950/30">
                            <p className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-6">Paso Seleccionado</p>

                            {activeStageInfo ? (
                                <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-6">
                                    <div className="bg-slate-900 rounded-2xl p-6 border border-slate-800 relative overflow-hidden">
                                         {/* Decorative bg number */}
                                         <span className="absolute top-2 right-4 text-6xl font-black text-slate-800/30 pointer-events-none opacity-20">{activeStageInfo.index}</span>

                                         <div className="flex flex-wrap items-center gap-3 mb-4">
                                             <label className="sr-only" htmlFor="pipeline-stage-select">Stage</label>
                                             <select
                                                 id="pipeline-stage-select"
                                                 className="w-full sm:w-auto rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm font-semibold text-white focus:outline-none focus:ring-2 focus:ring-emerald-500/40"
                                                 value={activeStageKey ?? ""}
                                                 onChange={(event) => setActiveStageKey(event.target.value)}
                                             >
                                                 {stageSelectOptions.map((stage) => {
                                                     const stageTitle = tStages.has(`${stage.key}.title` as any)
                                                       ? tStages(`${stage.key}.title` as any)
                                                       : stage.label || stage.key;
                                                     return (
                                                       <option key={stage.key} value={stage.key}>
                                                         #{String(stage.index).padStart(2, "0")} {stageTitle}
                                                       </option>
                                                     );
                                                 })}
                                             </select>
                                         </div>
                                         <p className="text-slate-300 text-sm leading-relaxed mb-6">
                                             {activeStageInfo.description}
                                         </p>

                                         {/* Mini visualization placeholder as in image */}
                                         <div className="h-12 w-full flex items-end gap-1 opacity-50">
                                             {[40, 70, 50, 90, 60, 30, 80].map((h, i) => (
                                                 <div key={i} style={{height: `${h}%`}} className="flex-1 bg-emerald-500/50 rounded-t-sm"></div>
                                             ))}
                                         </div>
                                    </div>

                                    <div className="bg-slate-950/40 rounded-2xl border border-slate-800 p-4">
                                        <div className="flex items-center justify-between mb-3">
                                            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500">Preview de etapa</p>
                                            <span className="text-[10px] text-slate-600">
                                              #{activeStageInfo.index} {activeStageTitle || activeStageInfo.id}
                                            </span>
                                        </div>

                                        {stagePreviewLoading && (
                                            <div className="text-xs text-slate-500">Cargando audio...</div>
                                        )}

                                        {!stagePreviewLoading && stagePreviewUrl && (
                                            <>
                                                <WaveformPlayer
                                                    src={stagePreviewUrl}
                                                    accentColor="#10b981"
                                                    className="bg-slate-950/60 border border-slate-800/80 shadow-none p-2 !gap-2 rounded-2xl"
                                                    canvasClassName="h-12"
                                                    hideDownload={true}
                                                    authRedirectPath={`/mix/result/${jobId}`}
                                                />
                                                <div className="mt-3 flex flex-wrap gap-2">
                                                    <button
                                                        type="button"
                                                        onClick={handleStageShare}
                                                        disabled={isStageSharing}
                                                        className="flex-1 min-w-[120px] inline-flex items-center justify-center gap-2 rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-[11px] font-semibold text-emerald-100 transition hover:bg-emerald-500/20 disabled:opacity-60"
                                                    >
                                                        <ShareIcon className="w-4 h-4" />
                                                        {isStageSharing ? tStudio('downloading') : "Compartir"}
                                                    </button>
                                                    <button
                                                        type="button"
                                                        onClick={handleStageDownload}
                                                        disabled={isStageDownloading}
                                                        className="flex-1 min-w-[120px] inline-flex items-center justify-center gap-2 rounded-lg bg-amber-500 px-3 py-2 text-[11px] font-semibold text-slate-950 transition hover:bg-amber-400 shadow-[0_0_16px_rgba(251,191,36,0.45)] disabled:opacity-60"
                                                    >
                                                        <ArrowDownTrayIcon className="w-4 h-4" />
                                                        {isStageDownloading ? tStudio('downloading') : "Descargar"}
                                                    </button>
                                                </div>
                                            </>
                                        )}

                                        {!stagePreviewLoading && !stagePreviewUrl && (
                                            <div className="text-xs text-slate-500">Audio no disponible para este paso.</div>
                                        )}
                                    </div>
                                </div>
                            ) : (
                                <div className="text-slate-500 text-sm">Selecciona un paso para ver detalles.</div>
                            )}
                        </div>
                    </div>
                )}
            </div>
        </div>

        {/* Share Modal */}
        {isShareModalOpen && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
                <div className="w-full max-w-md rounded-2xl border border-emerald-500/30 bg-slate-950 p-6 shadow-2xl">
                    <h3 className="text-xl font-bold text-emerald-100 mb-2">Compartir Mezcla</h3>
                    <p className="text-sm text-emerald-200/60 mb-4">
                        {"Comparte este enlace \u00fanico. El enlace expirar\u00e1 en 7 d\u00edas."}
                    </p>

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
                            Copiar
                        </button>
                    </div>

                    <div className="flex gap-4 justify-center py-2">
                        <a
                          href={`https://wa.me/?text=${encodeURIComponent(shareLink)}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          aria-label="WhatsApp"
                          title="WhatsApp"
                          className="flex h-10 w-10 items-center justify-center rounded-full border border-emerald-500/40 bg-emerald-500/10 text-emerald-200 transition hover:bg-emerald-500/20 hover:text-emerald-100"
                        >
                          <svg viewBox="0 0 24 24" className="h-5 w-5 fill-current" aria-hidden="true">
                            <path d="M20.52 3.48A11.94 11.94 0 0 0 12.05 0C5.39 0 .01 5.38 0 12.02c0 2.12.56 4.19 1.62 6.02L0 24l6.14-1.61a12 12 0 0 0 5.91 1.51h.01c6.64 0 12.03-5.38 12.03-12.02 0-3.21-1.25-6.23-3.57-8.4ZM12.06 22a9.93 9.93 0 0 1-5.07-1.39l-.36-.21-3.64.96.97-3.55-.23-.36a9.96 9.96 0 1 1 8.33 4.55Zm5.53-7.46c-.3-.15-1.77-.87-2.05-.97-.28-.1-.48-.15-.68.15-.2.3-.78.97-.96 1.17-.18.2-.36.22-.66.07-.3-.15-1.27-.47-2.41-1.5-.89-.8-1.49-1.78-1.66-2.08-.17-.3-.02-.46.13-.61.13-.13.3-.36.45-.54.15-.18.2-.3.3-.5.1-.2.05-.38-.03-.53-.08-.15-.68-1.64-.93-2.25-.24-.58-.49-.5-.68-.51h-.58c-.2 0-.53.07-.8.38-.27.3-1.05 1.03-1.05 2.5 0 1.47 1.08 2.9 1.23 3.1.15.2 2.12 3.24 5.14 4.54.72.31 1.29.5 1.73.64.73.23 1.39.2 1.91.12.58-.09 1.77-.72 2.02-1.42.25-.7.25-1.3.17-1.42-.08-.12-.28-.2-.58-.35Z" />
                          </svg>
                        </a>
                        <a
                          href={`https://mail.google.com/mail/?view=cm&fs=1&su=${encodeURIComponent("Mezcla Piroola")}&body=${encodeURIComponent(shareLink)}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          aria-label="Gmail"
                          title="Gmail"
                          className="flex h-10 w-10 items-center justify-center rounded-full border border-emerald-500/40 bg-emerald-500/10 text-emerald-200 transition hover:bg-emerald-500/20 hover:text-emerald-100"
                        >
                          <svg viewBox="0 0 24 24" className="h-5 w-5 fill-current" aria-hidden="true">
                            <path d="M20.5 4h-17A2.5 2.5 0 0 0 1 6.5v11A2.5 2.5 0 0 0 3.5 20h17a2.5 2.5 0 0 0 2.5-2.5v-11A2.5 2.5 0 0 0 20.5 4Zm-1.4 2L12 10.95 4.9 6h14.2ZM3.5 18.5a.5.5 0 0 1-.5-.5V7.55l8.4 5.85a1 1 0 0 0 1.2 0L21 7.55V18a.5.5 0 0 1-.5.5h-17Z" />
                          </svg>
                        </a>
                    </div>

                    <div className="mt-4 flex justify-end">
                        <button onClick={() => setIsShareModalOpen(false)} className="text-sm text-slate-400 hover:text-white">Cerrar</button>
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
                        {!report && loadingReport && (
                            <div className="flex h-40 items-center justify-center space-x-2">
                                <div className="h-3 w-3 animate-bounce rounded-full bg-emerald-500 delay-75"></div>
                                <div className="h-3 w-3 animate-bounce rounded-full bg-emerald-500 delay-150"></div>
                                <div className="h-3 w-3 animate-bounce rounded-full bg-emerald-500 delay-300"></div>
                            </div>
                        )}

                        {report && (
                            <ReportViewer report={report} jobId={jobId} authRedirectPath={`/mix/result/${jobId}`} />
                        )}

                        {!report && !loadingReport && (
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
    </div>
  );
}
