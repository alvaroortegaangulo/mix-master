// frontend/src/components/MixResultPanel.tsx
"use client";

import { useEffect, useMemo, useState } from "react";
import type { MixResult } from "../lib/mixApi";
import { getBackendBaseUrl } from "../lib/mixApi";
import { MixPipelinePanel } from "./MixPipelinePanel";
import { ReportViewer } from "./ReportViewer";
import { fetchJobReport } from "../lib/mixApi";

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
  const [showOriginal, setShowOriginal] = useState(false);
  const [reportData, setReportData] = useState<any>(null);
  const [reportLoading, setReportLoading] = useState(false);

  const { originalFullSongUrl, fullSongUrl, jobId, metrics } = result;

  // Fetch Report Data
  useEffect(() => {
    if (!jobId) return;

    async function loadReport() {
        try {
            setReportLoading(true);
            const data = await fetchJobReport(jobId);
            setReportData(data);
        } catch (e) {
            console.error("Failed to load report", e);
        } finally {
            setReportLoading(false);
        }
    }
    loadReport();
  }, [jobId]);

  return (
    <section className="mt-6 space-y-8">

    <div className="rounded-3xl border border-emerald-500/40 bg-emerald-900/30 p-6 text-emerald-50 shadow-xl shadow-emerald-900/40">
      {/* Cabecera con players: original vs master */}
      <div className="space-y-2">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-emerald-100">
            {showOriginal ? "Mix original" : "AI mix & mastering (resultado)"}
          </h2>
          <p className="mt-1 text-xs text-emerald-200/90">
            {showOriginal
              ? "Original mix (antes del procesamiento)"
              : "Escucha el resultado final tras la mezcla"}
          </p>
          <audio
            controls
            src={showOriginal ? originalFullSongUrl : fullSongUrl}
            className="mt-2 w-full rounded-lg bg-emerald-950/60"
          />
        </div>
        <button
          type="button"
          onClick={() => setShowOriginal((v) => !v)}
          className="inline-flex items-center gap-2 rounded-lg border border-emerald-500/50 bg-emerald-950/60 px-3 py-1.5 text-[11px] font-medium text-emerald-50 hover:border-emerald-300 hover:bg-emerald-900/80"
        >
          {showOriginal ? "AI mix & mastering" : "Mix Original"}
        </button>
      </div>
      </div>

      {/* Report Viewer */}
      {reportLoading && <p className="text-center text-slate-400">Loading report...</p>}
      {!reportLoading && reportData && (
          <ReportViewer report={reportData} jobId={jobId} />
      )}


{/* Métricas principales (colapsadas) */}
<details className="mt-6 rounded-xl border border-emerald-500/30 bg-emerald-950/30 p-4 group">
  <summary className="flex cursor-pointer list-none items-center justify-between gap-2 [&::-webkit-details-marker]:hidden">
    <div className="flex-1">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-emerald-200/90">
        Metrics
      </h3>
      <p className="mt-1 text-xs text-emerald-200/90">
        Resumen del loudness final, la afinación vocal y el tempo/tonalidad
        del master.
      </p>
    </div>
    <span
      aria-hidden="true"
      className="ml-2 text-xs text-emerald-200/90 transition-transform duration-200 group-open:rotate-180"
    >
      ▼
    </span>
  </summary>

        <div className="mt-4 grid gap-4 md:grid-cols-3">
          <div>
            <p className="text-xs uppercase text-emerald-200/90">Loudness</p>
            <p className="text-sm text-emerald-50">
              Peak:{" "}
              <span className="font-semibold">
                {metrics.final_peak_dbfs.toFixed(1)} dBFS
              </span>
            </p>
            <p className="text-sm text-emerald-50">
              RMS:{" "}
              <span className="font-semibold">
                {metrics.final_rms_dbfs.toFixed(1)} dBFS
              </span>
            </p>
          </div>
          <div>
            <p className="text-xs uppercase text-emerald-200/90">Vocal tuning</p>
            <p className="text-sm text-emerald-50">
              Shift medio:{" "}
              <span className="font-semibold">
                {metrics.vocal_shift_mean.toFixed(2)} semitonos
              </span>
            </p>
            <p className="text-xs text-emerald-200/90">
              Rango: {metrics.vocal_shift_min.toFixed(2)} –{" "}
              {metrics.vocal_shift_max.toFixed(2)} st
            </p>
          </div>
          <div>
            <p className="text-xs uppercase text-emerald-200/90">Tempo &amp; key</p>
            <p className="text-sm text-emerald-50">
              Tempo:{" "}
              <span className="font-semibold">
                {metrics.tempo_bpm.toFixed(1)} BPM
              </span>
            </p>
            <p className="text-sm text-emerald-50">
              Key:{" "}
              <span className="font-semibold">
                {metrics.key} {metrics.scale}
              </span>
            </p>
          </div>
        </div>
      </details>

  {/* Secci?n de detalles del procesamiento eliminada; la informaci?n se muestra en el informe final */}

    </section>
  );
}
