"use client";

import { useState, useEffect } from "react";
import {
  ArrowPathIcon,
  SpeakerWaveIcon,
  CheckCircleIcon,
} from "@heroicons/react/24/outline";

export function LiveSoundAnalysis({ className }: { className?: string }) {
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
    <section className={`py-24 border-t border-slate-900 relative overflow-hidden ${className || 'bg-slate-950'}`}>
        {/* Background Gradients */}
        <div className="absolute top-0 left-0 w-full h-full overflow-hidden pointer-events-none">
            <div className="absolute top-1/4 -left-64 w-96 h-96 bg-cyan-900/10 rounded-full blur-3xl"></div>
            <div className="absolute bottom-1/4 -right-64 w-96 h-96 bg-purple-900/10 rounded-full blur-3xl"></div>
        </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        {/* Header */}
        <div className="mb-16">
          <div className="flex items-center gap-2 mb-6">
             <div className="h-2 w-2 rounded-full bg-teal-400 animate-pulse"></div>
             <div className="text-xs font-bold tracking-widest text-teal-400 uppercase">
                Live Analytics Engine
             </div>
          </div>
          <h2 className="text-4xl md:text-5xl font-bold tracking-tight text-white mb-6">
            Visualize the Invisible.
          </h2>
          <p className="max-w-2xl text-lg text-slate-400 leading-relaxed">
            Stop guessing. Piroola provides surgical precision metrics to ensure your mix meets streaming standards (Spotify, Apple Music) and broadcast.
          </p>
        </div>

        {/* Dashboard Container */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

          {/* LEFT PANEL: Frequency Spectrum */}
          <div className="lg:col-span-2 bg-slate-900/50 rounded-3xl border border-slate-800 p-6 flex flex-col justify-between min-h-[500px] shadow-2xl relative overflow-hidden">

             {/* Top Bar of Panel */}
             <div className="flex justify-between items-start mb-8 relative z-10">
                 <div className="flex items-center gap-2">
                     <div className="bg-teal-500/20 p-1.5 rounded-lg">
                        <svg className="w-5 h-5 text-teal-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                           <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                        </svg>
                     </div>
                     <h3 className="text-lg font-semibold text-white">Frequency Spectrum</h3>
                 </div>
                 <div className="text-xs font-mono text-slate-300 pt-2">20Hz - 20kHz</div>
             </div>

             {/* Spectrum Visualizer */}
             <div className="flex-1 flex items-end justify-between gap-1 px-2 mb-8 relative z-10 h-64">
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
             <div className="grid grid-cols-3 gap-4 border-t border-slate-800 pt-6 relative z-10">
                 <div>
                     <div className="text-[10px] font-mono uppercase tracking-wider text-slate-300 mb-1">Low End (Sub)</div>
                     <div className="text-white font-medium">Balanced</div>
                 </div>
                 <div>
                     <div className="text-[10px] font-mono uppercase tracking-wider text-slate-300 mb-1">Vocal Presence</div>
                     <div className="text-teal-400 font-medium">Optimal</div>
                 </div>
                 <div className="text-right">
                     <div className="text-[10px] font-mono uppercase tracking-wider text-slate-300 mb-1">Air / Shine</div>
                     <div className="text-white font-medium">+1.2 dB</div>
                 </div>
             </div>

             {/* Background Effects */}
             <div className="absolute bottom-0 left-0 right-0 h-1/2 bg-gradient-to-t from-teal-900/10 to-transparent pointer-events-none"></div>
          </div>


          {/* RIGHT COLUMN: Metrics Cards */}
          <div className="flex flex-col gap-4">

             {/* Controls / Header for Right Column */}
             <div className="flex justify-end gap-3 mb-2">
                 <button className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-slate-700 bg-slate-900/50 text-xs font-medium text-slate-300 hover:bg-slate-800 transition">
                    <ArrowPathIcon className="w-3 h-3" />
                    Re-Scan
                 </button>
                 <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-slate-700 bg-slate-900/50 text-xs font-mono text-slate-400">
                    <span>Target:</span>
                    <span className="text-teal-400">-14 LUFS</span>
                 </div>
             </div>

             {/* Card 1: Integrated Loudness */}
             <div className="bg-slate-900/50 rounded-2xl border border-slate-800 p-6 shadow-lg relative group overflow-hidden">
                <div className="flex justify-between items-start mb-2">
                    <div className="text-[10px] font-mono uppercase tracking-wider text-slate-300">Integrated Loudness</div>
                    <SpeakerWaveIcon className="w-4 h-4 text-teal-500/50" />
                </div>
                <div className="text-4xl font-bold text-white mb-1 tabular-nums tracking-tight">
                    {lufs.toFixed(1)} <span className="text-lg font-normal text-slate-200">LUFS</span>
                </div>

                {/* Progress Bar */}
                <div className="mt-4 mb-2 relative h-1.5 bg-slate-800 rounded-full overflow-hidden">
                    <div className="absolute top-0 left-0 h-full bg-teal-400 w-[85%] rounded-full shadow-[0_0_10px_rgba(45,212,191,0.5)] transition-all duration-300" style={{ width: `${Math.min(100, ((-1 * lufs) / 14) * 85)}%` }}></div>
                </div>
                <div className="flex justify-between text-[10px] text-slate-300 font-mono mb-4">
                    <span>-30</span>
                    <span>-14 (Target)</span>
                    <span>-8</span>
                </div>

                <div className="flex items-center gap-2 text-teal-400 text-xs font-medium bg-teal-950/30 p-2 rounded-lg border border-teal-900/50 inline-block">
                    <CheckCircleIcon className="w-4 h-4" />
                    Spotify Ready
                </div>
             </div>

             {/* Card 2: Stereo Image */}
             <div className="bg-slate-900/50 rounded-2xl border border-slate-800 p-6 shadow-lg relative overflow-hidden">
                 <div className="flex justify-between items-start">
                     <div>
                        <div className="text-[10px] font-mono uppercase tracking-wider text-slate-300 mb-1">Stereo Image</div>
                        <div className="text-2xl font-bold text-white mb-1">Wide</div>
                        <div className="text-sm font-mono text-slate-400 mb-3 tabular-nums">Correlation: <span className="text-white">+{correlation.toFixed(2)}</span></div>
                     </div>

                     {/* Visual representation of Stereo Field (Circle) */}
                     <div className="h-12 w-12 rounded-full border border-slate-700 bg-slate-950 relative flex items-center justify-center overflow-hidden">
                        <div className="absolute inset-0 bg-purple-500/20 animate-pulse rounded-full transform scale-75"></div>
                        <div className="w-8 h-4 border border-purple-400/50 rounded-[100%] transform -rotate-12 opacity-80"></div>
                        <div className="w-8 h-4 border border-teal-400/50 rounded-[100%] absolute transform rotate-12 opacity-80"></div>
                     </div>
                 </div>

                 <p className="text-xs text-slate-300 leading-relaxed border-t border-slate-800/50 pt-3 mt-1">
                     Excellent mono compatibility. No critical phase cancellations.
                 </p>
             </div>

             {/* Card 3: Dynamic Range */}
             <div className="bg-slate-900/50 rounded-2xl border border-slate-800 p-6 shadow-lg flex items-center justify-between">
                 <div>
                    <div className="text-[10px] font-mono uppercase tracking-wider text-slate-300 mb-1">Dynamic Range</div>
                    <div className="text-3xl font-bold text-white tabular-nums">{dynamicRange} <span className="text-lg font-normal text-slate-200">dB</span></div>
                 </div>

                 {/* Mini Histogram */}
                 <div className="flex items-end gap-1 h-10">
                    <div className="w-2 bg-purple-900/40 h-4 rounded-sm"></div>
                    <div className="w-2 bg-purple-800/60 h-6 rounded-sm"></div>
                    <div className="w-2 bg-purple-500 h-10 rounded-sm shadow-[0_0_10px_rgba(168,85,247,0.4)]"></div>
                    <div className="w-2 bg-purple-800/60 h-7 rounded-sm"></div>
                 </div>
             </div>

          </div>
        </div>
      </div>
    </section>
  );
}
