// frontend/src/components/SpaceDepthStylePanel.tsx
"use client";

export type SpaceBus = {
  key: string;
  label: string;
  description?: string;
};

type Props = {
  /** Lista de buses que queremos mostrar (drums, bass, guitars, etc.) */
  buses: SpaceBus[];
  /**
   * Mapa busKey -> estilo seleccionado.
   * Si no hay entrada para un bus, se considera "auto".
   */
  value: Record<string, string>;
  /** Callback cuando cambia el estilo de un bus */
  onChange: (busKey: string, style: string) => void;
};

const STYLE_OPTIONS: { value: string; label: string }[] = [
  { value: "auto", label: "Auto (según material)" },
  { value: "flamenco_rumba", label: "Flamenco / Rumba" },
  { value: "urban_trap", label: "Urbano / Trap / Hip-hop" },
  { value: "rock", label: "Rock / Pop-rock" },
  { value: "latin_pop", label: "Latin pop / Reggaeton" },
  { value: "edm", label: "EDM / Club" },
  { value: "ballad_ambient", label: "Balada / Ambient" },
  { value: "acoustic", label: "Acústico / Singer-songwriter" },
];

export function SpaceDepthStylePanel({ buses, value, onChange }: Props) {
  if (!buses.length) return null;

  return (
    <aside className="rounded-2xl border border-slate-800/80 bg-slate-900/80 p-4 text-xs shadow-lg">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-300">
        Space / Depth by bus
      </h3>
      <p className="mt-1 text-[11px] text-slate-400">
        Elige el carácter de reverb, delay y modulación para cada bus
        (rooms, plates, halls, springs, etc.). Estas elecciones se usan
        en la etapa de espacio / profundidad del pipeline.
      </p>

      <div className="mt-3 space-y-2">
        {buses.map((bus) => (
          <div
            key={bus.key}
            className="flex items-center justify-between gap-2 rounded-lg bg-slate-950/60 px-2.5 py-2"
          >
            <div className="min-w-0">
              <p className="truncate text-[11px] font-medium text-slate-100">
                {bus.label}
              </p>
              {bus.description && (
                <p className="mt-0.5 text-[10px] text-slate-400">
                  {bus.description}
                </p>
              )}
            </div>
            <select
              className="max-w-[10rem] rounded-md border border-slate-700 bg-slate-900 px-2 py-1 text-[11px] text-slate-100 outline-none focus:border-teal-400 focus:ring-1 focus:ring-teal-400"
              value={value[bus.key] ?? "auto"}
              onChange={(e) => onChange(bus.key, e.target.value)}
            >
              {STYLE_OPTIONS.map((opt) => (
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
