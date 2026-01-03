"use client";

import { useTranslations } from "next-intl";

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
    label: "Auto (based on material)",
    description:
      "Conservative automatic mode. Uses short rooms/plates, moderate sends and aggressive low-cut to avoid muddy mixes. Safe default if no style is chosen.",
    buses: {},
  },
};

export function SpaceDepthStylePanel({ buses, value, onChange }: Props) {
  const t = useTranslations('MixTool');

  // Move STYLE_OPTIONS inside component to use translations
  const STYLE_OPTIONS: { value: string; label: string }[] = [
    { value: "Flamenco_Rumba", label: t('styleOptions.Flamenco_Rumba') },
    { value: "EDM_Club", label: t('styleOptions.EDM_Club') },
    {
      value: "Acoustic_SingerSongwriter",
      label: t('styleOptions.Acoustic_SingerSongwriter'),
    },
  ];

  if (!buses.length) return null;

  return (
    <aside className="rounded-2xl border border-teal-500/40 bg-teal-500/10 p-4 text-xs shadow-lg shadow-teal-500/20 text-teal-50">
      <div className="space-y-2">
        {buses.map((bus) => (
          <div
            key={bus.key}
            className="flex items-center justify-between gap-2 rounded-lg border border-teal-500/30 bg-teal-500/5 px-2.5 py-2"
          >
            <div className="min-w-0">
              <p className="text-[11px] font-medium text-teal-50">
                {bus.label}
              </p>
            </div>
            <div className="flex items-center gap-1">
              <select
                className="max-w-[10rem] rounded-md border border-teal-500/60 bg-slate-950/80 px-2 py-1 text-[11px] text-teal-50 outline-none focus:border-teal-400 focus:ring-1 focus:ring-teal-400"
                value={value[bus.key] ?? "auto"}
                onChange={(e) => onChange(bus.key, e.target.value)}
              >
                <option value="auto">{t('auto')}</option>
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
    </aside>
  );
}
