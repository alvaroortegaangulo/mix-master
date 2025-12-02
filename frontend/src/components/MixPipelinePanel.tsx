// frontend/src/components/MixPipelinePanel.tsx
"use client";

import { useEffect, useMemo, useState } from "react";
import type { MixResult } from "../lib/mixApi";
import { getBackendBaseUrl } from "../lib/mixApi";

type Props = {
  result: MixResult;
  /**
   * Lista de keys de stages del pipeline que se ejecutaron
   * (tal y como los conoce el backend: dc_offset, loudness, static_mix_eq, etc.)
   * Si viene undefined o vacía, se muestran todos los stages del backend.
   */
  enabledPipelineStageKeys?: string[];
};

export type PipelineStage = {
  key: string;
  label: string;
  description: string;
  index: number;
  mediaSubdir: string | null;
  updatesCurrentDir: boolean;
  previewMixRelPath: string | null;
};

export function MixPipelinePanel({ result, enabledPipelineStageKeys }: Props) {
  const { fullSongUrl, jobId } = result;

  const [stages, setStages] = useState<PipelineStage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeKey, setActiveKey] = useState<string>("");

  // Cargar la definición del pipeline desde el backend
  useEffect(() => {
    const base = getBackendBaseUrl();
    const url = `${base}/pipeline/stages`;
    const controller = new AbortController();

    async function loadStages() {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(url, { signal: controller.signal });
        if (!res.ok) {
          throw new Error(
            `No se pudo obtener la definición del pipeline (${res.status})`,
          );
        }
        const data = (await res.json()) as PipelineStage[];

        // Ordenamos por index por si acaso
        const sorted = [...data].sort((a, b) => a.index - b.index);

        // Si tenemos lista de stages habilitados para ESTE job,
        // filtramos para mostrar sólo esos (respetando el orden del backend).
        const filtered =
          enabledPipelineStageKeys && enabledPipelineStageKeys.length > 0
            ? sorted.filter((s) => enabledPipelineStageKeys.includes(s.key))
            : sorted;

        setStages(filtered);

        // Ajustar la etapa activa
        if (!activeKey && filtered.length > 0) {
          // si no hay etapa activa aún, seleccionamos la última (mastering normalmente)
          setActiveKey(filtered[filtered.length - 1].key);
        } else if (activeKey) {
          // Si hay activa y ya no existe (porque no estaba habilitada), caemos a la última
          const stillExists = filtered.some((s) => s.key === activeKey);
          if (!stillExists && filtered.length > 0) {
            setActiveKey(filtered[filtered.length - 1].key);
          }
        }
      } catch (err: any) {
        if (err?.name === "AbortError") return;
        console.error("Error cargando pipeline stages", err);
        setError(err?.message ?? "Error cargando la definición del pipeline.");
      } finally {
        setLoading(false);
      }
    }

    void loadStages();
    return () => controller.abort();
  }, [activeKey, enabledPipelineStageKeys]);

  const activeStage = useMemo(() => {
    if (!stages.length) return null;
    return stages.find((s) => s.key === activeKey) ?? stages[stages.length - 1];
  }, [stages, activeKey]);

  // URL del audio procesado para la etapa activa
  const processedUrl = useMemo(() => {
    if (!stages.length || !activeStage) return fullSongUrl;

    const base = getBackendBaseUrl();
    const activeIndex = stages.findIndex((s) => s.key === activeStage.key);
    if (activeIndex === -1) {
      return fullSongUrl;
    }

    const candidate = [...stages]
      .slice(0, activeIndex + 1)
      .reverse()
      .find((s) => s.previewMixRelPath);

    if (candidate && candidate.previewMixRelPath) {
      return `${base}/files/${encodeURIComponent(
        jobId,
      )}${candidate.previewMixRelPath}`;
    }

    // Fallback: si no hay preview específico, usamos el master final
    return fullSongUrl;
  }, [stages, activeStage, fullSongUrl, jobId]);

  return (
    <section className="mt-6 rounded-2xl border border-emerald-500/40 bg-emerald-900/30 p-4 text-emerald-50 shadow-inner shadow-emerald-900/40">
    <details className="group">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-2 md:flex-row md:items-center md:justify-between [&::-webkit-details-marker]:hidden">
        <div className="flex-1">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-emerald-100">
            Pipeline
          </h3>
          <p className="mt-1 text-xs text-emerald-200/90">
            Explora cómo va evolucionando la mezcla etapa a etapa, escuchando
            el resultado acumulado hasta la etapa seleccionada.
          </p>
        </div>
        <span
          aria-hidden="true"
          className="ml-2 text-xs text-emerald-200 transition-transform duration-200 group-open:rotate-180"
        >
          ▼
        </span>
      </summary>
      {/* resto igual */}


        {loading && !stages.length && (
          <p className="mt-3 text-xs text-emerald-200/80">
            Cargando definición del pipeline…
          </p>
        )}

        {error && (
          <p className="mt-3 text-xs text-red-400">
            {error} (endpoint esperado:{" "}
            <code className="bg-slate-950 px-1">/pipeline/stages</code>).
          </p>
        )}

        {!loading && !error && stages.length > 0 && activeStage && (
          <div className="mt-4">
            {/* Tabs con índice de etapa (sólo las etapas habilitadas para este job) */}
            <div className="flex flex-wrap gap-2">
              {stages.map((stage) => {
                const isActive = stage.key === activeStage.key;
                return (
                  <button
                    key={stage.key}
                    type="button"
                    onClick={() => setActiveKey(stage.key)}
                    className={[
                      "rounded-full px-3 py-1 text-xs font-medium transition",
                      isActive
                        ? "bg-emerald-500 text-emerald-950 shadow-sm"
                        : "bg-emerald-950/60 text-emerald-100 hover:bg-emerald-900/70",
                    ].join(" ")}
                  >
                    {stage.index}
                  </button>
                );
              })}
            </div>

            {/* Contenido de la etapa activa */}
            <div className="mt-4 rounded-xl bg-emerald-950/40 p-4">
              <p className="text-sm font-semibold text-emerald-50">
                {`Stage ${activeStage.index} · ${activeStage.label}`}
              </p>
              <p className="mt-2 text-xs text-emerald-200/90">
                {activeStage.description}
              </p>

              <div className="mt-4">
                <audio
                  controls
                  src={processedUrl}
                  className="mt-1 w-full rounded-lg bg-emerald-900/70"
                />
              </div>
            </div>
          </div>
        )}
      </details>
    </section>
  );
}
