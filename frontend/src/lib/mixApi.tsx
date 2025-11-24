// frontend/src/lib/mixApi.ts

export type MixResult = {
  jobId: string;
  fullSongUrl: string;
  metrics: {
    tempo_bpm: number;
    key: string;
    scale: string;
    // ...añade el resto de campos que devuelva el backend
  };
};

export type JobStatus = {
  jobId: string;
  status: "queued" | "running" | "done" | "error";
  stageIndex: number;
  totalStages: number;
  stageKey: string;
  message: string;
  progress: number; // 0–100
  result?: MixResult;
  error?: string;
};

function getBackendBaseUrl(): string {
  const fromEnv = process.env.NEXT_PUBLIC_BACKEND_URL?.trim();
  if (fromEnv && fromEnv.length > 0) {
    return fromEnv.replace(/\/+$/, "");
  }
  return "http://127.0.0.1:8000";
}

// 1) Arrancar job
export async function startMixJob(files: File[]): Promise<{ jobId: string }> {
  const formData = new FormData();
  files.forEach((f) => formData.append("files", f));

  const baseUrl = getBackendBaseUrl();

  const res = await fetch(`${baseUrl}/mix`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    throw new Error(`Error starting mix job: ${res.status} ${res.statusText}`);
  }

  const data = (await res.json()) as { jobId: string };
  return data;
}

// 2) Consultar estado
export async function fetchJobStatus(jobId: string): Promise<JobStatus> {
  const baseUrl = getBackendBaseUrl();

  const res = await fetch(`${baseUrl}/jobs/${jobId}/status`, {
    method: "GET",
  });

  if (!res.ok) {
    throw new Error(`Error fetching job status: ${res.status} ${res.statusText}`);
  }

  const data = (await res.json()) as JobStatus;

  // Si hay resultado y fullSongUrl es relativo, pegamos la base
  if (data.result && data.result.fullSongUrl && !data.result.fullSongUrl.startsWith("http")) {
    data.result.fullSongUrl = `${baseUrl}${data.result.fullSongUrl}`;
  }

  return data;
}
