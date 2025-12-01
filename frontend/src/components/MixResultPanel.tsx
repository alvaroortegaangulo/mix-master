// frontend/src/components/MixResultPanel.tsx
"use client";

import { useEffect, useMemo, useState } from "react";
import type { MixResult } from "../lib/mixApi";
import { getBackendBaseUrl } from "../lib/mixApi";
import { MixPipelinePanel } from "./MixPipelinePanel";

type Props = {
  result: MixResult;
  /**
   * Lista de keys de stages del pipeline que se ejecutaron para ESTE job.
   * Son los mismos que usas en el selector inicial (dc_offset, loudness, static_mix_eq, etc.).
   */
  enabledPipelineStageKeys?: string[];
};

type StageKey =
  | "dc_offset"
  | "loudness"
  | "spectral_cleanup"
  | "dynamics"
  | "key"
  | "vocal_tuning"
  | "mastering";

type StageRow = Record<string, string>;

type StageOption = {
  key: StageKey;
  label: string;
  explanationTitle: string;
  intro: string;
  /**
   * Ruta relativa (desde /files/{jobId}) al CSV de análisis de esta etapa.
   * Se montará como:
   *   `${BACKEND_BASE_URL}/files/${jobId}${getCsvPath(jobId)}`
   */
  getCsvPath: (jobId: string) => string;
};


const PIPELINE_TO_STAGE_KEY: Partial<Record<string, StageKey>> = {
  dc_offset: "dc_offset",
  loudness: "loudness",
  static_mix_eq: "spectral_cleanup",
  static_mix_dyn: "dynamics",
  tempo_key: "key",
  vocal_tuning: "vocal_tuning",
  mastering: "mastering",
};


const STAGE_OPTIONS: StageOption[] = [
  {
    key: "dc_offset",
    label: "DC Offset (offset de continua)",
    explanationTitle: "Eliminación de DC offset",
    intro:
      "Primero se analiza si alguna pista tiene un desplazamiento de continua (DC offset). " +
      "Ese offset desplaza toda la forma de onda hacia arriba o abajo y resta headroom, " +
      "además de poder generar clics y comportamientos raros en compresores y limitadores.",
    getCsvPath: () => `/work/analysis/dc_offset_analysis.csv`,
  },
  {
    key: "loudness",
    label: "Loudness / Normalización de volumen",
    explanationTitle: "Normalización de loudness por pista",
    intro:
      "Se mide el nivel RMS y pico de cada stem, y se calcula la ganancia necesaria para " +
      "llevarlas a un objetivo común de loudness. Esto hace que todas las pistas trabajen " +
      "en una zona cómoda sin que unas queden enterradas ni otras saturen la mezcla.",
    getCsvPath: () => `/work/analysis/loudness_analysis.csv`,
  },
  {
    key: "spectral_cleanup",
    label: "Limpieza espectral (HPF + notches)",
    explanationTitle: "Limpieza espectral y filtros de resonancias",
    intro:
      "Se analiza el contenido en graves de cada pista para recomendar filtros pasa-altos " +
      "y se buscan resonancias estrechas para recortarlas con filtros notch. " +
      "Esto limpia el 'emborronamiento' en graves y recorta picos molestos en medio/agudos.",
    getCsvPath: () => `/work/analysis/spectral_cleanup_analysis.csv`,
  },
  {
    key: "dynamics",
    label: "Dinámica (compresión y limitador por pista)",
    explanationTitle: "Control de dinámica por canal",
    intro:
      "Se miden RMS, pico y factor de cresta de cada pista y, en función de su perfil, " +
      "se decide si aplicar compresión y limitador. Esto ayuda a controlar transitorios " +
      "sin matar la pegada natural del instrumento.",
    getCsvPath: () => `/work/analysis/dynamics_analysis.csv`,
  },
  {
    key: "key",
    label: "Tempo & Key del tema",
    explanationTitle: "Detección de tonalidad del tema",
    intro:
      "A partir del full mix se estima la tonalidad del tema (key + escala) y la confianza " +
      "de esa estimación. Esto se usa después para afinar la voz correctamente.",
    getCsvPath: () => `/work/analysis/key_analysis.csv`,
  },
  {
    key: "vocal_tuning",
    label: "Vocal tuning / Auto-Tune",
    explanationTitle: "Afinación de la voz principal",
    intro:
      "Se aplica corrección de afinación a la voz principal según la tonalidad detectada. " +
      "Se registra cuántos semitonos corrige hacia arriba o hacia abajo para tener una " +
      "idea de cuánto 'trabajo' está haciendo el autotune.",
    getCsvPath: () => `/work/analysis/vocal_autotune_log.csv`,
  },
  {
    key: "mastering",
    label: "Mastering por stems",
    explanationTitle: "Ajustes de mastering por pista",
    intro:
      "En la fase de mastering se analiza el pico y el RMS de cada stem para decidir " +
      "cuánta ganancia extra empujar hacia el limitador y cómo equilibrar el conjunto " +
      "respecto al nivel objetivo final.",
    getCsvPath: () => `/work/analysis/mastering_analysis.csv`,
  },
];

// ------------------------------------------------------------------
// Utils CSV / numéricos
// ------------------------------------------------------------------

function parseCsv(text: string): { headers: string[]; rows: StageRow[] } {
  const lines = text.split(/\r?\n/).filter((l) => l.trim().length > 0);
  if (lines.length === 0) {
    return { headers: [], rows: [] };
  }

  const headers = lines[0].split(",").map((h) => h.trim());
  const rows: StageRow[] = lines.slice(1).map((line) => {
    const cols = line.split(",");
    const row: StageRow = {};
    headers.forEach((h, i) => {
      row[h] = (cols[i] ?? "").trim();
    });
    return row;
  });

  return { headers, rows };
}

function toNumber(value: string | undefined): number | null {
  if (!value) return null;
  const normalized = value.replace(",", ".");
  const n = Number(normalized);
  return Number.isFinite(n) ? n : null;
}

// ------------------------------------------------------------------
// Resúmenes y explicaciones por etapa
// ------------------------------------------------------------------

// DC OFFSET --------------------------------------------------------

type DcOffsetSummary = {
  trackCount: number;
  numCorrected: number;
  avgOffset: number | null;
  maxOffset: number | null;
};

function summarizeDcOffset(rows: StageRow[]): DcOffsetSummary | null {
  if (!rows.length) return null;
  const offsets: number[] = [];
  let numCorrected = 0;

  for (const row of rows) {
    const v = toNumber(row["max_abs_dc_offset"]);
    if (v === null) continue;
    offsets.push(v);
    if (v > 0.0005) {
      // ~0.05% del nivel máximo
      numCorrected += 1;
    }
  }

  if (!offsets.length) return null;
  const sum = offsets.reduce((a, b) => a + b, 0);
  const avg = sum / offsets.length;
  const max = Math.max(...offsets);

  return {
    trackCount: rows.length,
    numCorrected,
    avgOffset: avg,
    maxOffset: max,
  };
}

function explainDcOffsetRow(row: StageRow): string | null {
  const maxOffset = toNumber(row["max_abs_dc_offset"]);
  if (maxOffset === null || maxOffset < 0.0005) return null;

  const filename =
    row["filename"] || row["relative_path"] || "Pista sin nombre";

  const percent = maxOffset * 100;
  return `${filename}: se detectó un DC offset máximo de ${percent.toFixed(
    2,
  )} % del nivel de señal. En la corrección se centra la forma de onda alrededor de 0 para recuperar headroom y evitar artefactos.`;
}

// LOUDNESS ---------------------------------------------------------

type LoudnessSummary = {
  trackCount: number;
  targetRms: number | null;
  minGain: number | null;
  maxGain: number | null;
};

function summarizeLoudness(rows: StageRow[]): LoudnessSummary | null {
  if (!rows.length) return null;

  let targetRms: number | null = null;
  const gains: number[] = [];

  for (const row of rows) {
    if (targetRms === null) {
      targetRms = toNumber(row["target_rms_dbfs"]);
    }
    const g = toNumber(row["gain_db_to_target_rms"]);
    if (g !== null) gains.push(g);
  }

  let minGain: number | null = null;
  let maxGain: number | null = null;
  if (gains.length > 0) {
    minGain = Math.min(...gains);
    maxGain = Math.max(...gains);
  }

  return {
    trackCount: rows.length,
    targetRms,
    minGain,
    maxGain,
  };
}

function explainLoudnessRow(row: StageRow): string | null {
  const filename =
    row["filename"] || row["relative_path"] || "Pista sin nombre";

  const originalRms = toNumber(row["rms_dbfs"]);
  const targetRms = toNumber(row["target_rms_dbfs"]);
  const gain = toNumber(row["gain_db_to_target_rms"]);

  const parts: string[] = [];

  if (gain !== null) {
    parts.push(
      `se ha calculado un ajuste de ${
        gain >= 0 ? `+${gain.toFixed(1)} dB` : `${gain.toFixed(1)} dB`
      }`,
    );
  }

  if (originalRms !== null && targetRms !== null) {
    parts.push(
      `para acercar el RMS desde ${originalRms.toFixed(
        1,
      )} dBFS hacia un objetivo de ${targetRms.toFixed(1)} dBFS`,
    );
  }

  if (!parts.length) return null;
  return `${filename}: ${parts.join(", ")}.`;
}

// ESPECTRAL --------------------------------------------------------

type SpectralSummary = {
  trackCount: number;
  tracksWithHpf: number;
  medianHpf: number | null;
  totalNotches: number;
};

function summarizeSpectral(rows: StageRow[]): SpectralSummary | null {
  if (!rows.length) return null;

  const hpfVals: number[] = [];
  let tracksWithHpf = 0;
  let totalNotches = 0;

  for (const row of rows) {
    const hpf = toNumber(row["recommended_hpf_cutoff_hz"]);
    if (hpf !== null && hpf > 0) {
      hpfVals.push(hpf);
      tracksWithHpf += 1;
    }

    const numNotches = toNumber(row["num_notches"]);
    if (numNotches !== null && numNotches > 0) {
      totalNotches += numNotches;
    }
  }

  let medianHpf: number | null = null;
  if (hpfVals.length > 0) {
    const sorted = [...hpfVals].sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    medianHpf =
      sorted.length % 2 === 0
        ? (sorted[mid - 1] + sorted[mid]) / 2
        : sorted[mid];
  }

  return {
    trackCount: rows.length,
    tracksWithHpf,
    medianHpf,
    totalNotches,
  };
}

function explainSpectralRow(row: StageRow): string | null {
  const filename =
    row["filename"] || row["relative_path"] || "Pista sin nombre";
  const hpf = toNumber(row["recommended_hpf_cutoff_hz"]);
  const numNotches = toNumber(row["num_notches"]);

  const parts: string[] = [];

  if (hpf !== null && hpf > 0) {
    parts.push(`se recomienda un HPF en torno a ${hpf.toFixed(0)} Hz`);
  }

  if (numNotches !== null && numNotches > 0) {
    parts.push(
      `se han identificado aproximadamente ${numNotches.toFixed(
        0,
      )} resonancias estrechas para recortar con notches`,
    );
  }

  if (!parts.length) return null;
  return `${filename}: ${parts.join(", ")}.`;
}

// DINÁMICA ---------------------------------------------------------

type DynamicsSummary = {
  trackCount: number;
  compEnabledCount: number;
  limiterEnabledCount: number;
  medianCrest: number | null;
};

function summarizeDynamics(rows: StageRow[]): DynamicsSummary | null {
  if (!rows.length) return null;

  let compEnabled = 0;
  let limiterEnabled = 0;
  const crests: number[] = [];

  for (const row of rows) {
    if (row["comp_enabled"] === "1" || row["comp_enabled"] === "true") {
      compEnabled += 1;
    }
    if (row["limiter_enabled"] === "1" || row["limiter_enabled"] === "true") {
      limiterEnabled += 1;
    }
    const cf = toNumber(row["crest_factor_db"]);
    if (cf !== null) crests.push(cf);
  }

  let medianCrest: number | null = null;
  if (crests.length > 0) {
    const sorted = [...crests].sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    medianCrest =
      sorted.length % 2 === 0
        ? (sorted[mid - 1] + sorted[mid]) / 2
        : sorted[mid];
  }

  return {
    trackCount: rows.length,
    compEnabledCount: compEnabled,
    limiterEnabledCount: limiterEnabled,
    medianCrest,
  };
}

function explainDynamicsRow(row: StageRow): string | null {
  const filename =
    row["filename"] || row["relative_path"] || "Pista sin nombre";
  const profile = row["instrument_profile"] || "";
  const compEnabled =
    row["comp_enabled"] === "1" || row["comp_enabled"] === "true";
  const limiterEnabled =
    row["limiter_enabled"] === "1" || row["limiter_enabled"] === "true";
  const threshold = toNumber(row["comp_threshold_dbfs"]);
  const ratio = toNumber(row["comp_ratio"]);

  const parts: string[] = [];

  if (profile) {
    parts.push(`perfil detectado: ${profile}`);
  }

  if (compEnabled && threshold !== null && ratio !== null) {
    parts.push(
      `compresión alrededor de ${threshold.toFixed(1)} dBFS con ratio ${ratio.toFixed(
        1,
      )}:1`,
    );
  } else if (compEnabled) {
    parts.push(`compresión suave activada`);
  }

  if (limiterEnabled) {
    const lt = toNumber(row["limiter_threshold_dbfs"]);
    parts.push(
      `limitador para controlar picos${lt !== null ? ` por encima de ${lt.toFixed(1)} dBFS` : ""}`,
    );
  }

  if (!parts.length) return null;
  return `${filename}: ${parts.join(", ")}.`;
}

// KEY --------------------------------------------------------------

type KeySummary = {
  key: string;
  scale: string;
  strength: number | null;
};

function summarizeKey(rows: StageRow[]): KeySummary | null {
  if (!rows.length) return null;
  const row = rows[0];
  const key = row["key"] || "";
  const scale = row["scale"] || "";
  const strength = toNumber(row["strength"]);
  if (!key || !scale) return null;
  return { key, scale, strength };
}

// VOCAL TUNING -----------------------------------------------------

type VocalSummary = {
  shiftMin: number | null;
  shiftMax: number | null;
  shiftMean: number | null;
};

function summarizeVocal(rows: StageRow[]): VocalSummary | null {
  if (!rows.length) return null;
  const row = rows[0];

  return {
    shiftMin: toNumber(row["shift_semitones_min"]),
    shiftMax: toNumber(row["shift_semitones_max"]),
    shiftMean: toNumber(row["shift_semitones_mean"]),
  };
}

// MASTERING --------------------------------------------------------

type MasteringSummary = {
  trackCount: number;
  targetPeak: number | null;
  minDrive: number | null;
  maxDrive: number | null;
};

function summarizeMastering(rows: StageRow[]): MasteringSummary | null {
  if (!rows.length) return null;
  let targetPeak: number | null = null;
  const drives: number[] = [];

  for (const row of rows) {
    if (targetPeak === null) {
      targetPeak = toNumber(row["recommended_target_peak_dbfs"]);
    }
    const drive = toNumber(row["recommended_drive_db"]);
    if (drive !== null) drives.push(drive);
  }

  let minDrive: number | null = null;
  let maxDrive: number | null = null;
  if (drives.length > 0) {
    minDrive = Math.min(...drives);
    maxDrive = Math.max(...drives);
  }

  return {
    trackCount: rows.length,
    targetPeak,
    minDrive,
    maxDrive,
  };
}

function explainMasteringRow(row: StageRow): string | null {
  const filename =
    row["filename"] || row["relative_path"] || "Pista sin nombre";
  const isVocal = row["is_vocal"] === "1" || row["is_vocal"] === "true";
  const drive = toNumber(row["recommended_drive_db"]);
  const targetPeak = toNumber(row["recommended_target_peak_dbfs"]);

  const parts: string[] = [];

  if (isVocal) {
    parts.push("pista vocal");
  }

  if (drive !== null) {
    parts.push(
      `se recomienda empujar ${drive >= 0 ? `+${drive.toFixed(2)} dB` : `${drive.toFixed(2)} dB`}`,
    );
  }

  if (targetPeak !== null) {
    parts.push(`para llegar aproximadamente a un pico de ${targetPeak.toFixed(1)} dBFS`);
  }

  if (!parts.length) return null;
  return `${filename}: ${parts.join(", ")}.`;
}

// ------------------------------------------------------------------
// Componente principal
// ------------------------------------------------------------------

export function MixResultPanel({
  result,
  enabledPipelineStageKeys,
}: Props) {
  const { originalFullSongUrl, fullSongUrl, metrics, jobId } = result;

  const [selectedStageKey, setSelectedStageKey] = useState<StageKey | "">("");
  const [csvHeaders, setCsvHeaders] = useState<string[]>([]);
  const [csvRows, setCsvRows] = useState<StageRow[] | null>(null);
  const [csvLoading, setCsvLoading] = useState(false);
  const [csvError, setCsvError] = useState<string | null>(null);

  // Filtrar STAGE_OPTIONS en función de los stages realmente ejecutados
  const stageOptionsForJob = useMemo(() => {
    if (!enabledPipelineStageKeys || enabledPipelineStageKeys.length === 0) {
      // Si no nos dicen nada, mostramos todas (comportamiento anterior)
      return STAGE_OPTIONS;
    }


    const enabledStageKeys = new Set<StageKey>();
    for (const pipelineKey of enabledPipelineStageKeys) {
      const mapped = PIPELINE_TO_STAGE_KEY[pipelineKey];
      if (mapped) {
        enabledStageKeys.add(mapped);
      }
    }

    if (enabledStageKeys.size === 0) {
      return STAGE_OPTIONS;
    }

    return STAGE_OPTIONS.filter((opt) => enabledStageKeys.has(opt.key));
  }, [enabledPipelineStageKeys]);



  // Si cambia el conjunto de opciones (nuevo job o selección distinta),
  // y la etapa seleccionada ya no existe, reseteamos el selector.
  useEffect(() => {
    if (!selectedStageKey) return;
    const exists = stageOptionsForJob.some((s) => s.key === selectedStageKey);
    if (!exists) {
      setSelectedStageKey("");
    }
  }, [stageOptionsForJob, selectedStageKey]);

  const selectedStage = useMemo(
    () =>
      stageOptionsForJob.find((s) => s.key === selectedStageKey) ?? null,
    [selectedStageKey, stageOptionsForJob],
  );

  // Cargar CSV cuando cambia la etapa
  useEffect(() => {
    if (!selectedStage) {
      setCsvHeaders([]);
      setCsvRows(null);
      setCsvError(null);
      return;
    }


    const baseUrl = getBackendBaseUrl();
    const url = `${baseUrl}/files/${encodeURIComponent(
      jobId,
    )}${selectedStage.getCsvPath(jobId)}`;
    const controller = new AbortController();

    async function loadCsv() {
      setCsvLoading(true);
      setCsvError(null);
      try {
        const res = await fetch(url, { signal: controller.signal });
        if (!res.ok) {
          throw new Error(`No se pudo leer el CSV (${res.status})`);
        }
        const text = await res.text();
        const { headers, rows } = parseCsv(text);
        setCsvHeaders(headers);
        setCsvRows(rows);
      } catch (err: any) {
        if (err?.name === "AbortError") return;
        console.error("Error cargando CSV de análisis", err);
        setCsvError(
          err?.message ?? "Error leyendo el fichero de análisis para esta etapa.",
        );
        setCsvHeaders([]);
        setCsvRows(null);
      } finally {
        setCsvLoading(false);
      }
    }

    void loadCsv();
    return () => controller.abort();
  }, [selectedStage, jobId]);

  // Resúmenes por etapa (sólo cuando corresponde)
  const dcSummary = useMemo(() => {
    if (!selectedStage || selectedStage.key !== "dc_offset") return null;
    if (!csvRows) return null;
    return summarizeDcOffset(csvRows);
  }, [selectedStage, csvRows]);

  const loudnessSummary = useMemo(() => {
    if (!selectedStage || selectedStage.key !== "loudness") return null;
    if (!csvRows) return null;
    return summarizeLoudness(csvRows);
  }, [selectedStage, csvRows]);

  const spectralSummary = useMemo(() => {
    if (!selectedStage || selectedStage.key !== "spectral_cleanup") return null;
    if (!csvRows) return null;
    return summarizeSpectral(csvRows);
  }, [selectedStage, csvRows]);

  const dynamicsSummary = useMemo(() => {
    if (!selectedStage || selectedStage.key !== "dynamics") return null;
    if (!csvRows) return null;
    return summarizeDynamics(csvRows);
  }, [selectedStage, csvRows]);

  const keySummary = useMemo(() => {
    if (!selectedStage || selectedStage.key !== "key") return null;
    if (!csvRows) return null;
    return summarizeKey(csvRows);
  }, [selectedStage, csvRows]);

  const vocalSummary = useMemo(() => {
    if (!selectedStage || selectedStage.key !== "vocal_tuning") return null;
    if (!csvRows) return null;
    return summarizeVocal(csvRows);
  }, [selectedStage, csvRows]);

  const masteringSummary = useMemo(() => {
    if (!selectedStage || selectedStage.key !== "mastering") return null;
    if (!csvRows) return null;
    return summarizeMastering(csvRows);
  }, [selectedStage, csvRows]);

  return (
    <section className="mt-10 rounded-2xl border border-slate-800/80 bg-slate-900/80 p-6 shadow-xl">
      <h2 className="mb-4 text-xl font-semibold text-slate-50">Your AI Mix</h2>

      {/* Players */}
      <div className="grid gap-6 md:grid-cols-2">
        <div>
          <p className="mb-1 text-sm font-medium text-slate-200">
            Original mix (antes del procesamiento)
          </p>
          <audio
            controls
            src={originalFullSongUrl}
            className="mt-1 w-full rounded-lg bg-slate-800"
          />
        </div>
        <div>
          <p className="mb-1 text-sm font-medium text-slate-200">
            AI mix & mastering (resultado)
          </p>
          <audio
            controls
            src={fullSongUrl}
            className="mt-1 w-full rounded-lg bg-slate-800"
          />
        </div>
      </div>
      

      {/* Panel Pipeline: solo stages elegidos */}
      <MixPipelinePanel
        result={result}
        enabledPipelineStageKeys={enabledPipelineStageKeys}
      />


      {/* Métricas principales (colapsadas) */}
      <details className="mt-6 rounded-xl bg-slate-950/40 p-4">
        <summary className="flex cursor-pointer list-none flex-col [&::-webkit-details-marker]:hidden">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
            Metrics
          </h3>
          <p className="mt-1 text-xs text-slate-400">
            Resumen del loudness final, la afinación vocal y el tempo/tonalidad
            del master.
          </p>
        </summary>

        <div className="mt-4 grid gap-4 md:grid-cols-3">
          <div>
            <p className="text-xs uppercase text-slate-400">Loudness</p>
            <p className="text-sm text-slate-200">
              Peak:{" "}
              <span className="font-semibold">
                {metrics.final_peak_dbfs.toFixed(1)} dBFS
              </span>
            </p>
            <p className="text-sm text-slate-200">
              RMS:{" "}
              <span className="font-semibold">
                {metrics.final_rms_dbfs.toFixed(1)} dBFS
              </span>
            </p>
          </div>
          <div>
            <p className="text-xs uppercase text-slate-400">Vocal tuning</p>
            <p className="text-sm text-slate-200">
              Shift medio:{" "}
              <span className="font-semibold">
                {metrics.vocal_shift_mean.toFixed(2)} semitonos
              </span>
            </p>
            <p className="text-xs text-slate-400">
              Rango:{" "}
              {metrics.vocal_shift_min.toFixed(2)} –{" "}
              {metrics.vocal_shift_max.toFixed(2)} st
            </p>
          </div>
          <div>
            <p className="text-xs uppercase text-slate-400">Tempo &amp; key</p>
            <p className="text-sm text-slate-200">
              Tempo:{" "}
              <span className="font-semibold">
                {metrics.tempo_bpm.toFixed(1)} BPM
              </span>
            </p>
            <p className="text-sm text-slate-200">
              Key:{" "}
              <span className="font-semibold">
                {metrics.key} {metrics.scale}
              </span>
            </p>
          </div>
        </div>
        </div>
      </details>



       {/* Selector de etapa / detalles de logs (colapsado) */}
      <details className="mt-8 border-t border-slate-800/70 pt-6">
        <summary className="cursor-pointer list-none [&::-webkit-details-marker]:hidden">
          <h3 className="mb-1 text-sm font-semibold uppercase tracking-wide text-slate-400">
            Detalles del procesamiento
          </h3>
          <p className="text-xs text-slate-400">
            Selecciona una etapa del pipeline para ver un resumen de los cambios
            aplicados, extraído directamente de los ficheros de análisis.
          </p>
        </summary>

        <div className="mt-4">
          <div className="flex flex-col gap-3 md:flex-row md:items-center">
            <label className="text-xs font-medium text-slate-300 md:w-48">
              Etapa:
            </label>
            <select
              value={selectedStageKey}
              onChange={(e) =>
                setSelectedStageKey(e.target.value as StageKey | "")
              }
              className="w-full rounded-lg border border-slate-700 bg-slate-900/70 px-3 py-2 text-xs text-slate-100 outline-none transition hover:border-slate-500 focus:border-indigo-400 focus:ring-1 focus:ring-indigo-400 md:w-80"
            >
              <option value="">Selecciona una etapa…</option>
              {STAGE_OPTIONS.map((stage) => (
                <option key={stage.key} value={stage.key}>
                  {stage.label}
                </option>
              ))}
            </select>
          </div>

          {/* Panel explicativo de cada etapa */}
          {selectedStage && (
            <div className="mt-5 rounded-xl border border-slate-800 bg-slate-950/50 p-4">
              <h4 className="text-sm font-semibold text-slate-100">
                {selectedStage.explanationTitle}
              </h4>
              <p className="mt-2 text-xs text-slate-300">
                {selectedStage.intro}
              </p>

              {csvLoading && (
                <p className="mt-3 text-xs text-slate-400">
                  Cargando datos de análisis de esta etapa…
                </p>
              )}

              {csvError && (
                <p className="mt-3 text-xs text-red-400">{csvError}</p>
              )}

              {!csvLoading &&
                !csvError &&
                (!csvRows || csvRows.length === 0) && (
                  <p className="mt-3 text-xs text-slate-400">
                    No se han encontrado filas en el CSV de esta etapa. Es
                    posible que el pipeline no haya generado todavía el
                    fichero o que la estructura haya cambiado.
                  </p>
                )}

              {/* Resúmenes por etapa, sólo cuando hay datos */}
              {!csvLoading && !csvError && csvRows && csvRows.length > 0 && (
                <>
                  {/* aquí mantienes TODO tu bloque actual:
                      DC OFFSET, LOUDNESS, SPECTRAL, DYNAMICS, KEY,
                      VOCAL_TUNING, MASTERING, etc. No hace falta tocarlo,
                      solo déjalo dentro de este fragmento */}
                </>
              )}
            </div>
          )}
        </div>
      </details>



            {/* Resúmenes por etapa, sólo cuando hay datos */}
            {!csvLoading && !csvError && csvRows && csvRows.length > 0 && (
              <>
                {/* DC OFFSET */}
                {selectedStage.key === "dc_offset" && dcSummary && (
                  <div className="mt-3 text-xs text-slate-200">
                    <p>
                      Se han analizado{" "}
                      <span className="font-semibold">
                        {dcSummary.trackCount}
                      </span>{" "}
                      pistas en busca de DC offset.
                    </p>
                    {dcSummary.numCorrected > 0 && (
                      <p className="mt-1">
                        En{" "}
                        <span className="font-semibold">
                          {dcSummary.numCorrected}
                        </span>{" "}
                        pistas se ha detectado un offset significativo y se ha
                        corregido para recentrar la señal.
                      </p>
                    )}
                    {dcSummary.maxOffset !== null && (
                      <p className="mt-1 text-slate-300">
                        El offset máximo observado ronda{" "}
                        <span className="font-semibold">
                          {(dcSummary.maxOffset * 100).toFixed(2)} %
                        </span>{" "}
                        del nivel de señal.
                      </p>
                    )}
                    <div className="mt-3 space-y-1">
                      {csvRows.slice(0, 4).map((row, i) => {
                        const s = explainDcOffsetRow(row);
                        return s ? (
                          <p key={i} className="text-slate-300">
                            • {s}
                          </p>
                        ) : null;
                      })}
                    </div>
                  </div>
                )}

                {/* LOUDNESS */}
                {selectedStage.key === "loudness" && loudnessSummary && (
                  <div className="mt-3 text-xs text-slate-200">
                    <p>
                      Se han analizado{" "}
                      <span className="font-semibold">
                        {loudnessSummary.trackCount}
                      </span>{" "}
                      pistas para normalizar su loudness.
                    </p>
                    {loudnessSummary.targetRms !== null && (
                      <p className="mt-1 text-slate-300">
                        Objetivo de RMS:{" "}
                        <span className="font-semibold">
                          {loudnessSummary.targetRms.toFixed(1)} dBFS
                        </span>
                        .
                      </p>
                    )}
                    {loudnessSummary.minGain !== null &&
                      loudnessSummary.maxGain !== null && (
                        <p className="mt-1 text-slate-300">
                          Los ajustes de ganancia van desde{" "}
                          <span className="font-semibold">
                            {loudnessSummary.minGain.toFixed(1)} dB
                          </span>{" "}
                          hasta{" "}
                          <span className="font-semibold">
                            {loudnessSummary.maxGain.toFixed(1)} dB
                          </span>
                          , elevando pistas débiles y atenuando las demasiado
                          fuertes.
                        </p>
                      )}
                    <div className="mt-3 space-y-1">
                      {csvRows.slice(0, 4).map((row, i) => {
                        const s = explainLoudnessRow(row);
                        return s ? (
                          <p key={i} className="text-slate-300">
                            • {s}
                          </p>
                        ) : null;
                      })}
                    </div>
                  </div>
                )}

                {/* SPECTRAL */}
                {selectedStage.key === "spectral_cleanup" &&
                  spectralSummary && (
                    <div className="mt-3 text-xs text-slate-200">
                      <p>
                        Se han pasado por la etapa de limpieza espectral{" "}
                        <span className="font-semibold">
                          {spectralSummary.trackCount}
                        </span>{" "}
                        pistas.
                      </p>
                      {spectralSummary.tracksWithHpf > 0 && (
                        <p className="mt-1 text-slate-300">
                          En{" "}
                          <span className="font-semibold">
                            {spectralSummary.tracksWithHpf}
                          </span>{" "}
                          pistas se recomienda aplicar un HPF para eliminar
                          graves innecesarios.
                          {spectralSummary.medianHpf !== null && (
                            <>
                              {" "}
                              La frecuencia de corte típica ronda{" "}
                              <span className="font-semibold">
                                {spectralSummary.medianHpf.toFixed(0)} Hz
                              </span>
                              .
                            </>
                          )}
                        </p>
                      )}
                      {spectralSummary.totalNotches > 0 && (
                        <p className="mt-1 text-slate-300">
                          Se han detectado en total{" "}
                          <span className="font-semibold">
                            {spectralSummary.totalNotches}
                          </span>{" "}
                          resonancias a recortar con notches.
                        </p>
                      )}
                      <div className="mt-3 space-y-1">
                        {csvRows.slice(0, 4).map((row, i) => {
                          const s = explainSpectralRow(row);
                          return s ? (
                            <p key={i} className="text-slate-300">
                              • {s}
                            </p>
                          ) : null;
                        })}
                      </div>
                    </div>
                  )}

                {/* DINÁMICA */}
                {selectedStage.key === "dynamics" && dynamicsSummary && (
                  <div className="mt-3 text-xs text-slate-200">
                    <p>
                      Se han analizado{" "}
                      <span className="font-semibold">
                        {dynamicsSummary.trackCount}
                      </span>{" "}
                      pistas a nivel dinámico.
                    </p>
                    <p className="mt-1 text-slate-300">
                      Compresión activada en{" "}
                      <span className="font-semibold">
                        {dynamicsSummary.compEnabledCount}
                      </span>{" "}
                      pistas y limitador en{" "}
                      <span className="font-semibold">
                        {dynamicsSummary.limiterEnabledCount}
                      </span>
                      .
                    </p>
                    {dynamicsSummary.medianCrest !== null && (
                      <p className="mt-1 text-slate-300">
                        El factor de cresta típico ronda{" "}
                        <span className="font-semibold">
                          {dynamicsSummary.medianCrest.toFixed(1)} dB
                        </span>
                        , lo que indica la relación entre transitorios y nivel
                        medio.
                      </p>
                    )}
                    <div className="mt-3 space-y-1">
                      {csvRows.slice(0, 4).map((row, i) => {
                        const s = explainDynamicsRow(row);
                        return s ? (
                          <p key={i} className="text-slate-300">
                            • {s}
                          </p>
                        ) : null;
                      })}
                    </div>
                  </div>
                )}

                {/* KEY */}
                {selectedStage.key === "key" && keySummary && (
                  <div className="mt-3 text-xs text-slate-200">
                    <p>
                      El tema se ha estimado en{" "}
                      <span className="font-semibold">
                        {keySummary.key} {keySummary.scale}
                      </span>
                      .
                    </p>
                    {keySummary.strength !== null && (
                      <p className="mt-1 text-slate-300">
                        Confianza de la estimación:{" "}
                        <span className="font-semibold">
                          {(keySummary.strength * 100).toFixed(1)} %
                        </span>
                        .
                      </p>
                    )}
                    <p className="mt-2 text-slate-300">
                      Esta tonalidad se usa como referencia para la etapa de
                      vocal tuning y para asegurar que los ajustes armónicos
                      respetan la armonía del tema.
                    </p>
                  </div>
                )}

                {/* VOCAL TUNING */}
                {selectedStage.key === "vocal_tuning" && vocalSummary && (
                  <div className="mt-3 text-xs text-slate-200">
                    {vocalSummary.shiftMean !== null && (
                      <p>
                        El autotune ha corregido la voz una media de{" "}
                        <span className="font-semibold">
                          {vocalSummary.shiftMean.toFixed(2)} semitonos
                        </span>{" "}
                        respecto a la afinación original.
                      </p>
                    )}
                    {vocalSummary.shiftMin !== null &&
                      vocalSummary.shiftMax !== null && (
                        <p className="mt-1 text-slate-300">
                          El rango de corrección va desde{" "}
                          <span className="font-semibold">
                            {vocalSummary.shiftMin.toFixed(2)} st
                          </span>{" "}
                          hasta{" "}
                          <span className="font-semibold">
                            {vocalSummary.shiftMax.toFixed(2)} st
                          </span>
                          .
                        </p>
                      )}
                    <p className="mt-2 text-slate-300">
                      Valores cercanos a 0 significan que la toma ya estaba muy
                      afinada; valores altos indican intervenciones más
                      agresivas.
                    </p>
                  </div>
                )}

                {/* MASTERING */}
                {selectedStage.key === "mastering" && masteringSummary && (
                  <div className="mt-3 text-xs text-slate-200">
                    <p>
                      En mastering se han analizado{" "}
                      <span className="font-semibold">
                        {masteringSummary.trackCount}
                      </span>{" "}
                      stems.
                    </p>
                    {masteringSummary.targetPeak !== null && (
                      <p className="mt-1 text-slate-300">
                        El sistema apunta a un pico objetivo en torno a{" "}
                        <span className="font-semibold">
                          {masteringSummary.targetPeak.toFixed(1)} dBFS
                        </span>
                        .
                      </p>
                    )}
                    {masteringSummary.minDrive !== null &&
                      masteringSummary.maxDrive !== null && (
                        <p className="mt-1 text-slate-300">
                          Las recomendaciones de drive por pista van desde{" "}
                          <span className="font-semibold">
                            {masteringSummary.minDrive.toFixed(2)} dB
                          </span>{" "}
                          hasta{" "}
                          <span className="font-semibold">
                            {masteringSummary.maxDrive.toFixed(2)} dB
                          </span>
                          , empujando más las pistas que admiten nivel sin
                          distorsionar y conteniendo las que ya van altas.
                        </p>
                      )}
                    <div className="mt-3 space-y-1">
                      {csvRows.slice(0, 4).map((row, i) => {
                        const s = explainMasteringRow(row);
                        return s ? (
                          <p key={i} className="text-slate-300">
                            • {s}
                          </p>
                        ) : null;
                      })}
                    </div>
                  </div>
                )}
              </>
            )}

            {/* Tabla genérica del CSV */}
            {csvRows && csvRows.length > 0 && !csvLoading && (
              <div className="mt-4 max-h-64 overflow-auto rounded-lg border border-slate-800 bg-slate-950/70">
                <table className="min-w-full text-xs">
                  <thead className="bg-slate-900">
                    <tr>
                      {csvHeaders.map((h) => (
                        <th
                          key={h}
                          className="px-2 py-1 text-left font-semibold text-slate-300"
                        >
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {csvRows.slice(0, 80).map((row, idx) => (
                      <tr
                        key={idx}
                        className="border-t border-slate-800/60 odd:bg-slate-950/40"
                      >
                        {csvHeaders.map((h) => (
                          <td key={h} className="px-2 py-1 text-slate-200">
                            {row[h] ?? ""}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {!csvLoading &&
              !csvError &&
              (!csvRows || csvRows.length === 0) && (
                <p className="mt-3 text-xs text-slate-400">
                  No se han encontrado filas en el CSV de esta etapa. Es posible
                  que el pipeline no haya generado todavía el fichero o que la
                  estructura haya cambiado.
                </p>
              )}
          </div>
        )}
      </div>
    </section>
  );
}
