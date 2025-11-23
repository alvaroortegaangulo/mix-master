// frontend/src/lib/mixApi.ts

export type MixResponse = {
  jobId: string;
  fullSongUrl: string; // en la respuesta final SIEMPRE será absoluta
  metrics: {
    tempo_bpm: number;
    key: string;
    scale: string;
    // añade aquí el resto de campos que devuelve tu backend
  };
};

/**
 * Resuelve la URL base del backend, preparada para:
 * - Render: NEXT_PUBLIC_BACKEND_URL (p.ej. https://backend-de7a.onrender.com)
 * - Local:  fallback a http://127.0.0.1:8000 si la env no está definida
 */
function getBackendBaseUrl(): string {
  const fromEnv = process.env.NEXT_PUBLIC_BACKEND_URL?.trim();

  if (fromEnv && fromEnv.length > 0) {
    // quitamos barra final para evitar dobles barras
    return fromEnv.replace(/\/+$/, "");
  }

  // Fallback razonable para desarrollo local
  return "http://127.0.0.1:8000";
}

export async function sendMixRequest(files: File[]): Promise<MixResponse> {
  const formData = new FormData();
  files.forEach((f) => formData.append("files", f));

  const baseUrl = getBackendBaseUrl();

  const res = await fetch(`${baseUrl}/mix`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    throw new Error(`Error en mezcla: ${res.status} ${res.statusText}`);
  }

  // Respuesta tal y como la envía el backend (fullSongUrl puede ser relativa o absoluta)
  const data = (await res.json()) as MixResponse;

  // Si el backend devuelve /files/..., pegamos la base del backend
  const fullSongUrl = data.fullSongUrl.startsWith("http")
    ? data.fullSongUrl
    : `${baseUrl}${data.fullSongUrl}`;

  return {
    ...data,
    fullSongUrl,
  };
}
