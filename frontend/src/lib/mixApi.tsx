// frontend/src/lib/mixApi.ts
export type MixResponse = {
  jobId: string;
  fullSongUrl: string;
  metrics: {
    tempo_bpm: number;
    key: string;
    scale: string;
    // añade aquí el resto de campos que devuelve tu backend
  };
};

export async function sendMixRequest(files: File[]): Promise<MixResponse> {
  const formData = new FormData();
  files.forEach((f) => formData.append("files", f));

  const baseUrl = process.env.NEXT_PUBLIC_BACKEND_URL;
  if (!baseUrl) {
    throw new Error("NEXT_PUBLIC_BACKEND_URL no está definido");
  }

  const res = await fetch(`${baseUrl}/mix`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    throw new Error(`Error en mezcla: ${res.status} ${res.statusText}`);
  }

  return (await res.json()) as MixResponse;
}
