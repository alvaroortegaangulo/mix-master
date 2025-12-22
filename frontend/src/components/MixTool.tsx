"use client";

import { useState, useEffect, useMemo } from "react";
import {
  startMixJob,
  fetchJobStatus,
  type JobStatus,
  fetchPipelineStages,
  type PipelineStage,
  type StemProfilePayload,
  openJobStatusStream,
  cleanupTemp,
} from "../lib/mixApi";
import { getSongModeStages } from "../lib/mixUtils";
import dynamic from "next/dynamic";
import Script from "next/script";
import { UploadDropzone } from "./UploadDropzone";
import { type SpaceBus } from "./SpaceDepthStylePanel";
import { useAuth } from "../context/AuthContext";
import { gaEvent } from "../lib/ga";
import { useTranslations } from "next-intl";

const siteName = "Piroola";
const fallbackSiteUrl = "https://music-mix-master.com";
const siteUrl = (() => {
  // Safe check for window/process
  if (typeof process !== "undefined" && process.env.NEXT_PUBLIC_SITE_URL) {
      const envUrl = process.env.NEXT_PUBLIC_SITE_URL.trim();
      if (envUrl) {
          try {
             return new URL(envUrl).origin;
          } catch {
             return fallbackSiteUrl;
          }
      }
  }
  return fallbackSiteUrl;
})();

const HOMEPAGE_DESCRIPTION =
  "Transform your tracks with Piroola. Our AI-powered mixing and mastering service delivers professional studio-quality results from your multi-track stems in minutes.";

const MixResultPanel = dynamic(
  () => import("./MixResultPanel").then((mod) => mod.MixResultPanel),
  {
    loading: () => <p className="text-center text-teal-400">Loading result...</p>,
  }
);
const StemsProfilePanel = dynamic(
  () => import("./StemsProfilePanel").then((mod) => mod.StemsProfilePanel)
);
const SpaceDepthStylePanel = dynamic(
  () =>
    import("./SpaceDepthStylePanel").then(
      (mod) => mod.SpaceDepthStylePanel
    )
);

type StemProfile = {
  id: string;
  fileName: string;
  extension: string;
  profile: string;
};

type SpaceDepthBus = SpaceBus;


type StageUiInfo = {
  label: string;
  description: string;
};


type MixToolProps = {
  resumeJobId?: string;
};


function mapStemProfileToBusKey(profile: string): string {
  switch (profile) {
    case "Kick":
    case "Snare":
      return "drums";

    case "Percussion":
      return "percussion";

    case "Bass_Electric":
      return "bass";

    case "Acoustic_Guitar":
    case "Electric_Guitar_Rhythm":
      return "guitars";

    case "Keys_Piano":
    case "Synth_Pads":
      return "keys_synths";

    case "Lead_Vocal_Melodic":
    case "Lead_Vocal_Rap":
      return "lead_vocal";

    case "Backing_Vocals":
      return "bkg_vocals";

    case "FX_EarCandy":
      return "fx";

    case "Ambience_Atmos":
      return "ambience";

    default:
      return "other";
  }
}

export function MixTool({ resumeJobId }: MixToolProps) {
  const [uploadMode, setUploadMode] = useState<"song" | "stems">("stems");
  const [files, setFiles] = useState<File[]>([]);
  const [stemProfiles, setStemProfiles] = useState<StemProfile[]>([]);
  const [selectionWarning, setSelectionWarning] = useState<string | null>(null);

  const [loading, setLoading] = useState(false);
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(resumeJobId ?? null);

  const [availableStages, setAvailableStages] = useState<PipelineStage[]>([]);
  const [selectedStageKeys, setSelectedStageKeys] = useState<string[]>([]);
  const [showStageSelector, setShowStageSelector] = useState(true);
  const [isPipelineCollapsed, setIsPipelineCollapsed] = useState(true);
  const songModeStageKeys = useMemo(
    () => getSongModeStages(availableStages),
    [availableStages],
  );
  const isSongMode = uploadMode === "song";

  const t = useTranslations('MixTool');

  // UseAuth hook not used directly here for layout but context handles user state if needed for API calls implicitly if token is in storage.
  // Actually, we might need user info, but let's assume API handles it via token.

  const [spaceBusStyles, setSpaceBusStyles] = useState<Record<string, string>>(
     {},
  );

  const serviceJsonLd = useMemo(
    () => ({
      "@context": "https://schema.org",
      "@type": "Service",
      name: "AI Audio Mixing & Mastering",
      serviceType: "Audio mixing and mastering",
      provider: {
        "@type": "Organization",
        name: siteName,
        url: siteUrl,
      },
      url: siteUrl,
      description: HOMEPAGE_DESCRIPTION,
      areaServed: "Worldwide",
    }),
    [],
  );

  const STAGE_GROUP_LABELS: Record<string, string> = {
    S0: "NORMALIZE INPUT",
    S1: "TECHNICAL PREPARATION",
    S2: "PHASE & ALIGNMENT",
    S3: "MIXBUS PREP",
    S4: "FILTERS & RESONANCE",
    S5: "DYNAMICS",
    S6: "SPACE / REVERB",
    S7: "TONAL BALANCE",
    S8: "COLOR & SATURATION",
    S9: "MASTER PREP",
    S10: "FINAL QC",
    S11: "REPORTING",
    OTHER: "OTHER",
  };
  const STAGE_GROUP_ORDER = [
    "S0",
    "S1",
    "S2",
    "S3",
    "S4",
    "S5",
    "S6",
    "S7",
    "S8",
    "S9",
    "S10",
    "S11",
    "OTHER",
  ];

  // We construct this dynamically to use translations
  const HUMAN_STAGE_TEXT: Record<string, { title: string; description: string }> = {
    S0_SESSION_FORMAT: {
      title: t('stage.S0_SESSION_FORMAT.title'),
      description: t('stage.S0_SESSION_FORMAT.description'),
    },
    S1_STEM_DC_OFFSET: {
      title: t('stage.S1_STEM_DC_OFFSET.title'),
      description: t('stage.S1_STEM_DC_OFFSET.description'),
    },
    S1_STEM_WORKING_LOUDNESS: {
      title: t('stage.S1_STEM_WORKING_LOUDNESS.title'),
      description: t('stage.S1_STEM_WORKING_LOUDNESS.description'),
    },
    S1_KEY_DETECTION: {
      title: t('stage.S1_KEY_DETECTION.title'),
      description: t('stage.S1_KEY_DETECTION.description'),
    },
    S1_VOX_TUNING: {
      title: t('stage.S1_VOX_TUNING.title'),
      description: t('stage.S1_VOX_TUNING.description'),
    },
    S1_MIXBUS_HEADROOM: {
      title: t('stage.S1_MIXBUS_HEADROOM.title'),
      description: t('stage.S1_MIXBUS_HEADROOM.description'),
    },
    S2_GROUP_PHASE_DRUMS: {
      title: t('stage.S2_GROUP_PHASE_DRUMS.title'),
      description: t('stage.S2_GROUP_PHASE_DRUMS.description'),
    },
    S3_MIXBUS_HEADROOM: {
      title: t('stage.S3_MIXBUS_HEADROOM.title'),
      description: t('stage.S3_MIXBUS_HEADROOM.description'),
    },
    S3_LEADVOX_AUDIBILITY: {
      title: t('stage.S3_LEADVOX_AUDIBILITY.title'),
      description: t('stage.S3_LEADVOX_AUDIBILITY.description'),
    },
    S4_STEM_HPF_LPF: {
      title: t('stage.S4_STEM_HPF_LPF.title'),
      description: t('stage.S4_STEM_HPF_LPF.description'),
    },
    S4_STEM_RESONANCE_CONTROL: {
      title: t('stage.S4_STEM_RESONANCE_CONTROL.title'),
      description: t('stage.S4_STEM_RESONANCE_CONTROL.description'),
    },
    S5_STEM_DYNAMICS_GENERIC: {
      title: t('stage.S5_STEM_DYNAMICS_GENERIC.title'),
      description: t('stage.S5_STEM_DYNAMICS_GENERIC.description'),
    },
    S5_LEADVOX_DYNAMICS: {
      title: t('stage.S5_LEADVOX_DYNAMICS.title'),
      description: t('stage.S5_LEADVOX_DYNAMICS.description'),
    },
    S5_BUS_DYNAMICS_DRUMS: {
      title: t('stage.S5_BUS_DYNAMICS_DRUMS.title'),
      description: t('stage.S5_BUS_DYNAMICS_DRUMS.description'),
    },
    S6_MANUAL_CORRECTION: {
      title: t('stage.S6_MANUAL_CORRECTION.title'),
      description: t('stage.S6_MANUAL_CORRECTION.description'),
    },
    S7_MIXBUS_TONAL_BALANCE: {
      title: t('stage.S7_MIXBUS_TONAL_BALANCE.title'),
      description: t('stage.S7_MIXBUS_TONAL_BALANCE.description'),
    },
    S8_MIXBUS_COLOR_GENERIC: {
      title: t('stage.S8_MIXBUS_COLOR_GENERIC.title'),
      description: t('stage.S8_MIXBUS_COLOR_GENERIC.description'),
    },
    S9_MASTER_GENERIC: {
      title: t('stage.S9_MASTER_GENERIC.title'),
      description: t('stage.S9_MASTER_GENERIC.description'),
    },
    S10_MASTER_FINAL_LIMITS: {
      title: t('stage.S10_MASTER_FINAL_LIMITS.title'),
      description: t('stage.S10_MASTER_FINAL_LIMITS.description'),
    },
    S11_REPORT_GENERATION: {
      title: t('stage.S11_REPORT_GENERATION.title'),
      description: t('stage.S11_REPORT_GENERATION.description'),
    }
  };

  const STAGE_UI_INFO: Record<string, StageUiInfo> = {
    // We map keys to the translated Human Stage Text
    // This is a bit redundant but keeps structure if backend returns raw keys
    ...Object.entries(HUMAN_STAGE_TEXT).reduce((acc, [key, val]) => {
        acc[key] = { label: val.title.toUpperCase(), description: val.description };
        return acc;
    }, {} as Record<string, StageUiInfo>)
  };

  const SPACE_DEPTH_BUSES: SpaceDepthBus[] = [
    {
      key: "drums",
      label: t('spaceDepthBuses.drums.label'),
      description: t('spaceDepthBuses.drums.description'),
    },
    {
      key: "percussion",
      label: t('spaceDepthBuses.percussion.label'),
      description: t('spaceDepthBuses.percussion.description'),
    },
    {
      key: "bass",
      label: t('spaceDepthBuses.bass.label'),
      description: t('spaceDepthBuses.bass.description'),
    },
    {
      key: "guitars",
      label: t('spaceDepthBuses.guitars.label'),
      description: t('spaceDepthBuses.guitars.description'),
    },
    {
      key: "keys_synths",
      label: t('spaceDepthBuses.keys_synths.label'),
      description: t('spaceDepthBuses.keys_synths.description'),
    },
    {
      key: "lead_vocal",
      label: t('spaceDepthBuses.lead_vocal.label'),
      description: t('spaceDepthBuses.lead_vocal.description'),
    },
    {
      key: "backing_vocals",
      label: t('spaceDepthBuses.backing_vocals.label'),
      description: t('spaceDepthBuses.backing_vocals.description'),
    },
    {
      key: "fx",
      label: t('spaceDepthBuses.fx.label'),
      description: t('spaceDepthBuses.fx.description'),
    },
    {
      key: "ambience",
      label: t('spaceDepthBuses.ambience.label'),
      description: t('spaceDepthBuses.ambience.description'),
    },
    {
      key: "other",
      label: t('spaceDepthBuses.other.label'),
      description: t('spaceDepthBuses.other.description'),
    },
  ];

useEffect(() => {
  // No limpiar si estamos reanudando un job, para no borrar correcciones guardadas
  if (resumeJobId) return;
  cleanupTemp().catch((err) => {
    console.error("Error cleaning temp on page load", err);
  });
}, [resumeJobId]);

useEffect(() => {
  if (resumeJobId) {
    setJobStatus(null);
    setError(null);
    setActiveJobId(resumeJobId);
  }
}, [resumeJobId]);

useEffect(() => {
  if (!activeJobId) return;

  let cancelled = false;
  let finished = false;
  let stopPolling: (() => void) | null = null;
  let wsHandle: { close: () => void } | null = null;

  setLoading(true);
  setError(null);

  const applyStatus = (status: JobStatus) => {
    if (cancelled) return;
    setJobStatus(status);
    setError(null);

    if (status.stageKey === "waiting_for_correction") {
      finished = true;
      setLoading(false);
      wsHandle?.close();
      window.location.href = `/studio/${activeJobId}`;
      return;
    }

    if (status.status === "done") {
      finished = true;
      setLoading(false);
      wsHandle?.close();
      return;
    }

    if (status.status === "error") {
      finished = true;
      setError(status.error ?? "Error processing mix");
      setLoading(false);
      wsHandle?.close();
      return;
    }

    if (status.status === "queued" || status.status === "running") {
      setLoading(true);
    }
  };

  const startPolling = () => {
    if (stopPolling) return;
    let stopped = false;
    let consecutiveErrors = 0;

    const pollStatus = async () => {
      while (!cancelled && !stopped && !finished) {
        try {
          const status = await fetchJobStatus(activeJobId);
          if (cancelled || stopped) break;
          applyStatus(status);
          consecutiveErrors = 0;
        } catch (err: any) {
          if (!cancelled) {
            consecutiveErrors += 1;
            setError(err.message ?? "Unknown error");
            setLoading(true);
          }
        }

        const delayMs =
          consecutiveErrors > 0
            ? Math.min(5000, 1000 * (consecutiveErrors + 1))
            : 1000;
        await new Promise((resolve) => setTimeout(resolve, delayMs));
      }
    };

    void pollStatus();
    stopPolling = () => {
      stopped = true;
    };
  };

  wsHandle = openJobStatusStream(activeJobId, {
    onOpen: () => {
      if (!finished) setLoading(true);
    },
    onStatus: (status) => {
      applyStatus(status);
    },
    onError: () => {
      if (!cancelled && !finished) {
        wsHandle?.close();
        wsHandle = null;
        startPolling();
      }
    },
    onClose: () => {
      if (!cancelled && !finished) {
        startPolling();
      }
    },
  });

  // Always poll as a fallback for reliability (e.g. dropped WS messages)
  startPolling();

  return () => {
    cancelled = true;
    finished = true;
    if (stopPolling) {
      stopPolling();
      stopPolling = null;
    }
    if (wsHandle) {
      wsHandle.close();
      wsHandle = null;
    }
  };
}, [activeJobId]);


  // Cargar definición de stages del backend
  useEffect(() => {
    async function loadStages() {
      try {
        const stages = await fetchPipelineStages();
        setAvailableStages(stages);
      } catch (err: any) {
        console.error("Error fetching pipeline stages", err);
      }
    }
    void loadStages();
  }, []);
  
  // Sync default stage selection with the current upload mode
  useEffect(() => {
    if (!availableStages.length) return;
  
    const nextKeys =
      uploadMode === "song"
        ? songModeStageKeys
        : availableStages.map((s) => s.key);
  
    setSelectedStageKeys(nextKeys);
  }, [availableStages, uploadMode, songModeStageKeys]);

  const toggleStage = (key: string) => {
    setSelectedStageKeys((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key],
    );
  };

  const selectAllStages = () => {
    if (isSongMode) {
      setSelectedStageKeys(songModeStageKeys);
      return;
    }
    setSelectedStageKeys(availableStages.map((s) => s.key));
  };

  const clearStages = () => {
    setSelectedStageKeys([]);
  };

  const groupedStages = useMemo(() => {
    const groups: Record<string, PipelineStage[]> = {};
    for (const stage of availableStages) {
      const prefix = stage.key.split("_")[0] || "OTHER";
      if (!groups[prefix]) {
        groups[prefix] = [];
      }
      groups[prefix].push(stage);
    }
    return groups;
  }, [availableStages]);


  const visibleSpaceDepthBuses = useMemo(() => {
    if (!stemProfiles.length) return [];
    const usedBusKeys = new Set<string>();
    for (const stem of stemProfiles) {
      const busKey = mapStemProfileToBusKey(stem.profile || "auto");
      usedBusKeys.add(busKey);
    }
    return SPACE_DEPTH_BUSES.filter((bus) => usedBusKeys.has(bus.key));
  }, [stemProfiles]);

  const handleBusStyleChange = (busKey: string, style: string) => {
    setSpaceBusStyles((prev) => {
      const next = { ...prev };
      if (style === "auto") {
        delete next[busKey];
      } else {
        next[busKey] = style;
      }
      return next;
    });
  };

  const handleModeChange = (mode: "song" | "stems") => {
    setUploadMode(mode);
    setFiles([]); // Reset files on mode change
    setJobStatus(null);
    setActiveJobId(null);
    setLoading(false);
    setError(null);
    setStemProfiles([]);
    setSpaceBusStyles({});
    setSelectionWarning(null);
  };

  const handleFilesSelected = (selected: File[]) => {
    setJobStatus(null);
    setActiveJobId(null);
    setLoading(false);
    setError(null);
    setSelectionWarning(null);
    setShowStageSelector(true);
    setIsPipelineCollapsed(true);
    setSpaceBusStyles({});
    setFiles([]);
    setStemProfiles([]);

    if (isSongMode) {
      if (selected.length !== 1) {
        setError(t('songModeWarning'));
        return;
      }

      const [file] = selected;
      const name = file.name.toLowerCase();
      const isWav =
        name.endsWith(".wav") ||
        file.type === "audio/wav" ||
        file.type === "audio/x-wav";

      if (!isWav) {
        setError(t('songModeWarning'));
        return;
      }

      setFiles([file]);
      return;
    }

    if (selected.length === 1) {
      setSelectionWarning(
        t('selectionWarning')
      );
    }

    setFiles(selected);

    // Track upload start/selection
    gaEvent("upload_stems", {
        mode: uploadMode,
        file_count: selected.length,
        total_size_mb: Math.round(selected.reduce((acc, f) => acc + f.size, 0) / (1024 * 1024)),
        format: selected[0]?.type || "unknown",
    });

    const newProfiles: StemProfile[] = selected.map((file, index) => {
      const dotIndex = file.name.lastIndexOf(".");
      let baseName = file.name;
      let ext = "";
      if (dotIndex !== -1) {
        baseName = file.name.slice(0, dotIndex);
        ext = file.name.slice(dotIndex + 1);
      }
      return {
        id: `${file.name}-${index}`,
        fileName: baseName,
        extension: ext,
        profile: "auto",
      };
    });
    setStemProfiles(newProfiles);
  };

  const handleStemProfileChange = (id: string, profile: string) => {
    setStemProfiles((prev) =>
      prev.map((stem) =>
        stem.id === id ? { ...stem, profile } : stem,
      ),
    );
  };

  const hasFiles = files.length > 0;

  const handleGenerateMix = async () => {
    if (!files.length) return;
    setLoading(true);
    setError(null);
    setJobStatus(null);
    setActiveJobId(null);

    try {
      const enabled =
        selectedStageKeys.length > 0 ? selectedStageKeys : undefined;

      const stemProfilesPayload: StemProfilePayload[] = stemProfiles.map(
        (sp) => ({
          name: sp.extension
            ? `${sp.fileName}.${sp.extension}`
            : sp.fileName,
          profile: sp.profile || "auto",
        }),
      );

      // Payload opcional de Space / Depth:
      // solo enviamos buses donde se haya elegido algo distinto de "auto"
      const spaceDepthBusStylesPayload =
        Object.keys(spaceBusStyles).length > 0
          ? { ...spaceBusStyles }
          : undefined;


      // Ocultar a la vez Pipeline steps + Select stems profile
      setStemProfiles([]);
      setShowStageSelector(false);
      setSpaceBusStyles({});

      const { jobId } = await startMixJob(
        files,
        enabled,
        stemProfilesPayload,
        spaceDepthBusStylesPayload,
      );

      // Track job start
      gaEvent("mix_job_started", {
        job_id: jobId,
        mode: uploadMode,
        files_count: files.length,
        pipeline_stages_count: enabled?.length ?? 0,
      });

      const totalStages =
        enabled?.length ?? availableStages.length ?? 0;

      setJobStatus({
        jobId,
        status: "queued",
        stageIndex: 0,
        totalStages,
        stageKey: "queued",
        message: "Job queued...",
        progress: 0,
      });

      setActiveJobId(jobId);
    } catch (err: any) {
      setError(err.message ?? "Unknown error");
      setLoading(false);
    }
  };

  const result =
    jobStatus?.status === "done" && jobStatus.result
      ? jobStatus.result
      : null;



  const stageUiInfo: StageUiInfo | null =
    jobStatus && jobStatus.stageKey
      ? STAGE_UI_INFO[jobStatus.stageKey] ?? null
      : null;



  const progressInfo = useMemo(() => {
    if (
      !jobStatus ||
      (jobStatus.status !== "queued" && jobStatus.status !== "running")
    ) {
      return null;
    }

    const percent = Math.round(jobStatus.progress ?? 0);

    // Queued state
    if (jobStatus.status === "queued") {
      return {
        percent,
        title: (t("waitingQueue") || "Queue").toUpperCase(),
        description: jobStatus.message || "Waiting for worker...",
      };
    }

    // Running state
    const title =
      stageUiInfo?.label || jobStatus.stageKey?.toUpperCase() || "PROCESSING";
    const description = stageUiInfo?.description || jobStatus.message || "";

    return { percent, title, description };
  }, [jobStatus, stageUiInfo, t]);

    const isProcessing =
    loading ||
    (jobStatus &&
      (jobStatus.status === "queued" || jobStatus.status === "running"));


  return (
    <div className="flex-1 flex flex-col">
      <Script
        id="ld-service"
        type="application/ld+json"
        strategy="afterInteractive"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(serviceJsonLd) }}
      />
      {/* Layout: grid con 3 columnas a partir de lg.
          Centro más estrecho en portátiles, más ancho en pantallas grandes */}
      <main className="flex flex-1 items-stretch justify-center px-4 py-8">
        <div
          className="
            w-full mx-auto grid grid-cols-1
            lg:grid-cols-[minmax(0,1fr)_minmax(auto,36rem)_minmax(0,1fr)]
            2xl:grid-cols-[minmax(0,1fr)_minmax(auto,48rem)_minmax(0,1fr)]
            gap-8
          "
        >

{/* Columna izquierda (1ª columna en lg+): estilos Space / Depth por bus */}
<div className="lg:col-start-1">
  <h2 className="sr-only">Space & Depth Settings</h2>
  {stemProfiles.length > 0 &&
    visibleSpaceDepthBuses.length > 0 && (
      <div className="w-full max-w-xs mx-auto">
        <SpaceDepthStylePanel
          buses={visibleSpaceDepthBuses}
          value={spaceBusStyles}
          onChange={handleBusStyleChange}
        />
      </div>
    )}
</div>
          {/* Columna central */}
          <div className="lg:col-start-2 flex justify-center">
            <div className="w-full max-w-3xl">
              <section
                id="how-it-works"
                className="rounded-2xl border border-slate-700/60 bg-slate-900/60 p-8 shadow-2xl shadow-slate-900/50"
              >
                <h2 className="sr-only">{t('uploadMixConfig')}</h2>

                <div className="mb-6 flex justify-center">
                  <div className="inline-flex rounded-lg bg-slate-950 p-1 shadow-inner shadow-slate-900">
                    <button
                      type="button"
                      onClick={() => handleModeChange("song")}
                      className={`rounded-md px-6 py-2 text-sm font-semibold transition-colors ${
                        uploadMode === "song"
                          ? "bg-teal-500 text-slate-950 shadow-sm"
                          : "text-slate-400 hover:text-slate-200"
                      }`}
                    >
                      {t('songMode')}
                    </button>
                    <button
                      type="button"
                      onClick={() => handleModeChange("stems")}
                      className={`rounded-md px-6 py-2 text-sm font-semibold transition-colors ${
                        uploadMode === "stems"
                          ? "bg-teal-500 text-slate-950 shadow-sm"
                          : "text-slate-400 hover:text-slate-200"
                      }`}
                    >
                      {t('stemsMode')}
                    </button>
                  </div>
                </div>

                <div id="upload">
                  <UploadDropzone
                    onFilesSelected={handleFilesSelected}
                    disabled={loading}
                    filesCount={files.length}
                    uploadMode={uploadMode}
                  />
                </div>

                {selectionWarning && (
                  <div className="mt-3 rounded-md border border-amber-400/60 bg-amber-500/10 px-3 py-2 text-xs text-amber-100">
                    {selectionWarning}
                  </div>
                )}

                {showStageSelector && availableStages.length > 0 && (
                  <section className="mt-6 rounded-2xl border border-amber-500/40 bg-amber-500/10 text-amber-50 shadow-lg shadow-amber-500/20">
                    {/* Cabecera plegable */}
                    <button
                      type="button"
                      onClick={() =>
                        setIsPipelineCollapsed((prev) => !prev)
                      }
                      className="flex w-full items-center justify-between px-4 py-3 text-xs font-semibold uppercase tracking-wide text-amber-100 hover:bg-amber-500/15"
                      aria-expanded={!isPipelineCollapsed}
                    >
                      <span>{t('pipelineSteps')}</span>
                      <span className="flex items-center gap-2 text-[11px] text-amber-200 normal-case">
                        <span>
                          {selectedStageKeys.length} /{" "}
                          {availableStages.length} {t('enabled')}
                        </span>
                        <span className="text-amber-300">
                          {isPipelineCollapsed ? "▼" : "▲"}
                        </span>
                      </span>
                    </button>

                    {/* Contenido expandible */}
                    {!isPipelineCollapsed && (
                      <div className="border-t border-amber-500/40 px-4 py-3">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-[11px] font-medium text-amber-100">
                            {t('pipelineStepsDesc')}
                          </span>
                          <div className="flex gap-2">
                            <button
                              type="button"
                              onClick={selectAllStages}
                              className="rounded-full bg-amber-600/80 px-2.5 py-1 text-[11px] text-amber-50 hover:bg-amber-500"
                            >
                              {t('all')}
                            </button>
                            <button
                              type="button"
                              onClick={clearStages}
                              className="rounded-full bg-amber-600/80 px-2.5 py-1 text-[11px] text-amber-50 hover:bg-amber-500"
                            >
                              {t('none')}
                            </button>
                          </div>
                        </div>

                        <div className="mt-5 space-y-4">
                          {[...STAGE_GROUP_ORDER, ...Object.keys(groupedStages).filter((g) => !STAGE_GROUP_ORDER.includes(g))].map((groupKey) => {
                            const stages = groupedStages[groupKey];
                            if (!stages || stages.length === 0) return null;
                            return (
                              <div
                                key={groupKey}
                                className="relative rounded-2xl border-2 border-dashed border-amber-500/60 bg-amber-500/5 px-3 py-3"
                              >
                                <span className="absolute -top-3 right-4 rounded-full bg-slate-950 px-3 py-1 text-[11px] font-semibold tracking-wide text-amber-100 shadow">
                                  {STAGE_GROUP_LABELS[groupKey] ?? groupKey}
                                </span>
                                <div className="space-y-2">
                                  {stages.map((stage) => {
                                    const isDisabledForSong =
                                      isSongMode &&
                                      !songModeStageKeys.includes(stage.key);
                                    return (
                                    <label
                                      key={stage.key}
                                      className={[
                                        "flex items-start gap-2 rounded-lg bg-slate-950/70 px-3 py-2 text-xs text-amber-50",
                                        isDisabledForSong
                                          ? "cursor-not-allowed opacity-60"
                                          : "cursor-pointer hover:bg-slate-900",
                                      ].join(" ")}
                                    >
                                      <input
                                        type="checkbox"
                                        className="mt-[2px] h-3.5 w-3.5 rounded border-amber-400 bg-slate-950 text-amber-200 focus:ring-amber-400"
                                        checked={selectedStageKeys.includes(
                                          stage.key,
                                        )}
                                        onChange={() => toggleStage(stage.key)}
                                        disabled={isDisabledForSong}
                                      />
                                      <div>
                                        <span className="font-semibold">
                                          {HUMAN_STAGE_TEXT[stage.key]?.title ??
                                            stage.label}
                                        </span>
                                        <p className="mt-0.5 text-[11px] text-amber-200/80">
                                          {HUMAN_STAGE_TEXT[stage.key]?.description ??
                                            stage.description ??
                                            ""}
                                        </p>
                                      </div>
                                    </label>
                                    );
                                  })}
                                </div>
                              </div>
                            );
                          })}
                        </div>


                      </div>
                    )}
                  </section>
                )}

                <div className="mt-8 flex justify-center">
                  <button
                    type="button"
                    onClick={handleGenerateMix}
                    disabled={!hasFiles || loading}
                    className={[
                      "inline-flex items-center justify-center rounded-full px-6 py-2.5 text-sm font-semibold",
                      "bg-teal-500 text-slate-950 shadow-md shadow-teal-500/30",
                      "transition hover:bg-teal-400 hover:shadow-lg disabled:opacity-60 disabled:cursor-not-allowed",
                    ].join(" ")}
                  >
                    {loading ? t('processing') : t('generateMix')}
                  </button>
                </div>

      {progressInfo && (
        <div className="mx-auto mt-6 w-full max-w-md select-none">
          {/* Progress Bar Row */}
          <div className="mb-2 flex items-center gap-3">
            <div className="flex-1 overflow-hidden rounded-full border border-slate-800 bg-slate-950/50 h-2.5">
              <div
                className="relative h-full bg-amber-500 shadow-[0_0_12px_rgba(245,158,11,0.6)] transition-all duration-300 ease-out"
                style={{ width: `${progressInfo.percent}%` }}
              >
                <div className="absolute inset-0 bg-white/20" />
              </div>
            </div>
            <span className="min-w-[3ch] text-right font-mono text-sm font-bold text-amber-400">
              {progressInfo.percent}%
            </span>
          </div>

          {/* Title */}
          <h3 className="mb-1 text-center text-xs font-bold uppercase tracking-[0.15em] text-amber-100">
            {progressInfo.title}
          </h3>

          {/* Description */}
          <p className="mx-auto max-w-xs text-center text-[11px] font-medium leading-relaxed text-amber-200/70">
            {progressInfo.description}
          </p>
        </div>
      )}

                {error && (
                  <p className="text-center text-sm text-red-400">
                    {error}
                  </p>
                )}

              </section>

              {isProcessing && (
                <div className="flex justify-center">
                  <video
                    src="/loading.mp4"
                    autoPlay
                    loop
                    muted
                    playsInline
                    aria-label="Processing your mix..."
                    className="h-24 w-auto rounded-lg"
                  />
                </div>
              )}

              {result && (
                <MixResultPanel
                  result={result}
                  enabledPipelineStageKeys={selectedStageKeys}
                />
              )}
            </div>
          </div>

          {/* Columna derecha: panel de perfiles centrado */}
          <div className="lg:col-start-3">
            <h2 className="sr-only">Stem Profiles</h2>
            {stemProfiles.length > 0 && (
              <div className="w-full max-w-xs mx-auto">
                <StemsProfilePanel
                  stems={stemProfiles}
                  onChangeProfile={handleStemProfileChange}
                />
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

