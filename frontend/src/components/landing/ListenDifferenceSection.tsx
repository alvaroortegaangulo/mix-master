"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Link } from "../../i18n/routing";
import { WaveformPlayer } from "../WaveformPlayer";
import { ScrollReveal } from "./ScrollReveal";

export function ListenDifferenceSection({ className }: { className?: string }) {
  const t = useTranslations("ListenDifferenceSection");
  const examples = useTranslations("Examples");
  const [showOriginal, setShowOriginal] = useState(false);
  const titleText = t("title");
  const titlePlain = titleText.replace(/<[^>]+>/g, "");

  return (
    <section
      className={`relative overflow-hidden px-4 py-12 md:py-16 lg:py-20 ${className || "bg-slate-950"}`}
    >
      <div className="absolute inset-0 pointer-events-none z-0">
        <div className="absolute inset-0 bg-[#050508]" />
        <div className="absolute inset-0 grid-landing-diagonal" />
        <div className="absolute inset-0 grid-landing-vignette" />
        <div className="absolute -top-[30%] left-1/2 h-[50%] w-[50%] -translate-x-1/2 rounded-full bg-amber-500/15 blur-[140px]" />
        <div className="absolute top-[30%] -right-[10%] h-[45%] w-[45%] rounded-full bg-orange-400/12 blur-[160px]" />
        <div className="absolute bottom-[5%] -left-[10%] h-[40%] w-[40%] rounded-full bg-teal-500/10 blur-[160px]" />
      </div>

      <div className="relative z-10 mx-auto max-w-6xl">
        <ScrollReveal className="mx-auto max-w-3xl text-center" delay={0.05}>
          <h2
            className="text-3xl sm:text-4xl md:text-5xl font-black font-['Orbitron'] tracking-tight text-white mb-4 metallic-sheen"
            data-text={titlePlain}
          >
            {t.rich("title", {
              amber: (chunks) => <span className="text-amber-400">{chunks}</span>,
            })}
          </h2>
          <p className="text-sm sm:text-base md:text-lg text-slate-300 leading-relaxed">
            {t("subtitle")}
          </p>
        </ScrollReveal>

        <ScrollReveal
          className="mt-8 md:mt-10"
          delay={0.1}
        >
          <div className="relative rounded-[28px] border border-amber-500/20 bg-slate-900/40 p-5 sm:p-6 md:p-8 shadow-[0_30px_80px_rgba(0,0,0,0.55)] backdrop-blur">
            <div className="absolute inset-0 rounded-[28px] ring-1 ring-amber-500/10 pointer-events-none" />
            <div className="relative flex flex-col gap-4">
              <div className="flex flex-col items-center gap-3 sm:flex-row sm:justify-between">
                <span className="inline-flex items-center rounded-full border border-amber-500/30 bg-amber-500/10 px-3 py-1 text-[11px] font-semibold text-amber-200">
                  {examples("items.rock.title")}
                </span>
                <div className="inline-flex bg-slate-950/80 p-1 rounded-full border border-slate-800/80">
                  <button
                    type="button"
                    onClick={() => setShowOriginal(true)}
                    aria-pressed={showOriginal}
                    className={`px-5 py-1.5 rounded-full text-xs font-bold transition-all ${
                      showOriginal
                        ? "bg-slate-800 text-white shadow-sm"
                        : "text-slate-500 hover:text-slate-300"
                    }`}
                  >
                    {examples("toggleOriginal")}
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowOriginal(false)}
                    aria-pressed={!showOriginal}
                    className={`px-5 py-1.5 rounded-full text-xs font-bold transition-all ${
                      !showOriginal
                        ? "bg-amber-500 text-slate-950 shadow-lg shadow-amber-500/20"
                        : "text-slate-500 hover:text-slate-300"
                    }`}
                  >
                    {examples("toggleMaster")}
                  </button>
                </div>
              </div>

              <WaveformPlayer
                src="/examples/rock_mixdown.wav"
                compareSrc="/examples/rock_original.wav"
                isCompareActive={showOriginal}
                accentColor={showOriginal ? "#64748b" : "#f59e0b"}
                className="w-full bg-slate-950/90 border border-slate-800/70 px-4 py-3 shadow-lg shadow-black/40"
                canvasClassName="h-14 sm:h-16 md:h-20"
                hideDownload={true}
              />
            </div>
          </div>
        </ScrollReveal>

        <ScrollReveal className="mt-8 flex justify-center" delay={0.15}>
          <Link
            href="/examples"
            className="inline-flex items-center justify-center rounded-full bg-amber-400 px-5 py-2 text-sm font-semibold text-slate-950 shadow-lg shadow-amber-500/20 transition hover:bg-amber-300"
          >
            {t("cta")}
          </Link>
        </ScrollReveal>
      </div>
    </section>
  );
}
