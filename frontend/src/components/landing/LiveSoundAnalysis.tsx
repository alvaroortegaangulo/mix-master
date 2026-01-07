"use client";

import { useState, useEffect } from "react";
import { SpeakerWaveIcon } from "@heroicons/react/24/outline";
import { useTranslations } from "next-intl";
import { ScrollReveal } from "./ScrollReveal";

export function LiveSoundAnalysis({ className }: { className?: string }) {
  const t = useTranslations('LiveSoundAnalysis');
  const title = t('title');
  const titlePlain = title.replace(/<[^>]+>/g, "");

  // State for animations
  const [spectrumData, setSpectrumData] = useState<number[]>([]);
  const [lufs, setLufs] = useState(-13.2);
  const [correlation, setCorrelation] = useState(0.80);
  const [dynamicRange, setDynamicRange] = useState(13);

  // Initialize spectrum bars
  useEffect(() => {
    // Generate 32 bars
    setSpectrumData(Array.from({ length: 32 }, () => Math.random() * 100));
  }, []);

  // Animation Loop
  useEffect(() => {
    const interval = setInterval(() => {
      // Animate Spectrum
      setSpectrumData((prev) =>
        prev.map((val) => {
          const delta = (Math.random() - 0.5) * 30; // Random change
          const newVal = Math.max(10, Math.min(100, val + delta)); // Clamp between 10 and 100
          return newVal;
        })
      );

      // Animate LUFS (jitter around -13.2)
      setLufs((prev) => {
        const jitter = (Math.random() - 0.5) * 0.2;
        return Number((-13.2 + jitter).toFixed(1));
      });

      // Animate Correlation (jitter around 0.80)
      setCorrelation((prev) => {
        const jitter = (Math.random() - 0.5) * 0.02;
        return Number((0.80 + jitter).toFixed(2));
      });

      // Animate Dynamic Range (jitter around 13)
      setDynamicRange((prev) => {
         // Less frequent change for integer
         if (Math.random() > 0.7) {
             const jitter = Math.floor(Math.random() * 3) - 1; // -1, 0, 1
             return Math.max(10, Math.min(16, 13 + jitter));
         }
         return prev;
      });

    }, 150);

    return () => clearInterval(interval);
  }, []);

    return (
    <section className={`lg:min-h-screen flex flex-col justify-center py-12 md:py-14 lg:py-16 2xl:py-20 border-t border-slate-900 relative overflow-hidden ${className || 'bg-slate-950'}`}>
        {/* Background image */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none z-0">
            <div className="absolute inset-0 analysis-wallpaper" />
            <div className="absolute inset-0 analysis-wallpaper-overlay" />
        </div>

      <div className="max-w-7xl 2xl:max-w-[1600px] mx-auto px-4 sm:px-6 lg:px-8 2xl:px-4 relative z-10">
        {/* Header */}
        <ScrollReveal className="mb-6 text-right" delay={0.05}>
          <h2
            className="text-3xl md:text-5xl 2xl:text-6xl font-bold tracking-tight mb-4 font-['Orbitron'] text-white glow-teal metallic-sheen"
            data-text={titlePlain}
          >
            {t.rich('title', {
              teal: (chunks) => <span className="text-teal-400">{chunks}</span>,
            })}
          </h2>
          <p className="max-w-3xl text-sm sm:text-base text-slate-400 leading-relaxed ml-auto">
            {t('description')}
          </p>
        </ScrollReveal>

        {/* Dashboard Container */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 lg:gap-5 font-['Orbitron']">

          {/* LEFT PANEL: Frequency Spectrum */}
          <ScrollReveal
            className="lg:col-span-2 bg-slate-900/50 rounded-3xl border border-slate-800 p-3 md:p-4 2xl:p-5 flex flex-col justify-between min-h-[190px] md:min-h-[220px] 2xl:min-h-[300px] shadow-2xl relative overflow-hidden"
            delay={0.1}
          >

             {/* Top Bar of Panel */}
             <div className="flex justify-between items-start mb-3 relative z-10">
                 <div className="flex items-center gap-2">
                     <div className="bg-teal-500/20 p-1.5 rounded-lg">
                        <svg className="w-5 h-5 text-teal-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true" focusable="false">
                           <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                        </svg>
                     </div>
                     <h3 className="text-base sm:text-lg font-semibold text-white">{t('spectrum.title')}</h3>
                 </div>
                 <div className="text-xs text-slate-300 pt-2">{t('spectrum.range')}</div>
             </div>

             {/* Spectrum Visualizer */}
             <div className="flex-1 flex items-end justify-between gap-1 px-2 mb-3 relative z-10 h-8">
                {spectrumData.map((height, i) => (
                    <div
                        key={i}
                        className="w-full bg-gradient-to-t from-teal-900/40 to-teal-400 rounded-t-sm transition-all duration-300 ease-in-out opacity-90 hover:opacity-100"
                        style={{ height: `${height}%` }}
                    ></div>
                ))}

                {/* Grid Lines */}
                <div className="absolute inset-0 border-t border-slate-800/50 top-0 w-full"></div>
                <div className="absolute inset-0 border-t border-slate-800/50 top-1/4 w-full"></div>
                <div className="absolute inset-0 border-t border-slate-800/50 top-2/4 w-full"></div>
                <div className="absolute inset-0 border-t border-slate-800/50 top-3/4 w-full"></div>
             </div>

             {/* Bottom Metrics */}
             <div className="grid grid-cols-3 gap-2 border-t border-slate-800 pt-3 relative z-10">
                 <div>
                     <div className="text-[10px] 2xl:text-xs uppercase tracking-wider text-slate-300 mb-1">{t('spectrum.sub')}</div>
                     <div className="text-white font-medium 2xl:text-lg">{t('spectrum.balanced')}</div>
                 </div>
                 <div>
                     <div className="text-[10px] 2xl:text-xs uppercase tracking-wider text-slate-300 mb-1">{t('spectrum.vocal')}</div>
                     <div className="text-teal-400 font-medium 2xl:text-lg">{t('spectrum.optimal')}</div>
                 </div>
                 <div className="text-right">
                     <div className="text-[10px] 2xl:text-xs uppercase tracking-wider text-slate-300 mb-1">{t('spectrum.air')}</div>
                     <div className="text-white font-medium 2xl:text-lg">+1.2 dB</div>
                 </div>
             </div>

             {/* Background Effects */}
             <div className="absolute bottom-0 left-0 right-0 h-1/2 bg-gradient-to-t from-teal-900/10 to-transparent pointer-events-none"></div>
          </ScrollReveal>


          {/* RIGHT COLUMN: Metrics Cards */}
          <ScrollReveal className="flex flex-col gap-3" delay={0.15}>

             {/* Card 1: Integrated Loudness */}
             <div className="bg-slate-900/50 rounded-2xl border border-slate-800 p-3 2xl:p-4 shadow-lg relative group overflow-hidden">
                <div className="flex justify-between items-start mb-2">
                    <div className="text-[10px] 2xl:text-xs uppercase tracking-wider text-slate-300">{t('metrics.loudness')}</div>
                    <SpeakerWaveIcon className="w-4 h-4 text-teal-400/70 icon-float" aria-hidden="true" />
                </div>
                <div className="text-xl 2xl:text-4xl font-bold text-white mb-1 tabular-nums tracking-tight">
                    {lufs.toFixed(1)} <span className="text-sm sm:text-base 2xl:text-xl font-normal text-slate-200">LUFS</span>
                </div>

                {/* Progress Bar */}
                <div className="mt-2 mb-2 relative h-1.5 bg-slate-800 rounded-full overflow-hidden">
                    <div className="absolute top-0 left-0 h-full bg-teal-400 w-[85%] rounded-full shadow-[0_0_10px_rgba(45,212,191,0.5)] transition-all duration-300" style={{ width: `${Math.min(100, ((-1 * lufs) / 14) * 85)}%` }}></div>
                </div>
                <div className="flex justify-between text-[9px] text-slate-300 mb-3">
                    <span>-30</span>
                    <span>-14 ({t('metrics.target')})</span>
                    <span>-8</span>
                </div>

             </div>

             <div className="grid grid-cols-2 gap-3 sm:flex sm:flex-col">
               {/* Card 2: Stereo Image */}
               <div className="bg-slate-900/50 rounded-2xl border border-slate-800 p-3 2xl:p-4 shadow-lg relative overflow-hidden">
                   <div className="flex justify-between items-start gap-2">
                       <div className="min-w-0">
                          <div className="text-[9px] sm:text-[10px] uppercase tracking-wider text-slate-300 mb-1">{t('metrics.stereoImage')}</div>
                          <div className="text-sm sm:text-lg font-bold text-white mb-1 leading-tight">{t('metrics.wide')}</div>
                          <div className="text-[10px] sm:text-xs text-slate-300 mb-2 sm:mb-3 tabular-nums">
                            {t('metrics.correlation')}: <span className="text-white">+{correlation.toFixed(2)}</span>
                          </div>
                       </div>

                       {/* Visual representation of Stereo Field (Circle) */}
                       <div className="h-8 w-8 sm:h-10 sm:w-10 rounded-full border border-slate-700 bg-slate-950 relative flex items-center justify-center overflow-hidden stereo-icon">
                          <div className="absolute inset-0 bg-violet-500/20 animate-pulse rounded-full transform scale-75"></div>
                          <div className="w-6 h-3 sm:w-7 sm:h-3.5 border border-violet-400/50 rounded-[100%] transform -rotate-12 opacity-80 stereo-orbit"></div>
                          <div className="w-6 h-3 sm:w-7 sm:h-3.5 border border-teal-400/50 rounded-[100%] absolute transform rotate-12 opacity-80 stereo-orbit-delayed"></div>
                       </div>
                   </div>
               </div>

               {/* Card 3: Dynamic Range */}
               <div className="bg-slate-900/50 rounded-2xl border border-slate-800 p-3 2xl:p-4 shadow-lg flex items-center justify-between gap-2">
                   <div className="min-w-0">
                      <div className="text-[9px] sm:text-[10px] uppercase tracking-wider text-slate-300 mb-1">{t('metrics.dynamicRange')}</div>
                      <div className="text-base sm:text-xl font-bold text-white tabular-nums">
                        {dynamicRange} <span className="text-[11px] sm:text-base font-normal text-slate-200">dB</span>
                      </div>
                   </div>

                   {/* Mini Histogram */}
                   <div className="flex items-end gap-0.5 sm:gap-1 h-6 sm:h-8">
                      <div className="w-1 sm:w-1.5 bg-violet-900/40 h-3 rounded-sm histogram-bar histogram-bar-1"></div>
                      <div className="w-1 sm:w-1.5 bg-violet-800/60 h-4 sm:h-5 rounded-sm histogram-bar histogram-bar-2"></div>
                      <div className="w-1 sm:w-1.5 bg-violet-500 h-6 sm:h-8 rounded-sm shadow-[0_0_10px_rgba(139,92,246,0.4)] histogram-bar histogram-bar-3"></div>
                      <div className="w-1 sm:w-1.5 bg-violet-800/60 h-5 sm:h-6 rounded-sm histogram-bar histogram-bar-4"></div>
                   </div>
               </div>
             </div>

          </ScrollReveal>
        </div>
      </div>

      <style jsx>{`
        .icon-float {
          animation: icon-float 3.2s ease-in-out infinite;
          filter: drop-shadow(0 0 8px rgba(45, 212, 191, 0.35));
        }

        .stereo-icon {
          animation: stereo-pulse 2.8s ease-in-out infinite;
          box-shadow: 0 0 12px rgba(139, 92, 246, 0.25);
        }

        .stereo-orbit {
          animation: stereo-orbit 6s linear infinite;
          transform-origin: center;
        }

        .stereo-orbit-delayed {
          animation: stereo-orbit 6s linear infinite;
          animation-delay: -1.8s;
          transform-origin: center;
        }

        .histogram-bar {
          transform-origin: bottom;
          animation: histogram-bounce 1.6s ease-in-out infinite;
          will-change: transform;
        }

        .histogram-bar-1 {
          animation-delay: 0s;
        }

        .histogram-bar-2 {
          animation-delay: 0.2s;
        }

        .histogram-bar-3 {
          animation-delay: 0.4s;
        }

        .histogram-bar-4 {
          animation-delay: 0.1s;
        }

        @keyframes icon-float {
          0%,
          100% {
            transform: translateY(0);
            opacity: 0.7;
          }
          50% {
            transform: translateY(-3px);
            opacity: 1;
          }
        }

        @keyframes stereo-pulse {
          0%,
          100% {
            transform: scale(1);
          }
          50% {
            transform: scale(1.05);
          }
        }

        @keyframes stereo-orbit {
          0% {
            transform: rotate(-10deg);
          }
          100% {
            transform: rotate(350deg);
          }
        }

        @keyframes histogram-bounce {
          0%,
          100% {
            transform: scaleY(0.75);
          }
          50% {
            transform: scaleY(1.2);
          }
        }
      `}</style>
    </section>
  );
}
