"use client";

import { useEffect, useState } from "react";

type ProcessingVisualizerProps = {
  stageKey: string;
  progress: number;
  description?: string;
};

// Map stages to visual themes
const getVisualMode = (stageKey: string) => {
  const key = (stageKey || "").toUpperCase();

  if (!key) return "analysis";
  if (key.includes("REPORT")) return "reporting";
  if (key.includes("MASTER")) return "mastering";
  if (key.includes("COLOR")) return "color";
  if (key.includes("SPACE") || key.includes("DEPTH") || key.includes("REVERB")) return "space";
  if (key.includes("ROUTING") || key.includes("STATIC_MIX")) return "routing";
  if (key.includes("PHASE") || key.includes("POLARITY") || key.includes("ALIGNMENT") || key.includes("GROUP_PHASE")) return "alignment";
  if (key.includes("KEY_DETECTION") || key.includes("VOX_TUNING")) return "tuning";
  if (key.includes("HEADROOM") || key.includes("LOUDNESS") || key.includes("LEVEL")) return "level";
  if (key.includes("SPECTRAL") || key.includes("EQ") || key.includes("TONAL") || key.includes("HPF") || key.includes("LPF") || key.includes("RESONANCE")) return "spectral";
  if (key.includes("DYNAMICS") || key.includes("COMP") || key.includes("LIMIT")) return "dynamics";
  if (key.startsWith("S0") || key.includes("SESSION_FORMAT") || key.includes("METADATA") || key.includes("INPUT") || key.includes("INITIALIZING")) return "metadata";
  if (key.includes("MANUAL")) return "routing";
  return "analysis"; // default
};

const LOG_MESSAGES: Record<string, string[]> = {
  metadata: [
    "Parsing session config...",
    "Reading stems manifest...",
    "Normalizing file headers...",
    "Checking bit depth...",
    "Tagging input metadata...",
    "Building session map...",
    "Validating channel layout...",
    "Caching stem profiles...",
  ],
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
  tuning: [
    "Estimating key center...",
    "Tracking pitch contour...",
    "Quantizing note targets...",
    "Aligning formant peaks...",
    "Detecting vibrato rate...",
    "Applying pitch curve...",
    "Smoothing transitions...",
    "Rebuilding harmonics...",
  ],
  routing: [
    "Assigning stems to buses...",
    "Building aux routing matrix...",
    "Normalizing bus gains...",
    "Checking summing headroom...",
    "Applying pan law...",
    "Locking routing graph...",
    "Syncing subgroup phase...",
    "Storing routing snapshot...",
  ],
  space: [
    "Designing reverb tail...",
    "Estimating room size...",
    "Placing sources in depth...",
    "Balancing early reflections...",
    "Tuning decay time...",
    "Shaping stereo width...",
    "Filtering reverb return...",
    "Rendering spatial field...",
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
  level: [
    "Measuring headroom...",
    "Calculating target gain...",
    "Adjusting mixbus level...",
    "Monitoring peaks...",
    "Applying trim automation...",
    "Validating LUFS window...",
    "Smoothing gain ramps...",
    "Writing level snapshot...",
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
  color: [
    "Driving harmonic enhancer...",
    "Measuring saturation curve...",
    "Applying tonal glue...",
    "Balancing even/odd harmonics...",
    "Checking THD window...",
    "Smoothing coloration...",
    "Restoring transients...",
    "Calibrating warmth...",
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
  ],
  reporting: [
    "Compiling stage metrics...",
    "Rendering summary charts...",
    "Writing report.json...",
    "Generating comparisons...",
    "Assembling snapshots...",
    "Verifying totals...",
    "Packaging results...",
    "Finalizing report...",
  ],
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
        {mode === "metadata" && (
          <div className="grid w-full max-w-md grid-cols-3 gap-3 px-2">
            {["WAV", "SR", "STEMS"].map((label, i) => (
              <div key={label} className="relative h-24 rounded-xl border border-slate-800 bg-slate-900/60 overflow-hidden">
                <div
                  className="absolute inset-x-3 top-4 h-1 rounded-full bg-teal-500/60 animate-pulse"
                  style={{ animationDelay: `${i * 0.2}s` }}
                />
                <div className="absolute inset-x-3 top-8 h-1 rounded-full bg-teal-500/20" />
                <div className="absolute inset-x-3 top-12 h-1 rounded-full bg-teal-500/10" />
                <div className="absolute left-3 bottom-3 text-[10px] font-mono text-teal-300">
                  {label}
                </div>
                <div className="absolute right-3 top-3">
                  <span className="absolute inline-flex h-2 w-2 animate-ping rounded-full bg-emerald-400/60" />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400" />
                </div>
              </div>
            ))}
          </div>
        )}

        {mode === "analysis" && (
          <div className="relative w-full max-w-xs h-32">
            <div
              className="absolute top-0 left-0 w-full h-0.5 bg-teal-400 shadow-[0_0_15px_rgba(45,212,191,1)] z-10"
              style={{ animation: "scan 2s linear infinite" }}
            />
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
          </div>
        )}

        {mode === "alignment" && (
          <div className="w-full max-w-sm px-2">
            <div className="flex items-center justify-between text-[10px] text-slate-500 mb-2">
              <span>L</span>
              <span>R</span>
            </div>
            <div className="grid grid-cols-2 gap-4 h-20">
              <div className="flex items-end gap-1 h-full">
                {Array.from({ length: 14 }).map((_, i) => (
                  <div
                    key={i}
                    className="w-1 bg-slate-600 rounded-full"
                    style={{ height: `${Math.sin(i * 0.6) * 35 + 50}%` }}
                  />
                ))}
              </div>
              <div className="flex items-end gap-1 h-full">
                {Array.from({ length: 14 }).map((_, i) => (
                  <div
                    key={i}
                    className="w-1 bg-slate-600 rounded-full"
                    style={{ height: `${Math.cos(i * 0.6) * 35 + 50}%` }}
                  />
                ))}
              </div>
            </div>
            <div className="mt-4">
              <div className="relative h-2 rounded-full bg-slate-800 overflow-hidden">
                <div className="absolute inset-0 bg-gradient-to-r from-rose-500/30 via-teal-400/50 to-emerald-500/30" />
                <div
                  className="absolute left-0 top-1/2 -translate-y-1/2 h-3 w-3 rounded-full bg-teal-400 shadow-[0_0_10px_rgba(45,212,191,0.8)]"
                  style={{ animation: "phaseDot 3s ease-in-out infinite" }}
                />
              </div>
            </div>
          </div>
        )}

        {mode === "tuning" && (
          <div className="relative w-full max-w-xs h-32 px-4">
            <div className="absolute inset-x-0 top-4 bottom-4 flex flex-col justify-between">
              {Array.from({ length: 7 }).map((_, i) => (
                <div key={i} className="h-px bg-slate-700/70" />
              ))}
            </div>
            <div className="absolute left-4 right-4 top-4 bottom-4">
              <div
                className="absolute left-0 h-3 w-3 rounded-full bg-amber-400 shadow-[0_0_10px_rgba(251,191,36,0.8)]"
                style={{ animation: "pitch 2.6s ease-in-out infinite" }}
              />
              <div
                className="absolute right-0 h-2 w-2 rounded-full bg-teal-400/80 shadow-[0_0_8px_rgba(45,212,191,0.7)]"
                style={{ animation: "pitchAlt 3.2s ease-in-out infinite" }}
              />
            </div>
          </div>
        )}

        {mode === "routing" && (
          <div className="relative w-full max-w-sm h-32">
            <svg className="absolute inset-0 h-full w-full" viewBox="0 0 320 120" fill="none">
              <path d="M40 30 H140" stroke="rgba(71,85,105,0.8)" strokeWidth="2" />
              <path d="M40 60 H140" stroke="rgba(71,85,105,0.8)" strokeWidth="2" />
              <path d="M40 90 H140" stroke="rgba(71,85,105,0.8)" strokeWidth="2" />
              <path d="M140 30 V90" stroke="rgba(71,85,105,0.8)" strokeWidth="2" />
              <path
                d="M140 60 H230"
                stroke="rgba(20,184,166,0.8)"
                strokeWidth="2"
                strokeDasharray="6 6"
                style={{ animation: "routeFlow 2.2s linear infinite" }}
              />
              <path
                d="M230 60 H280"
                stroke="rgba(20,184,166,0.8)"
                strokeWidth="2"
                strokeDasharray="6 6"
                style={{ animation: "routeFlow 2.2s linear infinite" }}
              />
              <circle cx="40" cy="30" r="6" fill="rgba(148,163,184,0.8)" />
              <circle cx="40" cy="60" r="6" fill="rgba(148,163,184,0.8)" />
              <circle cx="40" cy="90" r="6" fill="rgba(148,163,184,0.8)" />
              <circle cx="140" cy="60" r="8" fill="rgba(20,184,166,0.9)" />
              <circle cx="280" cy="60" r="7" fill="rgba(16,185,129,0.9)" />
            </svg>
            <div className="absolute left-[132px] top-[52px] h-4 w-4 rounded-full bg-teal-400/40 animate-ping" />
          </div>
        )}

        {mode === "space" && (
          <div className="relative w-40 h-40">
            <div
              className="absolute inset-0 rounded-full border border-teal-500/30"
              style={{ animation: "reverbPulse 3.2s ease-in-out infinite" }}
            />
            <div
              className="absolute inset-4 rounded-full border border-teal-500/40"
              style={{ animation: "reverbPulse 3.2s ease-in-out infinite", animationDelay: "0.6s" }}
            />
            <div
              className="absolute inset-8 rounded-full border border-teal-500/50"
              style={{ animation: "reverbPulse 3.2s ease-in-out infinite", animationDelay: "1.2s" }}
            />
            <div className="absolute inset-0 rounded-full bg-teal-500/10 blur-2xl" />
            <div className="absolute left-1/2 top-1/2 h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-teal-400 shadow-[0_0_12px_rgba(45,212,191,0.8)]" />
          </div>
        )}

        {mode === "spectral" && (
          <div className="flex items-end justify-center gap-1 h-32 w-full px-8">
            {Array.from({ length: 20 }).map((_, i) => (
              <div
                key={i}
                className="w-1.5 bg-teal-500 rounded-t-sm shadow-[0_0_10px_rgba(20,184,166,0.5)]"
                style={{
                  height: "20%",
                  animation: "equalizer 1.5s infinite ease-in-out",
                  animationDelay: `${i * 0.1}s`,
                }}
              />
            ))}
          </div>
        )}

        {mode === "level" && (
          <div className="flex items-end gap-6">
            <div className="flex flex-col-reverse gap-1 h-28 w-10 rounded-xl border border-slate-800 bg-slate-900/60 px-2 py-2">
              {Array.from({ length: 10 }).map((_, i) => {
                const color = i > 7 ? "bg-rose-500/70" : i > 5 ? "bg-amber-400/70" : "bg-emerald-500/70";
                return (
                  <div
                    key={i}
                    className={`h-2 rounded-sm ${color}`}
                    style={{ animation: "meterBlink 1.8s ease-in-out infinite", animationDelay: `${i * 0.12}s` }}
                  />
                );
              })}
            </div>
            <div className="flex flex-col justify-between h-28 text-[10px] text-slate-500">
              <span>0 dB</span>
              <span>-6</span>
              <span>-12</span>
              <span>-18</span>
              <span>-24</span>
            </div>
          </div>
        )}

        {mode === "dynamics" && (
          <div className="relative w-40 h-40 rounded-full border-4 border-slate-800 flex items-center justify-center">
            <div className="absolute inset-0 rounded-full border-4 border-t-teal-500 border-r-transparent border-b-transparent border-l-transparent animate-spin"></div>
            <div className="text-2xl font-mono font-bold text-teal-400 animate-pulse">
              COMP
            </div>
            <div className="absolute inset-2 rounded-full border border-teal-500/20 animate-ping"></div>
          </div>
        )}

        {mode === "color" && (
          <div className="relative w-full max-w-xs h-24 rounded-2xl overflow-hidden border border-slate-800 bg-slate-900/60">
            <div className="absolute inset-0 bg-gradient-to-r from-amber-500 via-rose-500 to-teal-400 opacity-80" />
            <div
              className="absolute inset-y-0 w-16 bg-white/20 blur-md"
              style={{ animation: "colorSweep 3s ease-in-out infinite" }}
            />
            <div className="absolute bottom-2 left-3 text-[10px] font-mono text-slate-900/70">
              Color
            </div>
          </div>
        )}

        {mode === "mastering" && (
          <div className="relative w-full max-w-sm h-28 rounded-2xl border border-slate-800 bg-slate-900/60 px-4 py-3 overflow-hidden">
            <div className="absolute left-0 right-0 top-1/3 border-t border-rose-500/60" />
            <div className="absolute left-4 right-4 bottom-3 flex items-end gap-1 h-16">
              {Array.from({ length: 24 }).map((_, i) => (
                <div
                  key={i}
                  className="w-1 rounded-t-sm bg-teal-400/70"
                  style={{
                    height: "20%",
                    animation: "limiter 1.8s ease-in-out infinite",
                    animationDelay: `${i * 0.07}s`,
                  }}
                />
              ))}
            </div>
            <div className="absolute right-4 top-3 text-[10px] font-mono text-rose-400">-1 dBTP</div>
          </div>
        )}

        {mode === "reporting" && (
          <div className="relative w-full max-w-xs h-28">
            <div className="absolute inset-0 rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
              <div className="h-2 w-2/3 bg-slate-700 rounded mb-2" />
              <div className="h-2 w-1/2 bg-slate-700 rounded" />
              <div className="mt-4 flex items-end gap-1 h-10">
                {Array.from({ length: 8 }).map((_, i) => (
                  <div
                    key={i}
                    className="w-2 rounded-sm bg-teal-500/70"
                    style={{
                      height: "30%",
                      animation: "reportBars 2s ease-in-out infinite",
                      animationDelay: `${i * 0.1}s`,
                    }}
                  />
                ))}
              </div>
              <div className="absolute top-3 right-3 h-5 w-5 rounded-full border border-emerald-400/60 text-emerald-400 flex items-center justify-center text-[10px]">
                OK
              </div>
            </div>
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

      <style jsx>{`
        @keyframes scan {
          0% { top: 0%; opacity: 0; }
          10% { opacity: 1; }
          90% { opacity: 1; }
          100% { top: 100%; opacity: 0; }
        }
        @keyframes equalizer {
          0% { height: 20%; opacity: 0.5; }
          50% { height: 90%; opacity: 1; filter: brightness(1.5); }
          100% { height: 20%; opacity: 0.5; }
        }
        @keyframes phaseDot {
          0% { left: 0%; }
          50% { left: calc(100% - 0.75rem); }
          100% { left: 0%; }
        }
        @keyframes pitch {
          0% { top: 70%; }
          50% { top: 20%; }
          100% { top: 70%; }
        }
        @keyframes pitchAlt {
          0% { top: 30%; }
          50% { top: 75%; }
          100% { top: 30%; }
        }
        @keyframes routeFlow {
          0% { stroke-dashoffset: 24; }
          100% { stroke-dashoffset: 0; }
        }
        @keyframes reverbPulse {
          0% { transform: scale(0.85); opacity: 0.25; }
          50% { transform: scale(1); opacity: 0.6; }
          100% { transform: scale(1.1); opacity: 0; }
        }
        @keyframes colorSweep {
          0% { left: -20%; opacity: 0.2; }
          50% { opacity: 0.6; }
          100% { left: 120%; opacity: 0.2; }
        }
        @keyframes meterBlink {
          0%, 100% { opacity: 0.25; }
          50% { opacity: 1; }
        }
        @keyframes limiter {
          0% { height: 20%; opacity: 0.4; }
          50% { height: 100%; opacity: 1; }
          100% { height: 20%; opacity: 0.4; }
        }
        @keyframes reportBars {
          0% { height: 30%; opacity: 0.5; }
          50% { height: 90%; opacity: 1; }
          100% { height: 30%; opacity: 0.5; }
        }
      `}</style>

    </div>
  );
}
