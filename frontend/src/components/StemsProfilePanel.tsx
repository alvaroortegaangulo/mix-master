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
  { value: "auto", label: "Auto" },
  { value: "drums", label: "Drums" },
  { value: "percussion", label: "Percussion" },
  { value: "bass", label: "Bass" },
  { value: "acoustic_guitar", label: "Acoustic guitar" },
  { value: "electric_guitar", label: "Electric guitar" },
  { value: "keys", label: "Keys / Piano" },
  { value: "synth", label: "Synth / Pads" },
  { value: "lead_vocal", label: "Lead vocal" },
  { value: "backing_vocals", label: "Backing vocals" },
  { value: "fx", label: "FX / Ear candy" },
  { value: "ambience", label: "Ambience / Atmos" },
  { value: "other", label: "Other" },
];

export function StemsProfilePanel({ stems, onChangeProfile }: Props) {
  if (!stems.length) return null;

  return (
    <aside className="rounded-2xl border border-slate-800/80 bg-slate-900/80 p-4 text-xs shadow-lg">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-300">
        Select stems profile
      </h3>
      <p className="mt-1 text-[11px] text-slate-400">
        Etiqueta cada stem con su función en la mezcla. Más adelante usaremos
        estos perfiles para enrutar buses (drums, bass, guitars, vocals, FX,
        etc.).
      </p>

      {/* SIN scroll interno: el alto se adapta a la lista */}
      <div className="mt-3 space-y-2">
        {stems.map((stem) => (
          <div
            key={stem.id}
            className="flex items-center justify-between gap-2 rounded-lg bg-slate-950/60 px-2.5 py-2"
          >
            <div className="min-w-0">
              <p className="truncate text-[11px] font-medium text-slate-100">
                {stem.fileName}
                {stem.extension && (
                  <span className="text-slate-500">.{stem.extension}</span>
                )}
              </p>
            </div>
            <select
              className="max-w-[9.5rem] rounded-md border border-slate-700 bg-slate-900 px-2 py-1 text-[11px] text-slate-100 outline-none focus:border-indigo-400 focus:ring-1 focus:ring-indigo-400"
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
