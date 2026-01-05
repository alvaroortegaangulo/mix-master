"use client";

import { useState } from "react";
import { WaveformPlayer } from "../WaveformPlayer";

type ExampleItem = {
  id: string;
  title: string;
  genre: string;
  summary: string;
  highlights: string[];
  metrics: string[];
  originalSrc: string;
  masterSrc: string;
};

type ToggleLabels = {
  original: string;
  master: string;
};

type Props = {
  examples: ExampleItem[];
  toggleLabels: ToggleLabels;
  notableChangesLabel: string;
};

type ExampleCardProps = {
  example: ExampleItem;
  toggleLabels: ToggleLabels;
  notableChangesLabel: string;
};

function ExampleCard({ example, toggleLabels, notableChangesLabel }: ExampleCardProps) {
  const [showOriginal, setShowOriginal] = useState(false);

  return (
    <article className="rounded-2xl border border-slate-800/70 bg-slate-900/40 p-6 shadow-lg shadow-slate-900/60">
      <div className="flex items-start mb-3">
        <div>
          <p className="text-xs uppercase tracking-wide text-teal-300/80">{example.genre}</p>
          <h2 className="text-xl font-semibold text-slate-100">{example.title}</h2>
        </div>
      </div>

      <p className="text-sm text-slate-400 mb-4">{example.summary}</p>

      <div className="rounded-2xl border border-slate-800/70 bg-slate-950/60 p-4 mb-4">
        <div className="flex flex-col items-center gap-3">
          <div className="inline-flex bg-slate-900 p-1 rounded-full border border-slate-800">
            <button
              type="button"
              onClick={() => setShowOriginal(true)}
              className={`px-5 py-1.5 rounded-full text-xs font-bold transition-all ${showOriginal ? "bg-slate-800 text-white shadow-sm" : "text-slate-500 hover:text-slate-300"}`}
            >
              {toggleLabels.original}
            </button>
            <button
              type="button"
              onClick={() => setShowOriginal(false)}
              className={`px-5 py-1.5 rounded-full text-xs font-bold transition-all ${!showOriginal ? "bg-amber-500 text-slate-950 shadow-lg shadow-amber-500/20" : "text-slate-500 hover:text-slate-300"}`}
            >
              {toggleLabels.master}
            </button>
          </div>

          <WaveformPlayer
            src={example.masterSrc}
            compareSrc={example.originalSrc}
            isCompareActive={showOriginal}
            accentColor={showOriginal ? "#64748b" : "#f59e0b"}
            className="bg-transparent shadow-none border-none p-0 !gap-2 w-full"
            canvasClassName="h-14"
            hideDownload={true}
          />
        </div>
      </div>

      <div className="flex flex-wrap gap-2 mb-4">
        {example.highlights.map((item) => (
          <span key={item} className="rounded-full border border-slate-800 bg-slate-900/70 px-3 py-1 text-xs text-slate-200">
            {item}
          </span>
        ))}
      </div>

      <div className="rounded-xl border border-slate-800/70 bg-slate-950/50 p-4">
        <p className="text-xs uppercase tracking-[0.12em] text-slate-400 mb-2">{notableChangesLabel}</p>
        <ul className="space-y-2 text-sm text-slate-300 list-disc list-inside">
          {example.metrics.map((metric) => (
            <li key={metric}>{metric}</li>
          ))}
        </ul>
      </div>
    </article>
  );
}

export function ExamplesGrid({ examples, toggleLabels, notableChangesLabel }: Props) {
  return (
    <div className="grid gap-6 sm:grid-cols-2">
      {examples.map((example) => (
        <ExampleCard
          key={example.id}
          example={example}
          toggleLabels={toggleLabels}
          notableChangesLabel={notableChangesLabel}
        />
      ))}
    </div>
  );
}
