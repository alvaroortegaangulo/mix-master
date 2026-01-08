"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Link } from "../../i18n/routing";
import { WaveformPlayer } from "../WaveformPlayer";
import { ScrollReveal } from "./ScrollReveal";
import {
  SparklesIcon,
  BoltIcon,
  ArrowsPointingOutIcon,
  ShieldCheckIcon
} from "@heroicons/react/24/outline";

export function ListenDifferenceSection({ className }: { className?: string }) {
  const t = useTranslations("ListenDifferenceSection");
  const examples = useTranslations("Examples");
  const [showOriginal, setShowOriginal] = useState(false);

  const metricsData = {
    original: {
      integratedLufs: "-16.0",
      truePeak: "-4.5 dBTP",
      lra: "5.5 LU",
      crestFactor: "14.2 dB",
      correlation: "0.82",
      diffLr: "0.35 dB"
    },
    master: {
      integratedLufs: "-9.5",
      truePeak: "-0.2 dBTP",
      lra: "3.5 LU",
      crestFactor: "9.8 dB",
      correlation: "0.98",
      diffLr: "0.05 dB"
    }
  };

  const currentMetrics = showOriginal ? metricsData.original : metricsData.master;

  const improvements = [
    { icon: SparklesIcon, key: "eqMatching" },
    { icon: BoltIcon, key: "dynamicGlue" },
    { icon: ArrowsPointingOutIcon, key: "stereoWidth" },
    { icon: ShieldCheckIcon, key: "truePeakLimiting" }
  ];

  return (
    <section
      className={`relative overflow-hidden px-4 py-12 sm:py-16 md:py-20 lg:py-24 min-h-[100svh] sm:min-h-0 flex flex-col justify-center ${className || "bg-slate-950"}`}
    >
      <div className="absolute inset-0 pointer-events-none z-0">
        <div className="absolute inset-0 bg-[#050508]" />
        <div className="absolute inset-0 grid-landing-diagonal" />
        <div className="absolute inset-0 grid-landing-vignette" />
        <div className="absolute -top-[30%] left-1/2 h-[50%] w-[50%] -translate-x-1/2 rounded-full bg-amber-500/15 blur-[140px]" />
        <div className="absolute top-[30%] -right-[10%] h-[45%] w-[45%] rounded-full bg-orange-400/12 blur-[160px]" />
        <div className="absolute bottom-[5%] -left-[10%] h-[40%] w-[40%] rounded-full bg-teal-500/10 blur-[160px]" />
      </div>

      <div className="relative z-10 mx-auto max-w-7xl w-full">
        <ScrollReveal className="mx-auto max-w-3xl text-center mb-10 md:mb-14" delay={0.05}>
          <h2
            className="text-3xl sm:text-4xl md:text-5xl font-black font-['Orbitron'] tracking-tight text-white mb-4 glow-amber metallic-sheen"
            data-text={titlePlain}
          >
            {t.rich("title", {
              amber: (chunks) => <span className="text-amber-400">{chunks}</span>,
            })}
          </h2>
          <p className="text-sm sm:text-base md:text-lg text-slate-300 leading-relaxed max-w-2xl mx-auto">
            {t("subtitle")}
          </p>
        </ScrollReveal>

        <ScrollReveal
          className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch"
          delay={0.1}
        >
          {/* Main Player Box */}
          <div className="lg:col-span-8 relative rounded-[28px] border border-amber-500/20 bg-slate-900/60 p-6 sm:p-8 shadow-[0_30px_80px_rgba(0,0,0,0.55)] backdrop-blur flex flex-col justify-between min-h-[400px]">
            <div className="absolute inset-0 rounded-[28px] ring-1 ring-amber-500/10 pointer-events-none" />

            {/* Header / Info */}
            <div className="mb-6 flex justify-between items-start">
              <div>
                <h3 className="text-xl sm:text-2xl font-bold text-white mb-1">Deep Flow</h3>
                <p className="text-sm text-slate-400">Trap / Hip-Hop • 140 BPM</p>
              </div>
              <div className="bg-slate-950/50 px-3 py-1 rounded-full border border-slate-800 text-xs text-amber-400 font-mono">
                {showOriginal ? "-16.0 LUFS" : "-9.5 LUFS (Optimized)"}
              </div>
            </div>

            {/* Waveform Player */}
            <div className="flex-1 flex flex-col justify-center">
              <WaveformPlayer
                src="/examples/rock_mixdown.wav"
                compareSrc="/examples/rock_original.wav"
                isCompareActive={showOriginal}
                accentColor={showOriginal ? "#64748b" : "#f59e0b"}
                className="w-full bg-slate-950/90 border border-slate-800/70 px-4 py-4 shadow-lg shadow-black/40 rounded-xl"
                canvasClassName="h-32 sm:h-40 md:h-48"
                hideDownload={true}
              />
            </div>

            {/* Controls / Toggle */}
            <div className="mt-8 flex justify-center">
               <div className="inline-flex bg-slate-950/80 p-1.5 rounded-full border border-slate-800/80 shadow-xl">
                  <button
                    type="button"
                    onClick={() => setShowOriginal(true)}
                    aria-pressed={showOriginal}
                    className={`px-6 py-2 rounded-full text-xs sm:text-sm font-bold transition-all duration-300 ${
                      showOriginal
                        ? "bg-slate-700 text-white shadow-inner"
                        : "text-slate-500 hover:text-slate-300"
                    }`}
                  >
                    {examples("toggleOriginal")}
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowOriginal(false)}
                    aria-pressed={!showOriginal}
                    className={`px-6 py-2 rounded-full text-xs sm:text-sm font-bold transition-all duration-300 ${
                      !showOriginal
                        ? "bg-amber-500 text-slate-950 shadow-lg shadow-amber-500/20"
                        : "text-slate-500 hover:text-slate-300"
                    }`}
                  >
                    {examples("toggleMaster")}
                  </button>
                </div>
            </div>
          </div>

          {/* Metrics Panel */}
          <div className="lg:col-span-4 flex flex-col gap-6">
            <div className="flex-1 relative rounded-[28px] border border-slate-800 bg-slate-900/60 p-6 sm:p-8 shadow-xl backdrop-blur flex flex-col justify-center">
               <h3 className="text-lg font-bold text-white mb-6 flex items-center gap-2">
                 <span className="w-2 h-2 rounded-full bg-teal-500 animate-pulse"></span>
                 {t("metrics.integratedLufs")}
               </h3>

               <div className="space-y-5">
                 {Object.entries(currentMetrics).map(([key, value]) => (
                   <div key={key} className="flex justify-between items-end border-b border-slate-800/60 pb-2">
                     <span className="text-sm text-slate-400 font-medium">
                        {t(`metrics.${key}`)}
                     </span>
                     <span className={`text-base font-mono font-bold ${showOriginal ? 'text-slate-300' : 'text-teal-400'}`}>
                       {value}
                     </span>
                   </div>
                 ))}
               </div>
            </div>
          </div>
        </ScrollReveal>

        {/* Improvements Section */}
        <ScrollReveal className="mt-8" delay={0.2}>
           <div className="rounded-[24px] bg-slate-900/40 border border-slate-800/60 p-6 backdrop-blur">
              <div className="flex flex-col md:flex-row items-center justify-between gap-6">
                 <h3 className="text-lg font-bold text-white shrink-0 pr-4 border-r border-slate-800 hidden md:block">
                    {t("improvementsTitle")}
                 </h3>
                 <div className="grid grid-cols-2 md:grid-cols-4 gap-4 w-full">
                    {improvements.map(({ icon: Icon, key }) => (
                      <div key={key} className="flex items-center gap-3 bg-slate-950/50 rounded-xl p-3 border border-slate-800/50">
                         <div className={`p-2 rounded-lg ${showOriginal ? 'bg-slate-800 text-slate-500' : 'bg-teal-500/10 text-teal-400'}`}>
                           <Icon className="w-5 h-5" />
                         </div>
                         <span className="text-xs sm:text-sm font-medium text-slate-300 leading-tight">
                           {t(`improvements.${key}`)}
                         </span>
                      </div>
                    ))}
                 </div>
              </div>
           </div>
        </ScrollReveal>

        <ScrollReveal className="mt-10 flex justify-center" delay={0.25}>
          <Link
            href="/examples"
            className="inline-flex items-center justify-center rounded-full bg-amber-400 px-8 py-3 text-sm font-bold text-slate-950 shadow-lg shadow-amber-500/20 transition hover:bg-amber-300 hover:scale-105 active:scale-95"
          >
            {t("cta")}
          </Link>
        </ScrollReveal>
      </div>
    </section>
  );
}
