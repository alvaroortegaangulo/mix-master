// frontend/src/app/page.tsx
"use client";

import { useState, useEffect, useMemo } from "react";
import {
  startMixJob,
  fetchJobStatus,
  type JobStatus,
  fetchPipelineStages,
  type PipelineStage,
  type StemProfilePayload,
  cleanupTemp,  
} from "../lib/mixApi";
import { UploadDropzone } from "../components/UploadDropzone";
import { MixResultPanel } from "../components/MixResultPanel";
import { StemsProfilePanel } from "../components/StemsProfilePanel";
import { SpaceDepthStylePanel, type SpaceBus } from "../components/SpaceDepthStylePanel";

type StemProfile = {
  id: string;
  fileName: string;
  extension: string;
  profile: string;
};

type SpaceDepthBus = SpaceBus;

const SPACE_DEPTH_BUSES: SpaceDepthBus[] = [
  {
    key: "drums",
    label: "Drums bus",
    description: "Drum kit, baterías programadas, loops, etc.",
  },
  {
    key: "percussion",
    label: "Percussion bus",
    description: "Percusiones adicionales, palmas, shakers, etc.",
  },
  {
    key: "bass",
    label: "Bass bus",
    description: "Bajo eléctrico, bajo synth, sub-bass.",
  },
  {
    key: "guitars",
    label: "Guitars bus",
    description: "Guitarras acústicas y eléctricas.",
  },
  {
    key: "keys_synths",
    label: "Keys / Synths bus",
    description: "Pianos, Rhodes, pads, sintetizadores.",
  },
  {
    key: "lead_vocal",
    label: "Lead vocal bus",
    description: "Voz principal.",
  },
  {
    key: "backing_vocals",
    label: "Backing vocals bus",
    description: "Coros, dobles, harmonies.",
  },
  {
    key: "fx",
    label: "FX / Ear candy bus",
    description: "Risers, impacts, vocal chops, efectos creativos.",
  },
  {
    key: "ambience",
    label: "Ambience / Atmos bus",
    description: "Ambientes, atmósferas, room mics, fx de fondo.",
  },
  {
    key: "other",
    label: "Other bus",
    description: "Cualquier stem no clasificado en las categorías anteriores.",
  },
];


const handleResetApp = async () => {
  try {
    // limpiamos al pulsar el "logo"
    await cleanupTemp();
  } catch (err) {
    console.error("Error cleaning temp on reset", err);
  } finally {
    // recarga completa de la página
    window.location.reload();
  }
};


type StageUiInfo = {
  label: string;
  description: string;
};

const STAGE_UI_INFO: Record<string, StageUiInfo> = {
  S0_SESSION_FORMAT: {
    label: "SESSION FORMAT",
    description:
      "Session format normalization (samplerate, bit depth, headroom and bus routing).",
  },
  S1_STEM_DC_OFFSET: {
    label: "STEM DC OFFSET",
    description:
      "DC offset detection and correction on each stem.",
  },
  S1_STEM_WORKING_LOUDNESS: {
    label: "STEM WORKING LOUDNESS",
    description:
      "Per-stem working loudness normalization based on the detected instrument profile.",
  },
  S1_KEY_DETECTION: {
    label: "GLOBAL KEY DETECTION",
    description:
      "Global key and scale detection for the song.",
  },
  S1_VOX_TUNING: {
    label: "VOCAL TUNING",
    description:
      "Pitch-correction of vocal tracks using the detected key, within natural pitch and retune-speed limits.",
  },
  S2_GROUP_PHASE_DRUMS: {
    label: "DRUM PHASE ALIGNMENT",
    description:
      "Phase and polarity alignment across the drum and percussion group.",
  },
  S3_MIXBUS_HEADROOM: {
    label: "MIXBUS HEADROOM",
    description:
      "Global mixbus headroom adjustment (peak level and working LUFS).",
  },
  S3_LEADVOX_AUDIBILITY: {
    label: "LEAD VOCAL AUDIBILITY",
    description:
      "Static level balancing of the lead vocal against the mix so it sits clearly on top without sounding detached.",
  },
  S4_STEM_HPF_LPF: {
    label: "STEM HPF/LPF FILTERS",
    description:
      "Per-stem high-pass / low-pass filtering driven by the instrument profile.",
  },
  S4_STEM_RESONANCE_CONTROL: {
    label: "STEM RESONANCE CONTROL",
    description:
      "Per-stem resonance control using narrow, limited cuts on resonant bands.",
  },
  S5_STEM_DYNAMICS_GENERIC: {
    label: "STEM DYNAMICS",
    description:
      "Generic per-stem dynamics processing (compression/gating) to control dynamic range.",
  },
  S5_LEADVOX_DYNAMICS: {
    label: "LEAD VOCAL DYNAMICS",
    description:
      "Lead vocal-focused dynamics processing (main compression and gentle level automation).",
  },
  S5_BUS_DYNAMICS_DRUMS: {
    label: "DRUM BUS DYNAMICS",
    description:
      "Drum-bus compression to enhance punch and glue the drum kit together.",
  },
  S6_BUS_REVERB_STYLE: {
    label: "BUS REVERB & SPACE",
    description:
      "Style-aware reverb and space assignment per bus family.",
  },
  S7_MIXBUS_TONAL_BALANCE: {
    label: "MIXBUS TONAL BALANCE",
    description:
      "Broad-band tonal EQ on the mixbus to match the target tonal balance for the chosen style.",
  },
  S8_MIXBUS_COLOR_GENERIC: {
    label: "MIXBUS COLOR & SATURATION",
    description:
      "Subtle mixbus coloration and saturation to add glue and harmonic density.",
  },
  S9_MASTER_GENERIC: {
    label: "STEREO MASTERING",
    description:
      "Final stereo mastering (target loudness, ceiling and moderate M/S width adjustment).",
  },
  S10_MASTER_FINAL_LIMITS: {
    label: "FINAL MASTER QC",
    description:
      "Final master quality-control pass over true-peak level, loudness (LUFS), L/R balance and stereo correlation with only micro-adjustments applied.",
  },
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


export default function HomePage() {
  const [files, setFiles] = useState<File[]>([]);
  const [stemProfiles, setStemProfiles] = useState<StemProfile[]>([]);

  const [loading, setLoading] = useState(false);
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [availableStages, setAvailableStages] = useState<PipelineStage[]>([]);
  const [selectedStageKeys, setSelectedStageKeys] = useState<string[]>([]);
  const [showStageSelector, setShowStageSelector] = useState(true);
  const [isPipelineCollapsed, setIsPipelineCollapsed] = useState(true);

  const [spaceBusStyles, setSpaceBusStyles] = useState<Record<string, string>>(
     {},
  );

  const HUMAN_STAGE_TEXT: Record<
    string,
    { title: string; description: string }
  > = {
    S0_SESSION_FORMAT: {
      title: "Session format & routing",
      description:
        "Normaliza samplerate/bit depth y asigna buses lógicos para empezar limpio.",
    },
    S1_STEM_DC_OFFSET: {
      title: "DC offset check",
      description: "Detecta y corrige desplazamientos DC en cada stem.",
    },
    S1_STEM_WORKING_LOUDNESS: {
      title: "Working loudness",
      description:
        "Iguala el nivel de trabajo por stem según su perfil de instrumento.",
    },
    S1_KEY_DETECTION: {
      title: "Key detection",
      description: "Estima la tonalidad global (key + escala) del tema.",
    },
    S1_VOX_TUNING: {
      title: "Vocal tuning",
      description: "Afina la voz principal respetando la tonalidad detectada.",
    },
    S2_GROUP_PHASE_DRUMS: {
      title: "Phase alignment (drums)",
      description: "Alinea fase/polaridad en el grupo de baterías/percusión.",
    },
    S3_MIXBUS_HEADROOM: {
      title: "Mixbus headroom",
      description: "Ajusta el headroom global para dejar espacio a procesar.",
    },
    S3_LEADVOX_AUDIBILITY: {
      title: "Lead vocal audibility",
      description: "Equilibra la voz principal frente al mix estático.",
    },
    S4_STEM_HPF_LPF: {
      title: "HPF/LPF por stem",
      description:
        "Aplica filtros pasa-altos/bajos según el perfil del instrumento.",
    },
    S4_STEM_RESONANCE_CONTROL: {
      title: "Resonance control",
      description: "Detecta y atenúa resonancias estrechas en cada stem.",
    },
    S5_STEM_DYNAMICS_GENERIC: {
      title: "Stem dynamics",
      description: "Control dinámico genérico por pista (compresión/gate).",
    },
    S5_LEADVOX_DYNAMICS: {
      title: "Lead vocal dynamics",
      description: "Compresión y control de dinámica para la voz principal.",
    },
    S5_BUS_DYNAMICS_DRUMS: {
      title: "Drum bus dynamics",
      description: "Compresión en el bus de baterías para pegada y glue.",
    },
    S6_BUS_REVERB_STYLE: {
      title: "Space / reverb style",
      description: "Asigna estilos de reverb/espacio por familia de buses.",
    },
    S7_MIXBUS_TONAL_BALANCE: {
      title: "Mixbus tonal balance",
      description: "EQ broad-band para ajustar el balance tonal al estilo.",
    },
    S8_MIXBUS_COLOR_GENERIC: {
      title: "Mixbus color",
      description: "Saturación/coloración suave en el mixbus para cohesión.",
    },
    S9_MASTER_GENERIC: {
      title: "Master prep",
      description:
        "Ajuste previo de mastering (nivel y balance) antes del QC final.",
    },
    S10_MASTER_FINAL_LIMITS: {
      title: "Master final QC",
      description: "Chequeo final de TP/LUFS/correlación con micro-ajustes.",
    },
  };


useEffect(() => {
  // Limpiar temp siempre que se entra / recarga la página
  cleanupTemp().catch((err) => {
    console.error("Error cleaning temp on page load", err);
  });
}, []);


  // Cargar definición de stages del backend
  useEffect(() => {
    async function loadStages() {
      try {
        const stages = await fetchPipelineStages();
        setAvailableStages(stages);
        setSelectedStageKeys(stages.map((s) => s.key));
      } catch (err: any) {
        console.error("Error fetching pipeline stages", err);
      }
    }
    void loadStages();
  }, []);

  const toggleStage = (key: string) => {
    setSelectedStageKeys((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key],
    );
  };

  const selectAllStages = () => {
    setSelectedStageKeys(availableStages.map((s) => s.key));
  };

  const clearStages = () => {
    setSelectedStageKeys([]);
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



  const handleFilesSelected = (selected: File[]) => {
    setFiles(selected);
    setJobStatus(null);
    setError(null);
    setShowStageSelector(true);
    setIsPipelineCollapsed(true);
    setSpaceBusStyles({}); 

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

      setJobStatus({
        jobId,
        status: "queued",
        stageIndex: 0,
        totalStages: 7,
        stageKey: "queued",
        message: "Job queued...",
        progress: 0,
      });

      while (true) {
        const status = await fetchJobStatus(jobId);
        setJobStatus(status);

        if (status.status === "done") {
          setLoading(false);
          break;
        }
        if (status.status === "error") {
          setLoading(false);
          setError(status.error ?? "Error processing mix");
          break;
        }

        await new Promise((resolve) => setTimeout(resolve, 1000));
      }
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



  const progressHeader =
    jobStatus &&
    (jobStatus.status === "queued" || jobStatus.status === "running")
      ? (() => {
          const percent = Math.round(jobStatus.progress ?? 0);
          const currentStep = jobStatus.stageIndex ?? 0;
          const totalSteps = jobStatus.totalStages ?? 0;

          // En cola: texto genérico
          if (jobStatus.status === "queued" || totalSteps === 0) {
            return `[${percent}%] Step ${currentStep}/${totalSteps} – Waiting in queue…`;
          }

          const label =
            stageUiInfo?.label ||
            jobStatus.stageKey ||
            "Processing";

          return `[${percent}%] Step ${currentStep}/${totalSteps} – Running stage ${label}…`;
        })()
      : null;

  const progressSubtext =
    jobStatus &&
    (jobStatus.status === "queued" || jobStatus.status === "running")
      ? stageUiInfo?.description || jobStatus.message || null
      : null;


  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* Top bar */}
<header className="border-b border-slate-800/80">
  <div className="mx-auto flex h-16 max-w-5xl items-center px-4">
    <div className="flex items-center gap-2">
      <div className="h-7 w-7 rounded-full bg-teal-400/90 flex items-center justify-center text-slate-950 text-lg font-bold">
        A
      </div>
      <button
        type="button"
        onClick={handleResetApp}
        className="text-lg font-semibold tracking-tight bg-transparent border-none p-0 cursor-pointer"
      >
        Audio Alchemy
      </button>
    </div>
  </div>
</header>

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
              <section className="rounded-2xl border border-slate-800/80 bg-slate-900/70 p-8 shadow-xl">
                <div className="text-center mb-8">
                  <h1 className="text-3xl font-bold text-slate-50 mb-2">
                    Upload Your Stems
                  </h1>
                  <p className="text-slate-400">
                    Drag and drop your audio files to begin the magic.
                  </p>
                </div>

                <UploadDropzone
                  onFilesSelected={handleFilesSelected}
                  disabled={loading}
                  filesCount={files.length}
                />

                {showStageSelector && availableStages.length > 0 && (
                  <section className="mt-6 rounded-xl border border-slate-800/70 bg-slate-900/60">
                    {/* Cabecera plegable */}
                    <button
                      type="button"
                      onClick={() =>
                        setIsPipelineCollapsed((prev) => !prev)
                      }
                      className="flex w-full items-center justify-between px-4 py-3 text-xs font-semibold uppercase tracking-wide text-slate-300 hover:bg-slate-900/70"
                      aria-expanded={!isPipelineCollapsed}
                    >
                      <span>Pipeline steps</span>
                      <span className="flex items-center gap-2 text-[11px] text-slate-400 normal-case">
                        <span>
                          {selectedStageKeys.length} /{" "}
                          {availableStages.length} enabled
                        </span>
                        <span className="text-slate-500">
                          {isPipelineCollapsed ? "▼" : "▲"}
                        </span>
                      </span>
                    </button>

                    {/* Contenido expandible */}
                    {!isPipelineCollapsed && (
                      <div className="border-t border-slate-800/60 px-4 py-3">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-[11px] font-medium text-slate-300">
                            Activa o desactiva las etapas del pipeline
                            para este job.
                          </span>
                          <div className="flex gap-2">
                            <button
                              type="button"
                              onClick={selectAllStages}
                              className="rounded-full bg-slate-800 px-2.5 py-1 text-[11px] text-slate-200 hover:bg-slate-700"
                            >
                              All
                            </button>
                            <button
                              type="button"
                              onClick={clearStages}
                              className="rounded-full bg-slate-800 px-2.5 py-1 text-[11px] text-slate-200 hover:bg-slate-700"
                            >
                              None
                            </button>
                          </div>
                        </div>

                        <div className="mt-3 space-y-2">
                          {availableStages.map((stage) => (
                            <label
                              key={stage.key}
                              className="flex cursor-pointer items-start gap-2 rounded-lg bg-slate-950/60 px-3 py-2 text-xs text-slate-200 hover:bg-slate-900"
                            >
                              <input
                                type="checkbox"
                                className="mt-[2px] h-3.5 w-3.5 rounded border-slate-600 bg-slate-900"
                                checked={selectedStageKeys.includes(
                                  stage.key,
                                )}
                                onChange={() => toggleStage(stage.key)}
                              />
                              <div>
                                <span className="font-semibold">
                                  {HUMAN_STAGE_TEXT[stage.key]?.title ??
                                    stage.label}
                                </span>
                                <p className="mt-0.5 text-[11px] text-slate-400">
                                  {HUMAN_STAGE_TEXT[stage.key]?.description ??
                                    stage.description ??
                                    ""}
                                </p>
                              </div>
                            </label>
                          ))}
                        </div>

                        <p className="mt-2 text-[11px] text-slate-500">
                          Las etapas desmarcadas se saltarán en el
                          pipeline. El orden y la lógica de cada etapa
                          siguen viniendo de{" "}
                          <code className="rounded bg-slate-950 px-1">
                            pipeline.py
                          </code>
                          .
                        </p>
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
                    {loading ? "Processing..." : "Generate AI Mix"}
                  </button>
                </div>

      {progressHeader && (
        <p className="mt-4 text-center text-sm font-mono text-slate-300">
          {progressHeader}
          {progressSubtext && (
            <>
              <br />
              <span className="font-sans text-[11px] text-slate-400">
                {progressSubtext}
              </span>
            </>
          )}
        </p>
      )}

                {error && (
                  <p className="mt-4 text-center text-sm text-red-400">
                    {error}
                  </p>
                )}
              </section>

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

      <footer className="border-t border-slate-800/80 py-4 text-center text-xs text-slate-500">
        © 2025 Audio Alchemy. All Rights Reserved.
      </footer>
    </div>
  );
}
