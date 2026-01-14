"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Link } from "../../i18n/routing";
import { WaveformPlayer } from "../WaveformPlayer";
import { ScrollReveal } from "./ScrollReveal";
import { SonarBackground } from "./SonarBackground";
import {
  SparklesIcon,
  BoltIcon,
  ArrowsPointingOutIcon,
  MicrophoneIcon,
  SunIcon,
  CubeTransparentIcon,
  ArrowUpTrayIcon,
  WifiIcon,
  InformationCircleIcon
} from "@heroicons/react/24/outline";

export function ListenDifferenceSection({ className }: { className?: string }) {
  const t = useTranslations("ListenDifferenceSection");
  const titlePlain = t("titlePlain");
  const examples = useTranslations("Examples");
  const [showOriginal, setShowOriginal] = useState(false);

  const metricsData = {
    original: {
      integratedLufs: { value: "-16.0", unit: "LUFS" },
      truePeak: { value: "-4.5", unit: "dBTP" },
      lra: { value: "5.5", unit: "LU" },
      crestFactor: { value: "14.2", unit: "dB" },
      correlation: { value: "0.82", unit: "" },
      diffLr: { value: "0.35", unit: "dB" }
    },
    master: {
      integratedLufs: { value: "-9.5", unit: "LUFS" },
      truePeak: { value: "-0.2", unit: "dBTP" },
      lra: { value: "3.5", unit: "LU" },
      crestFactor: { value: "9.8", unit: "dB" },
      correlation: { value: "0.98", unit: "" },
      diffLr: { value: "0.05", unit: "dB" }
    }
  };

  const currentMetrics = showOriginal ? metricsData.original : metricsData.master;

  const improvements = [
    {
      key: "instantProSound",
      icon: SparklesIcon,
      color: "bg-blue-500/10 text-blue-400"
    },
    {
      key: "claritySeparation",
      icon: ArrowsPointingOutIcon,
      color: "bg-emerald-500/10 text-emerald-400"
    },
    {
      key: "punchyLows",
      icon: BoltIcon,
      color: "bg-purple-500/10 text-purple-400"
    },
    {
      key: "presence",
      icon: MicrophoneIcon,
      color: "bg-orange-500/10 text-orange-400"
    },
    {
      key: "premiumSheen",
      icon: SunIcon,
      color: "bg-yellow-500/10 text-yellow-400"
    },
    {
      key: "glueCohesion",
      icon: CubeTransparentIcon,
      color: "bg-indigo-500/10 text-indigo-400"
    },
    {
      key: "platformLoudness",
      icon: ArrowUpTrayIcon,
      color: "bg-rose-500/10 text-rose-400"
    },
    {
      key: "stereoWidth",
      icon: WifiIcon,
      color: "bg-cyan-500/10 text-cyan-400"
    }
  ];

  return (
    <section
      className={`relative isolate z-0 overflow-hidden px-4 py-12 sm:py-16 md:py-20 lg:py-24 min-h-[100svh] sm:min-h-0 flex flex-col justify-center ${className || "bg-slate-950"}`}
    >
      <SonarBackground />

      <div className="relative z-10 mx-auto max-w-7xl w-full">
        
        {/* 1. Title & Subtitle - Staggered */}
        <div className="mx-auto max-w-3xl text-center mb-10 md:mb-14">
          <ScrollReveal delay={0.1} direction="up">
            <h2
              className="text-3xl sm:text-4xl md:text-5xl font-black font-['Orbitron'] tracking-tight text-white mb-4 glow-amber metallic-sheen"
              data-text={titlePlain}
            >
              {t.rich("titleMain", {
                amber: (chunks) => <span className="text-amber-400">{chunks}</span>,
              })}
            </h2>
          </ScrollReveal>
          
          <ScrollReveal delay={0.2} direction="up">
            <p className="text-sm sm:text-base md:text-lg text-slate-300 leading-relaxed max-w-2xl mx-auto">
              {t("subtitle")}
            </p>
          </ScrollReveal>
        </div>

        {/* 2. Main Grid - Player enters left, Metrics enters right */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
          
          {/* Main Player Box - Enters from Left */}
          <ScrollReveal 
            className="lg:col-span-8 relative rounded-[28px] border border-amber-500/20 bg-slate-900/60 p-6 sm:p-8 lg:p-5 xl:p-6 2xl:p-8 shadow-[0_30px_80px_rgba(0,0,0,0.55)] backdrop-blur flex flex-col justify-between min-h-[400px] lg:min-h-[340px] xl:min-h-[400px]"
            delay={0.3}
            direction="left" // or "up" if you prefer vertical only
            x={20} // Slight horizontal movement
          >
            <div className="absolute inset-0 rounded-[28px] ring-1 ring-amber-500/10 pointer-events-none" />

            {/* Header / Info */}
            <div className="mb-6 flex justify-between items-start lg:mb-4 xl:mb-6">
              <div>
                <h3 className="text-xl sm:text-2xl lg:text-lg xl:text-xl font-bold text-white mb-1 lg:mb-0.5">Street Noise</h3>
                <p className="text-sm text-slate-400 lg:text-xs xl:text-sm">Rock & Roll • 105 BPM</p>
              </div>
              <div className="bg-slate-950/50 px-3 py-1 lg:px-2.5 lg:py-0.5 rounded-full border border-slate-800 text-xs lg:text-[10px] text-amber-400 font-mono">
                {showOriginal ? "-16.0 LUFS" : "-9.5 LUFS (Optimized)"}
              </div>
            </div>

            {/* Waveform Player */}
            <div className="flex-1 flex flex-col justify-center">
              <WaveformPlayer
                src="/examples/rock_mixdown.mp3"
                compareSrc="/examples/rock_original.mp3"
                isCompareActive={showOriginal}
                accentColor={showOriginal ? "#64748b" : "#f59e0b"}
                className="w-full bg-slate-950/90 border border-slate-800/70 px-4 py-4 lg:px-3 lg:py-3 shadow-lg shadow-black/40 rounded-xl"
                canvasClassName="h-32 sm:h-40 md:h-48 lg:h-32 xl:h-40 2xl:h-48"
                hideDownload={true}
              />
            </div>

            {/* Controls / Toggle */}
            <div className="mt-8 flex justify-center lg:mt-5 xl:mt-7">
               <div className="inline-flex bg-slate-950/80 p-1.5 lg:p-1 rounded-full border border-slate-800/80 shadow-xl">
                  <button
                    type="button"
                    onClick={() => setShowOriginal(true)}
                    aria-pressed={showOriginal}
                    className={`px-6 py-2 lg:px-4 lg:py-1.5 rounded-full text-xs sm:text-sm lg:text-[11px] font-bold transition-all duration-300 ${
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
                    className={`px-6 py-2 lg:px-4 lg:py-1.5 rounded-full text-xs sm:text-sm lg:text-[11px] font-bold transition-all duration-300 ${
                      !showOriginal
                        ? "bg-amber-500 text-slate-950 shadow-lg shadow-amber-500/20"
                        : "text-slate-500 hover:text-slate-300"
                    }`}
                  >
                    {examples("toggleMaster")}
                  </button>
                </div>
            </div>
          </ScrollReveal>

          {/* Metrics Panel - Enters from Right/Bottom */}
          <ScrollReveal 
            className="lg:col-span-4 flex flex-col gap-6 lg:gap-4 xl:gap-6"
            delay={0.4}
            direction="up" // Keeping it up to match alignment better on mobile
          >
            <div className="flex-1 relative rounded-[28px] border border-slate-800 bg-slate-900/60 p-6 sm:p-8 lg:p-5 xl:p-6 2xl:p-8 shadow-xl backdrop-blur flex flex-col justify-center">
               <div className="space-y-5 lg:space-y-3 xl:space-y-4">
                 {Object.entries(currentMetrics).map(([key, { value, unit }]) => (
                   <div key={key} className="flex justify-between items-center border-b border-slate-800/60 pb-2 lg:pb-1.5">
                     <div className="flex items-center gap-2">
                       <span className="text-sm text-slate-400 font-medium lg:text-xs xl:text-sm">
                          {t(`metrics.${key}.label`)}
                       </span>
                       <div className="group relative">
                          <InformationCircleIcon className="w-4 h-4 lg:h-3.5 lg:w-3.5 text-slate-600 hover:text-teal-400 cursor-help transition-colors" />
                          <div className="absolute bottom-full left-1/2 mb-2 hidden -translate-x-1/2 whitespace-normal rounded-lg bg-slate-800 px-3 py-2 text-xs text-white shadow-xl w-48 z-50 border border-slate-700 pointer-events-none group-hover:block">
                            {t(`metrics.${key}.tooltip`)}
                            <div className="absolute top-full left-1/2 -mt-1 -ml-1 h-2 w-2 border-r border-b border-slate-700 bg-slate-800 rotate-45"></div>
                          </div>
                       </div>
                     </div>
                     <div className="text-right">
                       <span className={`text-base lg:text-sm xl:text-base font-mono font-bold ${showOriginal ? 'text-slate-300' : 'text-teal-400'}`}>
                         {value}
                       </span>
                       {unit && <span className="text-xs lg:text-[10px] xl:text-xs text-slate-500 ml-1">{unit}</span>}
                     </div>
                   </div>
                 ))}
               </div>
            </div>
          </ScrollReveal>
        </div>

        {/* 3. Improvements Grid - Individual Cards Pop In Sequentially */}
        <div className="mt-12 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {improvements.map(({ icon: Icon, key, color }, index) => (
            <ScrollReveal
              key={key}
              delay={0.5 + (index * 0.05)} // Staggered delay: 0.50, 0.55, 0.60...
              direction="up"
              className="bg-slate-900/40 border border-slate-800 rounded-2xl p-6 hover:bg-slate-900/60 transition-colors duration-300"
            >
              <div className={`w-10 h-10 rounded-lg flex items-center justify-center mb-4 ${color}`}>
                <Icon className="w-6 h-6" />
              </div>
              <h3 className="text-white font-bold text-base mb-2">
                {t(`improvements.${key}.title`)}
              </h3>
              <p className="text-slate-400 text-sm leading-relaxed">
                {t(`improvements.${key}.description`)}
              </p>
            </ScrollReveal>
          ))}
        </div>

        {/* 4. CTA Button - Last to appear */}
        <ScrollReveal className="mt-12 flex justify-center" delay={0.9}>
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
