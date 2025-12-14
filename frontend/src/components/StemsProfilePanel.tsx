// frontend/src/components/StemsProfilePanel.tsx
"use client";

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

const STEM_PROFILE_OPTIONS: { value: string; label: string }[] = [
  { value: "auto", label: "Auto-detect (recommended)" },

  { value: "Kick", label: "Kick (main kick drum)" },
  { value: "Snare", label: "Snare (main snare)" },
  { value: "Percussion", label: "Percussion (palmas, bongos, shakers…)" },

  { value: "Bass_Electric", label: "Electric / synth bass" },

  { value: "Acoustic_Guitar", label: "Acoustic guitar (rhythm)" },
  { value: "Electric_Guitar_Rhythm", label: "Electric guitar (rhythm)" },

  { value: "Keys_Piano", label: "Piano / keys" },
  { value: "Synth_Pads", label: "Synth pads / textures" },

  { value: "Lead_Vocal_Melodic", label: "Lead vocal (melodic)" },
  { value: "Lead_Vocal_Rap", label: "Lead vocal (rap / spoken)" },
  { value: "Backing_Vocals", label: "Backing vocals / doubles" },

  { value: "FX_EarCandy", label: "FX / ear candy" },
  { value: "Ambience_Atmos", label: "Ambience / atmos" },

  { value: "Other", label: "Other / unclassified" },
];

export function StemsProfilePanel({ stems, onChangeProfile }: Props) {
  if (!stems.length) return null;

  return (
    <aside className="rounded-2xl border border-amber-500/40 bg-amber-500/10 p-4 text-xs shadow-lg shadow-amber-500/20 text-amber-50">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-amber-100">
        Select stems profile
      </h3>
      <p className="mt-1 text-[11px] text-amber-200">
        Label each stem with its function in the mix. 
        Later we will use these profiles to route buses 
        (drums, bass, guitars, vocals, FX, etc.).
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
