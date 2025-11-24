// frontend/src/components/MixResultPanel.tsx
import type { MixResult } from "../lib/mixApi";

type Props = {
  result: MixResult;
};

export function MixResultPanel({ result }: Props) {
  const { originalFullSongUrl, fullSongUrl, metrics } = result;

  return (
    <section className="mt-10 rounded-2xl border border-slate-800/80 bg-slate-900/80 p-6 shadow-xl">
      <h2 className="text-xl font-semibold text-slate-50 mb-4">
        Your AI Mix
      </h2>

      {/* Original vs Procesado */}
      <div className="space-y-6">
        {/* Original */}
        {originalFullSongUrl && (
          <div>
            <h3 className="mb-2 text-xs font-semibold tracking-[0.2em] text-slate-400 uppercase">
              Original
            </h3>
            <div className="rounded-full bg-slate-800/80 px-4 py-3">
              <audio
                src={originalFullSongUrl}
                controls
                className="w-full"
              />
            </div>
          </div>
        )}

        {/* Mix procesado */}
        <div>
          <h3 className="mb-2 text-xs font-semibold tracking-[0.2em] text-slate-400 uppercase">
            AI Mix (Processed)
          </h3>
          <div className="rounded-full bg-slate-800/80 px-4 py-3">
            <audio src={fullSongUrl} controls className="w-full" />
          </div>
        </div>
      </div>

      {/* Métricas */}
      <div className="mt-8">
        <h3 className="text-xs font-semibold tracking-[0.2em] text-slate-400 uppercase">
          Mix Metrics
        </h3>
        <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
          <div>
            <p className="text-slate-400">Tempo</p>
            <p className="font-medium text-slate-50">
              {metrics.tempo_bpm.toFixed(1)} BPM
            </p>
          </div>
          <div>
            <p className="text-slate-400">Key</p>
            <p className="font-medium text-slate-50">
              {metrics.key} {metrics.scale}
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
