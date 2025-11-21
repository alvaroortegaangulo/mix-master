// frontend/src/app/page.tsx
"use client";

import { useState } from "react";
import { sendMixRequest, type MixResponse } from "../lib/mixApi";
import { UploadDropzone } from "../components/UploadDropzone";
import { MixResultPanel } from "../components/MixResultPanel";

export default function HomePage() {
  const [files, setFiles] = useState<File[]>([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<MixResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFilesSelected = (selected: File[]) => {
    setFiles(selected);
    setResult(null);
    setError(null);
  };

  const handleGenerateMix = async () => {
    setError(null);
    setLoading(true);

    try {
      const res = await sendMixRequest(files);
      setResult(res);
    } catch (err: any) {
      setError(err.message ?? "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  const hasFiles = files.length > 0;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* Top bar */}
      <header className="border-b border-slate-800/80">
        <div className="mx-auto flex h-16 max-w-5xl items-center px-4">
          <div className="flex items-center gap-2">
            <div className="h-7 w-7 rounded-full bg-teal-400/90 flex items-center justify-center text-slate-950 text-lg font-bold">
              A
            </div>
            <span className="text-lg font-semibold tracking-tight">
              Audio Alchemy
            </span>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="flex flex-1 items-center justify-center px-4">
        <div className="w-full max-w-3xl">
          <section className="rounded-2xl border border-slate-800/80 bg-slate-900/70 p-8 shadow-xl">
            <div className="text-center mb-8">
              <h1 className="text-3xl font-bold text-slate-50 mb-2">
                Upload Your Stems
              </h1>
              <p className="text-slate-400">
                Drag and drop your audio files to begin the magic.
              </p>
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
                {loading ? "Generating mix..." : "Generate AI Mix"}
              </button>
            </div>

            {error && (
              <p className="mt-4 text-center text-sm text-red-400">{error}</p>
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
