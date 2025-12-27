
import { useTranslations } from "next-intl";

export function TechSpecsSection({ className }: { className?: string }) {
    const t = useTranslations('TechSpecsSection');
    const specs = [
      { value: "96k", label: t("internalProcessing") },
      { value: "32-bit", label: t("floatDepth") },
      { value: "12+", label: t("processingStages") },
      { value: "0s", label: t("latency") },
      { value: "-14 LUFS", label: "OBJETIVO STREAMING" },
      { value: "-1.0 dBTP", label: "TRUE PEAK SEGURO" },
      { value: "WIDE", label: "IMAGEN ESTEREO" },
      { value: "12-16 dB", label: "RANGO DINAMICO" },
      { value: "AI-MATCH", label: "BALANCE TONAL" },
      { value: "+3.2 dB", label: "PUNCH TRANSIENTE" },
      { value: "OK", label: "PHASE CHECK" },
      { value: "-90 dB", label: "NOISE FLOOR" },
      { value: "DEPTH", label: "PROFUNDIDAD 3D" },
      { value: "SOFT", label: "SATURACION MUSICAL" },
    ];
    const marqueeSpecs = [...specs, ...specs];

    return (
      <section className={`py-8 md:py-10 lg:py-12 overflow-hidden ${className || 'bg-slate-900'}`}>
        <div className="max-w-6xl mx-auto px-4 text-center">
          <h2 className="text-2xl sm:text-3xl font-bold text-white mb-6">{t('title')}</h2>

          <div className="relative max-w-5xl mx-auto">
            <div className="pointer-events-none absolute inset-y-0 left-0 w-16 bg-gradient-to-r from-slate-950 to-transparent" />
            <div className="pointer-events-none absolute inset-y-0 right-0 w-16 bg-gradient-to-l from-slate-950 to-transparent" />
            <div className="overflow-hidden">
              <div className="tech-specs-track flex w-max gap-3 py-2">
                {marqueeSpecs.map((spec, index) => (
                  <div
                    key={`${spec.label}-${index}`}
                    aria-hidden={index >= specs.length ? "true" : undefined}
                    className="flex items-center gap-3 rounded-full border border-slate-800/80 bg-slate-900/60 px-4 py-2 shadow-sm"
                  >
                    <span className="text-sm sm:text-base font-semibold text-teal-300 tabular-nums">
                      {spec.value}
                    </span>
                    <span className="text-[10px] sm:text-xs font-medium uppercase tracking-widest text-slate-300">
                      {spec.label}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
        <style jsx>{`
          @keyframes techSpecsMarquee {
            0% {
              transform: translateX(0);
            }
            100% {
              transform: translateX(-50%);
            }
          }
          .tech-specs-track {
            animation: techSpecsMarquee 28s linear infinite;
            animation-direction: reverse;
            will-change: transform;
          }
          @media (prefers-reduced-motion: reduce) {
            .tech-specs-track {
              animation: none;
              transform: translateX(0);
            }
          }
        `}</style>
      </section>
    );
  }
