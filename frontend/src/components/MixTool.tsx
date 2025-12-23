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
import { gaEvent } from "../lib/ga";
import { useTranslations } from "next-intl";

const siteName = "Piroola";
const fallbackSiteUrl = "https://music-mix-master.com";
const siteUrl = (() => {
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

// --- Pipeline Configuration & Utilities ---

// Mapping individual stage IDs to Group IDs
const STAGE_TO_GROUP: Record<string, string> = {
  S0_SESSION_FORMAT: "HIDDEN",
  S1_STEM_DC_OFFSET: "TECHNICAL_PREPARATION",
  S1_STEM_WORKING_LOUDNESS: "TECHNICAL_PREPARATION",
  S1_KEY_DETECTION: "TECHNICAL_PREPARATION",
  S1_VOX_TUNING: "TECHNICAL_PREPARATION",
  S1_MIXBUS_HEADROOM: "TECHNICAL_PREPARATION",
  S2_GROUP_PHASE_DRUMS: "PHASE_ALIGNMENT",
  S3_MIXBUS_HEADROOM: "MIXBUS_PREP",
  S3_LEADVOX_AUDIBILITY: "MIXBUS_PREP",
  S4_STEM_HPF_LPF: "SPECTRAL_CLEANUP",
  S4_STEM_RESONANCE_CONTROL: "SPECTRAL_CLEANUP",
  S5_STEM_DYNAMICS_GENERIC: "DYNAMICS",
  S5_LEADVOX_DYNAMICS: "DYNAMICS",
  S5_BUS_DYNAMICS_DRUMS: "DYNAMICS",
  S6_BUS_REVERB_STYLE: "SPACE",
  S6_MANUAL_CORRECTION: "MANUAL_CORRECTION",
  S7_MIXBUS_TONAL_BALANCE: "MASTERING",
  S8_MIXBUS_COLOR_GENERIC: "MASTERING",
  S9_MASTER_GENERIC: "MASTERING",
  S10_MASTER_FINAL_LIMITS: "MASTERING",
  S11_REPORT_GENERATION: "HIDDEN",
};

// Estimated processing time in minutes per stage
const STAGE_ESTIMATES_MIN: Record<string, number> = {
  S0_SESSION_FORMAT: 0.5,
  S1_STEM_DC_OFFSET: 0.5,
  S1_STEM_WORKING_LOUDNESS: 0.5,
  S1_KEY_DETECTION: 0.2,
  S1_VOX_TUNING: 1.0,
  S1_MIXBUS_HEADROOM: 0.2,
  S2_GROUP_PHASE_DRUMS: 0.8,
  S3_MIXBUS_HEADROOM: 0.2,
  S3_LEADVOX_AUDIBILITY: 0.5,
  S4_STEM_HPF_LPF: 0.8,
  S4_STEM_RESONANCE_CONTROL: 1.2,
  S5_STEM_DYNAMICS_GENERIC: 1.0,
  S5_LEADVOX_DYNAMICS: 0.8,
  S5_BUS_DYNAMICS_DRUMS: 0.8,
  S6_MANUAL_CORRECTION: 0, // Manual step
  S7_MIXBUS_TONAL_BALANCE: 1.0,
  S8_MIXBUS_COLOR_GENERIC: 0.8,
  S9_MASTER_GENERIC: 0.8,
  S10_MASTER_FINAL_LIMITS: 0.5,
  S11_REPORT_GENERATION: 0.5,
};

type GroupConfig = {
  id: string;
  labelKey: string; // Key within 'MixTool.stageGroups'
};

const GROUPS_CONFIG: GroupConfig[] = [
  { id: "TECHNICAL_PREPARATION", labelKey: "technicalPreparation" },
  { id: "PHASE_ALIGNMENT", labelKey: "phaseAlignment" },
  { id: "MIXBUS_PREP", labelKey: "mixBusPrep" },
  { id: "SPECTRAL_CLEANUP", labelKey: "spectralCleanup" },
  { id: "DYNAMICS", labelKey: "dynamics" },
  { id: "SPACE", labelKey: "space" },
  { id: "MANUAL_CORRECTION", labelKey: "manualCorrection" },
  { id: "MASTERING", labelKey: "mastering" },
];

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

  // Group expansion state
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({});

  const songModeStageKeys = useMemo(
    () => getSongModeStages(availableStages),
    [availableStages],
  );
  const isSongMode = uploadMode === "song";

  const t = useTranslations('MixTool');

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

  // Load translations for stages
  const HUMAN_STAGE_TEXT: Record<string, { title: string; description: string }> = useMemo(() => {
    // We assume backend stage keys might be stable, otherwise fallback to raw key
    // We'll iterate availableStages or known keys if needed.
    // For now, mapping known keys from the big list.
    const keys = Object.keys(STAGE_TO_GROUP);
    const map: Record<string, { title: string; description: string }> = {};
    keys.forEach(k => {
      // @ts-ignore - dynamic key access
      map[k] = {
        title: t(`stage.${k}.title`),
        description: t(`stage.${k}.description`),
      };
    });
    return map;
  }, [t]);

  const STAGE_UI_INFO: Record<string, StageUiInfo> = {
     ...Object.entries(HUMAN_STAGE_TEXT).reduce((acc, [key, val]) => {
        acc[key] = { label: val.title.toUpperCase(), description: val.description };
        return acc;
    }, {} as Record<string, StageUiInfo>)
  };

  const SPACE_DEPTH_BUSES: SpaceDepthBus[] = [
    { key: "drums", label: t('spaceDepthBuses.drums.label'), description: t('spaceDepthBuses.drums.description') },
    { key: "percussion", label: t('spaceDepthBuses.percussion.label'), description: t('spaceDepthBuses.percussion.description') },
    { key: "bass", label: t('spaceDepthBuses.bass.label'), description: t('spaceDepthBuses.bass.description') },
    { key: "guitars", label: t('spaceDepthBuses.guitars.label'), description: t('spaceDepthBuses.guitars.description') },
    { key: "keys_synths", label: t('spaceDepthBuses.keys_synths.label'), description: t('spaceDepthBuses.keys_synths.description') },
    { key: "lead_vocal", label: t('spaceDepthBuses.lead_vocal.label'), description: t('spaceDepthBuses.lead_vocal.description') },
    { key: "backing_vocals", label: t('spaceDepthBuses.backing_vocals.label'), description: t('spaceDepthBuses.backing_vocals.description') },
    { key: "fx", label: t('spaceDepthBuses.fx.label'), description: t('spaceDepthBuses.fx.description') },
    { key: "ambience", label: t('spaceDepthBuses.ambience.label'), description: t('spaceDepthBuses.ambience.description') },
    { key: "other", label: t('spaceDepthBuses.other.label'), description: t('spaceDepthBuses.other.description') },
  ];

  useEffect(() => {
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
  
    // Default: Select all available stages (full mix)
    // For Song mode, filtering is applied via isSongMode logic or separate key list
    const keys = uploadMode === "song"
       ? songModeStageKeys
       : availableStages.map(s => s.key);

    setSelectedStageKeys(keys);
  }, [availableStages, uploadMode, songModeStageKeys]);

  const toggleStage = (key: string) => {
    if (isSongMode && !songModeStageKeys.includes(key)) return; // Cannot toggle disabled in song mode

    setSelectedStageKeys((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key],
    );
  };

  const selectAllStages = () => {
    if (isSongMode) {
      setSelectedStageKeys(songModeStageKeys);
      return;
    }
    // Select all available
    setSelectedStageKeys(availableStages.map((s) => s.key));
  };

  const clearStages = () => {
    // Keep hidden stages if we want to ensure S0/S11 run,
    // but typically the list is empty and we re-inject hidden ones on submit.
    // However, keeping them in state is safer if submit logic relies on it.
    // We'll filter only visible ones.
    const hiddenKeys = availableStages
        .filter(s => STAGE_TO_GROUP[s.key] === "HIDDEN")
        .map(s => s.key);

    setSelectedStageKeys(hiddenKeys);
  };

  // Grouping Logic
  const groupedStages = useMemo(() => {
    const groups: Record<string, PipelineStage[]> = {};

    // Initialize groups from config to ensure order
    GROUPS_CONFIG.forEach(c => { groups[c.id] = []; });
    groups["OTHER"] = [];

    availableStages.forEach(stage => {
      const groupKey = STAGE_TO_GROUP[stage.key] || "OTHER";
      if (groupKey === "HIDDEN") return; // Skip hidden stages in UI
      if (!groups[groupKey]) groups[groupKey] = [];
      groups[groupKey].push(stage);
    });

    return groups;
  }, [availableStages]);

  const toggleGroup = (groupId: string) => {
    if (!groupedStages[groupId]) return;

    const groupStages = groupedStages[groupId];
    const groupStageKeys = groupStages.map(s => s.key);

    // Check if all relevant stages in this group are selected
    // For song mode, we only care about intersection with songModeStageKeys
    const relevantKeys = isSongMode
      ? groupStageKeys.filter(k => songModeStageKeys.includes(k))
      : groupStageKeys;

    if (relevantKeys.length === 0) return; // Nothing to toggle

    const allSelected = relevantKeys.every(k => selectedStageKeys.includes(k));

    if (allSelected) {
      // Deselect all
      setSelectedStageKeys(prev => prev.filter(k => !relevantKeys.includes(k)));
    } else {
      // Select all
      setSelectedStageKeys(prev => {
        const unique = new Set([...prev, ...relevantKeys]);
        return Array.from(unique);
      });
    }
  };

  const toggleGroupExpand = (groupId: string) => {
    setExpandedGroups(prev => ({
      ...prev,
      [groupId]: !prev[groupId]
    }));
  };

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
    setFiles([]);
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
      const isSupported =
        name.endsWith(".wav") ||
        name.endsWith(".aif") ||
        name.endsWith(".aiff") ||
        name.endsWith(".mp3") ||
        [
          "audio/wav",
          "audio/x-wav",
          "audio/aiff",
          "audio/x-aiff",
          "audio/mpeg",
          "audio/mp3",
        ].includes(file.type);

      if (!isSupported) {
        setError(t('songModeWarning'));
        return;
      }
      setFiles([file]);
      return;
    }

    if (selected.length === 1) {
      setSelectionWarning(t('selectionWarning'));
    }

    setFiles(selected);

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

  const estimatedMinutes = useMemo(() => {
    if (!selectedStageKeys.length) return 0;

    let total = 0;
    // Always include hidden mandatory stages in calculation if they will run
    // Assuming S0 and S11 run if we submit
    total += STAGE_ESTIMATES_MIN["S0_SESSION_FORMAT"] || 0;
    total += STAGE_ESTIMATES_MIN["S11_REPORT_GENERATION"] || 0;

    selectedStageKeys.forEach(key => {
        if (STAGE_TO_GROUP[key] !== "HIDDEN") {
           total += STAGE_ESTIMATES_MIN[key] || 0.5;
        }
    });

    return Math.ceil(total);
  }, [selectedStageKeys]);

  const handleGenerateMix = async () => {
    if (!files.length) return;
    setLoading(true);
    setError(null);
    setJobStatus(null);
    setActiveJobId(null);

    try {
      // Ensure hidden stages are included
      const hiddenStages = availableStages
        .filter(s => STAGE_TO_GROUP[s.key] === "HIDDEN")
        .map(s => s.key);

      const finalKeys = Array.from(new Set([...selectedStageKeys, ...hiddenStages]));
      const enabled = finalKeys.length > 0 ? finalKeys : undefined;

      const stemProfilesPayload: StemProfilePayload[] = stemProfiles.map(
        (sp) => ({
          name: sp.extension
            ? `${sp.fileName}.${sp.extension}`
            : sp.fileName,
          profile: sp.profile || "auto",
        }),
      );

      const spaceDepthBusStylesPayload =
        Object.keys(spaceBusStyles).length > 0
          ? { ...spaceBusStyles }
          : undefined;

      setStemProfiles([]);
      setShowStageSelector(false);
      setSpaceBusStyles({});

      const { jobId } = await startMixJob(
        files,
        enabled,
        stemProfilesPayload,
        spaceDepthBusStylesPayload,
      );

      gaEvent("mix_job_started", {
        job_id: jobId,
        mode: uploadMode,
        files_count: files.length,
        pipeline_stages_count: enabled?.length ?? 0,
      });

      const totalStages = enabled?.length ?? availableStages.length ?? 0;

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

    if (jobStatus.status === "queued") {
      return {
        percent,
        title: (t("waitingQueue") || "Queue").toUpperCase(),
        description: jobStatus.message || "Waiting for worker...",
      };
    }

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

      <main className="flex flex-1 items-stretch justify-center px-4 py-8">
        <div
          className="
            w-full mx-auto grid grid-cols-1
            lg:grid-cols-[minmax(0,1fr)_minmax(auto,36rem)_minmax(0,1fr)]
            2xl:grid-cols-[minmax(0,1fr)_minmax(auto,48rem)_minmax(0,1fr)]
            gap-8
          "
        >

          {/* Left Column: Space & Depth Settings */}
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

          {/* Center Column */}
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
                  <section className="mt-8">
                     <div className="flex items-center justify-between mb-4">
                        <h3 className="text-lg font-bold text-white tracking-wide flex items-center gap-2">
                           <span className="text-teal-400 text-xl">⚡</span> Pipeline IA
                        </h3>
                        <span className="text-xs font-mono uppercase text-teal-400 bg-teal-500/10 px-2 py-1 rounded border border-teal-500/20">
                           AUTO-PILOT ON
                        </span>
                     </div>
                     <p className="text-slate-400 text-sm mb-6">Cadena de procesamiento activa</p>

                     <div className="space-y-4">
                        {GROUPS_CONFIG.map(group => {
                            const stages = groupedStages[group.id];
                            if (!stages || stages.length === 0) return null;

                            const isExpanded = expandedGroups[group.id] || false;

                            // Check group selection state
                            // For song mode, only check relevant keys
                            const relevantKeys = isSongMode
                               ? stages.map(s => s.key).filter(k => songModeStageKeys.includes(k))
                               : stages.map(s => s.key);

                            // If no relevant keys in this group, maybe hide or disable?
                            // For now we keep showing but disabled state handles interactivity
                            const groupHasActiveStages = relevantKeys.length > 0;
                            const isGroupSelected = groupHasActiveStages && relevantKeys.every(k => selectedStageKeys.includes(k));
                            const isGroupPartiallySelected = groupHasActiveStages && !isGroupSelected && relevantKeys.some(k => selectedStageKeys.includes(k));

                            return (
                                <div key={group.id} className="rounded-xl border border-slate-700 bg-slate-900/50 overflow-hidden transition-all duration-300 hover:border-slate-600">
                                   {/* Group Header */}
                                   <div className="flex items-center justify-between p-4 bg-slate-900/80">
                                      <div className="flex items-center gap-4 flex-1 cursor-pointer" onClick={() => toggleGroupExpand(group.id)}>
                                         <div className={`p-2 rounded-lg ${isGroupSelected ? 'bg-teal-500/20 text-teal-400' : 'bg-slate-800 text-slate-500'}`}>
                                            {/* Icon Placeholder - could map icons per group later */}
                                            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                                            </svg>
                                         </div>
                                         <div>
                                            <h4 className="text-sm font-semibold text-slate-200">
                                                {/* @ts-ignore dynamic key */}
                                                {t(`stageGroups.${group.labelKey}`)}
                                            </h4>
                                            <p className="text-xs text-slate-500 mt-0.5">
                                                {stages.length} stages • {isGroupSelected ? "Active" : "Modified"}
                                            </p>
                                         </div>
                                      </div>

                                      <div className="flex items-center gap-3">
                                          <button
                                            onClick={() => toggleGroupExpand(group.id)}
                                            className="text-slate-500 hover:text-slate-300 transition-colors"
                                          >
                                              <span className={`inline-block transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`}>▼</span>
                                          </button>

                                          {/* Master Toggle */}
                                          <label className="relative inline-flex items-center cursor-pointer">
                                            <input
                                                type="checkbox"
                                                className="sr-only peer"
                                                checked={isGroupSelected}
                                                onChange={() => toggleGroup(group.id)}
                                                disabled={!groupHasActiveStages}
                                            />
                                            <div className="w-9 h-5 bg-slate-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-teal-500"></div>
                                          </label>
                                      </div>
                                   </div>

                                   {/* Expanded Details */}
                                   {isExpanded && (
                                       <div className="border-t border-slate-800 bg-slate-950/30 px-4 py-3 space-y-2">
                                           {stages.map(stage => {
                                               const isSelected = selectedStageKeys.includes(stage.key);
                                               const isDisabled = isSongMode && !songModeStageKeys.includes(stage.key);

                                               return (
                                                   <div key={stage.key} className="flex items-center justify-between py-2 pl-12 pr-2 hover:bg-white/5 rounded transition-colors">
                                                       <div className="flex flex-col">
                                                           <span className={`text-xs font-medium ${isSelected ? 'text-slate-300' : 'text-slate-600'}`}>
                                                               {HUMAN_STAGE_TEXT[stage.key]?.title || stage.label}
                                                           </span>
                                                           <span className="text-[10px] text-slate-600">
                                                               {HUMAN_STAGE_TEXT[stage.key]?.description}
                                                           </span>
                                                       </div>

                                                       <label className="relative inline-flex items-center cursor-pointer">
                                                            <input
                                                                type="checkbox"
                                                                className="sr-only peer"
                                                                checked={isSelected}
                                                                onChange={() => toggleStage(stage.key)}
                                                                disabled={isDisabled}
                                                            />
                                                            <div className={`w-7 h-4 bg-slate-800 rounded-full peer after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-slate-400 after:rounded-full after:h-3 after:w-3 after:transition-all ${isSelected ? 'peer-checked:bg-teal-500/50 peer-checked:after:translate-x-full peer-checked:after:bg-teal-400' : ''}`}></div>
                                                       </label>
                                                   </div>
                                               );
                                           })}
                                       </div>
                                   )}
                                </div>
                            );
                        })}
                     </div>
                  </section>
                )}

                <div className="mt-8 flex flex-col items-center gap-3">
                  <button
                    type="button"
                    onClick={handleGenerateMix}
                    disabled={!hasFiles || loading}
                    className={[
                      "w-full max-w-sm inline-flex items-center justify-center rounded-lg px-6 py-4 text-base font-bold tracking-wide",
                      "bg-gradient-to-r from-teal-500 to-teal-400 text-slate-950 shadow-lg shadow-teal-500/20",
                      "transition-all duration-200 hover:shadow-teal-500/40 hover:scale-[1.01] hover:brightness-110 disabled:opacity-60 disabled:cursor-not-allowed disabled:transform-none disabled:shadow-none",
                    ].join(" ")}
                  >
                    {loading ? (
                        <span className="flex items-center gap-2">
                            <svg className="animate-spin h-5 w-5 text-slate-900" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                            {t('processing')}
                        </span>
                    ) : (
                        t('generateMix')
                    )}
                  </button>

                  {/* Time Estimate */}
                  {!loading && hasFiles && (
                    <p className="text-xs text-slate-500 font-medium">
                       Estimado: ~{estimatedMinutes} min de procesamiento • 1 Crédito
                    </p>
                  )}
                </div>

                {progressInfo && (
                  <div className="mx-auto mt-6 w-full max-w-md select-none">
                    {/* Progress Bar Row */}
                    <div className="mb-2 flex items-center gap-3">
                      <div className="flex-1 overflow-hidden rounded-full border border-slate-800 bg-slate-950/50 h-2.5">
                        <div
                          className="relative h-full bg-teal-500 shadow-[0_0_12px_rgba(20,184,166,0.6)] transition-all duration-300 ease-out"
                          style={{ width: `${progressInfo.percent}%` }}
                        >
                          <div className="absolute inset-0 bg-white/20" />
                        </div>
                      </div>
                      <span className="min-w-[3ch] text-right font-mono text-sm font-bold text-teal-400">
                        {progressInfo.percent}%
                      </span>
                    </div>

                    <h3 className="mb-1 text-center text-xs font-bold uppercase tracking-[0.15em] text-teal-100">
                      {progressInfo.title}
                    </h3>
                    <p className="mx-auto max-w-xs text-center text-[11px] font-medium leading-relaxed text-teal-200/70">
                      {progressInfo.description}
                    </p>
                  </div>
                )}

                {error && (
                  <p className="mt-4 text-center text-sm text-red-400">
                    {error}
                  </p>
                )}

              </section>

              {isProcessing && (
                <div className="mt-12 flex justify-center">
                  <video
                    src="/loading.mp4"
                    autoPlay
                    loop
                    muted
                    playsInline
                    aria-label="Processing your mix..."
                    className="h-12 w-auto rounded-lg"
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

          {/* Right Column: Stem Profiles */}
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
