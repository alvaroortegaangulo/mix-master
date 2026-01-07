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

export function getApiBaseUrl(): string {
  const envApi =
    process.env.NEXT_PUBLIC_API_BASE_URL?.trim() ||
    process.env.NEXT_PUBLIC_BACKEND_URL?.trim();
  if (envApi) {
    return envApi.replace(/\/+$/, "");
  }

  if (typeof window !== "undefined") {
    return "/api";
  }

  const siteUrl = process.env.NEXT_PUBLIC_SITE_URL?.trim();
  if (siteUrl) {
    try {
      return new URL("/api", siteUrl).toString().replace(/\/+$/, "");
    } catch {
      // fall through
    }
  }

  const vercelUrl = process.env.VERCEL_URL?.trim();
  if (vercelUrl) {
    return `https://${vercelUrl.replace(/\/+$/, "")}/api`;
  }

  return "http://127.0.0.1:3000/api";
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
  return url;
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
  const headers: HeadersInit = {};
  // Añadimos el JWT si existe en cliente para endpoints protegidos
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("access_token");
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
  }
  return headers;
}

function withTimeoutSignal(timeoutMs: number): {
  signal: AbortSignal;
  cleanup: () => void;
} {
  const controller = new AbortController();
  const id =
    typeof window === "undefined"
      ? setTimeout(() => controller.abort(), timeoutMs)
      : window.setTimeout(() => controller.abort(), timeoutMs);
  const cleanup = () => {
    if (typeof window === "undefined") clearTimeout(id);
    else window.clearTimeout(id);
  };
  return { signal: controller.signal, cleanup };
}

export async function getStudioToken(
  jobId: string,
  ttlDays = 7,
): Promise<{ token: string; expires: number }> {
  const baseUrl = getApiBaseUrl();
  const { signal, cleanup } = withTimeoutSignal(15000);
  try {
    const res = await fetch(`${baseUrl}/jobs/${jobId}/studio-token`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...authHeaders(),
      },
      body: JSON.stringify({ ttl_days: ttlDays }),
      signal,
      cache: "no-store",
    });
    if (!res.ok) {
      throw new Error(
        `Failed to obtain studio token: ${res.status} ${res.statusText}`,
      );
    }
    return (await res.json()) as { token: string; expires: number };
  } finally {
    cleanup();
  }
}

export async function signFileUrl(
  jobId: string,
  filePath: string,
  token?: string,
): Promise<string> {
  const backendBaseUrl = getBackendBaseUrl();
  const apiBaseUrl = getApiBaseUrl();
  const normalizedPath = normalizeFilePath(jobId, filePath);

  if (token) {
    const sep = normalizedPath ? "/" : "";
    const clean = normalizedPath.startsWith("/")
      ? normalizedPath.slice(1)
      : normalizedPath;
    return `${backendBaseUrl}/files/${jobId}${sep}${clean}?t=${encodeURIComponent(
      token,
    )}`;
  }

  // [FIX] Expiración amplia y timeout para evitar cuelgues de UI en sesiones largas
  const expiresIn = 3600 * 6; // 6h

  const { signal, cleanup } = withTimeoutSignal(12000);
  try {
    const res = await fetch(`${apiBaseUrl}/files/sign`, {
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
      signal,
      cache: "no-store",
    });
    if (!res.ok) {
      throw new Error(`Failed to sign URL: ${res.status} ${res.statusText}`);
    }
    const data = (await res.json()) as { url: string };

    // [MODIFIED] Correct hostname in case backend returned internal container URL
    try {
      const signedUrlObj = new URL(data.url);
      const currentBase = new URL(backendBaseUrl);

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
    } catch {
      // If URL parsing fails, return original
      return data.url;
    }
  } finally {
    cleanup();
  }
}

export async function createShareLink(jobId: string): Promise<string> {
  const baseUrl = getApiBaseUrl();
  const { signal, cleanup } = withTimeoutSignal(15000);
  try {
    const res = await fetch(`${baseUrl}/jobs/${jobId}/share`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...authHeaders(),
      },
      signal,
      cache: "no-store",
    });

    if (!res.ok) {
      throw new Error("Failed to create share link");
    }

    const data = await res.json();
    return data.token;
  } finally {
    cleanup();
  }
}

export async function getSharedJob(token: string): Promise<any> {
  const baseUrl = getApiBaseUrl();
  const { signal, cleanup } = withTimeoutSignal(15000);
  try {
    // Public endpoint
    const res = await fetch(`${baseUrl}/share/${token}`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
      signal,
      cache: "no-store",
    });

    if (!res.ok) {
      throw new Error("Failed to fetch shared job");
    }

    return res.json();
  } finally {
    cleanup();
  }
}

/**
 * Mapea el JSON crudo que devuelve el backend (Celery) al JobStatus
 * que usa tu frontend (queued/running/done/error, camelCase, etc.).
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function mapBackendStatusToJobStatus(raw: any, baseUrl: string): JobStatus {
  const backendStatus = (raw.status ?? raw.job_status ?? "pending") as string;
  const jobId: string = raw.jobId ?? raw.job_id ?? raw.id ?? "";

  // [FIX] Normalizamos stage_key/progress/stage_index para evitar estados finales perdidos
  const rawStageKey: string =
    raw.stage_key ?? raw.stageKey ?? raw.stage ?? raw.current_stage ?? "";
  const rawProgress: number =
    typeof raw.progress === "number" ? raw.progress : Number(raw.progress ?? 0);
  const totalStagesFromRaw =
    typeof raw.total_stages === "number"
      ? raw.total_stages
      : typeof raw.totalStages === "number"
        ? raw.totalStages
        : undefined;

  const stageIndexFromRaw =
    typeof raw.stage_index === "number"
      ? raw.stage_index
      : typeof raw.stageIndex === "number"
        ? raw.stageIndex
        : undefined;

  const totalStages = totalStagesFromRaw ?? 18; // [FIX] 18 por defecto en tu pipeline, mejor que 7

  // [FIX] Detección de "final real" aunque el backendStatus venga incoherente
  const looksFinished =
    rawStageKey === "finished" ||
    rawStageKey === "done" ||
    rawStageKey === "success" ||
    rawProgress >= 100 ||
    (typeof stageIndexFromRaw === "number" && stageIndexFromRaw >= totalStages);

  let status: JobStatus["status"];
  switch (backendStatus) {
    case "pending":
    case "queued":
      status = "queued";
      break;
    case "running":
    case "processing_correction":
    case "waiting_for_correction":
      status = looksFinished ? "done" : "running"; // [FIX]
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
      // [FIX] si parece finished, no lo marques como error por un string raro
      if (looksFinished) {
        status = "done";
      } else {
        console.warn(
          `[mixApi] Unknown backend status: "${backendStatus}". Defaulting to error.`,
        );
        status = "error";
      }
      break;
  }

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
      typeof stageIndexFromRaw === "number" ? stageIndexFromRaw : base.stageIndex;
    base.totalStages =
      typeof totalStagesFromRaw === "number" ? totalStagesFromRaw : base.totalStages;
    base.stageKey = rawStageKey || "running";
    base.message = raw.message ?? "Processing mix...";
    base.progress = Number.isFinite(rawProgress) ? rawProgress : base.progress;
  } else if (status === "done") {
    base.stageIndex =
      typeof stageIndexFromRaw === "number" ? stageIndexFromRaw : base.totalStages;
    base.stageKey = "finished";
    base.message = raw.message ?? "Mix finished";
    base.progress = 100;
  } else if (status === "error") {
    base.stageKey = "error";
    const defaultMsg = ["failed", "failure", "error"].includes(backendStatus)
      ? "Error while processing mix"
      : `Unknown job status: "${backendStatus}"`;
    base.message = raw.message ?? raw.error ?? defaultMsg;

    if (!base.error && !raw.message && !raw.error) {
      base.error = defaultMsg;
    }
    base.progress = base.progress || 0;
  }

  // Si tenemos resultado final, mapearlo a MixResult
  // [FIX] soporta variaciones de claves (snake/camel y anidado)
  const rawFullSongUrl =
    raw.full_song_url ??
    raw.fullSongUrl ??
    raw.full_song ??
    raw.result?.full_song_url ??
    raw.result?.fullSongUrl;

  const rawOriginalUrl =
    raw.original_full_song_url ??
    raw.originalFullSongUrl ??
    raw.original_full_song ??
    raw.result?.original_full_song_url ??
    raw.result?.originalFullSongUrl;

  if (status === "done" && rawFullSongUrl) {
    const m = raw.metrics ?? raw.result?.metrics ?? {};
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
        normalizeUrl(rawOriginalUrl, baseUrl),
      ),
      fullSongUrl: appendApiKeyParam(normalizeUrl(rawFullSongUrl, baseUrl)),
      metrics,
    };

    base.result = result;
  }

  return base;
}

async function attachSignedResultUrls(
  jobId: string,
  status: JobStatus,
  baseUrl: string,
): Promise<JobStatus> {
  if (!status.result) return status;

  const nextResult: MixResult = { ...status.result };
  const next: JobStatus = { ...status, result: nextResult };

  const signMaybe = async (
    rawUrl: string | undefined,
    key: "fullSongUrl" | "originalFullSongUrl",
  ) => {
    if (!rawUrl) return;
    try {
      const urlObj = new URL(rawUrl, baseUrl);
      const prefix = `/files/${jobId}/`;
      const filePath = urlObj.pathname.startsWith(prefix)
        ? urlObj.pathname.slice(prefix.length)
        : urlObj.pathname.replace(/^\/files\//, "");
      const signed = await signFileUrl(jobId, filePath);
      if (signed) {
        nextResult[key] = signed;
      }
    } catch (e) {
      console.warn(`Failed to sign ${key}`, e);
    }
  };

  await Promise.all([
    signMaybe(nextResult.fullSongUrl, "fullSongUrl"),
    signMaybe(nextResult.originalFullSongUrl, "originalFullSongUrl"),
  ]);

  return next;
}

export async function cleanupTemp(): Promise<void> {
  const { signal, cleanup } = withTimeoutSignal(15000);
  try {
    const res = await fetch(`${getApiBaseUrl()}/cleanup-temp`, {
      method: "POST",
      headers: authHeaders(),
      signal,
      cache: "no-store",
    });

    if (!res.ok) {
      throw new Error("Failed to cleanup temp");
    }
  } finally {
    cleanup();
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

  const { signal, cleanup } = withTimeoutSignal(120000);
  try {
    const res = await fetch(
      `${baseUrl}/mix/${encodeURIComponent(jobId)}/upload-file`,
      {
        method: "POST",
        headers: authHeaders(),
        body: fd,
        signal,
      },
    );

    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(
        `Error uploading file "${file.name}": ${res.status} ${res.statusText} ${text}`,
      );
    }
  } finally {
    cleanup();
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
  const baseUrl = getApiBaseUrl();

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

    if (spaceDepthBusStyles && Object.keys(spaceDepthBusStyles).length > 0) {
      formData.append(
        "space_depth_bus_styles_json",
        JSON.stringify(spaceDepthBusStyles),
      );
    }

    formData.append("upload_mode", uploadMode);

    const { signal, cleanup } = withTimeoutSignal(120000);
    try {
      const res = await fetch(`${baseUrl}/mix`, {
        method: "POST",
        headers: authHeaders(),
        body: formData,
        signal,
      });

      if (!res.ok) {
        throw new Error(
          `Error starting mix job: ${res.status} ${res.statusText}`,
        );
      }

      const data = (await res.json()) as { jobId: string };
      return { jobId: data.jobId };
    } finally {
      cleanup();
    }
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

  const { signal: initSignal, cleanup: initCleanup } = withTimeoutSignal(60000);
  let jobId: string;
  try {
    const initRes = await fetch(`${baseUrl}/mix/init`, {
      method: "POST",
      headers: authHeaders(),
      body: initForm,
      signal: initSignal,
    });

    if (!initRes.ok) {
      const text = await initRes.text().catch(() => "");
      throw new Error(
        `Error initializing mix job: ${initRes.status} ${initRes.statusText} ${text}`,
      );
    }

    const initData = (await initRes.json()) as { jobId: string };
    jobId = initData.jobId;
  } finally {
    initCleanup();
  }

  // 2) Uploads en paralelo (SIN compresión)
  await uploadFilesInParallelForJob(baseUrl, jobId, files, 10);

  // 3) Start: encolar tarea Celery para ese job
  const { signal: startSignal, cleanup: startCleanup } =
    withTimeoutSignal(30000);
  try {
    const startRes = await fetch(
      `${baseUrl}/mix/${encodeURIComponent(jobId)}/start`,
      {
        method: "POST",
        headers: authHeaders(),
        signal: startSignal,
        cache: "no-store",
      },
    );

    if (!startRes.ok) {
      const text = await startRes.text().catch(() => "");
      throw new Error(
        `Error starting mix pipeline for job ${jobId}: ${startRes.status} ${startRes.statusText} ${text}`,
      );
    }
  } finally {
    startCleanup();
  }

  return { jobId };
}

// -----------------------------------------------------------------------------
// 2) Consultar estado del job (GET /jobs/{jobId})
// -----------------------------------------------------------------------------

export async function fetchJobStatus(
  jobId: string,
  options?: { timeoutMs?: number; skipSigning?: boolean },
): Promise<JobStatus> {
  const apiBaseUrl = getApiBaseUrl();
  const backendBaseUrl = getBackendBaseUrl();

  // [FIX] timeout por defecto para evitar fetch colgado (y UI colgada)
  const timeoutMs = options?.timeoutMs ?? 15000;
  const controller = new AbortController();
  const setTimeoutFn =
    typeof window === "undefined" ? setTimeout : window.setTimeout;
  const clearTimeoutFn =
    typeof window === "undefined" ? clearTimeout : window.clearTimeout;

  const timeoutId = setTimeoutFn(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(
      `${apiBaseUrl}/jobs/${encodeURIComponent(jobId)}?_t=${Date.now()}`,
      {
        method: "GET",
        // Avoid any browser/proxy cache between pipeline updates
        cache: "no-store",
        headers: {
          ...authHeaders(),
        },
        signal: controller.signal,
      },
    );

    if (!res.ok) {
      throw new Error(`Error fetching job status: ${res.status} ${res.statusText}`);
    }

    const raw = await res.json();
    const mapped = mapBackendStatusToJobStatus(raw, backendBaseUrl);

    if (options?.skipSigning) {
      return mapped;
    }

    const signed = await attachSignedResultUrls(jobId, mapped, backendBaseUrl);
    return signed;
  } catch (err: any) {
    if (err?.name === "AbortError") {
      throw new Error("Job status request timed out");
    }
    throw err;
  } finally {
    clearTimeoutFn(timeoutId);
  }
}

export type JobStatusStreamHandlers = {
  onStatus: (status: JobStatus) => void;
  onError?: (error: Error | Event) => void;
  onClose?: (event: CloseEvent) => void;
  onOpen?: () => void;
};

export type JobStatusStream = {
  close: () => void;
};

export function openJobStatusStream(
  jobId: string,
  handlers: JobStatusStreamHandlers,
): JobStatusStream | null {
  if (typeof window === "undefined" || typeof WebSocket === "undefined") {
    return null;
  }

  const baseUrl = getBackendBaseUrl();
  const wsBase = baseUrl.startsWith("https")
    ? baseUrl.replace(/^https/i, "wss")
    : baseUrl.replace(/^http/i, "ws");

  const params = new URLSearchParams();

  const token = localStorage.getItem("access_token");
  if (token) params.set("token", token);
  params.set("_t", Date.now().toString());

  const wsUrl = `${wsBase}/ws/jobs/${encodeURIComponent(jobId)}?${params.toString()}`;

  let socket: WebSocket;
  try {
    socket = new WebSocket(wsUrl);
  } catch (err) {
    handlers.onError?.(err as Error);
    return null;
  }

  // [FIX] Fallback polling para evitar quedarse colgado si el WS pierde el "finished"
  let closed = false;
  let lastActivityAt = Date.now();
  let pollTimer: number | null = null;
  let backoffMs = 2500;
  const minBackoff = 2500;
  const maxBackoff = 15000;

  const clearPoll = () => {
    if (pollTimer != null) {
      window.clearTimeout(pollTimer);
      pollTimer = null;
    }
  };

  const schedulePoll = (ms: number) => {
    if (closed) return;
    clearPoll();
    pollTimer = window.setTimeout(() => {
      void pollOnce();
    }, ms);
  };

  const finalizeAndClose = () => {
    if (closed) return;
    closed = true;
    clearPoll();
    try {
      socket.close();
    } catch {
      // noop
    }
  };

  const pollOnce = async () => {
    if (closed) return;

    const silenceMs = Date.now() - lastActivityAt;
    const socketOpen = socket.readyState === WebSocket.OPEN;

    // Si WS está activo y hay mensajes recientes, no hagas polling agresivo
    if (socketOpen && silenceMs < 7000) {
      schedulePoll(minBackoff);
      return;
    }

    try {
      const st = await fetchJobStatus(jobId, { timeoutMs: 12000 });
      handlers.onStatus(st);
      lastActivityAt = Date.now();
      backoffMs = minBackoff;

      if (st.status === "done" || st.status === "error") {
        // [FIX] cerramos para que el consumidor (UI) deje de esperar
        finalizeAndClose();
        return;
      }

      schedulePoll(minBackoff);
    } catch (e) {
      // Reporta error pero sigue reintentando con backoff para no colgar UI
      handlers.onError?.(e as Error);
      backoffMs = Math.min(Math.round(backoffMs * 1.6), maxBackoff);
      schedulePoll(backoffMs);
    }
  };

  socket.onopen = () => {
    lastActivityAt = Date.now();
    handlers.onOpen?.();
    schedulePoll(minBackoff); // arranca fallback
  };

  socket.onmessage = (event: MessageEvent) => {
    void (async () => {
      try {
        const rawText =
          typeof event.data === "string"
            ? event.data
            : typeof (event.data as Blob).text === "function"
              ? await (event.data as Blob).text()
              : "";

        if (!rawText) return;
        const parsed = JSON.parse(rawText);
        const payload = parsed?.payload ?? parsed;

        lastActivityAt = Date.now();

        const mapped = mapBackendStatusToJobStatus(payload, baseUrl);
        const signed = await attachSignedResultUrls(jobId, mapped, baseUrl);
        handlers.onStatus(signed);

        // [FIX] Si llega el done/error por WS, cerramos y paramos polling
        if (signed.status === "done" || signed.status === "error") {
          finalizeAndClose();
        }
      } catch (err) {
        console.warn("Failed to parse job status WS message", err);
      }
    })();
  };

  socket.onerror = (event) => {
    handlers.onError?.(event);
    // no cerramos; dejamos que el polling fallback lo rescate
  };

  socket.onclose = (event) => {
    handlers.onClose?.(event);
    // si no está cerrado explícitamente, seguimos con polling (recovery)
    if (!closed) {
      schedulePoll(minBackoff);
    }
  };

  return {
    close: () => {
      finalizeAndClose();
    },
  };
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
  const baseUrl = getApiBaseUrl();
  const { signal, cleanup } = withTimeoutSignal(15000);
  try {
    const res = await fetch(`${baseUrl}/pipeline/stages`, {
      method: "GET",
      signal,
      cache: "no-store",
    });

    if (!res.ok) {
      throw new Error(
        `Error fetching pipeline stages: ${res.status} ${res.statusText}`,
      );
    }

    const data = (await res.json()) as PipelineStage[];
    return data.sort((a, b) => a.index - b.index);
  } finally {
    cleanup();
  }
}

export async function fetchInstrumentProfiles(): Promise<InstrumentProfileDef[]> {
  const base = getApiBaseUrl();
  const { signal, cleanup } = withTimeoutSignal(15000);
  try {
    const res = await fetch(`${base}/profiles/instruments`, {
      signal,
      cache: "no-store",
    });
    if (!res.ok) throw new Error("Error fetching instrument profiles");
    return (await res.json()) as InstrumentProfileDef[];
  } finally {
    cleanup();
  }
}

export async function fetchStyleProfiles(): Promise<StyleProfileDef[]> {
  const base = getApiBaseUrl();
  const { signal, cleanup } = withTimeoutSignal(15000);
  try {
    const res = await fetch(`${base}/profiles/styles`, {
      signal,
      cache: "no-store",
    });
    if (!res.ok) throw new Error("Error fetching style profiles");
    return (await res.json()) as StyleProfileDef[];
  } finally {
    cleanup();
  }
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function fetchJobReport(jobId: string): Promise<any> {
  // [FIX] No permitir “loading infinito” por firmado/report colgado:
  // - timeout
  // - fallback a URL directa si falla el sign
  // - cache no-store
  const backendBase = getBackendBaseUrl();

  let url: string | null = null;
  try {
    const signedUrl = await signFileUrl(jobId, "S11_REPORT_GENERATION/report.json");
    const separator = signedUrl.includes("?") ? "&" : "?";
    url = `${signedUrl}${separator}_t=${Date.now()}`;
  } catch (e) {
    // Fallback a URL directa (puede fallar con 401, pero no debe colgar)
    url = `${backendBase}/files/${encodeURIComponent(jobId)}/S11_REPORT_GENERATION/report.json?_t=${Date.now()}`;
  }

  const { signal, cleanup } = withTimeoutSignal(15000);
  try {
    const res = await fetch(url, { cache: "no-store", signal });

    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(`Failed to fetch report: ${res.status} ${res.statusText} ${text}`);
    }

    // Validación mínima para evitar que un HTML 200 se intente parsear “eternamente”
    const contentType = res.headers.get("content-type") || "";
    if (!contentType.toLowerCase().includes("application/json")) {
      const snippet = await res.text().catch(() => "");
      throw new Error(`Report is not JSON (content-type=${contentType}). Snippet: ${snippet.slice(0, 200)}`);
    }

    return await res.json();
  } finally {
    cleanup();
  }
}
