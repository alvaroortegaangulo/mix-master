// frontend/src/components/MixResultPanel.tsx
"use client";

import { useEffect, useMemo, useState } from "react";
import type { MixResult } from "../lib/mixApi";
import { getBackendBaseUrl } from "../lib/mixApi";
import { MixPipelinePanel } from "./MixPipelinePanel";
import { FinalReportModal } from "./FinalReportModal";

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
  | "space_depth"
  | "key_detection"
  | "vocal_tuning"
  | "mastering";

type StageOption = {
  key: StageKey;
  label: string;
  explanationTitle: string;
  intro: string;
  getCsvPath: () => string;
};

const STAGE_OPTIONS: StageOption[] = [
  {
    key: "dc_offset",
    label: "DC Offset / Pistas corruptas",
    explanationTitle: "Detección y corrección de DC offset",
    intro:
      "En esta etapa se analizan los stems uno a uno para detectar si tienen un desplazamiento " +
      "de DC offset (la forma de onda no está centrada en 0). Un DC offset pronunciado puede " +
      "reducir el headroom y provocar recortes innecesarios en etapas posteriores. Cuando se " +
      "detecta un offset significativo, se corrige y se deja registrado en el log.",
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
      "y se buscan resonancias estrechas para atenuarlas con notches suaves. Esto reduce " +
      "el ruido de baja frecuencia y las frecuencias estridentes que suelen enturbiar la mezcla.",
    getCsvPath: () => `/work/analysis/spectral_cleanup_analysis.csv`,
  },
  {
    key: "dynamics",
    label: "Dinámica por stems",
    explanationTitle: "Control de dinámica por pista",
    intro:
      "Se detectan los picos y el rango dinámico de cada stem para decidir si es necesario " +
      "usar compresión o limitación. El objetivo es controlar los picos agresivos manteniendo " +
      "el carácter dinámico de la interpretación.",
    getCsvPath: () => `/work/analysis/dynamics_analysis.csv`,
  },
  {
    key: "space_depth",
    label: "Reverb / Espacio y profundidad",
    explanationTitle: "Diseño de espacio y profundidad",
    intro:
      "Se asignan buses de reverb y se analizan los tiempos/decaimientos para situar cada stem " +
      "en un plano de profundidad: elementos frontales más secos, elementos de acompañamiento " +
      "más envueltos en reverb. Esto ayuda a construir la sensación de espacio en la mezcla.",
    getCsvPath: () => `/work/analysis/space_depth_analysis.csv`,
  },
  {
    key: "key_detection",
    label: "Detección de tonalidad",
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
// Utils
// ------------------------------------------------------------------

type StageRow = Record<string, string>;

function toNumber(value: string | undefined | null): number | null {
  if (value == null) return null;
  const v = Number(value);
  return Number.isFinite(v) ? v : null;
}

function formatDb(db: number | null, fallback = "N/A"): string {
  if (db == null || Number.isNaN(db)) return fallback;
  return `${db.toFixed(1)} dB`;
}

function formatSeconds(sec: number | null, fallback = "N/A"): string {
  if (sec == null || Number.isNaN(sec)) return fallback;
  if (sec < 1) return `${(sec * 1000).toFixed(0)} ms`;
  return `${sec.toFixed(2)} s`;
}

// ------------------------------------------------------------------
// Resúmenes por etapa (para los textos explicativos)
// ------------------------------------------------------------------

type DcOffsetSummary = {
  trackCount: number;
  numCorrected: number;
  avgBefore: number | null;
  avgAfter: number | null;
  maxOffset: number | null;
};

type LoudnessSummary = {
  trackCount: number;
  targetRms: number | null;
  minGain: number | null;
  maxGain: number | null;
};

type SpectralSummary = {
  trackCount: number;
  hpfAppliedCount: number;
  medianHpf: number | null;
  totalNotches: number;
};

type DynamicsSummary = {
  trackCount: number;
  compEnabledCount: number;
  limiterEnabledCount: number;
};

type KeySummary = {
  detectedKey: string | null;
  scale: string | null;
  confidence: number | null;
};

type VocalSummary = {
  trackCount: number;
  shiftMean: number | null;
  shiftMin: number | null;
  shiftMax: number | null;
};

type MasteringSummary = {
  trackCount: number;
  avgPeak: number | null;
  avgRms: number | null;
  targetLufs: number | null;
};

// ---- DC OFFSET ----

function summarizeDcOffset(rows: StageRow[]): DcOffsetSummary {
  let trackCount = 0;
  let numCorrected = 0;
  let sumBefore = 0;
  let sumAfter = 0;
  let countBefore = 0;
  let countAfter = 0;
  let maxOffset: number | null = null;

  for (const row of rows) {
    trackCount += 1;
    const corrected = row["corrected"] === "True" || row["corrected"] === "1";
    if (corrected) numCorrected += 1;

    const before = toNumber(row["offset_before"]);
    const after = toNumber(row["offset_after"]);
    if (before != null) {
      sumBefore += before;
      countBefore += 1;
      maxOffset = maxOffset == null ? before : Math.max(maxOffset, before);
    }
    if (after != null) {
      sumAfter += after;
      countAfter += 1;
    }
  }

  const avgBefore = countBefore > 0 ? sumBefore / countBefore : null;
  const avgAfter = countAfter > 0 ? sumAfter / countAfter : null;

  return { trackCount, numCorrected, avgBefore, avgAfter, maxOffset };
}

function explainDcOffsetRow(row: StageRow): string | null {
  const filename =
    row["filename"] || row["relative_path"] || "Pista sin nombre";

  const corrected = row["corrected"] === "True" || row["corrected"] === "1";
  const before = toNumber(row["offset_before"]);
  const after = toNumber(row["offset_after"]);

  if (corrected && before != null && after != null) {
    return `${filename}: se ha recortado el DC offset de ${(before * 100).toFixed(
      2,
    )}% a ${(after * 100).toFixed(2)}%.`;
  }

  if (!corrected && before != null) {
    return `${filename}: offset detectado de ${(before * 100).toFixed(
      2,
    )}%, pero dentro de los márgenes aceptables.`;
  }

  return null;
}

// ---- LOUDNESS ----

type LoudnessRow = StageRow;

function summarizeLoudness(rows: LoudnessRow[]): LoudnessSummary {
  let trackCount = 0;
  let targetRms: number | null = null;
  let minGain: number | null = null;
  let maxGain: number | null = null;

  for (const row of rows) {
    trackCount += 1;
    const target = toNumber(row["target_rms_dbfs"]);
    const gain = toNumber(row["required_gain_db"]);
    if (target != null) {
      // asumimos que todo el análisis usa el mismo target; cogemos el primero
      if (targetRms == null) targetRms = target;
    }
    if (gain != null) {
      if (minGain == null || gain < minGain) minGain = gain;
      if (maxGain == null || gain > maxGain) maxGain = gain;
    }
  }

  return {
    trackCount,
    targetRms,
    minGain,
    maxGain,
  };
}

function explainLoudnessRow(row: StageRow): string | null {
  const filename =
    row["filename"] || row["relative_path"] || "Pista sin nombre";

  const originalRms = toNumber(row["rms_dbfs"]);
  const target = toNumber(row["target_rms_dbfs"]);
  const gain = toNumber(row["required_gain_db"]);

  if (originalRms == null || target == null || gain == null) return null;

  const gainSign = gain >= 0 ? "subir" : "bajar";
  const gainAbs = Math.abs(gain);

  return `${filename}: RMS actual ${formatDb(
    originalRms,
  )}, objetivo ${formatDb(target)} ⇒ se propone ${gainSign} ${gainAbs.toFixed(
    1,
  )} dB.`;
}

// ---- SPECTRAL CLEANUP ----

type SpectralRow = StageRow;

function summarizeSpectral(rows: SpectralRow[]): SpectralSummary {
  let trackCount = 0;
  let hpfAppliedCount = 0;
  let hpfValues: number[] = [];
  let totalNotches = 0;

  for (const row of rows) {
    trackCount += 1;

    const hpfEnabled =
      row["hpf_enabled"] === "True" || row["hpf_enabled"] === "1";
    if (hpfEnabled) {
      hpfAppliedCount += 1;
      const freq = toNumber(row["hpf_freq_hz"]);
      if (freq != null) hpfValues.push(freq);
    }

    const notchesCount = toNumber(row["notches_count"]);
    if (notchesCount != null) totalNotches += notchesCount;
  }

  let medianHpf: number | null = null;
  if (hpfValues.length > 0) {
    const sorted = [...hpfValues].sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    medianHpf =
      sorted.length % 2 === 0
        ? (sorted[mid - 1] + sorted[mid]) / 2
        : sorted[mid];
  }

  return {
    trackCount,
    hpfAppliedCount,
    medianHpf,
    totalNotches,
  };
}

function explainSpectralRow(row: SpectralRow): string | null {
  const filename =
    row["filename"] || row["relative_path"] || "Pista sin nombre";

  const hpfEnabled =
    row["hpf_enabled"] === "True" || row["hpf_enabled"] === "1";
  const hpfFreq = toNumber(row["hpf_freq_hz"]);
  const notchesCount = toNumber(row["notches_count"]);

  const parts: string[] = [];

  if (hpfEnabled && hpfFreq != null) {
    parts.push(`HPF en ${hpfFreq.toFixed(0)} Hz para limpiar graves innecesarios`);
  }

  if (notchesCount != null && notchesCount > 0) {
    parts.push(
      `${notchesCount} notch${notchesCount > 1 ? "es" : ""} para controlar resonancias`,
    );
  }

  if (!parts.length) return null;

  return `${filename}: ${parts.join(" y ")}.`;
}

// ---- DYNAMICS ----

type DynamicsRow = StageRow;

function summarizeDynamics(rows: DynamicsRow[]): DynamicsSummary {
  let trackCount = 0;
  let compEnabledCount = 0;
  let limiterEnabledCount = 0;

  for (const row of rows) {
    trackCount += 1;
    const comp =
      row["comp_enabled"] === "True" || row["comp_enabled"] === "1";
    const lim =
      row["limiter_enabled"] === "True" ||
      row["limiter_enabled"] === "1";

    if (comp) compEnabledCount += 1;
    if (lim) limiterEnabledCount += 1;
  }

  return {
    trackCount,
    compEnabledCount,
    limiterEnabledCount,
  };
}

function explainDynamicsRow(row: DynamicsRow): string | null {
  const filename =
    row["filename"] || row["relative_path"] || "Pista sin nombre";

  const comp =
    row["comp_enabled"] === "True" || row["comp_enabled"] === "1";
  const lim =
    row["limiter_enabled"] === "True" ||
    row["limiter_enabled"] === "1";

  const parts: string[] = [];

  if (comp) parts.push("compresión dinámica");
  if (lim) parts.push("limitador de picos");

  if (!parts.length) {
    return `${filename}: sin procesado dinámico (la pista ya estaba controlada).`;
  }

  return `${filename}: se ha aplicado ${parts.join(" y ")} para controlar la dinámica.`;
}

// ---- KEY DETECTION ----

type KeyRow = StageRow;

function summarizeKey(rows: KeyRow[]): KeySummary {
  if (!rows.length) {
    return { detectedKey: null, scale: null, confidence: null };
  }

  const row = rows[0];
  const key = row["key"] || null;
  const scale = row["scale"] || null;
  const conf = toNumber(row["confidence"]);

  return {
    detectedKey: key,
    scale,
    confidence: conf,
  };
}

// ---- VOCAL TUNING ----

type VocalRow = StageRow;

function summarizeVocal(rows: VocalRow[]): VocalSummary {
  let trackCount = rows.length;
  let sumShift = 0;
  let countShift = 0;
  let minShift: number | null = null;
  let maxShift: number | null = null;

  for (const row of rows) {
    const shift = toNumber(row["avg_shift_semitones"]);
    if (shift != null) {
      sumShift += shift;
      countShift += 1;
      if (minShift == null || shift < minShift) minShift = shift;
      if (maxShift == null || shift > maxShift) maxShift = shift;
    }
  }

  const shiftMean = countShift > 0 ? sumShift / countShift : null;

  return {
    trackCount,
    shiftMean,
    shiftMin: minShift,
    shiftMax: maxShift,
  };
}

// ---- MASTERING ----

type MasteringRow = StageRow;

function summarizeMastering(rows: MasteringRow[]): MasteringSummary {
  let trackCount = 0;
  let peakSum = 0;
  let peakCount = 0;
  let rmsSum = 0;
  let rmsCount = 0;
  let targetLufs: number | null = null;

  for (const row of rows) {
    trackCount += 1;
    const peak = toNumber(row["peak_dbfs"]);
    const rms = toNumber(row["rms_dbfs"]);
    const target = toNumber(row["target_lufs"]);

    if (peak != null) {
      peakSum += peak;
      peakCount += 1;
    }
    if (rms != null) {
      rmsSum += rms;
      rmsCount += 1;
    }
    if (target != null && targetLufs == null) {
      targetLufs = target;
    }
  }

  const avgPeak = peakCount > 0 ? peakSum / peakCount : null;
  const avgRms = rmsCount > 0 ? rmsSum / rmsCount : null;

  return {
    trackCount,
    avgPeak,
    avgRms,
    targetLufs,
  };
}

// ------------------------------------------------------------------
// Componente principal
// ------------------------------------------------------------------

export function MixResultPanel({
  result,
  enabledPipelineStageKeys,
}: Props) {
  const [selectedStageKey, setSelectedStageKey] = useState<StageKey | "">("");
  const [csvRows, setCsvRows] = useState<StageRow[] | null>(null);
  const [csvLoading, setCsvLoading] = useState(false);
  const [csvError, setCsvError] = useState<string | null>(null);
  const [isReportModalOpen, setIsReportModalOpen] = useState(false);

  const { originalFullSongUrl, fullSongUrl, jobId, metrics } = result;

  const selectedStage: StageOption | undefined = useMemo(
    () => STAGE_OPTIONS.find((s) => s.key === selectedStageKey),
    [selectedStageKey],
  );

  // Carga del CSV cuando cambia la etapa seleccionada
  useEffect(() => {
    if (!selectedStage) {
      setCsvRows(null);
      setCsvError(null);
      return;
    }

    const controller = new AbortController();
    const base = getBackendBaseUrl();
    const csvPath = selectedStage.getCsvPath();
    const url = `${base}/files/${encodeURIComponent(jobId)}${csvPath}`;

    async function loadCsv() {
      try {
        setCsvLoading(true);
        setCsvError(null);
        setCsvRows(null);

        const res = await fetch(url, { signal: controller.signal });
        if (!res.ok) {
          throw new Error(
            `No se pudo cargar el CSV (${res.status} ${res.statusText})`,
          );
        }

        const text = await res.text();
        const lines = text.split(/\r?\n/).filter((l) => l.trim().length > 0);
        if (lines.length < 2) {
          setCsvRows([]);
          return;
        }

        const header = lines[0].split(",");
        const rows: StageRow[] = lines.slice(1).map((line) => {
          const cols = line.split(",");
          const row: StageRow = {};
          header.forEach((h, i) => {
            row[h] = cols[i] ?? "";
          });
          return row;
        });

        setCsvRows(rows);
      } catch (err: any) {
        if (err?.name === "AbortError") return;
        console.error("Error cargando CSV de etapa", err);
        setCsvError(err?.message ?? "Error cargando datos de análisis.");
      } finally {
        setCsvLoading(false);
      }
    }

    void loadCsv();
    return () => controller.abort();
  }, [selectedStage, jobId]);

  // Resúmenes derivados del CSV en función de la etapa
  const dcSummary = useMemo(
    () =>
      selectedStage?.key === "dc_offset" && csvRows
        ? summarizeDcOffset(csvRows)
        : null,
    [selectedStage, csvRows],
  );

  const loudnessSummary = useMemo(
    () =>
      selectedStage?.key === "loudness" && csvRows
        ? summarizeLoudness(csvRows)
        : null,
    [selectedStage, csvRows],
  );

  const spectralSummary = useMemo(
    () =>
      selectedStage?.key === "spectral_cleanup" && csvRows
        ? summarizeSpectral(csvRows)
        : null,
    [selectedStage, csvRows],
  );

  const dynamicsSummary = useMemo(
    () =>
      selectedStage?.key === "dynamics" && csvRows
        ? summarizeDynamics(csvRows)
        : null,
    [selectedStage, csvRows],
  );

  const keySummary = useMemo(
    () =>
      selectedStage?.key === "key_detection" && csvRows
        ? summarizeKey(csvRows)
        : null,
    [selectedStage, csvRows],
  );

  const vocalSummary = useMemo(
    () =>
      selectedStage?.key === "vocal_tuning" && csvRows
        ? summarizeVocal(csvRows)
        : null,
    [selectedStage, csvRows],
  );

  const masteringSummary = useMemo(
    () =>
      selectedStage?.key === "mastering" && csvRows
        ? summarizeMastering(csvRows)
        : null,
    [selectedStage, csvRows],
  );

  // Cabeceras del CSV para mostrar tabla raw al final
  const csvHeaders: string[] = useMemo(() => {
    if (!csvRows || !csvRows.length) return [];
    return Object.keys(csvRows[0]);
  }, [csvRows]);

  return (
    <section className="mt-6 rounded-3xl border border-slate-800/70 bg-slate-900/80 p-6 text-slate-50 shadow-xl shadow-black/40">
      {/* Cabecera con players: original vs master */}
      <div className="grid gap-4 md:grid-cols-2">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-300">
            Your AI Mix
          </h2>
          <p className="mt-1 text-xs text-slate-400">
            Original mix (antes del procesamiento)
          </p>
          <audio
            controls
            src={originalFullSongUrl}
            className="mt-2 w-full rounded-lg bg-slate-800"
          />
        </div>
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-300">
            AI mix &amp; mastering (resultado)
          </h2>
          <p className="mt-1 text-xs text-slate-400">
            Escucha el resultado final tras la mezcla
          </p>
          <audio
            controls
            src={fullSongUrl}
            className="mt-2 w-full rounded-lg bg-slate-800"
          />
        </div>
      </div>

            {/* Panel Pipeline: solo stages elegidos */}
      <MixPipelinePanel
        result={result}
        enabledPipelineStageKeys={enabledPipelineStageKeys}
      />

      <div className="mt-3 flex justify-end">
        <button
          type="button"
          onClick={() => setIsReportModalOpen(true)}
          className="inline-flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-950/60 px-3 py-1.5 text-[11px] font-medium text-slate-100 hover:border-indigo-400 hover:bg-slate-900/80"
        >
          Ver informe global del pipeline
          <span className="rounded-full bg-slate-800/80 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-indigo-200">
            S11
          </span>
        </button>
      </div>

      <FinalReportModal
        jobId={jobId}
        isOpen={isReportModalOpen}
        onClose={() => setIsReportModalOpen(false)}
      />


{/* Métricas principales (colapsadas) */}
<details className="mt-6 rounded-xl bg-slate-950/40 p-4 group">
  <summary className="flex cursor-pointer list-none items-center justify-between gap-2 [&::-webkit-details-marker]:hidden">
    <div className="flex-1">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
        Metrics
      </h3>
      <p className="mt-1 text-xs text-slate-400">
        Resumen del loudness final, la afinación vocal y el tempo/tonalidad
        del master.
      </p>
    </div>
    <span
      aria-hidden="true"
      className="ml-2 text-xs text-slate-400 transition-transform duration-200 group-open:rotate-180"
    >
      ▼
    </span>
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
              Rango: {metrics.vocal_shift_min.toFixed(2)} –{" "}
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
      </details>

{/* Selector de etapa / detalles de logs (colapsado) */}
<details className="mt-8 border-t border-slate-800/70 pt-6 group">
  <summary className="flex cursor-pointer list-none items-center justify-between gap-2 [&::-webkit-details-marker]:hidden">
    <div className="flex-1">
      <h3 className="mb-1 text-sm font-semibold uppercase tracking-wide text-slate-400">
        Detalles del procesamiento
      </h3>
      <p className="text-xs text-slate-400">
        Selecciona una etapa del pipeline para ver un resumen de los cambios
        aplicados, extraído directamente de los ficheros de análisis.
      </p>
    </div>
    <span
      aria-hidden="true"
      className="ml-2 text-xs text-slate-400 transition-transform duration-200 group-open:rotate-180"
    >
      ▼
    </span>
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
                <p className="mt-3 text-xs text-slate-400">
                  {csvError} (comprueba que el fichero existe y respeta el
                  formato esperado).
                </p>
              )}

              {/* Cuando hay filas y no hay error, mostramos resúmenes y tabla */}
              {!csvLoading && !csvError && csvRows && csvRows.length > 0 && (
                <div className="mt-4 space-y-4 text-xs">
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
                          pistas se ha aplicado corrección para recentrar la
                          forma de onda alrededor de 0.
                        </p>
                      )}
                      {dcSummary.avgBefore !== null &&
                        dcSummary.avgAfter !== null && (
                          <p className="mt-1 text-slate-300">
                            De media, el offset ha pasado de{" "}
                            <span className="font-semibold">
                              {(dcSummary.avgBefore * 100).toFixed(2)} %
                            </span>{" "}
                            a{" "}
                            <span className="font-semibold">
                              {(dcSummary.avgAfter * 100).toFixed(2)} %
                            </span>
                            .
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
                        pistas para igualar su nivel de trabajo.
                      </p>
                      {loudnessSummary.targetRms !== null && (
                        <p className="mt-1 text-slate-300">
                          El objetivo de loudness por pista está en torno a{" "}
                          <span className="font-semibold">
                            {loudnessSummary.targetRms.toFixed(1)} dBFS RMS
                          </span>
                          .
                        </p>
                      )}
                      {(loudnessSummary.minGain !== null ||
                        loudnessSummary.maxGain !== null) && (
                        <p className="mt-1 text-slate-300">
                          Las correcciones de ganancia van aproximadamente desde{" "}
                          {loudnessSummary.minGain !== null && (
                            <>
                              <span className="font-semibold">
                                {loudnessSummary.minGain.toFixed(1)} dB
                              </span>
                            </>
                          )}
                          {loudnessSummary.minGain !== null &&
                            loudnessSummary.maxGain !== null && (
                              <span>{" hasta "}</span>
                            )}
                          {loudnessSummary.maxGain !== null && (
                            <span className="font-semibold">
                              {loudnessSummary.maxGain.toFixed(1)} dB
                            </span>
                          )}
                          .
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

                  {/* SPECTRAL CLEANUP */}
                  {selectedStage.key === "spectral_cleanup" &&
                    spectralSummary && (
                      <div className="mt-3 text-xs text-slate-200">
                        <p>
                          Se han analizado{" "}
                          <span className="font-semibold">
                            {spectralSummary.trackCount}
                          </span>{" "}
                          pistas a nivel espectral.
                        </p>
                        {spectralSummary.hpfAppliedCount > 0 && (
                          <p className="mt-1 text-slate-300">
                            Se ha recomendado HPF en{" "}
                            <span className="font-semibold">
                              {spectralSummary.hpfAppliedCount}
                            </span>{" "}
                            pistas
                            {spectralSummary.medianHpf !== null && (
                              <>
                                {" "}
                                con una frecuencia típica alrededor de{" "}
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

                  {/* DYNAMICS */}
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

                  {/* KEY DETECTION */}
                  {selectedStage.key === "key_detection" && keySummary && (
                    <div className="mt-3 text-xs text-slate-200">
                      {keySummary.detectedKey && keySummary.scale ? (
                        <p>
                          Se ha estimado la tonalidad como{" "}
                          <span className="font-semibold">
                            {keySummary.detectedKey} {keySummary.scale}
                          </span>
                          {keySummary.confidence !== null && (
                            <>
                              {" "}
                              con una confianza aproximada del{" "}
                              <span className="font-semibold">
                                {(keySummary.confidence * 100).toFixed(1)}%
                              </span>
                              .
                            </>
                          )}
                        </p>
                      ) : (
                        <p>
                          No se ha podido estimar una tonalidad clara a partir
                          del mix.
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
                  {selectedStage.key === "vocal_tuning" &&
                    vocalSummary && (
                      <div className="mt-3 text-xs text-slate-200">
                        <p>
                          Se han contabilizado{" "}
                          <span className="font-semibold">
                            {vocalSummary.trackCount}
                          </span>{" "}
                          segmentos vocales afinados.
                        </p>
                        {vocalSummary.shiftMean !== null && (
                          <p className="mt-1 text-slate-300">
                            De media, el autotune corrige{" "}
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
                          Valores cercanos a 0 significan que la toma ya estaba
                          muy afinada; valores altos indican intervenciones más
                          agresivas.
                        </p>
                      </div>
                    )}

                  {/* MASTERING */}
                  {selectedStage.key === "mastering" && masteringSummary && (
                    <div className="mt-3 text-xs text-slate-200">
                      <p>
                        Se han analizado{" "}
                        <span className="font-semibold">
                          {masteringSummary.trackCount}
                        </span>{" "}
                        stems en la etapa de mastering.
                      </p>
                      {(masteringSummary.avgPeak !== null ||
                        masteringSummary.avgRms !== null) && (
                        <p className="mt-1 text-slate-300">
                          Los niveles medios por pista rondan{" "}
                          {masteringSummary.avgPeak !== null && (
                            <>
                              pico{" "}
                              <span className="font-semibold">
                                {masteringSummary.avgPeak.toFixed(1)} dBFS
                              </span>
                            </>
                          )}
                          {masteringSummary.avgPeak !== null &&
                            masteringSummary.avgRms !== null && (
                              <span>{", "}</span>
                            )}
                          {masteringSummary.avgRms !== null && (
                            <>
                              RMS{" "}
                              <span className="font-semibold">
                                {masteringSummary.avgRms.toFixed(1)} dBFS
                              </span>
                            </>
                          )}
                          .
                        </p>
                      )}
                      {masteringSummary.targetLufs !== null && (
                        <p className="mt-1 text-slate-300">
                          El objetivo global de loudness se sitúa alrededor de{" "}
                          <span className="font-semibold">
                            {masteringSummary.targetLufs.toFixed(1)} LUFS
                          </span>
                          .
                        </p>
                      )}
                    </div>
                  )}

                  {/* Tabla raw con los datos del CSV */}
                  <div className="mt-4 overflow-x-auto rounded-lg border border-slate-800 bg-slate-950/40">
                    <table className="min-w-full border-collapse text-[11px]">
                      <thead className="bg-slate-900/80">
                        <tr>
                          {csvHeaders.map((h) => (
                            <th
                              key={h}
                              className="px-2 py-1 text-left font-semibold uppercase tracking-wide text-slate-400"
                            >
                              {h}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {csvRows.map((row, idx) => (
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
                </div>
              )}

              {!csvLoading &&
                !csvError &&
                (!csvRows || csvRows.length === 0) && (
                  <p className="mt-3 text-xs text-slate-400">
                    No se han encontrado filas en el CSV de esta etapa. Es
                    posible que el pipeline no haya generado todavía el fichero
                    o que la estructura haya cambiado.
                  </p>
                )}
            </div>
          )}
        </div>
      </details>
    </section>
  );
}
