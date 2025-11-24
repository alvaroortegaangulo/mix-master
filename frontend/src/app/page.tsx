// frontend/src/app/page.tsx
"use client";

import { useState } from "react";
import { startMixJob, fetchJobStatus, type JobStatus } from "../lib/mixApi";
import { UploadDropzone } from "../components/UploadDropzone";
import { MixResultPanel } from "../components/MixResultPanel";

export default function HomePage() {
  const [files, setFiles] = useState<File[]>([]);
  const [loading, setLoading] = useState(false);
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFilesSelected = (selected: File[]) => {
    setFiles(selected);
    setJobStatus(null);
    setError(null);
  };

  const hasFiles = files.length > 0;

  const handleGenerateMix = async () => {
    setError(null);
    setLoading(true);
    setJobStatus(null);

    try {
      // 1) Arrancar job
      const { jobId } = await startMixJob(files);

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
              <p className="text-slate-400">Drag and drop your audio files to begin the magic penis 2.</p>
            </div>

            <UploadDropzone
              onFilesSelected={handleFilesSelected}
              disabled={loading}
              filesCount={files.length}
            />

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
