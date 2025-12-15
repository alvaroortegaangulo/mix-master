"use client";

import { useEffect, useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { getBackendBaseUrl, signFileUrl } from "@/lib/mixApi";
import { AuthModal } from "@/components/AuthModal";
import WaveSurfer from 'wavesurfer.js';
import {
  PlayIcon,
  PauseIcon,
  ArrowPathIcon,
  MusicalNoteIcon,
  AdjustmentsHorizontalIcon,
  StopIcon,
  ArrowDownTrayIcon,
  CheckIcon,
  XMarkIcon
} from "@heroicons/react/24/solid";

interface StemControl {
  name: string;
  volume: number;
  pan: number;
  mute: boolean;
  solo: boolean;
  eq: {
    low: number;
    mid: number;
    high: number;
    enabled: boolean;
  };
  compression: {
    threshold: number;
    ratio: number;
    enabled: boolean;
  };
  reverb: {
    amount: number;
    enabled: boolean;
  };
  url?: string;
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

  const waveformRef = useRef<HTMLDivElement>(null);
  const wavesurferRef = useRef<WaveSurfer | null>(null);

  const audioContextRef = useRef<AudioContext | null>(null);
  const sourceNodesRef = useRef<Map<string, AudioBufferSourceNode>>(new Map());
  const gainNodesRef = useRef<Map<string, GainNode>>(new Map());
  const audioBuffersRef = useRef<Map<string, AudioBuffer>>(new Map());
  const startTimeRef = useRef<number>(0);
  const pauseTimeRef = useRef<number>(0);

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
      console.log("Studio: Starting load stems...");
      try {
        setLoadingStems(true);
        const baseUrl = getBackendBaseUrl();
        console.log("Studio: Fetching stems from", baseUrl);

        const res = await fetch(`${baseUrl}/jobs/${jobId}/stems`, {
             headers: {
                 "X-API-Key": process.env.NEXT_PUBLIC_MIXMASTER_API_KEY || "",
             }
        });
        console.log("Studio: Stems response", res.status);

        let stemFiles: string[] = [];
        if (res.ok) {
            const data = await res.json();
            stemFiles = data.stems || [];
        } else {
             stemFiles = ["vocals.wav", "drums.wav", "bass.wav", "other.wav"];
        }
        console.log("Studio: Stems list", stemFiles);

        const newStems: StemControl[] = stemFiles.map((file) => ({
          name: file.replace(".wav", "").replace(/_/g, " ").replace("S11", "").replace("S10", "").trim() || file,
          volume: 0,
          pan: 0,
          mute: false,
          solo: false,
          eq: { low: 0, mid: 0, high: 0, enabled: false },
          compression: { threshold: -20, ratio: 2, enabled: false },
          reverb: { amount: 0, enabled: false },
          url: undefined
        }));

        setStems(newStems);

        if (audioContextRef.current) {
            console.log("Studio: Loading buffers...");
            for (const file of stemFiles) {
                if (cancelled) break;
                console.log("Studio: Processing file", file);
                try {
                    // Try loading from S5 output since we stop there

                    let signedUrl = await signFileUrl(jobId, `S5_LEADVOX_DYNAMICS/${file}`);
                    // If not found (e.g. some stems didn't go through S5), try previous stages
                    let resp = await fetch(signedUrl);
                    if (!resp.ok) {
                         signedUrl = await signFileUrl(jobId, `S5_STEM_DYNAMICS_GENERIC/${file}`);
                         resp = await fetch(signedUrl);
                    }
                     if (!resp.ok) {
                         signedUrl = await signFileUrl(jobId, `S12_SEPARATE_STEMS/${file}`);
                         resp = await fetch(signedUrl);
                    }
                    if (!resp.ok) {
                        // Use default search
                         console.log("Studio: Specific S5 fetch failed, trying generic sign");
                         const stages = ["S5_LEADVOX_DYNAMICS", "S5_STEM_DYNAMICS_GENERIC", "S4_SPECTRAL_CLEANUP", "S0_SESSION_FORMAT", "S0_MIX_ORIGINAL"];
                         for (const s of stages) {
                             signedUrl = await signFileUrl(jobId, `${s}/${file}`);
                             resp = await fetch(signedUrl);
                             if (resp.ok) break;
                         }
                    }

                    if (resp.ok) {
                        console.log("Studio: Fetch OK, reading buffer");
                        const ab = await resp.arrayBuffer();
                        console.log("Studio: Decoding buffer", ab.byteLength);

                        try {
                            const decodePromise = audioContextRef.current.decodeAudioData(ab);
                            const timeoutPromise = new Promise<AudioBuffer>((_, reject) =>
                                setTimeout(() => reject(new Error("Audio decoding timed out")), 5000)
                            );

                            const decoded = await Promise.race([decodePromise, timeoutPromise]);
                            console.log("Studio: Decoded OK");
                            audioBuffersRef.current.set(newStems.find(s => s.name.includes(file.replace(".wav","")))?.name || file, decoded);

                            const blob = new Blob([ab], { type: 'audio/wav' });
                            const blobUrl = URL.createObjectURL(blob);

                            setStems(prev => prev.map(s => {
                                if (file.includes(s.name.replace(/ /g, "_"))) return { ...s, url: blobUrl };
                                return s;
                            }));

                            if (!duration && decoded) setDuration(decoded.duration);

                        } catch (decodeErr) {
                            console.warn(`Failed to decode stem ${file}:`, decodeErr);
                            // Set dummy URL to allow UI to show up
                            setStems(prev => prev.map(s => {
                                if (file.includes(s.name.replace(/ /g, "_"))) return { ...s, url: "mock-url-failed-decode" };
                                return s;
                            }));
                        }
                    } else {
                        console.log("Studio: Fetch failed for", file);
                    }
                } catch (e) {
                    console.error("Failed to load stem", file, e);
                }
            }
        } else {
            console.warn("Studio: No AudioContext, skipping buffers");
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
    if (!waveformRef.current || stems.length === 0) return;

    const selectedStem = stems[selectedStemIndex];
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
  }, [selectedStemIndex, stems]);

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
      if (!ctx) return;

      if (ctx.state === 'suspended') await ctx.resume();

      if (isPlaying) {
          sourceNodesRef.current.forEach(node => node.stop());
          sourceNodesRef.current.clear();
          pauseTimeRef.current = ctx.currentTime - startTimeRef.current;
          setIsPlaying(false);
      } else {
          startTimeRef.current = ctx.currentTime - pauseTimeRef.current;

          stems.forEach(stem => {
              const buffer = audioBuffersRef.current.get(stem.name) || audioBuffersRef.current.get(stems.find(s=>s.url === stem.url)?.name || "");
              if (!buffer) return;

              const source = ctx.createBufferSource();
              source.buffer = buffer;

              const gain = ctx.createGain();
              const vol = Math.pow(10, stem.volume / 20);
              gain.gain.value = stem.mute ? 0 : (stems.some(s => s.solo) && !stem.solo ? 0 : vol);

              source.connect(gain);
              gain.connect(ctx.destination);

              const offset = pauseTimeRef.current % buffer.duration;
              source.start(0, offset);

              sourceNodesRef.current.set(stem.name, source);
              gainNodesRef.current.set(stem.name, gain);
          });

          setIsPlaying(true);
      }
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
          const node = gainNodesRef.current.get(stem.name);
          if (node) {
              const vol = Math.pow(10, stem.volume / 20);
              const isSoloed = stems.some(s => s.solo);
              const effectiveVol = stem.mute ? 0 : (isSoloed && !stem.solo ? 0 : vol);
              node.gain.setTargetAtTime(effectiveVol, audioContextRef.current!.currentTime, 0.05);
          }
      });
  }, [stems]);


  const handleApplyCorrection = async (proceedToMastering: boolean) => {
      setRendering(true);
      try {
          const corrections = stems.map(s => ({
              name: s.name,
              volume_db: s.volume,
              pan: s.pan,
              eq: s.eq.enabled ? s.eq : undefined,
              compression: s.compression.enabled ? s.compression : undefined,
              reverb: s.reverb.enabled ? s.reverb : undefined,
              mute: s.mute,
              solo: s.solo
          }));

          const baseUrl = getBackendBaseUrl();
          // 1. Send corrections
          await fetch(`${baseUrl}/jobs/${jobId}/correction`, {
              method: 'POST',
              headers: {
                  'Content-Type': 'application/json',
                  "X-API-Key": process.env.NEXT_PUBLIC_MIXMASTER_API_KEY || "",
              },
              body: JSON.stringify({ corrections })
          });

          // 2. Trigger Resume (Next stages)
          // "Proceed to Mastering": Run S6 -> S7...S11
          // "Finish Here": Run S6 -> S11 (skip S7-S10)

          let stages: string[] = [];
          if (proceedToMastering) {
              // Full remainder
              stages = [
                  "S6_MANUAL_CORRECTION",
                  "S7_MIXBUS_TONAL_BALANCE",
                  "S8_MIXBUS_COLOR_GENERIC",
                  "S9_MASTER_GENERIC",
                  "S10_MASTER_FINAL_LIMITS",
                  "S11_REPORT_GENERATION"
              ];
          } else {
              // Skip mastering
              stages = [
                  "S6_MANUAL_CORRECTION",
                  "S11_REPORT_GENERATION"
              ];
          }

          // Pass `stages` override to /start
          await fetch(`${baseUrl}/mix/${jobId}/start`, {
               method: 'POST',
               headers: {
                   'Content-Type': 'application/json',
                   "X-API-Key": process.env.NEXT_PUBLIC_MIXMASTER_API_KEY || ""
               },
               body: JSON.stringify({ stages })
          });

          router.push(`/`);
      } catch (err) {
          console.error(err);
          alert("Error sending corrections");
      } finally {
          setRendering(false);
      }
  };

  const downloadStems = async () => {
      try {
          const baseUrl = getBackendBaseUrl();
          const url = `${baseUrl}/jobs/${jobId}/download-stems-zip`;
          // Trigger download by opening in new window or creating anchor
          // New window/tab might be blocked if not user initiated click,
          // but we are in click handler.

          // Need to handle auth headers if endpoint is guarded.
          // Download via anchor tag usually sends cookies but not headers.
          // If our API requires X-API-Key, we might need a signed URL first.

          // The endpoint uses `_guard_heavy_endpoint` which checks header or query param.
          // Let's use `signFileUrl` helper logic? No, it's a dynamic endpoint.
          // We can append ?api_key=... if we have it in env.

          // For now, assuming user is authorized via session cookie or API key in query.
          // We can use fetch to get blob and download.

          const res = await fetch(url, {
              headers: { "X-API-Key": process.env.NEXT_PUBLIC_MIXMASTER_API_KEY || "" }
          });
          if (!res.ok) throw new Error("Download failed");
          const blob = await res.blob();
          const blobUrl = window.URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = blobUrl;
          a.download = `${jobId}_stems.zip`;
          document.body.appendChild(a);
          a.click();
          a.remove();

      } catch (e) {
          console.error(e);
          alert("Failed to download stems");
      }
  };

  const downloadMixdown = async () => {
       try {
          const baseUrl = getBackendBaseUrl();
          const url = `${baseUrl}/jobs/${jobId}/download-mixdown`;

          const res = await fetch(url, {
              headers: { "X-API-Key": process.env.NEXT_PUBLIC_MIXMASTER_API_KEY || "" }
          });
          if (!res.ok) throw new Error("Download failed");
          const blob = await res.blob();
          const blobUrl = window.URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = blobUrl;
          a.download = `${jobId}_mixdown.wav`;
          document.body.appendChild(a);
          a.click();
          a.remove();
       } catch (e) {
           console.error(e);
           alert("Failed to download mixdown");
       }
  };

  const updateStem = (index: number, updates: Partial<StemControl>) => {
      setStems(prev => {
          const next = [...prev];
          next[index] = { ...next[index], ...updates };
          return next;
      });
  };

  const selectedStem = stems[selectedStemIndex];

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
                 <span className="text-sm font-medium text-white">{jobId.substring(0,8)}...</span>
             </div>
         </div>
         <div className="flex items-center gap-4">
             <button onClick={downloadStems} className="px-3 py-1.5 text-xs font-medium text-slate-400 hover:text-white border border-white/10 rounded hover:bg-white/5 transition-colors flex items-center gap-2">
                 <ArrowDownTrayIcon className="w-3 h-3" /> Stems (ZIP)
             </button>
             <button onClick={downloadMixdown} className="px-3 py-1.5 text-xs font-medium text-slate-400 hover:text-white border border-white/10 rounded hover:bg-white/5 transition-colors flex items-center gap-2">
                 <ArrowDownTrayIcon className="w-3 h-3" /> Mixdown
             </button>

             <div className="h-6 w-px bg-white/10 mx-2"></div>

             <button
                onClick={() => handleApplyCorrection(false)}
                disabled={rendering}
                className="px-4 py-1.5 bg-slate-700 hover:bg-slate-600 text-white text-xs font-bold rounded shadow-lg transition-all flex items-center gap-2"
             >
                <XMarkIcon className="w-3 h-3" />
                Finish here (not Mastering)
             </button>
             <button
                onClick={() => handleApplyCorrection(true)}
                disabled={rendering}
                className="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold rounded shadow-lg shadow-emerald-900/20 transition-all flex items-center gap-2"
             >
                {rendering ? <ArrowPathIcon className="w-3 h-3 animate-spin" /> : <CheckIcon className="w-3 h-3" />}
                Proceed to Mastering
             </button>
         </div>
      </header>

      <div className="flex flex-1 overflow-hidden">

          <aside className="w-72 bg-[#11131f] border-r border-white/5 flex flex-col shrink-0">
             <div className="p-4 border-b border-white/5 flex justify-between items-center">
                 <h2 className="text-xs font-bold text-slate-500 tracking-widest uppercase">Tracks ({stems.length})</h2>
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
                             <span className="text-[9px] font-mono w-6 text-right">{stem.volume > 0 ? '+' : ''}{stem.volume.toFixed(1)}</span>
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
                         <span>{(masterVolume * 20 - 20).toFixed(1)} dB</span>
                     </div>
                     <div className="h-2 bg-slate-800 rounded-full overflow-hidden relative">
                         <div className="absolute top-0 left-0 bottom-0 bg-gradient-to-r from-emerald-600 to-emerald-400" style={{ width: `${masterVolume * 100}%` }}></div>
                     </div>
                 </div>

                 <div className="flex flex-col items-center gap-2">
                     <div className="text-xl font-mono text-slate-300 tabular-nums tracking-widest">
                         {formatTime(currentTime)}
                     </div>
                     <div className="flex items-center gap-4">
                        <button onClick={() => { setIsPlaying(false); setCurrentTime(0); startTimeRef.current = audioContextRef.current?.currentTime || 0; pauseTimeRef.current = 0; }} className="text-slate-500 hover:text-white transition-colors"><StopIcon className="w-4 h-4" /></button>
                        <button
                            onClick={togglePlay}
                            className="w-10 h-10 rounded-full bg-white text-black flex items-center justify-center hover:scale-105 transition-transform shadow-[0_0_15px_rgba(255,255,255,0.2)]"
                        >
                            {isPlaying ? <PauseIcon className="w-5 h-5" /> : <PlayIcon className="w-5 h-5 ml-0.5" />}
                        </button>
                     </div>
                 </div>

                 <div className="w-48 flex items-center gap-3">
                     <span className="text-[10px] text-slate-500 font-bold">MONITOR</span>
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
                             <div className="flex items-center gap-2">
                                <input
                                    type="checkbox"
                                    checked={selectedStem.eq.enabled}
                                    onChange={(e) => updateStem(selectedStemIndex, { eq: {...selectedStem.eq, enabled: e.target.checked}})}
                                    className="rounded border-slate-600 bg-slate-800 text-emerald-500 focus:ring-emerald-500"
                                />
                                <span className={`text-xs font-bold ${selectedStem.eq.enabled ? 'text-emerald-400' : 'text-slate-500'}`}>Parametric EQ</span>
                             </div>
                        </div>
                        <div className={`transition-opacity ${selectedStem.eq.enabled ? 'opacity-100' : 'opacity-40 pointer-events-none'}`}>
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
                    </div>

                    <div className="bg-[#1e2336] rounded-xl p-4 border border-white/5 shadow-lg">
                        <div className="flex justify-between items-center mb-4">
                            <div className="flex items-center gap-2">
                                <input
                                    type="checkbox"
                                    checked={selectedStem.compression.enabled}
                                    onChange={(e) => updateStem(selectedStemIndex, { compression: {...selectedStem.compression, enabled: e.target.checked}})}
                                    className="rounded border-slate-600 bg-slate-800 text-emerald-500 focus:ring-emerald-500"
                                />
                                <span className={`text-xs font-bold ${selectedStem.compression.enabled ? 'text-emerald-400' : 'text-slate-500'}`}>Compressor</span>
                             </div>
                        </div>

                        <div className={`flex justify-around mb-4 transition-opacity ${selectedStem.compression.enabled ? 'opacity-100' : 'opacity-40 pointer-events-none'}`}>
                             <Knob label="THRESH" value={selectedStem.compression.threshold} min={-60} max={0} onChange={(v) => updateStem(selectedStemIndex, { compression: {...selectedStem.compression, threshold: v}})} />
                             <Knob label="RATIO" value={selectedStem.compression.ratio} min={1} max={20} onChange={(v) => updateStem(selectedStemIndex, { compression: {...selectedStem.compression, ratio: v}})} />
                        </div>
                    </div>

                    <div className="bg-[#1e2336] rounded-xl p-4 border border-white/5 shadow-lg">
                        <div className="flex justify-between items-center mb-4">
                            <span className="text-xs font-bold text-slate-300">Spatial</span>
                        </div>
                        <div className="flex justify-around">
                             <Knob label="PAN" value={selectedStem.pan} min={-1} max={1} step={0.1} onChange={(v) => updateStem(selectedStemIndex, { pan: v})} />
                             <div className="flex flex-col items-center gap-2">
                                 <div className="flex items-center gap-2 mb-1">
                                     <input
                                        type="checkbox"
                                        checked={selectedStem.reverb.enabled}
                                        onChange={(e) => updateStem(selectedStemIndex, { reverb: {...selectedStem.reverb, enabled: e.target.checked}})}
                                        className="rounded border-slate-600 bg-slate-800 text-purple-500 focus:ring-purple-500 w-3 h-3"
                                     />
                                     <span className={`text-[10px] font-bold ${selectedStem.reverb.enabled ? 'text-purple-400' : 'text-slate-500'}`}>REVERB</span>
                                 </div>
                                 <div className={selectedStem.reverb.enabled ? 'opacity-100' : 'opacity-40 pointer-events-none'}>
                                     <Knob label="AMT" value={selectedStem.reverb.amount} min={0} max={100} onChange={(v) => updateStem(selectedStemIndex, { reverb: {...selectedStem.reverb, amount: v}})} />
                                 </div>
                             </div>
                        </div>
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

function Knob({ label, value, min, max, step, onChange }: { label: string, value: number, min: number, max: number, step?: number, onChange: (v: number) => void }) {
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
            // Snap to step
            if (step) {
                newVal = Math.round(newVal / step) * step;
            }
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
                <span className={`text-[10px] font-mono transition-colors ${dragging ? 'text-emerald-400' : 'text-slate-600'}`}>{value.toFixed(step && step < 1 ? 2 : 1)}</span>
            </div>
        </div>
    );
}
