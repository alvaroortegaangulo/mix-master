// frontend/src/components/MixPipelinePanel.tsx
"use client";

import { useEffect, useMemo, useState } from "react";
import type { MixResult } from "../lib/mixApi";
import { getBackendBaseUrl } from "../lib/mixApi";
import { WaveformPlayer } from "./WaveformPlayer";

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
  description: string; // stage group name (e.g. "Phase & Polarity Alignment")
  index: number;
  mediaSubdir: string | null;
  updatesCurrentDir: boolean;
  previewMixRelPath: string | null;
};

/**
 * Descriptive info per phase (stage group).
 * Keyed by backend "description" (stage group name from contracts.json).
 */
const PIPELINE_PHASE_INFO: Record<
  string,
  { title: string; body: string }
> = {
  "Input & Metadata": {
    title: "Input & Metadata",
    body: "We prepare your session by organizing all uploaded files and normalizing formats, sample rates and basic metadata so the rest of the pipeline can work consistently.",
  },
  "Technical Preparation": {
    title: "Technical Preparation",
    body: "We fix basic technical issues on each stem: DC offset, working loudness and initial headroom to ensure a clean, reliable starting point for mixing.",
  },
  "Phase & Polarity Alignment": {
    title: "Phase & Polarity Alignment",
    body: "We analyze multi-mic groups (like drums) to align phase and correct polarity, avoiding cancellations and restoring impact and low-end clarity.",
  },
  "Static Mix & Routing": {
    title: "Static Mix & Routing",
    body: "We build a static balance and bus routing, placing faders and pan positions so that all elements are heard clearly before any heavy processing.",
  },
  "Spectral Cleanup": {
    title: "Spectral Cleanup",
    body: "We clean each stem using high-pass filters and gentle notch filters to remove rumble and harsh resonances, freeing up space in the mix.",
  },
  "Dynamics & Level Automation": {
    title: "Dynamics & Level Automation",
    body: "We control dynamics using compression, limiting and level automation, keeping performances expressive but preventing peaks from jumping out of the mix.",
  },
  "Space / Depth by Buses": {
    title: "Space & Depth by Buses",
    body: "We send instruments to dedicated reverb and ambience buses, placing them closer or farther in the soundstage to create a sense of depth and space.",
  },
  "Multiband EQ / Tonal Balance": {
    title: "Multiband EQ & Tonal Balance",
    body: "We fine-tune the overall spectral balance so the mix feels natural and translates well across different playback systems.",
  },
  "Mix Bus Color": {
    title: "Mix Bus Color",
    body: "We add gentle saturation and bus processing to glue the mix together, enhancing warmth, punch and perceived loudness without destroying dynamics.",
  },
  Mastering: {
    title: "Mastering",
    body: "We bring the track up to its target loudness, adjust final EQ, stereo width and limiting so it is ready for release on streaming platforms.",
  },
  "Master Stereo QC": {
    title: "Master Stereo QC",
    body: "We run final quality checks (true peak, loudness, stereo image and balance) to ensure the master meets the technical targets.",
  },
  Reporting: {
    title: "Reporting",
    body: "We generate a technical report and export the final master so you can review what was done at each stage of the pipeline.",
  },
};

export function MixPipelinePanel({
  result,
  enabledPipelineStageKeys,
}: Props) {
  const { fullSongUrl, jobId } = result;
  const [playbackUrl, setPlaybackUrl] = useState(fullSongUrl);

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

        // Keep backend order
        const sorted = [...data].sort((a, b) => a.index - b.index);

        // If we have enabled stages for THIS job, filter to those only.
        const filtered =
          enabledPipelineStageKeys && enabledPipelineStageKeys.length > 0
            ? sorted.filter((s) => enabledPipelineStageKeys.includes(s.key))
            : sorted;

        setStages(filtered);

        // Adjust active stage
        if (!activeKey && filtered.length > 0) {
          setActiveKey(filtered[filtered.length - 1].key);
        } else if (activeKey) {
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabledPipelineStageKeys]);

  const activeStage = useMemo(() => {
    if (!stages.length) return null;
    return stages.find((s) => s.key === activeKey) ?? stages[stages.length - 1];
  }, [stages, activeKey]);

  // URL of the processed audio for the active stage (sin firmar)
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

    return fullSongUrl;
  }, [stages, activeStage, fullSongUrl, jobId]);

  // Firmar/preparar la URL a reproducir para evitar 401 (requiere api_key)
  useEffect(() => {
    let cancelled = false;

    const appendApiKey = (url: string): string => {
      const key = process.env.NEXT_PUBLIC_MIXMASTER_API_KEY;
      if (!key || !url) return url;
      if (url.includes("api_key=")) return url;
      const sep = url.includes("?") ? "&" : "?";
      return `${url}${sep}api_key=${encodeURIComponent(key)}`;
    };

    async function buildPlaybackUrl() {
      if (!processedUrl) {
        if (!cancelled) setPlaybackUrl("");
        return;
      }

      try {
        const backend = new URL(getBackendBaseUrl());
        const urlObj = new URL(processedUrl, backend);

        // Normalizar host siempre al backend
        urlObj.protocol = backend.protocol;
        urlObj.host = backend.host;
        urlObj.port = backend.port;

        // Si ya viene firmada (sig/exp), úsala tal cual
        const hasSig = urlObj.searchParams.has("sig") && urlObj.searchParams.has("exp");
        const finalUrl = hasSig ? urlObj.toString() : appendApiKey(urlObj.toString());

        if (!cancelled) setPlaybackUrl(finalUrl);
      } catch (err) {
        console.warn("Could not prepare stage URL", err);
        if (!cancelled) {
          const backend = getBackendBaseUrl();
          const normalized = processedUrl.startsWith("http")
            ? processedUrl
            : `${backend}${processedUrl.startsWith("/") ? "" : "/"}${processedUrl}`;
          setPlaybackUrl(appendApiKey(normalized));
        }
      }
    }

    void buildPlaybackUrl();
    return () => {
      cancelled = true;
    };
  }, [processedUrl, jobId]);

  const phaseInfo = useMemo(() => {
    if (!activeStage) return null;
    const key = activeStage.description;
    return (
      PIPELINE_PHASE_INFO[key] ?? {
        title: activeStage.description || "Pipeline stage",
        body: "This stage applies incremental processing to refine the mix.",
      }
    );
  }, [activeStage]);

  return (
    <section className="mt-6 rounded-2xl border border-emerald-500/40 bg-emerald-900/30 p-4 text-emerald-50 shadow-inner shadow-emerald-900/40">
      <details className="group">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-2 md:flex-row md:items-center md:justify-between [&::-webkit-details-marker]:hidden">
          <div className="flex-1">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-emerald-100">
              Pipeline
            </h3>
            <p className="mt-1 text-xs text-emerald-200/90">
              Explore how the mix evolves at each phase by listening to the
              cumulative result after every major processing block.
            </p>
          </div>
          <span
            aria-hidden="true"
            className="ml-2 text-xs text-emerald-200 transition-transform duration-200 group-open:rotate-180"
          >
            ▼
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

        {!loading && !error && stages.length > 0 && activeStage && phaseInfo && (
          <div className="mt-4">
            {/* Tabs numéricos de stages */}
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
              {/* Título de la fase (antes subtítulo) */}
              <p className="text-sm font-semibold text-emerald-50">
                {phaseInfo.title}
              </p>

              {/* Texto descriptivo de lo que hace la fase */}
              <p className="mt-2 text-xs text-emerald-200/90">
                {phaseInfo.body}
              </p>

              {/* Info pequeña de contrato activo */}
              <p className="mt-2 text-[11px] text-emerald-300/80">
                Active contract:{" "}
                <span className="font-mono text-emerald-200">
                  {activeStage.key}
                </span>
              </p>

              {/* Reproductor estilo waveform para la fase */}
              <div className="mt-4">
                <WaveformPlayer src={playbackUrl} />
              </div>
            </div>
          </div>
        )}
      </details>
    </section>
  );
}
