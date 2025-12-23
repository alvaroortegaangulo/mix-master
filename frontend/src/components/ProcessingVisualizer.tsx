"use client";

import { useEffect, useState } from "react";

type ProcessingVisualizerProps = {
  stageKey: string;
  progress: number;
  description?: string;
};

// Map stages to visual themes
const getVisualMode = (stageKey: string) => {
  if (stageKey.startsWith("S0") || stageKey.startsWith("S1")) return "analysis";
  if (stageKey.includes("PHASE") || stageKey.includes("ALIGNMENT")) return "alignment";
  if (stageKey.includes("EQ") || stageKey.includes("TONAL") || stageKey.includes("SPECTRAL")) return "spectral";
  if (stageKey.includes("DYNAMICS") || stageKey.includes("LIMIT")) return "dynamics";
  if (stageKey.includes("MASTER")) return "mastering";
  return "analysis"; // default
};

const LOG_MESSAGES: Record<string, string[]> = {
  analysis: [
    "Initializing audio context...",
    "Loading librosa.core...",
    "Computing STFT (n_fft=2048)...",
    "Detecting zero-crossings...",
    "Analyzing dynamic range...",
    "Calculating LUFS integrated...",
    "Extracting transients...",
    "Checking sample rate consistency...",
    "Validating codec compatibility...",
    "Building silence-map...",
    "Sweeping headroom scan...",
  ],
  alignment: [
    "Correlating stereo channels...",
    "Detecting phase cancellation...",
    "Computing cross-correlation function...",
    "Adjusting time offset (ms)...",
    "Aligning polarity...",
    "Verifying mono compatibility...",
    "Tracing transient envelopes...",
    "Balancing mid/side energy...",
  ],
  spectral: [
    "Computing Mel-spectrogram...",
    "Detecting resonant frequencies...",
    "Applying dynamic EQ filters...",
    "Balancing spectral tilt...",
    "Checking pink noise reference...",
    "Optimizing low-end coherence...",
    "Scanning harmonic content...",
    "Aligning formant peaks...",
  ],
  dynamics: [
    "Measuring crest factor...",
    "Setting compressor threshold...",
    "Calculating attack/release times...",
    "Applying makeup gain...",
    "Smoothing envelopes...",
    "Detecting peaks > -1dBTP...",
    "Tapering transients...",
    "Calibrating transient shaper...",
  ],
  mastering: [
    "Finalizing limiting stage...",
    "Dithering to 16-bit...",
    "Checking True Peak compliance...",
    "Maximizing loudness...",
    "Rendering final mixdown...",
    "Tagging metadata...",
    "Documenting session cues...",
    "Ensuring export sanity checks...",
  ]
};

const shuffleLogs = (logs: string[]) => {
  return [...logs].sort(() => Math.random() - 0.5);
};

export function ProcessingVisualizer({ stageKey, progress, description }: ProcessingVisualizerProps) {
  const mode = getVisualMode(stageKey || "");
  const [logs, setLogs] = useState<string[]>([]);

  // Log simulation
  useEffect(() => {
    const baseLogs = LOG_MESSAGES[mode] || LOG_MESSAGES["analysis"];
    let logQueue = shuffleLogs(baseLogs);
    let index = 0;
    setLogs([]); // Reset on mode change

    const getNextLog = () => {
      if (index >= logQueue.length) {
        logQueue = shuffleLogs(baseLogs);
        index = 0;
      }
      return logQueue[index++];
    };

    const interval = setInterval(() => {
      const msg = getNextLog();
      const time = new Date().toISOString().split("T")[1].slice(0, 8);
      const logLine = `[${time}] ${msg}`;

      setLogs(prev => {
        const next = [...prev, logLine];
        return next.slice(-6); // Keep last 6 lines
      });
    }, 800);

    return () => clearInterval(interval);
  }, [mode]);

  return (
    <div className="w-full h-full flex flex-col items-center justify-center p-6 relative overflow-hidden rounded-xl bg-slate-950 border border-slate-800">

      {/* Background Grid Effect */}
      <div className="absolute inset-0 bg-[linear-gradient(rgba(15,23,42,0.9)_2px,transparent_2px),linear-gradient(90deg,rgba(15,23,42,0.9)_2px,transparent_2px)] bg-[size:30px_30px] opacity-20 pointer-events-none"></div>

      {/* Visual Animation Container */}
      <div className="relative w-full h-40 mb-6 flex items-center justify-center">

        {/* SPECTRAL / EQ MODE */}
        {(mode === "spectral" || mode === "mastering") && (
           <div className="flex items-end justify-center gap-1 h-32 w-full px-8">
             {Array.from({ length: 20 }).map((_, i) => (
               <div
                 key={i}
                 className="w-1.5 bg-teal-500 rounded-t-sm shadow-[0_0_10px_rgba(20,184,166,0.5)]"
                 style={{
                   height: "20%",
                   animation: `equalizer 1.5s infinite ease-in-out`,
                   animationDelay: `${i * 0.1}s`
                 }}
               />
             ))}
             <style jsx>{`
               @keyframes equalizer {
                 0% { height: 20%; opacity: 0.5; }
                 50% { height: 90%; opacity: 1; filter: brightness(1.5); }
                 100% { height: 20%; opacity: 0.5; }
               }
             `}</style>
           </div>
        )}

        {/* ANALYSIS / CODE MODE */}
        {(mode === "analysis" || mode === "alignment") && (
            <div className="relative w-full max-w-xs h-32">
                 {/* Scanner Line */}
                 <div className="absolute top-0 left-0 w-full h-0.5 bg-teal-400 shadow-[0_0_15px_rgba(45,212,191,1)] z-10 animate-[scan_2s_linear_infinite]" />

                 {/* Waveform representation */}
                 <div className="flex items-center justify-center gap-0.5 h-full opacity-60">
                    {Array.from({ length: 40 }).map((_, i) => (
                        <div
                            key={i}
                            className="w-1 bg-slate-600 rounded-full"
                            style={{
                                height: `${Math.sin(i * 0.5) * 40 + 50}%`,
                            }}
                        />
                    ))}
                 </div>
                 <style jsx>{`
                    @keyframes scan {
                        0% { top: 0%; opacity: 0; }
                        10% { opacity: 1; }
                        90% { opacity: 1; }
                        100% { top: 100%; opacity: 0; }
                    }
                 `}</style>
            </div>
        )}

        {/* DYNAMICS MODE */}
        {mode === "dynamics" && (
            <div className="relative w-40 h-40 rounded-full border-4 border-slate-800 flex items-center justify-center">
                 <div className="absolute inset-0 rounded-full border-4 border-t-teal-500 border-r-transparent border-b-transparent border-l-transparent animate-spin"></div>
                 <div className="text-2xl font-mono font-bold text-teal-400 animate-pulse">
                    COMP
                 </div>
                 <div className="absolute inset-2 rounded-full border border-teal-500/20 animate-ping"></div>
            </div>
        )}
      </div>

      {/* Terminal Output */}
      <div className="w-full bg-black/50 rounded-lg p-3 font-mono text-[10px] text-teal-500/80 border border-slate-800 h-24 overflow-hidden relative shadow-inner">
         <div className="absolute inset-0 pointer-events-none bg-gradient-to-b from-transparent via-transparent to-black/80"></div>
         <div className="flex flex-col justify-end h-full">
            {logs.map((log, i) => (
                <div key={i} className="truncate animate-[fadeIn_0.3s_ease-out]">
                    <span className="text-slate-500 mr-2">{">"}</span>
                    {log}
                </div>
            ))}
         </div>
      </div>

      {/* Progress Bar & Stage Name */}
      <div className="w-full mt-6">
         <div className="flex justify-between items-center mb-2">
            <h3 className="text-xs font-bold uppercase tracking-wider text-teal-400">
                {description || "Processing..."}
            </h3>
            <span className="text-xs font-mono text-teal-200">{Math.round(progress)}%</span>
         </div>
         <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
             <div
                className="h-full bg-teal-500 shadow-[0_0_10px_rgba(20,184,166,0.8)] transition-all duration-300"
                style={{ width: `${progress}%` }}
             />
         </div>
      </div>

    </div>
  );
}
