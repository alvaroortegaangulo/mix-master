// frontend/src/app/page.tsx
"use client";

import { useState, useEffect } from "react";
import {
  startMixJob,
  fetchJobStatus,
  type JobStatus,
  fetchPipelineStages,
  type PipelineStage,
} from "../lib/mixApi";
import { UploadDropzone } from "../components/UploadDropzone";
import { MixResultPanel } from "../components/MixResultPanel";

export default function HomePage() {
  const [files, setFiles] = useState<File[]>([]);
  const [loading, setLoading] = useState(false);
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [availableStages, setAvailableStages] = useState<PipelineStage[]>([]);
  const [selectedStageKeys, setSelectedStageKeys] = useState<string[]>([]);
  const [showStageSelector, setShowStageSelector] = useState(true);


  useEffect(() => {
    async function loadStages() {
      try {
        const stages = await fetchPipelineStages();
        setAvailableStages(stages);
        // Por defecto, todas las etapas activadas
        setSelectedStageKeys(stages.map((s) => s.key));
      } catch (err: any) {
        console.error("Error fetching pipeline stages", err);
        // No es crítico para mezclar, así que solo mostramos error suave
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


  const handleFilesSelected = (selected: File[]) => {
    setFiles(selected);
    setJobStatus(null);
    setError(null);
  };

  const hasFiles = files.length > 0;

  const handleGenerateMix = async () => {
    if (!files.length) return;
    setLoading(true);
    setError(null);
    setJobStatus(null);

    try {
      // 1) Arrancar job
      const enabled =
        selectedStageKeys.length > 0 ? selectedStageKeys : undefined;

      const { jobId } = await startMixJob(files, enabled);

      // A partir de aquí, escondemos el panel de selección para este job
      setShowStageSelector(false);

      // Estado inicial
      setJobStatus({
        jobId,
        status: "queued",
        stageIndex: 0,
        totalStages: 7,
        stageKey: "queued",
        message: "Job queued...",
        progress: 0,
      });

      // 2) Polling del estado hasta que termine
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

        // Esperar 1 segundo antes del siguiente poll
        await new Promise((resolve) => setTimeout(resolve, 1000));
      }
    } catch (err: any) {
      setError(err.message ?? "Unknown error");
      setLoading(false);
    }
  };

  // Resultado final (cuando status === "done" y hay result)
  const result = jobStatus?.status === "done" && jobStatus.result ? jobStatus.result : null;

  // Texto de progreso para el log
  const progressText =
    jobStatus && (jobStatus.status === "queued" || jobStatus.status === "running")
      ? `[${jobStatus.progress.toFixed(0)}%] Step ${jobStatus.stageIndex}/${jobStatus.totalStages} – ${jobStatus.message}`
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
            <span className="text-lg font-semibold tracking-tight">Audio Alchemy</span>
          </div>
        </div>
      </header>

      <main className="flex flex-1 items-center justify-center px-4">
        <div className="w-full max-w-3xl">
          <section className="rounded-2xl border border-slate-800/80 bg-slate-900/70 p-8 shadow-xl">
            <div className="text-center mb-8">
              <h1 className="text-3xl font-bold text-slate-50 mb-2">Upload Your Stems</h1>
              <p className="text-slate-400">Drag and drop your audio files to begin the magic.</p>
            </div>

            <UploadDropzone
              onFilesSelected={handleFilesSelected}
              disabled={loading}
              filesCount={files.length}
            />


            {showStageSelector && availableStages.length > 0 && (
              <section className="mt-6 rounded-xl border border-slate-800/70 bg-slate-900/60 p-4">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-300">
                    Pipeline steps
                  </h3>
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
                        checked={selectedStageKeys.includes(stage.key)}
                        onChange={() => toggleStage(stage.key)}
                      />
                      <div>
                        <span className="font-semibold">
                          Stage {stage.index}: {stage.label}
                        </span>
                        {stage.description && (
                          <p className="mt-0.5 text-[11px] text-slate-400">
                            {stage.description}
                          </p>
                        )}
                      </div>
                    </label>
                  ))}
                </div>

                <p className="mt-2 text-[11px] text-slate-500">
                  Las etapas desmarcadas se saltarán en el pipeline. El orden
                  y la lógica de cada etapa siguen viniendo de{" "}
                  <code className="rounded bg-slate-950 px-1">pipeline.py</code>.
                </p>
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

            {/* Línea de log con etapa y porcentaje */}
            {progressText && (
              <p className="mt-4 text-center text-sm text-slate-300 font-mono">
                {progressText}
              </p>
            )}

            {error && (
              <p className="mt-4 text-center text-sm text-red-400">
                {error}
              </p>
            )}
          </section>

          {result && <MixResultPanel result={result} />}
        </div>
      </main>

      <footer className="border-t border-slate-800/80 py-4 text-center text-xs text-slate-500">
        © 2025 Audio Alchemy. All Rights Reserved.
      </footer>
    </div>
  );
}
