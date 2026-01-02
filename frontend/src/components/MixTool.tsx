"use client";

import { useState, useEffect, useMemo, useRef } from "react";
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
import { gaEvent } from "../lib/ga";
import { useTranslations } from "next-intl";
import {
  PresentationChartLineIcon,
  AdjustmentsVerticalIcon,
  ArrowsPointingInIcon,
  HandRaisedIcon,
  BoltIcon,
  LockClosedIcon,
  ChevronDownIcon,
  ArrowLeftIcon
} from "@heroicons/react/24/outline";
import { ProcessingVisualizer } from "./ProcessingVisualizer";

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
  () => import("./SpaceDepthStylePanel").then((mod) => mod.SpaceDepthStylePanel)
);
const BUS_KEYS = [
  "drums",
  "percussion",
  "bass",
  "guitars",
  "keys_synths",
  "lead_vocal",
  "backing_vocals",
  "fx",
  "ambience",
  "other",
];

const PROFILE_TO_BUS: Record<string, string[]> = {
  auto: ["other"],
  Kick: ["drums"],
  Snare: ["drums"],
  Percussion: ["percussion"],
  Bass_Electric: ["bass"],
  Acoustic_Guitar: ["guitars"],
  Electric_Guitar_Rhythm: ["guitars"],
  Keys_Piano: ["keys_synths"],
  Synth_Pads: ["keys_synths"],
  Lead_Vocal_Melodic: ["lead_vocal"],
  Lead_Vocal_Rap: ["lead_vocal"],
  Backing_Vocals: ["backing_vocals"],
  FX_EarCandy: ["fx"],
  Ambience_Atmos: ["ambience"],
  Other: ["other"],
};

type StemProfile = {
  id: string;
  fileName: string;
  extension: string;
  profile: string;
};

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
  S2_GROUP_PHASE_DRUMS: "TECHNICAL_CALIBRATION_EQ", // Was PHASE_ALIGNMENT
  S3_MIXBUS_HEADROOM: "TECHNICAL_CALIBRATION_EQ", // Was MIXBUS_PREP
  S3_LEADVOX_AUDIBILITY: "TECHNICAL_CALIBRATION_EQ", // Was MIXBUS_PREP
  S4_STEM_HPF_LPF: "TECHNICAL_CALIBRATION_EQ", // Was SPECTRAL_CLEANUP
  S4_STEM_RESONANCE_CONTROL: "TECHNICAL_CALIBRATION_EQ", // Was SPECTRAL_CLEANUP
  S5_STEM_DYNAMICS_GENERIC: "DYNAMICS",
  S5_LEADVOX_DYNAMICS: "DYNAMICS",
  S5_BUS_DYNAMICS_DRUMS: "DYNAMICS",
  S6_BUS_REVERB_STYLE: "HIDDEN", // Was SPACE. Now Hidden.
  S6_MANUAL_CORRECTION: "MANUAL_CORRECTION",
  S7_MIXBUS_TONAL_BALANCE: "MASTERING",
  S8_MIXBUS_COLOR_GENERIC: "MASTERING",
  S9_MASTER_GENERIC: "MASTERING",
  S10_MASTER_FINAL_LIMITS: "MASTERING",
  S11_REPORT_GENERATION: "HIDDEN",
};

const QUICK_MODE_BASE_KEYS = [
  "S0_SESSION_FORMAT",
  "S1_STEM_DC_OFFSET",
  "S1_STEM_WORKING_LOUDNESS",
  "S3_MIXBUS_HEADROOM",
  "S7_MIXBUS_TONAL_BALANCE",
  "S9_MASTER_GENERIC",
  "S10_MASTER_FINAL_LIMITS",
];

const QUICK_MODE_OPTIONAL_KEYS = {
  drums: "S2_GROUP_PHASE_DRUMS",
  leadVocal: "S3_LEADVOX_AUDIBILITY",
};

// Estimated processing time in minutes per stage
const STAGE_ESTIMATES_MIN: Record<string, number> = {
  S0_SESSION_FORMAT: 0.5,
  S1_STEM_DC_OFFSET: 0.5,
  S1_STEM_WORKING_LOUDNESS: 0.5,
  S1_KEY_DETECTION: 0.2,
  S1_VOX_TUNING: 1.0,
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
  icon: any;
  theme: string;
};

const GROUPS_CONFIG: GroupConfig[] = [
  { id: "TECHNICAL_PREPARATION", labelKey: "technicalPreparation", icon: PresentationChartLineIcon, theme: "cyan" },
  { id: "TECHNICAL_CALIBRATION_EQ", labelKey: "technicalCalibrationEq", icon: AdjustmentsVerticalIcon, theme: "purple" },
  { id: "DYNAMICS", labelKey: "dynamics", icon: ArrowsPointingInIcon, theme: "orange" },
  { id: "MANUAL_CORRECTION", labelKey: "manualCorrection", icon: HandRaisedIcon, theme: "amber" },
  { id: "MASTERING", labelKey: "mastering", icon: BoltIcon, theme: "rose" },
];

const THEME_STYLES: Record<string, any> = {
  cyan: {
    text: "text-cyan-400",
    bg: "bg-cyan-500",
    border: "border-cyan-500/50",
    shadow: "shadow-cyan-500/10",
    toggle: "peer-checked:bg-cyan-500",
    cardBorder: "group-hover:border-cyan-500/30"
  },
  purple: {
    text: "text-purple-400",
    bg: "bg-purple-500",
    border: "border-purple-500/50",
    shadow: "shadow-purple-500/10",
    toggle: "peer-checked:bg-purple-500",
    cardBorder: "group-hover:border-purple-500/30"
  },
  orange: {
    text: "text-orange-400",
    bg: "bg-orange-500",
    border: "border-orange-500/50",
    shadow: "shadow-orange-500/10",
    toggle: "peer-checked:bg-orange-500",
    cardBorder: "group-hover:border-orange-500/30"
  },
  rose: {
    text: "text-rose-400",
    bg: "bg-rose-500",
    border: "border-rose-500/50",
    shadow: "shadow-rose-500/10",
    toggle: "peer-checked:bg-rose-500",
    cardBorder: "group-hover:border-rose-500/30"
  },
  amber: {
    text: "text-amber-400",
    bg: "bg-amber-500",
    border: "border-amber-500/50",
    shadow: "shadow-amber-500/10",
    toggle: "peer-checked:bg-amber-500",
    cardBorder: "group-hover:border-amber-500/30"
  }
};

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
  const [isQuickMode, setIsQuickMode] = useState(false);

  // Group expansion state
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({});
  const [uploadStep, setUploadStep] = useState<1 | 2 | 3>(1);
  const [busStyles, setBusStyles] = useState<Record<string, string>>(() =>
    Object.fromEntries(BUS_KEYS.map((key) => [key, "auto"])),
  );
  const [busConfirmationMessage, setBusConfirmationMessage] = useState<string>("");
  const [showBusPanel, setShowBusPanel] = useState(true);
  const pipelineRef = useRef<HTMLDivElement | null>(null);

  const t = useTranslations('MixTool');

  const songModeStageKeys = useMemo(
    () => getSongModeStages(availableStages),
    [availableStages],
  );
  const isSongMode = uploadMode === "song";

  const spaceDepthBuses = useMemo(
    () =>
      BUS_KEYS.map((key) => ({
        key,
        label: t(`spaceDepthBuses.${key}.label`) || key,
        description: t(`spaceDepthBuses.${key}.description`) || "",
      })),
    [t],
  );

  const activeBusKeys = useMemo(() => {
    const selected = new Set<string>();
    stemProfiles.forEach((stem) => {
      const mapped = PROFILE_TO_BUS[stem.profile] ?? ["other"];
      mapped.forEach((busKey) => selected.add(busKey));
    });
    const result = BUS_KEYS.filter((key) => selected.has(key));
    return result.length > 0 ? result : BUS_KEYS;
  }, [stemProfiles]);

  const hasDrums = useMemo(
    () => activeBusKeys.includes("drums") || activeBusKeys.includes("percussion"),
    [activeBusKeys],
  );
  const hasLeadVocal = useMemo(
    () => activeBusKeys.includes("lead_vocal"),
    [activeBusKeys],
  );

  const quickModeStageKeys = useMemo(() => {
    const availableKeys = new Set(availableStages.map((stage) => stage.key));
    const keys = [...QUICK_MODE_BASE_KEYS];
    if (hasDrums) {
      keys.push(QUICK_MODE_OPTIONAL_KEYS.drums);
    }
    if (hasLeadVocal) {
      keys.push(QUICK_MODE_OPTIONAL_KEYS.leadVocal);
    }
    return keys.filter((key) => availableKeys.has(key));
  }, [availableStages, hasDrums, hasLeadVocal]);

  const visibleSpaceDepthBuses = activeBusKeys.length
    ? spaceDepthBuses.filter((bus) => activeBusKeys.includes(bus.key))
    : spaceDepthBuses;
  // Use router from next-intl/routing to ensure locale preservation
  const { useRouter } = require("@/i18n/routing");
  const router = useRouter();

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
        acc[key] = { label: val.title, description: val.description };
        return acc;
    }, {} as Record<string, StageUiInfo>)
  };

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
        router.push(`/mix/result/${activeJobId}`);
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

    if (isSongMode) {
      setSelectedStageKeys(songModeStageKeys);
      return;
    }

    if (!isQuickMode) {
      setSelectedStageKeys(availableStages.map((stage) => stage.key));
    }
  }, [availableStages, isSongMode, songModeStageKeys, isQuickMode]);

  useEffect(() => {
    if (!availableStages.length) return;
    if (!isQuickMode || isSongMode) return;
    setSelectedStageKeys(quickModeStageKeys);
  }, [availableStages, isQuickMode, isSongMode, quickModeStageKeys]);

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

  const handleModeChange = (mode: "song" | "stems") => {
    setUploadMode(mode);
    setFiles([]);
    setJobStatus(null);
    setActiveJobId(null);
    setLoading(false);
    setError(null);
    setStemProfiles([]);
    setSelectionWarning(null);
    setUploadStep(1);
    setBusStyles(Object.fromEntries(BUS_KEYS.map((key) => [key, "auto"])));
  };

  const handleFilesSelected = (selected: File[]) => {
    setJobStatus(null);
    setActiveJobId(null);
    setLoading(false);
    setError(null);
    setSelectionWarning(null);
    setShowStageSelector(true);
    setFiles([]);
    setStemProfiles([]);
    setShowBusPanel(true);
    setBusConfirmationMessage("");

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
    setShowBusPanel(true);
    setBusConfirmationMessage("");
    if (!isSongMode && newProfiles.length) {
      setUploadStep(2);
    } else {
      setUploadStep(1);
    }
  };

  const handleStemProfileChange = (id: string, profile: string) => {
    setStemProfiles((prev) =>
      prev.map((stem) =>
        stem.id === id ? { ...stem, profile } : stem,
      ),
    );
  };

  const handleStepBack = () => {
    setUploadStep((prev) => (prev === 1 ? 1 : (prev - 1) as 1 | 2));
    setShowBusPanel(true);
    setBusConfirmationMessage("");
  };

  const handleConfirmProfiles = () => {
    setUploadStep(3);
    setShowBusPanel(true);
    setBusConfirmationMessage("");
  };

  const handleBusStyleChange = (busKey: string, style: string) => {
    setBusStyles((prev) => ({
      ...prev,
      [busKey]: style,
    }));
  };

  const handleConfirmBuses = () => {
    pipelineRef.current?.scrollIntoView({ behavior: "smooth" });
    setUploadStep(3);
    setShowBusPanel(false);
    setBusConfirmationMessage(t("uploadSteps.messages.mixReady"));
  };

  const hasFiles = files.length > 0;
  const isReadyForMix = uploadStep === 3 && !showBusPanel && Boolean(busConfirmationMessage);
  const readyMessageText =
    busConfirmationMessage || t("uploadSteps.messages.mixReady");

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

      setStemProfiles([]);
      setShowStageSelector(false);

      const { jobId } = await startMixJob(
        files,
        enabled,
        stemProfilesPayload,
        // No spaceBusStylesPayload anymore
        undefined,
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

  useEffect(() => {
    if (!files.length) {
      setUploadStep(1);
    }
  }, [files.length]);

  useEffect(() => {
    if (isProcessing) {
      setUploadStep(3);
    }
  }, [isProcessing]);

  const processingState = progressInfo
    ? {
        stageKey: jobStatus?.stageKey || "",
        progress: progressInfo.percent,
        description: progressInfo.description
          ? `${progressInfo.title} - ${progressInfo.description}`
          : progressInfo.title,
      }
    : undefined;


  return (
    <div className="flex-1 flex flex-col">
      <Script
        id="ld-service"
        type="application/ld+json"
        strategy="afterInteractive"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(serviceJsonLd) }}
      />

      <main className="flex flex-1 flex-col items-center px-4 py-8">
        <div className="text-center mb-8 max-w-2xl">
          <h1 className="text-3xl md:text-4xl font-bold text-white mb-4">
            {t("title")}
          </h1>
          <p className="text-slate-400 text-base md:text-lg">
            {t("subtitle")}
          </p>
        </div>

        {/* MAIN CARD CONTAINER */}
        <div className="w-full max-w-6xl rounded-3xl bg-slate-950 border border-slate-800 shadow-2xl shadow-black overflow-hidden grid grid-cols-1 lg:grid-cols-[1.5fr_1fr]">

            {/* LEFT COLUMN: Upload & Config */}
            <div className="p-8 lg:p-12 flex flex-col items-center justify-between border-b lg:border-b-0 lg:border-r border-slate-800 relative bg-[url('/bg-grid.svg')] bg-repeat opacity-95">
                {/* Background ambient glow */}
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full h-full max-w-[500px] max-h-[500px] bg-teal-500/5 blur-[120px] rounded-full pointer-events-none" />

                {/* Top: Mode Switcher */}
                <div className="relative z-10 w-full flex justify-center mb-8">
                    <div className="inline-flex rounded-lg bg-slate-950 p-1 border border-slate-800 shadow-inner">
                        <button
                            type="button"
                            onClick={() => handleModeChange("song")}
                            className={`rounded-md px-8 py-2.5 text-xs font-bold uppercase tracking-wider transition-all duration-200 ${
                                uploadMode === "song"
                                ? "bg-teal-500 text-slate-950 shadow-sm ring-1 ring-teal-500"
                                : "text-slate-500 hover:text-slate-300"
                            }`}
                        >
                            {t('songMode')}
                        </button>
                        <button
                            type="button"
                            onClick={() => handleModeChange("stems")}
                            className={`rounded-md px-8 py-2.5 text-xs font-bold uppercase tracking-wider transition-all duration-200 ${
                                uploadMode === "stems"
                                ? "bg-teal-500 text-slate-950 shadow-sm ring-1 ring-teal-500"
                                : "text-slate-500 hover:text-slate-300"
                            }`}
                        >
                            {t('stemsMode')}
                        </button>
                    </div>
                </div>

                {/* Center: Upload */}
                <div className="relative z-10 w-full max-w-lg flex-1 flex flex-col justify-center">
                    <div className="mb-4 flex items-start justify-between gap-3">
                        <div>
                              <h2 className="text-xl font-bold text-white leading-tight">
                                  {uploadStep === 1 && t("uploadSteps.labels.uploadTracks")}
                                  {uploadStep === 2 && t("uploadSteps.labels.selectProfiles")}
                                  {uploadStep === 3 && !isReadyForMix && t("uploadSteps.labels.busSelection")}
                              </h2>
                              {uploadStep > 1 && !isReadyForMix && (
                                  <p className="mt-1 text-xs text-slate-400">
                                      {uploadStep === 2
                                          ? t("uploadSteps.notes.profiles")
                                          : t("uploadSteps.notes.buses")}
                                  </p>
                            )}
                        </div>
                        {uploadStep > 1 && (
                            <button
                                type="button"
                                onClick={handleStepBack}
                                className="flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-900/60 px-3 py-2 text-xs font-semibold uppercase tracking-wider text-slate-400 transition hover:border-slate-500 hover:text-slate-200"
                            >
                                <ArrowLeftIcon className="w-3 h-3" />
                                {t("uploadSteps.buttons.back")}
                            </button>
                        )}
                    </div>

                    <div className="flex-1">
                        {isProcessing && processingState ? (
                            <div className="w-full min-h-[400px]">
                                <ProcessingVisualizer
                                    stageKey={processingState.stageKey}
                                    progress={processingState.progress}
                                    description={processingState.description}
                                />
                            </div>
                        ) : (
                            <div className="space-y-4">
                                {uploadStep === 2 && stemProfiles.length > 0 && (
                                    <div className="flex min-h-[400px] flex-col rounded-3xl border border-teal-500/40 bg-gradient-to-br from-teal-500/10 to-slate-900/70 p-5 shadow-lg shadow-teal-500/10">
                                        <StemsProfilePanel
                                            stems={stemProfiles}
                                            onChangeProfile={handleStemProfileChange}
                                            accent="teal"
                                        />
                                        <div className="mt-4 flex justify-end">
                                            <button
                                                type="button"
                                                disabled={loading || !stemProfiles.length}
                                                onClick={handleConfirmProfiles}
                                                className="rounded-full bg-teal-500 px-5 py-2.5 text-xs font-bold uppercase tracking-widest text-slate-950 transition hover:bg-teal-400 disabled:opacity-60"
                                            >
                                                {t("uploadSteps.buttons.confirmProfiles")}
                                            </button>
                                        </div>
                                    </div>
                                )}

                                {uploadStep === 3 && stemProfiles.length > 0 && showBusPanel && (
                                    <div className="flex min-h-[400px] flex-col gap-4 rounded-3xl border border-slate-700 bg-slate-900/60 p-5 shadow-lg shadow-slate-900/50">
                                        <div className="flex-1">
                                            <SpaceDepthStylePanel
                                                buses={visibleSpaceDepthBuses}
                                                value={busStyles}
                                                onChange={handleBusStyleChange}
                                            />
                                        </div>
                                        <div className="flex justify-end">
                                            <button
                                                type="button"
                                                disabled={loading}
                                                onClick={handleConfirmBuses}
                                                className="rounded-full bg-slate-200/90 px-5 py-2.5 text-xs font-bold uppercase tracking-widest text-slate-950 transition hover:bg-slate-100 disabled:opacity-60"
                                            >
                                                {t("uploadSteps.buttons.confirmBuses")}
                                            </button>
                                        </div>
                                    </div>
                                )}

                                {(uploadStep === 1 || isReadyForMix) && (
                                    isReadyForMix ? (
                                        <div className="flex min-h-[400px] flex-col items-center justify-center gap-4 rounded-3xl border-2 border-teal-500/40 bg-gradient-to-br from-slate-900/80 to-slate-950/60 px-8 py-10 text-center shadow-inner shadow-teal-500/20">
                                            <p className="text-lg font-semibold text-white max-w-xl">
                                                {readyMessageText}
                                            </p>
                                            <button
                                                type="button"
                                                onClick={handleGenerateMix}
                                                disabled={!hasFiles || loading}
                                                className="mt-2 rounded-full border border-teal-400 bg-gradient-to-r from-teal-500 to-cyan-500 px-5 py-2 text-[11px] font-bold uppercase tracking-[0.3em] text-slate-950 transition hover:brightness-110 disabled:opacity-60"
                                            >
                                                {t("generateMix")}
                                            </button>
                                        </div>
                                    ) : (
                                        <UploadDropzone
                                            onFilesSelected={handleFilesSelected}
                                            disabled={loading}
                                            filesCount={files.length}
                                            uploadMode={uploadMode}
                                        />
                                    )
                                )}
                            </div>
                        )}
                    </div>

                    {!isProcessing && selectionWarning && (
                        <div className="mt-4 rounded-md border border-amber-400/60 bg-amber-500/10 px-4 py-3 text-sm text-amber-100 flex items-center justify-center text-center">
                            {selectionWarning}
                        </div>
                    )}

                    {!isProcessing && error && (
                        <div className="mt-4 rounded-md border border-red-500/60 bg-red-500/10 px-4 py-3 text-sm text-red-200 text-center">
                            {error}
                        </div>
                    )}
                </div>

                {/* Bottom: Footer Status */}
                <div className="relative z-10 w-full flex items-center justify-between text-xs text-slate-500 mt-8 px-4">
                    <div className="flex items-center gap-2">
                        <span className="relative flex h-2 w-2">
                          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                          <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                        </span>
                        <span>Servidores listos</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                        <LockClosedIcon className="w-3.5 h-3.5" />
                        <span>Cifrado TLS seguro</span>
                    </div>
                </div>
            </div>

            {/* RIGHT COLUMN: Pipeline */}
            <div
                ref={pipelineRef}
                className="p-8 lg:p-10 bg-slate-900/50 flex flex-col relative"
            >
                {/* Header */}
                <div className="flex items-center justify-between mb-8">
                    <div>
                        <h3 className="text-xl font-bold text-white flex items-center gap-2">
                            <span className="text-teal-400">
                                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.384-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" /></svg>
                            </span>
                             Pipeline IA
                        </h3>
                        <p className="text-xs text-slate-500 mt-1">Cadena de procesamiento activa</p>
                    </div>
                    <div className="flex items-center gap-3">
                        <span
                            className={`text-[10px] font-semibold tracking-wide px-2 py-1 rounded border ${
                                isQuickMode
                                    ? "text-amber-300 border-amber-500/40 bg-amber-500/10"
                                    : "text-teal-300 border-teal-500/30 bg-teal-500/10"
                            }`}
                        >
                            {isQuickMode ? "Modo rápido" : "Modo completo"}
                        </span>
                        <label className="relative inline-flex items-center cursor-pointer">
                            <input
                                type="checkbox"
                                className="sr-only peer"
                                checked={isQuickMode}
                                onChange={() => setIsQuickMode((prev) => !prev)}
                            />
                            <div className="w-9 h-5 bg-slate-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-slate-400 after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-amber-500 peer-checked:after:bg-white"></div>
                        </label>
                    </div>
                </div>

                {/* Timeline Container */}
                <div className="flex-1 relative overflow-y-auto pr-2 -mr-2 custom-scrollbar">
                    {/* Vertical Line */}
                    <div className="absolute left-[1.65rem] top-4 bottom-4 w-px bg-slate-800" />

                    <div className="space-y-4 pb-6">
                        {GROUPS_CONFIG.map((group, idx) => {
                            const stages = groupedStages[group.id] || [];
                            // For visualization, assume if stages exist, the group is relevant.
                            // However, we want to respect songModeStageKeys.
                            const relevantKeys = isSongMode
                               ? stages.map(s => s.key).filter(k => songModeStageKeys.includes(k))
                               : stages.map(s => s.key);

                            const isDisabled = relevantKeys.length === 0;
                            // Update logic: toggle is selected if ANY of the stages is selected (unless disabled)
                            const isSelected = !isDisabled && relevantKeys.some(k => selectedStageKeys.includes(k));
                            const Icon = group.icon;
                            const theme = THEME_STYLES[group.theme] || THEME_STYLES.cyan;

                            return (
                                <div
                                    key={group.id}
                                    className={`relative group rounded-2xl border transition-all duration-300 ${
                                        isSelected
                                        ? 'bg-slate-900/40 border-slate-700/50'
                                        : 'bg-transparent border-transparent'
                                    } ${isDisabled ? 'opacity-30 grayscale' : 'opacity-100'} ${theme.cardBorder || ''}`}
                                >
                                    <div className="relative flex items-center p-3 gap-4">
                                        {/* Icon */}
                                        <div className={`
                                            relative z-10 flex items-center justify-center w-12 h-12 rounded-xl border transition-all duration-300 shrink-0
                                            group-hover:shadow-[0_0_15px_rgba(20,184,166,0.15)]
                                            ${isSelected
                                                ? `bg-slate-900 ${theme.border} ${theme.shadow}`
                                                : 'bg-slate-950 border-slate-800 shadow-none'}
                                        `}>
                                            {isSelected && <div className={`absolute inset-0 ${theme.bg}/10 rounded-xl`} />}
                                            <Icon className={`w-6 h-6 relative z-20 ${isSelected ? theme.text : 'text-slate-600'}`} />
                                        </div>

                                        {/* Content */}
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center justify-between gap-4">
                                                <div className="flex flex-col">
                                                    <h4 className={`text-sm font-bold ${isSelected ? 'text-white' : 'text-slate-500'}`}>
                                                        {/* @ts-ignore */}
                                                        {t(`stageGroups.${group.labelKey}`)}
                                                    </h4>
                                                    <p className="text-[10px] text-slate-500 mt-0.5 leading-relaxed">
                                                        {stages.length > 0
                                                            ? `${stages.length} pasos: ${stages.slice(0, 2).map(s => HUMAN_STAGE_TEXT[s.key]?.title).join(", ")}${stages.length > 2 ? '...' : ''}`
                                                            : "No active stages"
                                                        }
                                                    </p>
                                                </div>

                                                {/* Toggle */}
                                                <label className="relative inline-flex items-center cursor-pointer shrink-0">
                                                    <input
                                                        type="checkbox"
                                                        className="sr-only peer"
                                                        checked={isSelected}
                                                        onChange={() => toggleGroup(group.id)}
                                                        disabled={isDisabled}
                                                    />
                                                    <div className={`w-9 h-5 bg-slate-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-slate-400 after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all ${theme.toggle} peer-checked:after:bg-white`}></div>
                                                </label>
                                            </div>

                                            {/* Expand Button */}
                                            {stages.length > 0 && (
                                                <button
                                                    onClick={() => toggleGroupExpand(group.id)}
                                                    className={`mt-1 text-[10px] flex items-center gap-1 transition-colors w-fit ${isSelected ? theme.text : 'text-slate-600 hover:text-white'}`}
                                                >
                                                    {expandedGroups[group.id] ? "Ocultar detalles" : "Ver detalles"}
                                                    <ChevronDownIcon className={`w-3 h-3 transition-transform ${expandedGroups[group.id] ? 'rotate-180' : ''}`} />
                                                </button>
                                            )}
                                        </div>
                                    </div>

                                    {/* Expanded Stages List */}
                                    {expandedGroups[group.id] && (
                                        <div className="px-3 pb-3 pt-0 ml-[3.5rem] space-y-2 animate-in slide-in-from-top-2 duration-200">
                                            {stages.map(stage => {
                                               const isStageSelected = selectedStageKeys.includes(stage.key);
                                               const isStageDisabled = isSongMode && !songModeStageKeys.includes(stage.key);

                                               return (
                                                   <div key={stage.key} className="flex items-center justify-between text-xs group/stage">
                                                       <span className={`${isStageSelected ? 'text-slate-300' : 'text-slate-600'}`}>
                                                           {HUMAN_STAGE_TEXT[stage.key]?.title || stage.label}
                                                       </span>
                                                        <input
                                                            type="checkbox"
                                                            className={`rounded border-slate-700 bg-slate-800 ${theme.text} focus:ring-opacity-50 h-3 w-3`}
                                                            checked={isStageSelected}
                                                            onChange={() => toggleStage(stage.key)}
                                                            disabled={isStageDisabled}
                                                        />
                                                   </div>
                                               );
                                            })}
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                </div>

                {/* Footer Action */}
                <div className="mt-6 pt-6 border-t border-slate-800">
                    <button
                        type="button"
                        onClick={handleGenerateMix}
                        disabled={!hasFiles || loading}
                        className={[
                            "w-full rounded-xl px-6 py-4 text-base font-bold tracking-wide uppercase",
                            "bg-gradient-to-r from-teal-400 to-cyan-500 text-slate-950 shadow-lg shadow-teal-500/20",
                            "transition-all duration-200 hover:shadow-teal-500/40 hover:brightness-110 disabled:opacity-60 disabled:cursor-not-allowed disabled:shadow-none",
                            "flex items-center justify-center gap-3"
                        ].join(" ")}
                    >
                        {loading ? (
                            <>
                                <svg className="animate-spin h-5 w-5 text-slate-950" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                </svg>
                                {t('processing')}
                            </>
                        ) : (
                            <>
                                <div className="w-4 h-4 rounded-full border-2 border-slate-950/60" />
                                {t('generateMix')}
                            </>
                        )}
                    </button>
                    {!loading && hasFiles && (
                         <p className="text-center text-[10px] text-slate-500 font-medium mt-3 uppercase tracking-wide">
                            Estimado: ~{estimatedMinutes} min de procesamiento • 1 Crédito
                         </p>
                    )}
                </div>
            </div>
        </div>

      </main>
    </div>
  );
}
