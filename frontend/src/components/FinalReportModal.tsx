// frontend/src/components/FinalReportModal.tsx
"use client";

import { useEffect, useMemo, useState } from "react";
import { getBackendBaseUrl } from "../lib/mixApi";

type FinalMetrics = {
  true_peak_dbtp: number | null;
  lufs_integrated: number | null;
  lra: number | null;
  correlation: number | null;
  channel_loudness_diff_db: number | null;
  crest_factor_db: number | null;
  level_histogram_db?: {
    bin_edges_db: number[];
    counts: number[];
  } | null;
};

type StageReportEntry = {
  contract_id: string;
  stage_id?: string | null;
  name: string;
  status: string;
  key_metrics?: any;
};

type StageDuration = {
  contract_id: string;
  duration_sec: number;
};

type PipelineDurations = {
  stages: StageDuration[];
  total_duration_sec: number | null;
  generated_at_utc?: string | null;
};

type ReportCore = {
  pipeline_version: string;
  generated_at_utc: string;
  style_preset: string;
  stages: StageReportEntry[];
  final_metrics: FinalMetrics;
  pipeline_durations?: PipelineDurations | null;
};

type ReportEnvelope = {
  contract_id: string;
  stage_id?: string | null;
  style_preset?: string;
  metrics_from_contract?: Record<string, any>;
  limits_from_contract?: Record<string, any>;
  session?: {
    report?: ReportCore;
  };
};

type FinalReportModalProps = {
  jobId: string;
  isOpen: boolean;
  onClose: () => void;
};

function toNumberOrNull(value: any): number | null {
  if (value === null || value === undefined) return null;
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }
  const n = Number(value);
  if (!Number.isFinite(n)) return null;
  return n;
}

function formatDb(value: number | null, suffix: string = "dB"): string {
  if (value === null || Number.isNaN(value)) return "—";
  return `${value.toFixed(1)} ${suffix}`;
}

function formatLufs(value: number | null): string {
  if (value === null || Number.isNaN(value)) return "—";
  return `${value.toFixed(1)} LUFS`;
}

function prettifyStylePreset(style: string | undefined | null): string {
  if (!style) return "Estilo no definido";
  return style
    .replace(/_/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (m) => m.toUpperCase());
}

function formatUtcToLocal(iso: string | undefined | null): string {
  if (!iso) return "Fecha desconocida";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatDurationShort(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || Number.isNaN(seconds)) {
    return "N/A";
  }
  const total = Math.max(0, Math.round(seconds));
  const mins = Math.floor(total / 60);
  const secs = total % 60;
  if (mins === 0) return `${secs}s`;
  return `${mins}m ${secs.toString().padStart(2, "0")}s`;
}

// --- Comentarios "humanizados" para las métricas finales ---

function getLoudnessComment(lufs: number | null): string {
  if (lufs === null) {
    return "No se ha podido estimar el loudness integrado del tema.";
  }
  if (lufs <= -16) {
    return "Loudness bastante conservador y dinámico; hay mucho margen si quisieras un master más agresivo.";
  }
  if (lufs <= -12) {
    return "Loudness moderado, en línea con masters dinámicos pensados para streaming sin guerra de volumen.";
  }
  if (lufs <= -9) {
    return "Loudness alto pero todavía razonable para pop moderno; el tema debería sentirse lleno sin destruir la dinámica.";
  }
  if (lufs <= -7) {
    return "Loudness muy alto típico de masters muy comprimidos; puede sonar potente pero con menos respiración.";
  }
  return "Loudness extremadamente alto; es posible que la mezcla suene agresiva y con poca dinámica.";
}

function getTruePeakComment(tp: number | null): string {
  if (tp === null) {
    return "No se ha podido medir el true peak final del master.";
  }
  if (tp <= -2) {
    return "True peak muy seguro; hay margen más que suficiente para conversiones y reproducción en distintas plataformas.";
  }
  if (tp <= -1) {
    return "True peak en una zona segura (-2 a -1 dBTP), adecuado para distribución digital conservadora.";
  }
  if (tp <= -0.1) {
    return "True peak muy cercano a 0 dBTP; típico de masters modernos con ceiling ajustado.";
  }
  if (tp <= 0.3) {
    return "El true peak llega por encima de 0 dBTP; podría haber algo de clipping inter-sample según el conversor.";
  }
  return "True peak claramente por encima de 0 dBTP; conviene revisar el limitador final o bajar el ceiling.";
}

function getCrestComment(crest: number | null): string {
  if (crest === null) {
    return "No se ha podido estimar el factor de cresta del master.";
  }
  if (crest <= 6) {
    return "Factor de cresta muy bajo: el material está fuertemente limitado/compactado (sonido muy 'brickwall').";
  }
  if (crest <= 9) {
    return "Factor de cresta moderado; master moderno con cierta pegada pero bastante controlado dinámicamente.";
  }
  if (crest <= 12) {
    return "Factor de cresta saludable; buena relación entre transitorios y nivel medio, con sensación de dinámica.";
  }
  return "Factor de cresta alto; el tema es bastante dinámico, algo más cercano a una mezcla que a un master muy apretado.";
}

function getCorrelationComment(corr: number | null): string {
  if (corr === null) {
    return "No se ha podido medir la correlación estéreo.";
  }
  if (corr < 0) {
    return "Correlación negativa: hay problemas serios de fase; parte del contenido puede cancelarse al escuchar en mono.";
  }
  if (corr < 0.2) {
    return "Correlación muy baja; imagen estéreo extrema con riesgo de cancelaciones al pasar a mono.";
  }
  if (corr < 0.4) {
    return "Correlación algo baja; mezcla muy abierta, conviene revisar elementos fuertemente paneados o efectos M/S.";
  }
  if (corr < 0.8) {
    return "Correlación equilibrada; buena sensación estéreo sin riesgos graves de fase.";
  }
  return "Correlación muy alta (cercana a 1); mezcla bastante centrada/mono, con poca información puramente estéreo.";
}

function getChannelDiffComment(diff: number | null): string {
  if (diff === null) {
    return "No se ha podido medir el equilibrio entre canales izquierdo y derecho.";
  }
  const absDiff = Math.abs(diff);
  if (absDiff < 0.7) {
    return "Balance L/R muy centrado; no hay un lado claramente más fuerte que el otro.";
  }
  if (absDiff < 2) {
    return "Ligera preferencia hacia un canal; sensación estéreo natural con un pequeño peso hacia un lado.";
  }
  if (absDiff < 4) {
    return "Diferencia notable entre canales; puede percibirse el tema claramente cargado hacia un lado.";
  }
  return "Diferencia muy acusada entre canales; conviene revisar el paneo o el procesamiento M/S para equilibrar mejor.";
}

function getHistogramTypicalLevel(hist: FinalMetrics["level_histogram_db"]): number | null {
  if (!hist) return null;
  const edges = hist.bin_edges_db;
  const counts = hist.counts;
  if (!Array.isArray(edges) || !Array.isArray(counts)) return null;
  if (counts.length === 0 || edges.length < 2) return null;

  let maxIdx = 0;
  for (let i = 1; i < counts.length; i++) {
    if ((counts[i] ?? 0) > (counts[maxIdx] ?? 0)) {
      maxIdx = i;
    }
  }
  const start = typeof edges[maxIdx] === "number" ? edges[maxIdx] : NaN;
  const end = typeof edges[maxIdx + 1] === "number" ? edges[maxIdx + 1] : start;
  if (!Number.isFinite(start) || !Number.isFinite(end)) return null;
  return (start + end) / 2;
}

export function FinalReportModal({ jobId, isOpen, onClose }: FinalReportModalProps) {
  const [reportEnvelope, setReportEnvelope] = useState<ReportEnvelope | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stageAnalyses, setStageAnalyses] = useState<Record<string, any>>({});
  const [stageAnalysesLoading, setStageAnalysesLoading] = useState(false);

  useEffect(() => {
    if (!isOpen || !jobId) return;
    const controller = new AbortController();

    const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

    async function loadReport() {
      setLoading(true);
      setError(null);
      try {
        const baseUrl = getBackendBaseUrl();
        const url = `${baseUrl}/files/${encodeURIComponent(
          jobId,
        )}/S11_REPORT_GENERATION/analysis_S11_REPORT_GENERATION.json`;

        let lastErr: any = null;
        for (let attempt = 0; attempt < 4; attempt++) {
          try {
            const res = await fetch(url, { signal: controller.signal });
            if (!res.ok) {
              if (res.status === 404 && attempt < 3) {
                await sleep(800 * (attempt + 1));
                continue;
              }
              throw new Error(`No se pudo cargar el informe (HTTP ${res.status}).`);
            }

            // Sustituimos los -Infinity/Infinity/NaN por null para que el JSON sea válido.
            const raw = await res.text();
            const safe = raw
              .replace(/-Infinity/g, "null")
              .replace(/Infinity/g, "null")
              .replace(/NaN/g, "null");

            const data = JSON.parse(safe) as ReportEnvelope;
            setReportEnvelope(data);
            lastErr = null;
            break;
          } catch (err: any) {
            if (err?.name === "AbortError") return;
            lastErr = err;
            if (attempt < 3) {
              await sleep(800 * (attempt + 1));
            }
          }
        }

        if (lastErr) {
          throw lastErr;
        }
      } catch (err: any) {
        if (err?.name === "AbortError") return;
        console.error("[FinalReportModal] Error al cargar informe:", err);
        setError(
          err?.message ??
            "No se ha podido cargar el informe de mezcla. Prueba a relanzar el job.",
        );
      } finally {
        setLoading(false);
      }
    }

    loadReport();

    return () => {
      controller.abort();
    };
  }, [isOpen, jobId]);

  const coreReport = reportEnvelope?.session?.report;

  useEffect(() => {
    if (!isOpen || !coreReport?.stages?.length || !jobId) return;
    const controller = new AbortController();
    const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

    async function loadStageAnalyses() {
      setStageAnalysesLoading(true);
      try {
        const baseUrl = getBackendBaseUrl();
        const analyzed = (coreReport?.stages ?? []).filter(
          (s) => s.status === "analyzed",
        );

        const results = await Promise.all(
          analyzed.map(async (stage) => {
            const cid = stage.contract_id;
            const url = `${baseUrl}/files/${encodeURIComponent(
              jobId,
            )}/${cid}/analysis_${cid}.json`;
            try {
              const res = await fetch(url, { signal: controller.signal });
              if (!res.ok) {
                return [cid, null] as const;
              }
              const raw = await res.text();
              const safe = raw
                .replace(/-Infinity/g, "null")
                .replace(/Infinity/g, "null")
                .replace(/NaN/g, "null");
              return [cid, JSON.parse(safe)] as const;
            } catch (err: any) {
              if (err?.name === "AbortError") return [cid, null] as const;
              // reintento ligero por si está generándose aún
              await sleep(300);
              return [cid, null] as const;
            }
          }),
        );

        const map: Record<string, any> = {};
        for (const [cid, data] of results) {
          if (data) map[cid] = data;
        }
        setStageAnalyses(map);
      } finally {
        setStageAnalysesLoading(false);
      }
    }

    loadStageAnalyses();
    return () => controller.abort();
  }, [isOpen, jobId, coreReport]);

  const finalMetrics = useMemo(() => {
    const fm = coreReport?.final_metrics;
    if (!fm) return null;

    const tp = toNumberOrNull(fm.true_peak_dbtp);
    const lufs = toNumberOrNull(fm.lufs_integrated);
    const lra = toNumberOrNull(fm.lra);
    const corr = toNumberOrNull(fm.correlation);
    const diff = toNumberOrNull(fm.channel_loudness_diff_db);
    const crest = toNumberOrNull(fm.crest_factor_db);
    const hist = fm.level_histogram_db ?? null;

    return {
      truePeak: tp,
      lufs,
      lra,
      correlation: corr,
      channelDiff: diff,
      crest,
      histogram: hist,
      typicalLevel: getHistogramTypicalLevel(hist),
    };
  }, [coreReport]);

  const stages = coreReport?.stages ?? [];
  const pipelineDurations = coreReport?.pipeline_durations ?? null;
  const sortedDurations = useMemo(() => {
    if (!pipelineDurations?.stages) return [];
    const order = stages.map((s) => s.contract_id);
    return [...pipelineDurations.stages].sort((a, b) => {
      const ia = order.indexOf(a.contract_id);
      const ib = order.indexOf(b.contract_id);
      if (ia === -1 && ib === -1) return 0;
      if (ia === -1) return 1;
      if (ib === -1) return -1;
      return ia - ib;
    });
  }, [pipelineDurations, stages]);

  function humanizeKey(key: string): string {
    return key
      .replace(/_/g, " ")
      .replace(/\s+/g, " ")
      .trim()
      .replace(/^\w/, (m) => m.toUpperCase());
  }

  function formatValue(value: any): string {
    if (value === null || value === undefined) return "N/A";
    if (typeof value === "number") {
      return Number.isInteger(value) ? `${value}` : value.toFixed(2);
    }
    if (typeof value === "boolean") return value ? "Sí" : "No";
    if (typeof value === "string") return value;
    if (Array.isArray(value)) return value.slice(0, 3).join(", ");
    return "—";
  }

  function buildStageSummary(contractId: string): string[] {
    const analysis = stageAnalyses[contractId];
    if (!analysis) return [];
    const session = analysis.session;
    if (!session || typeof session !== "object") return [];

    const entries = Object.entries(session).filter(
      ([, v]) =>
        typeof v === "string" ||
        typeof v === "number" ||
        typeof v === "boolean",
    );

    return entries.slice(0, 6).map(
      ([k, v]) => `${humanizeKey(k)}: ${formatValue(v)}`,
    );
  }

  // Si el modal no está abierto, no renderizamos nada
  if (!isOpen) return null;

  const stylePreset = coreReport?.style_preset ?? reportEnvelope?.style_preset;
  const generatedAt = coreReport?.generated_at_utc;
  const analyzedStages = stages.filter((s) => s.status === "analyzed");

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/70 p-4">
      <div className="relative max-h-[90vh] w-full max-w-4xl overflow-hidden rounded-2xl border border-slate-800 bg-slate-950/95 shadow-2xl">
        {/* Header */}
        <div className="flex items-start justify-between border-b border-slate-800 px-5 py-4">
          <div>
            <h2 className="text-sm font-semibold leading-tight text-slate-50">
              ¡MEZCLA COMPLETADA!
              <span className="block text-[13px] font-normal text-slate-200">
                Informe de mezcla y mastering
              </span>
            </h2>
            <p className="mt-1 text-xs text-slate-400">
              Resumen técnico-humanizado del pipeline completo para este job.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-300 hover:border-red-400 hover:text-red-200"
          >
            Cerrar
          </button>
        </div>

        {/* Body scrollable */}
        <div className="max-h-[calc(90vh-3rem)] overflow-y-auto px-5 py-4">
          {/* Estado de carga / error */}
          {loading && (
            <p className="py-6 text-center text-xs text-slate-300">
              Cargando informe de mezcla…
            </p>
          )}

          {!loading && error && (
            <div className="rounded-xl border border-red-500/60 bg-red-950/30 p-4 text-xs text-red-100">
              <p className="font-semibold">No se ha podido cargar el informe.</p>
              <p className="mt-1">{error}</p>
              <p className="mt-2 text-[11px] text-red-200/80">
                Comprueba que el pipeline ha llegado hasta la etapa S11_REPORT_GENERATION
                y que el job no ha fallado en etapas anteriores.
              </p>
            </div>
          )}

          {!loading && !error && !coreReport && (
            <div className="rounded-xl border border-slate-700 bg-slate-900/40 p-4 text-xs text-slate-200">
              <p className="font-semibold">Informe no disponible.</p>
              <p className="mt-1">
                No se ha encontrado el fichero{" "}
                <span className="font-mono">
                  analysis_S11_REPORT_GENERATION.json
                </span>{" "}
                para este job. Es posible que la etapa S11 todavía no se haya ejecutado o
                que se haya producido algún error en el pipeline.
              </p>
            </div>
          )}

          {!loading && !error && coreReport && (
            <div className="space-y-5">
              {/* Resumen general */}
              <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                      Resumen rápido
                    </p>
                    <p className="mt-1 text-sm text-slate-50">
                      Estilo:{" "}
                      <span className="font-semibold">
                        {prettifyStylePreset(stylePreset)}
                      </span>
                    </p>
                    <p className="mt-1 text-xs text-slate-300">
                      Pipeline versión{" "}
                      <span className="font-mono">
                        {coreReport.pipeline_version || "v1.0.0"}
                      </span>{" "}
                      · Generado el{" "}
                      <span className="font-mono">
                        {formatUtcToLocal(generatedAt)}
                      </span>
                      .
                    </p>
                  </div>
                  <div className="rounded-lg border border-indigo-500/40 bg-indigo-500/10 px-3 py-2 text-[11px] text-slate-100">
                    <p className="font-semibold uppercase tracking-wide text-indigo-200">
                      Etapas analizadas
                    </p>
                    <p className="mt-0.5">
                      El pipeline ha recorrido{" "}
                      <span className="font-semibold">{analyzedStages.length}</span> etapas
                      principales, desde la preparación de sesión hasta el control de
                      límites del master.
                    </p>
                  </div>
                  {pipelineDurations && (
                    <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-[11px] text-amber-50">
                      <p className="font-semibold uppercase tracking-wide text-amber-200">
                        Tiempo del pipeline
                      </p>
                      <p className="mt-0.5 text-amber-50">
                        Duración total:{" "}
                        <span className="font-semibold">
                          {formatDurationShort(pipelineDurations.total_duration_sec)}
                        </span>
                      </p>
                      {sortedDurations.length > 0 && (
                        <p className="mt-1 text-amber-50/90">
                          Más lento:{" "}
                          {sortedDurations
                            .slice(0, 3)
                            .map((d) => {
                              const name =
                                stages.find((s) => s.contract_id === d.contract_id)?.name ||
                                d.contract_id;
                              return `${name}: ${formatDurationShort(d.duration_sec)}`;
                            })
                            .join(" • ")}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              </section>

              {pipelineDurations && (
                <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                    Duración por etapa
                  </h3>
                  <p className="mt-1 text-xs text-slate-300">
                    Tiempo total del pipeline:{" "}
                    <span className="font-semibold text-slate-100">
                      {formatDurationShort(pipelineDurations.total_duration_sec)}
                    </span>
                  </p>
                  {sortedDurations.length > 0 ? (
                    <ul className="mt-3 space-y-1 text-xs text-slate-200">
                      {sortedDurations.map((d) => {
                        const stageName =
                          stages.find((s) => s.contract_id === d.contract_id)?.name ||
                          d.contract_id;
                        return (
                          <li
                            key={d.contract_id}
                            className="flex items-center justify-between rounded-lg border border-slate-800/70 bg-slate-950/40 px-3 py-2"
                          >
                            <span className="font-medium text-slate-100">{stageName}</span>
                            <span className="font-mono text-slate-200">
                              {formatDurationShort(d.duration_sec)}
                            </span>
                          </li>
                        );
                      })}
                    </ul>
                  ) : (
                    <p className="mt-2 text-xs text-slate-400">
                      No se pudo registrar la duración de las etapas.
                    </p>
                  )}
                </section>
              )}

              {/* Métricas finales */}
              <section className="grid gap-4 md:grid-cols-2">
                <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                    Loudness y dinámica global
                  </h3>
                  {finalMetrics ? (
                    <dl className="mt-3 space-y-3 text-xs text-slate-200">
                      <div>
                        <dt className="font-semibold text-slate-100">
                          Loudness integrado (LUFS)
                        </dt>
                        <dd className="mt-0.5">
                          <span className="font-mono">
                            {formatLufs(finalMetrics.lufs)}
                          </span>
                          <p className="mt-1 text-slate-300">
                            {getLoudnessComment(finalMetrics.lufs)}
                          </p>
                        </dd>
                      </div>

                      <div>
                        <dt className="font-semibold text-slate-100">
                          Rango de sonoridad ("LRA")
                        </dt>
                        <dd className="mt-0.5">
                          <span className="font-mono">
                            {finalMetrics.lra !== null
                              ? `${finalMetrics.lra.toFixed(1)} LU`
                              : "—"}
                          </span>
                          <p className="mt-1 text-slate-300">
                            Indica cuánta variación de loudness hay a lo largo del tema:
                            valores bajos &lt; 5 LU son muy estables (radio / música muy
                            comprimida), mientras que valores altos dan sensación de
                            dinámica y cambios de intensidad.
                          </p>
                        </dd>
                      </div>

                      <div>
                        <dt className="font-semibold text-slate-100">
                          Factor de cresta aproximado
                        </dt>
                        <dd className="mt-0.5">
                          <span className="font-mono">
                            {finalMetrics.crest !== null
                              ? `${finalMetrics.crest.toFixed(1)} dB`
                              : "—"}
                          </span>
                          <p className="mt-1 text-slate-300">
                            Diferencia entre picos máximos y nivel medio del master. Valores
                            bajos implican limitación fuerte; valores más altos dejan respirar
                            más los transitorios.
                          </p>
                          <p className="mt-1 text-slate-300">
                            {getCrestComment(finalMetrics.crest)}
                          </p>
                        </dd>
                      </div>

                      {finalMetrics.typicalLevel !== null && (
                        <div>
                          <dt className="font-semibold text-slate-100">
                            Nivel RMS típico del tema
                          </dt>
                          <dd className="mt-0.5">
                            <span className="font-mono">
                              {finalMetrics.typicalLevel.toFixed(1)} dBFS
                            </span>
                            <p className="mt-1 text-slate-300">
                              Estimación basada en el histograma de niveles RMS por tramos
                              de tiempo: indica la zona de nivel donde el tema pasa más
                              tiempo.
                            </p>
                          </dd>
                        </div>
                      )}
                    </dl>
                  ) : (
                    <p className="mt-3 text-xs text-slate-400">
                      No se han podido calcular las métricas finales de loudness para este
                      job.
                    </p>
                  )}
                </div>

                <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                    Picos, imagen estéreo y equilibrio
                  </h3>
                  {finalMetrics ? (
                    <dl className="mt-3 space-y-3 text-xs text-slate-200">
                      <div>
                        <dt className="font-semibold text-slate-100">
                          True peak final
                        </dt>
                        <dd className="mt-0.5">
                          <span className="font-mono">
                            {formatDb(finalMetrics.truePeak, "dBTP")}
                          </span>
                          <p className="mt-1 text-slate-300">
                            Nivel máximo real del master tras sobremuestreo (true peak). Un
                            buen objetivo suele ser entre -2 y -1 dBTP para masters
                            conservadores, o alrededor de -1 dBTP para estilos más
                            agresivos.
                          </p>
                          <p className="mt-1 text-slate-300">
                            {getTruePeakComment(finalMetrics.truePeak)}
                          </p>
                        </dd>
                      </div>

                      <div>
                        <dt className="font-semibold text-slate-100">
                          Correlación L/R
                        </dt>
                        <dd className="mt-0.5">
                          <span className="font-mono">
                            {finalMetrics.correlation !== null
                              ? finalMetrics.correlation.toFixed(2)
                              : "—"}
                          </span>
                          <p className="mt-1 text-slate-300">
                            Mide la coherencia de fase entre los canales izquierdo y derecho.
                            Valores cercanos a 1 son muy mono; cercanos a 0, muy abiertos; y
                            valores negativos implican cancelaciones.
                          </p>
                          <p className="mt-1 text-slate-300">
                            {getCorrelationComment(finalMetrics.correlation)}
                          </p>
                        </dd>
                      </div>

                      <div>
                        <dt className="font-semibold text-slate-100">
                          Diferencia de loudness entre canales
                        </dt>
                        <dd className="mt-0.5">
                          <span className="font-mono">
                            {formatDb(finalMetrics.channelDiff, "dB")}
                          </span>
                          <p className="mt-1 text-slate-300">
                            Diferencia de nivel perceptivo (LUFS) entre canal izquierdo y
                            derecho. Valores muy altos indican que la mezcla está claramente
                            cargada hacia un lado.
                          </p>
                          <p className="mt-1 text-slate-300">
                            {getChannelDiffComment(finalMetrics.channelDiff)}
                          </p>
                        </dd>
                      </div>
                    </dl>
                  ) : (
                    <p className="mt-3 text-xs text-slate-400">
                      No se han podido calcular las métricas finales de picos/imagen
                      estéreo para este job.
                    </p>
                  )}
                </div>
              </section>

              {/* Detalle por etapas */}
              <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                  Recorrido por etapas del pipeline
                </h3>
                <p className="mt-1 text-xs text-slate-300">
                  Cada bloque resume cómo ha contribuido una etapa realmente ejecutada en
                  este pipeline. Se muestran los datos clave extraídos de su
                  <span className="font-mono"> analysis_{"<stage>"} .json</span>.
                </p>

                <div className="mt-3 space-y-2">
                  {analyzedStages.length === 0 && (
                    <p className="text-xs text-slate-400">
                      No se han encontrado etapas analizadas para este job.
                    </p>
                  )}
                  {analyzedStages.map((stage, index) => {
                    const statusLabel =
                      stage.status === "analyzed"
                        ? "Análisis completado"
                        : stage.status === "missing_analysis"
                        ? "Sin datos de análisis"
                        : stage.status;
                    const statusColor =
                      stage.status === "analyzed"
                        ? "border-emerald-500/50 bg-emerald-500/10 text-emerald-200"
                        : "border-slate-600 bg-slate-800/60 text-slate-200";
                    const bullets = buildStageSummary(stage.contract_id);

                    return (
                      <div
                        key={`${stage.contract_id}-${stage.stage_id ?? index}`}
                        className="rounded-lg border border-slate-800 bg-slate-900/50 p-3"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="text-[11px] uppercase tracking-wide text-slate-400">
                            Etapa {index + 1}: {stage.contract_id}
                          </div>
                          <span
                            className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium ${statusColor}`}
                          >
                            {statusLabel}
                          </span>
                        </div>
                        <p className="mt-1 text-sm font-medium text-slate-100">
                          {stage.name || "Etapa del pipeline"}
                        </p>
                        {stageAnalysesLoading && bullets.length === 0 && (
                          <p className="mt-1 text-[11px] text-slate-400">
                            Cargando resumen de esta etapa…
                          </p>
                        )}
                        {bullets.length > 0 && (
                          <ul className="mt-2 space-y-1 text-[11px] text-slate-200">
                            {bullets.map((line, i) => (
                              <li key={i}>• {line}</li>
                            ))}
                          </ul>
                        )}
                        {bullets.length === 0 && !stageAnalysesLoading && (
                          <p className="mt-1 text-[11px] text-slate-400">
                            No se han podido extraer datos de análisis para esta etapa.
                          </p>
                        )}
                      </div>
                    );
                  })}
                </div>
              </section>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
