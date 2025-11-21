// frontend/src/components/MixResultPanel.tsx
import type { MixResponse } from "../lib/mixApi";

type Props = {
  result: MixResponse;
};

export function MixResultPanel({ result }: Props) {
  const { fullSongUrl, metrics } = result;

  return (
    <section className="mt-8 rounded-2xl border border-slate-800/80 bg-slate-900/70 p-6 shadow-lg">
      <h2 className="text-xl font-semibold text-slate-50 mb-4">
        Your AI Mix
      </h2>

      <div className="mb-4 rounded-xl border border-slate-800 bg-slate-950/60 p-4">
        <audio controls className="w-full">
          <source src={fullSongUrl} />
          Your browser does not support the audio element.
        </audio>
      </div>

      <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-400 mb-2">
        Mix Metrics
      </h3>

      <div className="grid grid-cols-2 gap-4 text-sm text-slate-200">
        <div>
          <div className="text-slate-400 text-xs">Tempo</div>
          <div className="font-medium">{metrics.tempo_bpm?.toFixed?.(1)} BPM</div>
        </div>
        <div>
          <div className="text-slate-400 text-xs">Key</div>
          <div className="font-medium">
            {metrics.key} {metrics.scale}
          </div>
        </div>
        {/* Aquí añades el resto de métricas interesantes */}
      </div>
    </section>
  );
}
