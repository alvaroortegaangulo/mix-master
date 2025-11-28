// frontend/src/lib/mixApi.ts

export type MixMetrics = {
  final_peak_dbfs: number;
  final_rms_dbfs: number;
  tempo_bpm: number;
  tempo_confidence: number;
  key: string;
  scale: string;
  key_strength: number;
  vocal_shift_min: number;
  vocal_shift_max: number;
  vocal_shift_mean: number;
};

export type MixResult = {
  jobId: string;
  originalFullSongUrl: string;
  fullSongUrl: string;
  metrics: MixMetrics;
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

export type MixResponse = MixResult;


export type StemProfilePayload = {
  /** Nombre original del archivo tal y como llega en File.name, con extensión */
  name: string;
  /** Perfil seleccionado: drums, bass, lead_vocal, etc. o "auto" */
  profile: string;
};


export type SpaceDepthBusStylesPayload = {
  /** Bus lógico -> estilo de depth (flamenco_rumba, urban_trap, rock, etc.) */
  [busKey: string]: string;
};


export type InstrumentProfileDef = {
  id: string;
  family: string;
  label: string;
  notes: string;
};

export type StyleProfileDef = {
  id: string;
  label: string;
  has_reverb_profiles: boolean;
};


export function getBackendBaseUrl(): string {
  // 1) Si se ha configurado explícitamente, usamos esa URL (opcional)
  const fromEnv = process.env.NEXT_PUBLIC_BACKEND_URL?.trim();
  if (fromEnv && fromEnv.length > 0) {
    return fromEnv.replace(/\/+$/, "");
  }

  // 2) Si estamos en el navegador, deducimos según el hostname
  if (typeof window !== "undefined") {
    const { protocol, hostname } = window.location;

    // Entorno de desarrollo: frontend en localhost/127.0.0.1:3000
    if (hostname === "localhost" || hostname === "127.0.0.1") {
      // Backend local (puerto 8000)
      return "http://127.0.0.1:8000";
    }

    // Entorno de producción:
    // asumimos backend accesible en el MISMO hostname que el frontend,
    // pero escuchando en el puerto 8000
    //
    // Ejemplo:
    //   frontend: http://161.97.131.133:3000
    //   backend:  http://161.97.131.133:8000
    return `${protocol}//${hostname}:8000`;
  }

  // 3) Fallback para código que se ejecute en el servidor (build, SSR, etc.)
  //    En la práctica, si llegas aquí, suele ser entorno de desarrollo.
  return "http://127.0.0.1:8000";
}

function normalizeUrl(pathOrUrl: string | undefined, baseUrl: string): string {
  if (!pathOrUrl) return "";
  if (pathOrUrl.startsWith("http://") || pathOrUrl.startsWith("https://")) {
    return pathOrUrl;
  }
  // asumimos que el backend devuelve algo tipo "/files/..."
  return `${baseUrl}${pathOrUrl}`;
}

/**
 * Mapea el JSON crudo que devuelve el backend (Celery) al JobStatus
 * que usa tu frontend (queued/running/done/error, camelCase, etc.).
 */
function mapBackendStatusToJobStatus(raw: any, baseUrl: string): JobStatus {
  const backendStatus = (raw.status ?? "pending") as string;
  const jobId: string = raw.jobId ?? raw.job_id ?? "";

  let status: JobStatus["status"];
  switch (backendStatus) {
    case "pending":
      status = "queued";
      break;
    case "running":
      status = "running";
      break;
    case "finished":
    case "success":
      status = "done";
      break;
    case "failed":
    case "failure":
      status = "error";
      break;
    default:
      status = "error";
      break;
  }

  const totalStages =
    typeof raw.total_stages === "number" ? raw.total_stages : 7;

  const base: JobStatus = {
    jobId,
    status,
    stageIndex: 0,
    totalStages,
    stageKey: "queued",
    message: raw.message ?? "",
    progress: 0,
    error: raw.error,
  };

  if (backendStatus === "pending") {
    base.stageKey = "queued";
    base.message = raw.message ?? "Job pending in queue";
    base.progress = 0;
  } else if (backendStatus === "running") {
    base.stageIndex =
      typeof raw.stage_index === "number" ? raw.stage_index : base.stageIndex;
    base.totalStages =
      typeof raw.total_stages === "number" ? raw.total_stages : base.totalStages;
    base.stageKey = raw.stage_key ?? "running";
    base.message = raw.message ?? "Processing mix...";
    base.progress =
      typeof raw.progress === "number" ? raw.progress : base.progress;
  } else if (status === "done") {
    base.stageIndex = base.totalStages;
    base.stageKey = "finished";
    base.message = raw.message ?? "Mix finished";
    base.progress = 100;
  } else if (status === "error") {
    base.stageKey = "error";
    base.message =
      raw.message ?? raw.error ?? "Error while processing mix";
    base.progress = base.progress || 0;
  }

  // Si tenemos resultado final, mapearlo a MixResult
  if (status === "done" && raw.full_song_url) {
    const m = raw.metrics ?? {};
    const metrics: MixMetrics = {
      final_peak_dbfs: m.final_peak_dbfs ?? 0,
      final_rms_dbfs: m.final_rms_dbfs ?? 0,
      tempo_bpm: m.tempo_bpm ?? 0,
      tempo_confidence: m.tempo_confidence ?? 0,
      key: m.key ?? "",
      scale: m.scale ?? "",
      key_strength: m.key_strength ?? 0,
      vocal_shift_min: m.vocal_shift_min ?? 0,
      vocal_shift_max: m.vocal_shift_max ?? 0,
      vocal_shift_mean: m.vocal_shift_mean ?? 0,
    };

    const result: MixResult = {
      jobId,
      originalFullSongUrl: normalizeUrl(raw.original_full_song_url, baseUrl),
      fullSongUrl: normalizeUrl(raw.full_song_url, baseUrl),
      metrics,
    };

    base.result = result;
  }

  return base;
}


export async function cleanupTemp(): Promise<void> {
  const res = await fetch(`${getBackendBaseUrl()}/cleanup-temp`, {
    method: "POST",
  });

  if (!res.ok) {
    throw new Error("Failed to cleanup temp");
  }
}


// 1) Arrancar job (POST /mix)
export async function startMixJob(
  files: File[],
  enabledStageKeys?: string[],
  stemProfiles?: StemProfilePayload[],
  spaceDepthBusStyles?: SpaceDepthBusStylesPayload,
): Promise<{ jobId: string }> {
  const formData = new FormData();
  files.forEach((f) => formData.append("files", f));

  if (enabledStageKeys && enabledStageKeys.length > 0) {
    formData.append("stages_json", JSON.stringify(enabledStageKeys));
  }

  if (stemProfiles && stemProfiles.length > 0) {
    formData.append("stem_profiles_json", JSON.stringify(stemProfiles));
  }

  if (spaceDepthBusStyles && Object.keys(spaceDepthBusStyles).length > 0) {
    formData.append(
      "space_depth_bus_styles_json",
      JSON.stringify(spaceDepthBusStyles),
    );
  }

  const baseUrl = getBackendBaseUrl();
  const res = await fetch(`${baseUrl}/mix`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    throw new Error(`Error starting mix job: ${res.status} ${res.statusText}`);
  }

  const data = (await res.json()) as { jobId: string };
  return { jobId: data.jobId };
}


// 2) Consultar estado del job (GET /jobs/{jobId})
export async function fetchJobStatus(jobId: string): Promise<JobStatus> {
  const baseUrl = getBackendBaseUrl();
  const res = await fetch(`${baseUrl}/jobs/${encodeURIComponent(jobId)}`, {
    method: "GET",
  });

  if (!res.ok) {
    throw new Error(
      `Error fetching job status: ${res.status} ${res.statusText}`,
    );
  }

  const raw = await res.json();
  return mapBackendStatusToJobStatus(raw, baseUrl);
}





export type PipelineStage = {
  key: string;
  label: string;
  description: string;
  index: number;
  mediaSubdir: string | null;
  updatesCurrentDir: boolean;
  previewMixRelPath: string | null;
};

export async function fetchPipelineStages(): Promise<PipelineStage[]> {
  const baseUrl = getBackendBaseUrl();
  const res = await fetch(`${baseUrl}/pipeline/stages`, { method: "GET" });

  if (!res.ok) {
    throw new Error(
      `Error fetching pipeline stages: ${res.status} ${res.statusText}`,
    );
  }

  const data = (await res.json()) as PipelineStage[];
  return data.sort((a, b) => a.index - b.index);
}



export async function fetchInstrumentProfiles(): Promise<InstrumentProfileDef[]> {
  const base = getBackendBaseUrl();
  const res = await fetch(`${base}/profiles/instruments`);
  if (!res.ok) throw new Error("Error fetching instrument profiles");
  return (await res.json()) as InstrumentProfileDef[];
}

export async function fetchStyleProfiles(): Promise<StyleProfileDef[]> {
  const base = getBackendBaseUrl();
  const res = await fetch(`${base}/profiles/styles`);
  if (!res.ok) throw new Error("Error fetching style profiles");
  return (await res.json()) as StyleProfileDef[];
}