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

        // Ajustar la etapa activa:
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

  // Calculamos la URL del audio procesado para la etapa activa:
  //   - buscamos, desde el principio hasta la etapa activa, la última que tenga previewMixRelPath
  //   - si no hay ninguna, usamos directamente el master final (fullSongUrl)
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

  if (loading && !stages.length) {
    return (
      <section className="mt-6 rounded-2xl border border-slate-800/80 bg-slate-900/80 p-4">
        <p className="text-xs text-slate-400">
          Cargando definición del pipeline…
        </p>
      </section>
    );
  }

  if (error) {
    return (
      <section className="mt-6 rounded-2xl border border-slate-800/80 bg-slate-900/80 p-4">
        <details className="group">
          <summary className="flex cursor-pointer list-none [&::-webkit-details-marker]:hidden">
            <div>
              <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-300">
                Pipeline
              </h3>
              <p className="mt-1 text-xs text-slate-400">
                Explora cómo va evolucionando la mezcla etapa a etapa, escuchando
                el resultado acumulado hasta la etapa seleccionada.
              </p>
            </div>
          </summary>
          <p className="mt-2 text-xs text-red-400">
            {error} (endpoint esperado:{" "}
            <code className="bg-slate-950 px-1">/pipeline/stages</code>).
          </p>
        </details>
      </section>
    );
  }

  if (!activeStage) {
    // Si para este job no hay ningún stage (p.ej. edge-case), no mostramos nada
    return null;
  }

  return (
    <section className="mt-6 rounded-2xl border border-slate-800/80 bg-slate-900/80 p-4 shadow-inner">
      <details className="group">
        <summary className="flex cursor-pointer list-none flex-col gap-2 md:flex-row md:items-center md:justify-between [&::-webkit-details-marker]:hidden">
          <div>
            <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-300">
              Pipeline
            </h3>
            <p className="mt-1 text-xs text-slate-400">
              Explora cómo va evolucionando la mezcla etapa a etapa, escuchando
              el resultado acumulado hasta la etapa seleccionada.
            </p>
          </div>
        </summary>

        {/* Contenido expandible: tabs + player */}
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
                      ? "bg-indigo-500 text-white shadow-sm"
                      : "bg-slate-800 text-slate-300 hover:bg-slate-700",
                  ].join(" ")}
                >
                  {stage.index}
                </button>
              );
            })}
          </div>

          {/* Contenido de la etapa activa */}
          <div className="mt-4 rounded-xl bg-slate-950/40 p-4">
            <p className="text-sm font-semibold text-slate-100">
              {`Stage ${activeStage.index} · ${activeStage.label}`}
            </p>
            <p className="mt-2 text-xs text-slate-300">
              {activeStage.description}
            </p>

            {/* Solo mostramos la mezcla tras esta etapa */}
            <div className="mt-4">
              <p className="mb-1 text-xs font-medium text-slate-200">
                Mix tras esta etapa
              </p>
              <audio
                controls
                src={processedUrl}
                className="mt-1 w-full rounded-lg bg-slate-800"
              />
              <p className="mt-1 text-[11px] text-slate-500">
                Esta mezcla refleja todas las etapas habilitadas desde el inicio
                hasta{" "}
                <span className="font-semibold">
                  Stage {activeStage.index} · {activeStage.label}
                </span>
                . Si alguna etapa anterior no genera un bounce propio todavía, se
                usa la mezcla más cercana disponible (por defecto, el master
                final).
              </p>
            </div>
          </div>
        </div>
      </details>
    </section>
  );
}
