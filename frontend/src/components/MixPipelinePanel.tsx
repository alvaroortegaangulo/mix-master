// frontend/src/components/MixPipelinePanel.tsx
"use client";

import { useEffect, useMemo, useState } from "react";
import type { MixResult } from "../lib/mixApi";
import { getBackendBaseUrl } from "../lib/mixApi";

type Props = {
  result: MixResult;
  /**
   * List of pipeline stage keys that were executed for this job.
   * If undefined or empty, all backend stages are shown.
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

  // Load pipeline definition from the backend
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
            `Could not fetch pipeline definition (${res.status})`,
          );
        }
        const data = (await res.json()) as PipelineStage[];

        // Keep backend order just in case
        const sorted = [...data].sort((a, b) => a.index - b.index);

        // If we have enabled stages for THIS job, filter to those only.
        const filtered =
          enabledPipelineStageKeys && enabledPipelineStageKeys.length > 0
            ? sorted.filter((s) => enabledPipelineStageKeys.includes(s.key))
            : sorted;

        setStages(filtered);

        // Adjust active stage
        if (!activeKey && filtered.length > 0) {
          // if no active stage yet, select the last one (usually mastering)
          setActiveKey(filtered[filtered.length - 1].key);
        } else if (activeKey) {
          // If the active one no longer exists (disabled), fall back to the last one
          const stillExists = filtered.some((s) => s.key === activeKey);
          if (!stillExists && filtered.length > 0) {
            setActiveKey(filtered[filtered.length - 1].key);
          }
        }
      } catch (err: any) {
        if (err?.name === "AbortError") return;
        console.error("Error loading pipeline stages", err);
        setError(err?.message ?? "Error loading the pipeline definition.");
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

  // URL of the processed audio for the active stage
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

    // Fallback: if no preview exists, use the final master
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
              Explore how the mix evolves at each stage by listening to the cumulative result.
            </p>
          </div>
          <span
            aria-hidden="true"
            className="ml-2 text-xs text-emerald-200 transition-transform duration-200 group-open:rotate-180"
          >
            v
          </span>
        </summary>

        {loading && !stages.length && (
          <p className="mt-3 text-xs text-emerald-200/80">
            Loading pipeline definition...
          </p>
        )}

        {error && (
          <p className="mt-3 text-xs text-red-400">
            {error} (expected endpoint:{" "}
            <code className="bg-slate-950 px-1">/pipeline/stages</code>).
          </p>
        )}

        {!loading && !error && stages.length > 0 && activeStage && (
          <div className="mt-4">
            {/* Stage index tabs (only stages enabled for this job) */}
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

            <div className="mt-4 rounded-xl bg-emerald-950/40 p-4">
              <p className="text-sm font-semibold text-emerald-50">
                {`Stage ${activeStage.index} - ${activeStage.label}`}
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
