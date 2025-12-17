// frontend/src/lib/mixApi.tsx

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
  const fromEnv = process.env.NEXT_PUBLIC_BACKEND_URL?.trim();
  if (fromEnv && fromEnv.length > 0) {
    return fromEnv.replace(/\/+$/, "");
  }

  if (typeof window !== "undefined") {
    const { protocol, hostname } = window.location;

    // Desarrollo local
    if (hostname === "localhost" || hostname === "127.0.0.1") {
      return "http://127.0.0.1:8000";
    }

    // Producción sin env: asumimos api.<dominio>
    const rootDomain = hostname.replace(/^www\./, "");
    return `${protocol}//api.${rootDomain}`;
  }

  // Fallback para SSR/build
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

export function appendApiKeyParam(url: string): string {
  const key = process.env.NEXT_PUBLIC_MIXMASTER_API_KEY;
  if (!key) return url;
  if (!url) return url;
  if (url.includes("api_key=")) return url;
  const sep = url.includes("?") ? "&" : "?";
  return `${url}${sep}api_key=${encodeURIComponent(key)}`;
}

function normalizeFilePath(jobId: string, filePath: string): string {
  let clean = (filePath || "").trim();

  // Si viene como URL absoluta, extraemos solo el path
  try {
    const asUrl = new URL(clean, getBackendBaseUrl());
    clean = asUrl.pathname;
  } catch {
    // noop: usamos la ruta tal cual
  }

  // Quitamos query/fragment previos (?exp=..., #...)
  clean = clean.split(/[?#]/)[0];
  clean = clean.replace(/^\/+/, "");

  const prefixWithJob = `files/${jobId}/`;
  if (clean.startsWith(prefixWithJob)) {
    clean = clean.slice(prefixWithJob.length);
  } else if (clean.startsWith("files/")) {
    clean = clean.slice("files/".length);
  } else if (clean.startsWith(`${jobId}/`)) {
    clean = clean.slice(jobId.length + 1);
  }

  return clean;
}

function authHeaders(): HeadersInit {
  const key = process.env.NEXT_PUBLIC_MIXMASTER_API_KEY;
  const headers: HeadersInit = {};
  if (key) {
    headers["X-API-Key"] = key;
  }
  // Añadimos el JWT si existe en cliente para endpoints protegidos
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("access_token");
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
  }
  return headers;
}

export async function getStudioToken(jobId: string, ttlDays = 7): Promise<{ token: string; expires: number }> {
  const baseUrl = getBackendBaseUrl();
  const res = await fetch(`${baseUrl}/jobs/${jobId}/studio-token`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
    },
    body: JSON.stringify({ ttl_days: ttlDays }),
  });
  if (!res.ok) {
    throw new Error(`Failed to obtain studio token: ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as { token: string; expires: number };
}

export async function signFileUrl(jobId: string, filePath: string, token?: string): Promise<string> {
  const baseUrl = getBackendBaseUrl();
  const normalizedPath = normalizeFilePath(jobId, filePath);

  if (token) {
    const sep = normalizedPath ? "/" : "";
    const clean = normalizedPath.startsWith("/") ? normalizedPath.slice(1) : normalizedPath;
    return `${baseUrl}/files/${jobId}${sep}${clean}?t=${encodeURIComponent(token)}`;
  }

  // Request a longer expiration time to prevent 401 on long sessions
  const expiresIn = 3600;

  const res = await fetch(`${baseUrl}/files/sign`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
    },
    body: JSON.stringify({
      jobId,
      filePath: normalizedPath,
      expires_in: expiresIn,
    }),
  });
  if (!res.ok) {
    throw new Error(`Failed to sign URL: ${res.status} ${res.statusText}`);
  }
  const data = (await res.json()) as { url: string };

  // [MODIFIED] Correct hostname in case backend returned internal container URL
  try {
    const signedUrlObj = new URL(data.url);
    const currentBase = new URL(baseUrl);

    // Replace protocol/host/port if ANY differ (avoids http URLs blocked by CSP)
    if (
      signedUrlObj.host !== currentBase.host ||
      signedUrlObj.protocol !== currentBase.protocol ||
      signedUrlObj.port !== currentBase.port
    ) {
      signedUrlObj.protocol = currentBase.protocol;
      signedUrlObj.host = currentBase.host;
      signedUrlObj.port = currentBase.port;
      return signedUrlObj.toString();
    }
    return data.url;
  } catch (e) {
    // If URL parsing fails, return original
    return data.url;
  }
}

/**
 * Mapea el JSON crudo que devuelve el backend (Celery) al JobStatus
 * que usa tu frontend (queued/running/done/error, camelCase, etc.).
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function mapBackendStatusToJobStatus(raw: any, baseUrl: string): JobStatus {
  const backendStatus = (raw.status ?? "pending") as string;
  const jobId: string = raw.jobId ?? raw.job_id ?? "";

  let status: JobStatus["status"];
  switch (backendStatus) {
    case "pending":
    case "queued":
      status = "queued";
      break;
    case "running":
    case "processing_correction":
    case "waiting_for_correction":
      status = "running";
      break;
    case "finished":
    case "success":
    case "done":
      status = "done";
      break;
    case "failed":
    case "failure":
    case "error":
      status = "error";
      break;
    default:
      console.warn(`[mixApi] Unknown backend status: "${backendStatus}". Defaulting to error.`);
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

  if (status === "queued") {
    base.stageKey = "queued";
    base.message = raw.message ?? "Job pending in queue";
    base.progress = 0;
  } else if (status === "running") {
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
    // If we fell into default error, append the status to the message for debugging
    const defaultMsg = ["failed", "failure", "error"].includes(backendStatus)
      ? "Error while processing mix"
      : `Unknown job status: "${backendStatus}"`;

    base.message = raw.message ?? raw.error ?? defaultMsg;
    // Also ensure error field is set if missing so MixTool displays it
    if (!base.error && !raw.message && !raw.error) {
      base.error = defaultMsg;
    }
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
      originalFullSongUrl: appendApiKeyParam(
        normalizeUrl(raw.original_full_song_url, baseUrl),
      ),
      fullSongUrl: appendApiKeyParam(normalizeUrl(raw.full_song_url, baseUrl)),
      metrics,
    };

    base.result = result;
  }

  return base;
}

export async function cleanupTemp(): Promise<void> {
  const res = await fetch(`${getBackendBaseUrl()}/cleanup-temp`, {
    method: "POST",
    headers: authHeaders(),
  });

  if (!res.ok) {
    throw new Error("Failed to cleanup temp");
  }
}

// -----------------------------------------------------------------------------
// Helpers internos para subida paralela (SIN compresión)
// -----------------------------------------------------------------------------

async function uploadSingleFileForJob(
  baseUrl: string,
  jobId: string,
  file: File,
): Promise<void> {
  const fd = new FormData();
  fd.append("file", file);

  const res = await fetch(
    `${baseUrl}/mix/${encodeURIComponent(jobId)}/upload-file`,
    {
      method: "POST",
      headers: authHeaders(),
      body: fd,
    },
  );

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(
      `Error uploading file "${file.name}": ${res.status} ${res.statusText} ${text}`,
    );
  }
}

/**
 * Sube N ficheros en paralelo a un job existente, con límite de concurrencia.
 */
async function uploadFilesInParallelForJob(
  baseUrl: string,
  jobId: string,
  files: File[],
  concurrency = 10,
): Promise<void> {
  if (files.length === 0) return;

  let index = 0;

  async function worker() {
    while (true) {
      const currentIndex = index++;
      if (currentIndex >= files.length) break;
      const file = files[currentIndex];
      await uploadSingleFileForJob(baseUrl, jobId, file);
    }
  }

  const workersCount = Math.min(concurrency, files.length);
  const workers = Array.from({ length: workersCount }, () => worker());
  await Promise.all(workers);
}

// -----------------------------------------------------------------------------
// 1) Arrancar job (POST /mix o flujo multi-step /mix/init + uploads paralelos)
// -----------------------------------------------------------------------------

export async function startMixJob(
  files: File[],
  enabledStageKeys?: string[],
  stemProfiles?: StemProfilePayload[],
  spaceDepthBusStyles?: SpaceDepthBusStylesPayload,
  uploadMode: "song" | "stems" = "song",
): Promise<{ jobId: string }> {
  const baseUrl = getBackendBaseUrl();

  // Caso sencillo: 0 o 1 archivo -> /mix clásico
  if (files.length <= 1) {
    const formData = new FormData();
    files.forEach((f) => formData.append("files", f));

    if (enabledStageKeys && enabledStageKeys.length > 0) {
      formData.append("stages_json", JSON.stringify(enabledStageKeys));
    }

    if (stemProfiles && stemProfiles.length > 0) {
      formData.append("stem_profiles_json", JSON.stringify(stemProfiles));
    }

    if (
      spaceDepthBusStyles &&
      Object.keys(spaceDepthBusStyles).length > 0
    ) {
      formData.append(
        "space_depth_bus_styles_json",
        JSON.stringify(spaceDepthBusStyles),
      );
    }

    formData.append("upload_mode", uploadMode);

    const res = await fetch(`${baseUrl}/mix`, {
      method: "POST",
      headers: authHeaders(),
      body: formData,
    });

    if (!res.ok) {
      throw new Error(
        `Error starting mix job: ${res.status} ${res.statusText}`,
      );
    }

    const data = (await res.json()) as { jobId: string };
    return { jobId: data.jobId };
  }

  // Caso multi-archivo (>1): flujo en 3 pasos
  //   1) /mix/init
  //   2) /mix/{jobId}/upload-file (PARALELO)
  //   3) /mix/{jobId}/start

  // 1) INIT
  const initForm = new FormData();

  if (enabledStageKeys && enabledStageKeys.length > 0) {
    initForm.append("stages_json", JSON.stringify(enabledStageKeys));
  }

  if (stemProfiles && stemProfiles.length > 0) {
    initForm.append("stem_profiles_json", JSON.stringify(stemProfiles));
  }

  if (spaceDepthBusStyles && Object.keys(spaceDepthBusStyles).length > 0) {
    initForm.append(
      "space_depth_bus_styles_json",
      JSON.stringify(spaceDepthBusStyles),
    );
  }

  initForm.append("upload_mode", uploadMode);

  const initRes = await fetch(`${baseUrl}/mix/init`, {
    method: "POST",
    headers: authHeaders(),
    body: initForm,
  });

  if (!initRes.ok) {
    const text = await initRes.text().catch(() => "");
    throw new Error(
      `Error initializing mix job: ${initRes.status} ${initRes.statusText} ${text}`,
    );
  }

  const initData = (await initRes.json()) as { jobId: string };
  const jobId = initData.jobId;

  // 2) Uploads en paralelo (SIN compresión)
  await uploadFilesInParallelForJob(baseUrl, jobId, files, 10);

  // 3) Start: encolar tarea Celery para ese job
  const startRes = await fetch(
    `${baseUrl}/mix/${encodeURIComponent(jobId)}/start`,
    {
      method: "POST",
      headers: authHeaders(),
    },
  );

  if (!startRes.ok) {
    const text = await startRes.text().catch(() => "");
    throw new Error(
      `Error starting mix pipeline for job ${jobId}: ${startRes.status} ${startRes.statusText} ${text}`,
    );
  }

  return { jobId };
}

// -----------------------------------------------------------------------------
// 2) Consultar estado del job (GET /jobs/{jobId})
// -----------------------------------------------------------------------------

export async function fetchJobStatus(jobId: string): Promise<JobStatus> {
  const baseUrl = getBackendBaseUrl();
  const res = await fetch(`${baseUrl}/jobs/${encodeURIComponent(jobId)}?_t=${Date.now()}`, {
    method: "GET",
    // Avoid any browser/proxy cache between pipeline updates
    cache: "no-store",
    headers: {
      ...authHeaders(),
    },
  });

  if (!res.ok) {
    throw new Error(
      `Error fetching job status: ${res.status} ${res.statusText}`,
    );
  }

  const raw = await res.json();
  const mapped = mapBackendStatusToJobStatus(raw, baseUrl);

  // Firmar URLs de media si existen
  // [MODIFIED] Added error handling for signing to prevent crash if file not ready
  if (mapped.result?.fullSongUrl) {
    try {
      const urlObj = new URL(mapped.result.fullSongUrl, baseUrl);
      const prefix = `/files/${jobId}/`;
      const filePath = urlObj.pathname.startsWith(prefix)
        ? urlObj.pathname.slice(prefix.length)
        : urlObj.pathname.replace(/^\/files\//, "");
      mapped.result.fullSongUrl = await signFileUrl(jobId, filePath);
    } catch (e) {
      console.warn("Failed to sign fullSongUrl", e);
      // Keep mapped.result.fullSongUrl as is (unsigned) so user might see 401 instead of crashing app
    }
  }
  if (mapped.result?.originalFullSongUrl) {
    try {
      const urlObj = new URL(mapped.result.originalFullSongUrl, baseUrl);
      const prefix = `/files/${jobId}/`;
      const filePath = urlObj.pathname.startsWith(prefix)
        ? urlObj.pathname.slice(prefix.length)
        : urlObj.pathname.replace(/^\/files\//, "");
      mapped.result.originalFullSongUrl = await signFileUrl(jobId, filePath);
    } catch (e) {
      console.warn("Failed to sign originalFullSongUrl", e);
    }
  }

  return mapped;
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

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function fetchJobReport(jobId: string): Promise<any> {
  const baseUrl = getBackendBaseUrl();
  const rel = `/files/${jobId}/S11_REPORT_GENERATION/report.json`;
  const url = appendApiKeyParam(`${baseUrl}${rel}`);

  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Failed to fetch report: ${res.statusText}`);
  }
  return await res.json();
}
