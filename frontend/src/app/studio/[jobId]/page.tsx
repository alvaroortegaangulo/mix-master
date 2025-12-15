"use client";

import { useEffect, useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { fetchJobReport, getBackendBaseUrl, signFileUrl } from "@/lib/mixApi";
import { AuthModal } from "@/components/AuthModal";
import WaveSurfer from 'wavesurfer.js';
import {
  PlayIcon,
  PauseIcon,
  BackwardIcon,
  SpeakerWaveIcon,
  ArrowPathIcon,
  MusicalNoteIcon,
  AdjustmentsHorizontalIcon,
  CpuChipIcon,
  StopIcon
} from "@heroicons/react/24/solid";

interface StemControl {
  fileName: string;
  name: string;
  volume: number;
  pan: number;
  mute: boolean;
  solo: boolean;
  eq: {
    low: number;
    mid: number;
    high: number;
  };
  compression: {
    threshold: number;
    ratio: number;
  };
  url?: string;
  status?: "idle" | "loading" | "ready" | "error";
}

export default function StudioPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [showAuthModal, setShowAuthModal] = useState(false);

  const [stems, setStems] = useState<StemControl[]>([]);
  const [selectedStemIndex, setSelectedStemIndex] = useState<number>(0);
  const [loadingStems, setLoadingStems] = useState(true);
  const [rendering, setRendering] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [masterVolume, setMasterVolume] = useState(0.8);
  const selectedStem = stems[selectedStemIndex];

  const waveformRef = useRef<HTMLDivElement>(null);
  const wavesurferRef = useRef<WaveSurfer | null>(null);

  const audioContextRef = useRef<AudioContext | null>(null);
  const sourceNodesRef = useRef<Map<string, AudioBufferSourceNode>>(new Map());
  const gainNodesRef = useRef<Map<string, GainNode>>(new Map());
  const audioBuffersRef = useRef<Map<string, AudioBuffer>>(new Map());
  const startTimeRef = useRef<number>(0);
  const pauseTimeRef = useRef<number>(0);

  const stopAllSources = () => {
      sourceNodesRef.current.forEach((node) => {
          try { node.stop(); } catch (e) { /* noop */ }
      });
      sourceNodesRef.current.clear();
  };

  useEffect(() => {
    if (!authLoading && !user) {
      setShowAuthModal(true);
    }
  }, [authLoading, user]);

  useEffect(() => {
    if (typeof window !== "undefined" && !audioContextRef.current) {
      try {
        audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
        console.log("Studio: AudioContext initialized");
      } catch (e) {
        console.error("Studio: AudioContext init error", e);
      }
    }
    return () => {
        audioContextRef.current?.close();
    };
  }, []);

  useEffect(() => {
    if (!jobId || !user) return;

    let cancelled = false;

    async function load() {
      console.log("Studio: Starting load stems (metadata only)...");
      try {
        setLoadingStems(true);
        stopAllSources();
        audioBuffersRef.current.clear();
        gainNodesRef.current.clear();
        pauseTimeRef.current = 0;
        setIsPlaying(false);
        setCurrentTime(0);
        const baseUrl = getBackendBaseUrl();
        console.log("Studio: Fetching stems from", baseUrl);

        const res = await fetch(`${baseUrl}/jobs/${jobId}/stems`, {
          headers: {
            "X-API-Key": process.env.NEXT_PUBLIC_MIXMASTER_API_KEY || "",
          },
        });
        console.log("Studio: Stems response", res.status);

        let stemFiles: string[] = [];
        if (res.ok) {
          const data = await res.json();
          stemFiles = Array.isArray(data.stems) ? data.stems : [];
        } else {
          stemFiles = ["vocals.wav", "drums.wav", "bass.wav", "other.wav"];
        }
        console.log("Studio: Stems list", stemFiles);

        const newStems: StemControl[] = stemFiles.map((file) => ({
          fileName: file,
          name:
            file
              .replace(".wav", "")
              .replace(/_/g, " ")
              .replace("S11", "")
              .replace("S10", "")
              .trim() || file,
          volume: 0,
          pan: 0,
          mute: false,
          solo: false,
          eq: { low: 0, mid: 0, high: 0 },
          compression: { threshold: -20, ratio: 2 },
          url: undefined,
          status: "idle",
        }));

        if (!cancelled) {
          setStems(newStems);
          setSelectedStemIndex((idx) =>
            Math.min(Math.max(idx, 0), Math.max(newStems.length - 1, 0)),
          );
        }
      } catch (err) {
        console.error("Error loading stems:", err);
      } finally {
        console.log("Studio: Load complete, setting loadingStems false");
        setLoadingStems(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [jobId, user]);

  useEffect(() => {
    const ctx = audioContextRef.current;
    const stem = selectedStem;
    if (!ctx || !jobId || !user || !stem) return;
    if (stem.status === "loading") return;
    if (stem.url && audioBuffersRef.current.has(stem.fileName)) {
        const buf = audioBuffersRef.current.get(stem.fileName);
        if (buf) setDuration(buf.duration);
        return;
    }

    let cancelled = false;

    const loadStem = async () => {
        try {
            setStems(prev => prev.map((s, i) => i === selectedStemIndex ? { ...s, status: "loading" } : s));

            let signedUrl = await signFileUrl(jobId, `S12_SEPARATE_STEMS/${stem.fileName}`);
            let resp = await fetch(signedUrl);
            if (!resp.ok) {
                console.log("Studio: S12 fetch failed, trying S0", stem.fileName);
                signedUrl = await signFileUrl(jobId, `S0_SESSION_FORMAT/${stem.fileName}`);
                resp = await fetch(signedUrl);
            }

            if (!resp.ok) {
                throw new Error(`Failed to fetch stem ${stem.fileName}: ${resp.status} ${resp.statusText}`);
            }

            const ab = await resp.arrayBuffer();
            const decoded = await ctx.decodeAudioData(ab.slice(0));
            if (cancelled) return;

            audioBuffersRef.current.set(stem.fileName, decoded);
            const blob = new Blob([ab], { type: "audio/wav" });
            const blobUrl = URL.createObjectURL(blob);

            setStems(prev => prev.map((s, i) => i === selectedStemIndex ? { ...s, url: blobUrl, status: "ready" } : s));
            setDuration(decoded.duration);
        } catch (err) {
            if (!cancelled) {
                console.error("Failed to load stem", stem.fileName, err);
                setStems(prev => prev.map((s, i) => i === selectedStemIndex ? { ...s, status: "error" } : s));
            }
        }
    };

    loadStem();
    return () => { cancelled = true; };
  }, [jobId, user, selectedStemIndex, selectedStem?.fileName, selectedStem?.status, selectedStem?.url]);

  useEffect(() => {
      stopAllSources();
      setIsPlaying(false);
      setCurrentTime(0);
      pauseTimeRef.current = 0;
      startTimeRef.current = audioContextRef.current?.currentTime || 0;
  }, [selectedStemIndex]);

  useEffect(() => {
    if (!waveformRef.current || stems.length === 0) return;

    if (!selectedStem?.url) return;

    if (wavesurferRef.current) {
        wavesurferRef.current.destroy();
    }

    try {
        wavesurferRef.current = WaveSurfer.create({
          container: waveformRef.current,
          waveColor: '#334155',
          progressColor: '#10b981',
          cursorColor: '#fbbf24',
          barWidth: 2,
          barGap: 3,
          barRadius: 3,
          height: 300,
          normalize: true,
          url: selectedStem.url,
          interact: false,
        });

        wavesurferRef.current.on('ready', () => {
           if (wavesurferRef.current) {
               wavesurferRef.current.setTime(currentTime);
           }
        });
    } catch (e) {
        console.error("WaveSurfer init error", e);
    }

    return () => {
        wavesurferRef.current?.destroy();
    };
  }, [selectedStemIndex, selectedStem?.url]);

  useEffect(() => {
     if (wavesurferRef.current && isPlaying) {
         wavesurferRef.current.setVolume(0);
         if (!wavesurferRef.current.isPlaying()) {
             wavesurferRef.current.play();
         }
     } else if (wavesurferRef.current) {
         wavesurferRef.current.pause();
         wavesurferRef.current.setTime(currentTime);
     }
  }, [isPlaying]);

  const togglePlay = async () => {
      const ctx = audioContextRef.current;
      if (!ctx || !selectedStem) return;

      if (ctx.state === 'suspended') await ctx.resume();

      if (isPlaying) {
          stopAllSources();
          pauseTimeRef.current = ctx.currentTime - startTimeRef.current;
          setIsPlaying(false);
          return;
      }

      const buffer = audioBuffersRef.current.get(selectedStem.fileName);
      if (!buffer) return;

      stopAllSources();

      const source = ctx.createBufferSource();
      source.buffer = buffer;

      const gain = ctx.createGain();
      const vol = Math.pow(10, selectedStem.volume / 20) * masterVolume;
      gain.gain.value = selectedStem.mute ? 0 : vol;

      source.connect(gain);
      gain.connect(ctx.destination);

      const offset = pauseTimeRef.current % buffer.duration;
      startTimeRef.current = ctx.currentTime - offset;
      source.start(0, offset);
      source.onended = () => {
          sourceNodesRef.current.delete(selectedStem.fileName);
          setIsPlaying(false);
      };

      sourceNodesRef.current.set(selectedStem.fileName, source);
      gainNodesRef.current.set(selectedStem.fileName, gain);

      setIsPlaying(true);
  };

  useEffect(() => {
      let raf: number;
      const update = () => {
          if (isPlaying && audioContextRef.current) {
              const now = audioContextRef.current.currentTime - startTimeRef.current;
              setCurrentTime(now);
              raf = requestAnimationFrame(update);
          }
      };
      if (isPlaying) update();
      return () => cancelAnimationFrame(raf);
  }, [isPlaying]);

  useEffect(() => {
      stems.forEach(stem => {
          const node = gainNodesRef.current.get(stem.fileName);
          if (node) {
              const vol = Math.pow(10, stem.volume / 20) * masterVolume;
              node.gain.setTargetAtTime(stem.mute ? 0 : vol, audioContextRef.current!.currentTime, 0.05);
          }
      });
  }, [stems, masterVolume]);


  const handleRender = async () => {
      setRendering(true);
      try {
          const corrections = stems.map(s => ({
              name: s.name,
              volume_db: s.volume,
              pan: s.pan,
              eq: s.eq,
              compression: s.compression,
              mute: s.mute,
              solo: s.solo
          }));

          const res = await fetch(`${getBackendBaseUrl()}/jobs/${jobId}/correction`, {
              method: 'POST',
              headers: {
                  'Content-Type': 'application/json',
                  "X-API-Key": process.env.NEXT_PUBLIC_MIXMASTER_API_KEY || "",
              },
              body: JSON.stringify({ corrections })
          });

          if (!res.ok) throw new Error("Correction failed");
          router.push(`/`);
      } catch (err) {
          console.error(err);
          alert("Error sending corrections");
      } finally {
          setRendering(false);
      }
  };

  const updateStem = (index: number, updates: Partial<StemControl>) => {
      setStems(prev => {
          const next = [...prev];
          next[index] = { ...next[index], ...updates };
          return next;
      });
  };

  if (authLoading) return <div className="h-screen bg-[#0f111a]"></div>;

  if (!user) {
      return (
        <div className="h-screen bg-[#0f111a] flex items-center justify-center text-slate-500">
            <AuthModal isOpen={true} onClose={() => router.push('/')} />
        </div>
      );
  }

  if (loadingStems) return <div className="h-screen bg-[#0f111a] flex items-center justify-center text-emerald-500 font-mono">LOADING STUDIO ASSETS...</div>;

  return (
    <div className="flex flex-col h-screen bg-[#0f111a] text-slate-300 font-sans overflow-hidden selection:bg-emerald-500/30">

      <header className="h-14 bg-[#1e293b]/50 border-b border-white/5 flex items-center justify-between px-4 shrink-0 backdrop-blur-md">
         <div className="flex items-center gap-6">
             <div className="flex items-center gap-2 text-emerald-400 font-bold tracking-wider">
                 <AdjustmentsHorizontalIcon className="w-5 h-5" />
                 <span>Piroola Studio</span>
             </div>
             <div className="h-6 w-px bg-white/10 mx-2"></div>
             <div className="flex flex-col">
                 <span className="text-xs text-slate-500 uppercase tracking-wider">Project</span>
                 <span className="text-sm font-medium text-white">Neon Nights Demo</span>
             </div>
             <div className="flex items-center gap-4 ml-8 text-xs font-mono text-slate-400 bg-black/20 px-3 py-1 rounded border border-white/5">
                 <div className="flex items-center gap-2">
                     <span className="text-emerald-500">124</span> BPM
                 </div>
                 <div className="w-px h-3 bg-white/10"></div>
                 <div className="flex items-center gap-2">
                     <span className="text-emerald-500">4/4</span>
                 </div>
             </div>
         </div>
         <div className="flex items-center gap-4">
             <button onClick={() => router.back()} className="px-3 py-1.5 text-xs font-medium text-slate-400 hover:text-white border border-white/10 rounded hover:bg-white/5 transition-colors">
                 Exit
             </button>
             <button
                onClick={handleRender}
                disabled={rendering}
                className="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold rounded shadow-lg shadow-emerald-900/20 transition-all flex items-center gap-2"
             >
                {rendering ? <ArrowPathIcon className="w-3 h-3 animate-spin" /> : null}
                {rendering ? "EXPORTING..." : "EXPORT"}
             </button>
             <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 border border-white/10"></div>
         </div>
      </header>

      <div className="flex flex-1 overflow-hidden">

          <aside className="w-72 bg-[#11131f] border-r border-white/5 flex flex-col shrink-0">
             <div className="p-4 border-b border-white/5 flex justify-between items-center">
                 <h2 className="text-xs font-bold text-slate-500 tracking-widest uppercase">Tracks ({stems.length})</h2>
                 <button className="text-slate-500 hover:text-emerald-400">+</button>
             </div>
             <div className="flex-1 overflow-y-auto custom-scrollbar p-2 space-y-2">
                 {stems.map((stem, i) => (
                     <div
                        key={i}
                        onClick={() => setSelectedStemIndex(i)}
                        className={`p-3 rounded-lg border transition-all cursor-pointer group ${
                            selectedStemIndex === i
                            ? 'bg-slate-800/80 border-emerald-500/30 shadow-lg shadow-emerald-900/10'
                            : 'bg-[#161b2e] border-transparent hover:bg-slate-800 hover:border-slate-700'
                        }`}
                     >
                         <div className="flex items-center justify-between mb-2">
                             <div className="flex items-center gap-2">
                                 <div className={`w-2 h-2 rounded-full ${selectedStemIndex === i ? 'bg-emerald-400' : 'bg-slate-600'}`}></div>
                                 <span className={`text-sm font-medium truncate max-w-[120px] ${selectedStemIndex === i ? 'text-white' : 'text-slate-400 group-hover:text-slate-300'}`}>
                                     {stem.name}
                                 </span>
                             </div>
                             <div className="flex gap-1">
                                 <button
                                    onClick={(e) => { e.stopPropagation(); updateStem(i, { mute: !stem.mute }); }}
                                    className={`w-5 h-5 text-[10px] font-bold flex items-center justify-center rounded ${stem.mute ? 'bg-red-500 text-white' : 'bg-slate-700 text-slate-400 hover:bg-slate-600'}`}
                                 >M</button>
                                 <button
                                    onClick={(e) => { e.stopPropagation(); updateStem(i, { solo: !stem.solo }); }}
                                    className={`w-5 h-5 text-[10px] font-bold flex items-center justify-center rounded ${stem.solo ? 'bg-yellow-500 text-black' : 'bg-slate-700 text-slate-400 hover:bg-slate-600'}`}
                                 >S</button>
                             </div>
                         </div>
                         <div className="flex items-center gap-2">
                             <SpeakerWaveIcon className="w-3 h-3 text-slate-600" />
                             <input
                                type="range" min="-60" max="12" step="0.1"
                                value={stem.volume}
                                onClick={(e) => e.stopPropagation()}
                                onChange={(e) => updateStem(i, { volume: parseFloat(e.target.value) })}
                                className="w-full h-1 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-emerald-500"
                             />
                         </div>
                     </div>
                 ))}
             </div>
          </aside>

          <main className="flex-1 flex flex-col relative bg-[#0f111a]">
             <div className="absolute inset-0 pointer-events-none opacity-5"
                style={{
                    backgroundImage: 'linear-gradient(to right, #ffffff 1px, transparent 1px), linear-gradient(to bottom, #ffffff 1px, transparent 1px)',
                    backgroundSize: '40px 40px'
                }}>
             </div>

             <div className="h-8 border-b border-white/5 flex text-[10px] font-mono text-slate-600 items-center overflow-hidden select-none">
                 {Array.from({length: 20}).map((_, i) => (
                     <div key={i} className="flex-1 border-r border-white/5 pl-1">{i+1}.1</div>
                 ))}
             </div>

             <div className="flex-1 relative flex items-center justify-center p-10">
                 <div className="absolute top-0 bottom-0 left-1/2 w-0.5 bg-yellow-400 z-10 shadow-[0_0_10px_rgba(250,204,21,0.5)]"></div>

                 <div ref={waveformRef} className="w-full opacity-80" />

                 {!selectedStem?.url && (
                     <div className="text-slate-600 font-mono">Select a track to view waveform</div>
                 )}
             </div>

             <div className="h-20 bg-[#11131f] border-t border-white/5 px-6 flex items-center justify-between shrink-0 z-20">

                 <div className="flex flex-col gap-1 w-48">
                     <div className="flex justify-between text-[10px] text-slate-500 font-mono">
                         <span>MASTER OUT</span>
                         <span>-3.2 dB</span>
                     </div>
                     <div className="h-2 bg-slate-800 rounded-full overflow-hidden relative">
                         <div className="absolute top-0 left-0 bottom-0 bg-gradient-to-r from-emerald-600 to-emerald-400 w-[70%]"></div>
                     </div>
                 </div>

                 <div className="flex flex-col items-center gap-2">
                     <div className="text-xl font-mono text-slate-300 tabular-nums tracking-widest">
                         {formatTime(currentTime)}
                     </div>
                    <div className="flex items-center gap-4">
                       <button className="text-slate-500 hover:text-white transition-colors"><ArrowPathIcon className="w-4 h-4" /></button>
                        <button onClick={() => { stopAllSources(); setIsPlaying(false); setCurrentTime(0); startTimeRef.current = audioContextRef.current?.currentTime || 0; pauseTimeRef.current = 0; }} className="text-slate-500 hover:text-white transition-colors"><StopIcon className="w-4 h-4" /></button>
                        <button
                            onClick={togglePlay}
                            className="w-10 h-10 rounded-full bg-white text-black flex items-center justify-center hover:scale-105 transition-transform shadow-[0_0_15px_rgba(255,255,255,0.2)]"
                        >
                            {isPlaying ? <PauseIcon className="w-5 h-5" /> : <PlayIcon className="w-5 h-5 ml-0.5" />}
                        </button>
                        <button className="text-red-500 hover:text-red-400 transition-colors w-4 h-4 rounded-full border border-current flex items-center justify-center">
                            <div className="w-2 h-2 bg-current rounded-full"></div>
                        </button>
                     </div>
                 </div>

                 <div className="w-48 flex items-center gap-3">
                     <SpeakerWaveIcon className="w-4 h-4 text-slate-500" />
                     <input
                        type="range" min="0" max="1" step="0.01"
                        value={masterVolume}
                        onChange={(e) => setMasterVolume(parseFloat(e.target.value))}
                        className="w-full h-1 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-white"
                     />
                 </div>
             </div>
          </main>

          <aside className="w-80 bg-[#161b2e] border-l border-white/5 flex flex-col shrink-0 p-6 space-y-6 overflow-y-auto">

              <div>
                  <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-2">Selected Channel</div>
                  <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded bg-emerald-500/10 flex items-center justify-center text-emerald-500">
                          <MusicalNoteIcon className="w-5 h-5" />
                      </div>
                      <h2 className="text-xl font-bold text-white truncate" title={selectedStem?.name}>{selectedStem?.name || "No Track Selected"}</h2>
                  </div>
              </div>

              {selectedStem && (
                  <>
                    <div className="bg-[#1e2336] rounded-xl p-4 border border-white/5 shadow-lg">
                        <div className="flex justify-between items-center mb-4">
                            <span className="text-xs font-bold text-slate-300">Parametric EQ</span>
                            <div className="w-8 h-4 bg-emerald-500/20 rounded-full relative cursor-pointer border border-emerald-500/30">
                                <div className="absolute right-0.5 top-0.5 w-3 h-3 bg-emerald-400 rounded-full shadow-lg"></div>
                            </div>
                        </div>
                        <div className="h-20 bg-[#11131f] rounded-lg mb-4 border border-white/5 relative overflow-hidden">
                            <div className="absolute inset-0 bg-gradient-to-t from-emerald-500/5 to-transparent"></div>
                            <svg className="absolute inset-0 w-full h-full text-emerald-500/30" preserveAspectRatio="none">
                                <path d="M0,80 C20,80 40,60 80,60 C120,60 140,80 160,80 C200,80 220,40 260,40 C300,40 320,80 320,80 L320,80 L0,80 Z" fill="currentColor" />
                            </svg>
                        </div>

                        <div className="flex justify-between px-2">
                             <Knob label="LOW" value={selectedStem.eq.low} min={-12} max={12} onChange={(v) => updateStem(selectedStemIndex, { eq: {...selectedStem.eq, low: v}})} />
                             <Knob label="MID" value={selectedStem.eq.mid} min={-12} max={12} onChange={(v) => updateStem(selectedStemIndex, { eq: {...selectedStem.eq, mid: v}})} />
                             <Knob label="HIGH" value={selectedStem.eq.high} min={-12} max={12} onChange={(v) => updateStem(selectedStemIndex, { eq: {...selectedStem.eq, high: v}})} />
                        </div>
                    </div>

                    <div className="bg-[#1e2336] rounded-xl p-4 border border-white/5 shadow-lg">
                        <div className="flex justify-between items-center mb-4">
                            <span className="text-xs font-bold text-slate-300">Compressor</span>
                            <div className="w-8 h-4 bg-emerald-500/20 rounded-full relative cursor-pointer border border-emerald-500/30">
                                <div className="absolute right-0.5 top-0.5 w-3 h-3 bg-emerald-400 rounded-full shadow-lg"></div>
                            </div>
                        </div>

                        <div className="flex justify-around mb-4">
                             <Knob label="THRESH" value={selectedStem.compression.threshold} min={-60} max={0} onChange={(v) => updateStem(selectedStemIndex, { compression: {...selectedStem.compression, threshold: v}})} />
                             <Knob label="RATIO" value={selectedStem.compression.ratio} min={1} max={20} onChange={(v) => updateStem(selectedStemIndex, { compression: {...selectedStem.compression, ratio: v}})} />
                        </div>

                        <div className="flex items-center gap-2 text-[10px] text-slate-500 font-mono">
                            <span>GR</span>
                            <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden flex justify-end">
                                <div className="w-[10%] bg-red-500 h-full rounded-l-full"></div>
                            </div>
                        </div>
                    </div>

                    <div className="bg-[#1e2336] rounded-xl p-4 border border-purple-500/20 shadow-[0_0_20px_rgba(168,85,247,0.05)]">
                        <div className="flex items-center gap-2 mb-3 text-purple-400">
                            <CpuChipIcon className="w-4 h-4" />
                            <span className="text-xs font-bold uppercase tracking-wider">AI Insight</span>
                        </div>
                        <p className="text-xs text-slate-400 leading-relaxed mb-4">
                            Detected muddiness in low-mids (250Hz). Recommendation: Cut -2dB or sidechain to kick drum.
                        </p>
                        <button className="w-full py-2 bg-purple-600 hover:bg-purple-500 text-white text-xs font-bold rounded shadow-lg shadow-purple-900/40 transition-colors">
                            Apply Fix
                        </button>
                    </div>
                  </>
              )}
          </aside>
      </div>

      <AuthModal isOpen={showAuthModal} onClose={() => setShowAuthModal(false)} />
    </div>
  );
}

function formatTime(s: number) {
    const min = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    const ms = Math.floor((s % 1) * 100);
    return `${min.toString().padStart(2,'0')}:${sec.toString().padStart(2, '0')}.${ms.toString().padStart(2, '0')}`;
}

function Knob({ label, value, min, max, onChange }: { label: string, value: number, min: number, max: number, onChange: (v: number) => void }) {
    const [dragging, setDragging] = useState(false);
    const startYRef = useRef(0);
    const startValRef = useRef(0);

    const handleMouseDown = (e: React.MouseEvent) => {
        setDragging(true);
        startYRef.current = e.clientY;
        startValRef.current = value;

        const handleMove = (ev: MouseEvent) => {
            const dy = startYRef.current - ev.clientY;
            const range = max - min;
            const delta = (dy / 150) * range;
            let newVal = startValRef.current + delta;
            if (newVal < min) newVal = min;
            if (newVal > max) newVal = max;
            onChange(newVal);
        };
        const handleUp = () => {
            setDragging(false);
            window.removeEventListener('mousemove', handleMove);
            window.removeEventListener('mouseup', handleUp);
        };
        window.addEventListener('mousemove', handleMove);
        window.addEventListener('mouseup', handleUp);
    };

    const pct = (value - min) / (max - min);
    const rotation = -135 + (pct * 270);

    return (
        <div className="flex flex-col items-center gap-2 group select-none">
            <div
                onMouseDown={handleMouseDown}
                className="w-12 h-12 rounded-full bg-[#11131f] relative cursor-ns-resize shadow-[inset_0_2px_4px_rgba(0,0,0,0.5)] border border-slate-700 hover:border-slate-500 transition-colors"
            >
                <div
                    className="absolute top-1/2 left-1/2 w-0.5 h-4 bg-emerald-400 origin-bottom -translate-x-1/2 -translate-y-full rounded-full shadow-[0_0_5px_rgba(52,211,153,0.5)]"
                    style={{ transform: `translate(-50%, -50%) rotate(${rotation}deg)` }}
                ></div>
            </div>
            <div className="text-center">
                <span className="text-[9px] font-bold text-slate-500 block mb-0.5 tracking-wider">{label}</span>
                <span className={`text-[10px] font-mono transition-colors ${dragging ? 'text-emerald-400' : 'text-slate-600'}`}>{value.toFixed(1)}</span>
            </div>
        </div>
    );
}
