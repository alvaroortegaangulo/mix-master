// frontend/src/app/page.tsx
"use client";

import { useState } from "react";

type MixResponse = {
  jobId: string;
  fullSongUrl: string;
  metrics: {
    tempo_bpm: number;
    key: string;
    scale: string;
    // etc.
  };
};

async function sendMixRequest(files: File[]): Promise<MixResponse> {
  const formData = new FormData();
  files.forEach((f) => formData.append("files", f));

  const res = await fetch("https://backend-de7a.onrender.com/mix", {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    throw new Error("Error en mezcla");
  }

  const data = (await res.json()) as MixResponse;
  return data;
}

export default function HomePage() {
  const [files, setFiles] = useState<File[]>([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<MixResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files) return;
    setFiles(Array.from(e.target.files));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const res = await sendMixRequest(files);
      setResult(res);
    } catch (err: any) {
      setError(err.message ?? "Error desconocido");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen p-8">
      <h1 className="text-2xl font-bold mb-4">
        App de mezcla y masterización
      </h1>

      <form onSubmit={handleSubmit} className="space-y-4">
        <input
          type="file"
          multiple
          onChange={handleFileChange}
          accept="audio/*"
        />
        <button type="submit" disabled={loading || files.length === 0}>
          {loading ? "Procesando..." : "Enviar a mezclar"}
        </button>
      </form>

      {error && <p style={{ color: "red" }}>{error}</p>}

      {result && (
        <section className="mt-6">
          <h2 className="text-xl font-semibold mb-2">Resultado</h2>
          <audio controls src={result.fullSongUrl} />
          <pre className="mt-4">
            {JSON.stringify(result.metrics, null, 2)}
          </pre>
        </section>
      )}
    </main>
  );
}
