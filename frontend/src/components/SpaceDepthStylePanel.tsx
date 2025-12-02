"use client";

import { useState } from "react";

export type SpaceBus = {
  key: string;
  label: string;
  description?: string;
};

type Props = {
  buses: SpaceBus[];
  value: Record<string, string>;
  onChange: (busKey: string, style: string) => void;
};

const STYLE_OPTIONS: { value: string; label: string }[] = [
  { value: "Flamenco_Rumba", label: "Flamenco / Rumba" },
  { value: "EDM_Club", label: "EDM / Club" },
  {
    value: "Acoustic_SingerSongwriter",
    label: "Acoustic / Singer-songwriter",
  },
];

type StyleBusDoc = {
  title: string;
  summary: string;
  params: string;
};

type StyleDoc = {
  label: string;
  description: string;
  buses: Record<string, StyleBusDoc>;
};

const STYLE_DOCS: Record<string, StyleDoc> = {
  auto: {
    label: "Auto (según material)",
    description:
      "Modo automático conservador. Usa rooms y plates cortos, envíos moderados y filtros agresivos en graves para evitar que la mezcla se emborrone. Es un punto de partida seguro si no se elige un estilo específico.",
    buses: {},
  },
};

export function SpaceDepthStylePanel({ buses, value, onChange }: Props) {
  const [showDocs, setShowDocs] = useState(false);

  if (!buses.length) return null;

  return (
    <aside className="rounded-2xl border border-amber-500/50 bg-amber-500/10 p-4 text-xs shadow-lg text-amber-50">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold uppercase tracking-wide text-amber-100">
            Space / Depth by bus
          </h3>
          <p className="mt-1 text-[11px] text-amber-200">
            Asigna un estilo de reverb/espacio a cada bus familiar para guiar las
            etapas posteriores.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowDocs((v) => !v)}
          className="ml-2 inline-flex h-7 w-7 items-center justify-center rounded-full border border-amber-500/60 text-[11px] text-amber-100 hover:border-amber-300 hover:text-amber-50"
        >
          ?
        </button>
      </div>

      <div className="mt-3 space-y-2">
        {buses.map((bus) => (
          <div
            key={bus.key}
            className="flex items-center justify-between gap-2 rounded-lg border border-amber-500/30 bg-amber-500/5 px-2.5 py-2"
          >
            <div className="min-w-0">
              <p className="text-[11px] font-medium text-amber-50">
                {bus.label}
              </p>
              {bus.description && (
                <p className="mt-0.5 text-[10px] text-amber-200/80">
                  {bus.description}
                </p>
              )}
            </div>
            <div className="flex items-center gap-1">
              <select
                className="max-w-[10rem] rounded-md border border-amber-500/60 bg-slate-950/80 px-2 py-1 text-[11px] text-amber-50 outline-none focus:border-amber-400 focus:ring-1 focus:ring-amber-400"
                value={value[bus.key] ?? "auto"}
                onChange={(e) => onChange(bus.key, e.target.value)}
              >
                <option value="auto">Auto</option>
                {STYLE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        ))}
      </div>

      {showDocs && (
        <div className="mt-3 rounded-xl border border-amber-500/40 bg-amber-500/10 p-3 text-[11px] text-amber-100">
          <p className="font-semibold uppercase tracking-wide text-amber-200">
            Referencias rápidas
          </p>
          <p className="mt-1 text-amber-50/90">
            En modo Auto se aplican rooms/plates cortos con envíos moderados y
            filtros agresivos en graves para evitar enmascaramiento. Selecciona
            un estilo para forzar un espacio concreto por bus.
          </p>
        </div>
      )}
    </aside>
  );
}
