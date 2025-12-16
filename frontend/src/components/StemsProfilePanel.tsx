// frontend/src/components/StemsProfilePanel.tsx
"use client";

import { useTranslations } from "next-intl";

type StemProfile = {
  id: string;
  fileName: string;
  extension: string;
  profile: string;
};

type Props = {
  stems: StemProfile[];
  onChangeProfile: (id: string, profile: string) => void;
};

export function StemsProfilePanel({ stems, onChangeProfile }: Props) {
  const t = useTranslations('MixTool');

  // We need to fetch options inside the component to use translations
  const STEM_PROFILE_OPTIONS: { value: string; label: string }[] = [
    { value: "auto", label: t('autoRecommended') },

    { value: "Kick", label: t('profileOptions.Kick') },
    { value: "Snare", label: t('profileOptions.Snare') },
    { value: "Percussion", label: t('profileOptions.Percussion') },

    { value: "Bass_Electric", label: t('profileOptions.Bass_Electric') },

    { value: "Acoustic_Guitar", label: t('profileOptions.Acoustic_Guitar') },
    { value: "Electric_Guitar_Rhythm", label: t('profileOptions.Electric_Guitar_Rhythm') },

    { value: "Keys_Piano", label: t('profileOptions.Keys_Piano') },
    { value: "Synth_Pads", label: t('profileOptions.Synth_Pads') },

    { value: "Lead_Vocal_Melodic", label: t('profileOptions.Lead_Vocal_Melodic') },
    { value: "Lead_Vocal_Rap", label: t('profileOptions.Lead_Vocal_Rap') },
    { value: "Backing_Vocals", label: t('profileOptions.Backing_Vocals') },

    { value: "FX_EarCandy", label: t('profileOptions.FX_EarCandy') },
    { value: "Ambience_Atmos", label: t('profileOptions.Ambience_Atmos') },

    { value: "Other", label: t('profileOptions.Other') },
  ];

  if (!stems.length) return null;

  return (
    <aside className="rounded-2xl border border-amber-500/40 bg-amber-500/10 p-4 text-xs shadow-lg shadow-amber-500/20 text-amber-50">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-amber-100">
        {t('stemsProfile')}
      </h3>
      <p className="mt-1 text-[11px] text-amber-200">
        {t('stemsProfileDesc')}
      </p>

      {/* SIN scroll interno: el alto se adapta a la lista */}
      <div className="mt-3 space-y-2">
        {stems.map((stem) => (
          <div
            key={stem.id}
            className="flex items-center justify-between gap-2 rounded-lg border border-amber-500/30 bg-amber-500/5 px-2.5 py-2"
          >
            <div className="min-w-0">
              <p className="truncate text-[11px] font-medium text-amber-50">
                {stem.fileName}
                {stem.extension && (
                  <span className="text-amber-200/80">.{stem.extension}</span>
                )}
              </p>
            </div>
            <select
              className="max-w-[9.5rem] rounded-md border border-amber-500/60 bg-slate-950/80 px-2 py-1 text-[11px] text-amber-50 outline-none focus:border-amber-400 focus:ring-1 focus:ring-amber-400"
              value={stem.profile}
              onChange={(e) => onChangeProfile(stem.id, e.target.value)}
            >
              {STEM_PROFILE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
        ))}
      </div>
    </aside>
  );
}
