// services/mixApi.ts
export async function sendMixRequest(files: File[]) {
  const formData = new FormData();
  files.forEach(f => formData.append("files", f));

  const res = await fetch("http://tu-backend/mix", {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    throw new Error("Error en mezcla");
  }

  const data: {
    jobId: string;
    fullSongUrl: string;
    metrics: {
      tempo_bpm: number;
      key: string;
      scale: string;
      // etc.
    };
  } = await res.json();

  return data;
}
