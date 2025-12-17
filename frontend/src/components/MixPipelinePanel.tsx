"use client";

import { useEffect, useMemo, useState } from "react";
import type { MixResult } from "../lib/mixApi";
import { getBackendBaseUrl } from "../lib/mixApi";
import { WaveformPlayer } from "./WaveformPlayer";
import { useTranslations } from "next-intl";

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

// Map backend description strings to translation keys
const PHASE_KEY_MAP: Record<string, string> = {
  "Input & Metadata": "inputMetadata",
  "Technical Preparation": "technicalPreparation",
  "Phase & Polarity Alignment": "phasePolarityAlignment",
  "Static Mix & Routing": "staticMixRouting",
  "Spectral Cleanup": "spectralCleanup",
  "Dynamics & Level Automation": "dynamicsLevelAutomation",
  "Space / Depth by Buses": "spaceDepthByBuses",
  "Multiband EQ / Tonal Balance": "multibandEqTonalBalance",
  "Mix Bus Color": "mixBusColor",
  "Mastering": "mastering",
  "Master Stereo QC": "masterStereoQc",
  "Reporting": "reporting"
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

  const tPhases = useTranslations("PipelinePhases");
  const tPanel = useTranslations("MixPipelinePanel");

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

        // Filter stages based on what was actually executed (passed via enabledPipelineStageKeys).
        let filtered = sorted;

        if (Array.isArray(enabledPipelineStageKeys)) {
          const allowed = new Set(enabledPipelineStageKeys);
          filtered = sorted.filter((s) => allowed.has(s.key));
        }

        setStages(filtered);

        // Adjust active stage
        setActiveKey((prev) => {
          if (!filtered.length) return "";
          if (!prev) return filtered[filtered.length - 1].key;
          return filtered.some((s) => s.key === prev)
            ? prev
            : filtered[filtered.length - 1].key;
        });
      } catch (err: any) {
        if (err?.name === "AbortError") return;
        console.error("Error loading pipeline stages", err);
        setError(err?.message ?? tPanel("error"));
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
    const mappedKey = PHASE_KEY_MAP[key];

    if (mappedKey) {
        return {
            title: tPhases(`${mappedKey}.title`),
            body: tPhases(`${mappedKey}.body`)
        };
    }

    // Fallback if mapping fails or translation missing
    return {
        title: activeStage.description || "Pipeline stage",
        body: "This stage applies incremental processing to refine the mix.",
    };
  }, [activeStage, tPhases]);

  return (
    <section className="mt-6 rounded-2xl border border-emerald-500/40 bg-emerald-500/10 p-4 text-emerald-50 shadow-inner shadow-emerald-500/20">
      <details className="group">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-2 md:flex-row md:items-center md:justify-between [&::-webkit-details-marker]:hidden">
          <div className="flex-1">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-emerald-100">
              {tPanel("title")}
            </h3>
            <p className="mt-1 text-xs text-emerald-200/90">
              {tPanel("description")}
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
            {tPanel("loading")}
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
            {/* Stage Selector Dropdown */}
            <div className="mt-4">
              <select
                value={activeStage.key}
                onChange={(e) => setActiveKey(e.target.value)}
                className="w-full rounded-lg border border-emerald-500/30 bg-emerald-950/50 px-4 py-2 text-sm text-emerald-100 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
              >
                {stages.map((stage) => (
                  <option key={stage.key} value={stage.key} className="bg-slate-900 text-emerald-100">
                    {stage.index}. {stage.key}
                  </option>
                ))}
              </select>
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
