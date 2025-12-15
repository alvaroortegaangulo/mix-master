
"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { fetchJobReport, getBackendBaseUrl, signFileUrl } from "@/lib/mixApi";
import { AuthModal } from "@/components/AuthModal";

// ----------------------------------------------------------------------
// TYPES
// ----------------------------------------------------------------------
interface StemControl {
  name: string;
  volume: number; // dB, range -60 to +12
  pan: number;    // -1 (Left) to +1 (Right)
  mute: boolean;
  solo: boolean;
  eq: {
    low: number; // dB, -12 to +12
    mid: number; // dB, -12 to +12
    high: number; // dB, -12 to +12
  };
  compression: {
    threshold: number; // dB, -60 to 0
    ratio: number;     // 1 to 20
  };
  url?: string; // Loaded URL
  buffer?: AudioBuffer; // Decoded buffer
  sourceNode?: AudioBufferSourceNode;
  gainNode?: GainNode;
  panNode?: StereoPannerNode;
  eqNodes?: {
    low: BiquadFilterNode;
    mid: BiquadFilterNode;
    high: BiquadFilterNode;
  };
  compNode?: DynamicsCompressorNode;
}

// ----------------------------------------------------------------------
// STUDIO COMPONENT
// ----------------------------------------------------------------------
export default function StudioPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [showAuthModal, setShowAuthModal] = useState(false);

  // State
  const [stems, setStems] = useState<StemControl[]>([]);
  const [audioContext, setAudioContext] = useState<AudioContext | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [loadingStems, setLoadingStems] = useState(true);
  const [rendering, setRendering] = useState(false);

  // Checks authentication
  useEffect(() => {
    if (!authLoading && !user) {
      setShowAuthModal(true);
    }
  }, [authLoading, user]);

  // Initialize Audio Context
  useEffect(() => {
    if (typeof window !== "undefined" && !audioContext) {
      const ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
      setAudioContext(ctx);
    }
  }, [audioContext]);

  // Load Stems List and Data
  useEffect(() => {
    if (!jobId || !user || !audioContext) return;

    let cancelled = false;

    async function load() {
      try {
        setLoadingStems(true);
        // 1. Fetch available stems from backend
        // We assume backend has an endpoint for this, OR we try standard names if not.
        // Since we don't have a "list stems" endpoint yet, we will implement it first.
        // For now, let's assume standard 5 stems from Spleeter or list from a new endpoint.
        // Using a new endpoint: GET /jobs/{jobId}/stems

        const res = await fetch(`${getBackendBaseUrl()}/jobs/${jobId}/stems`, {
             headers: {
                 "X-API-Key": process.env.NEXT_PUBLIC_MIXMASTER_API_KEY || "",
             }
        });

        let stemFiles: string[] = [];
        if (res.ok) {
            const data = await res.json();
            stemFiles = data.stems || [];
        } else {
             // Fallback if endpoint not ready or empty
             stemFiles = ["vocals.wav", "drums.wav", "bass.wav", "piano.wav", "other.wav"];
        }

        // 2. Prepare stem controls
        const newStems: StemControl[] = stemFiles.map((file) => ({
          name: file.replace(".wav", ""),
          volume: 0,
          pan: 0,
          mute: false,
          solo: false,
          eq: { low: 0, mid: 0, high: 0 },
          compression: { threshold: 0, ratio: 1 },
        }));

        // 3. Load audio buffers
        const buffers = await Promise.all(
          stemFiles.map(async (file) => {
             // Sign URL
             const path = `S12_SEPARATE_STEMS/${file}`;
             const url = await signFileUrl(jobId, path);

             // Fetch audio
             const resp = await fetch(url);
             const arrayBuffer = await resp.arrayBuffer();
             const decoded = await audioContext!.decodeAudioData(arrayBuffer);
             return { name: file.replace(".wav", ""), buffer: decoded, url };
          })
        );

        if (cancelled) return;

        // Set duration from first buffer
        if (buffers.length > 0) {
            setDuration(buffers[0].buffer.duration);
        }

        // Merge buffers into stem controls
        setStems((prev) =>
            prev.map(s => {
                const found = buffers.find(b => b.name === s.name);
                return found ? { ...s, buffer: found.buffer, url: found.url } : s;
            }).filter(s => s.buffer) // only keep loaded ones
        );

      } catch (err) {
        console.error("Error loading stems:", err);
      } finally {
        setLoadingStems(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [jobId, user, audioContext]);


  // Playback Logic
  useEffect(() => {
     let animationFrame: number;

     const updateTime = () => {
         if (audioContext && isPlaying) {
             // This is a rough estimation. For precise DAW UI we need start time offset.
             // We'll fix this in togglePlay
             setCurrentTime(audioContext.currentTime);
             animationFrame = requestAnimationFrame(updateTime);
         }
     };

     if (isPlaying) {
         updateTime();
     } else {
         cancelAnimationFrame(animationFrame!);
     }

     return () => cancelAnimationFrame(animationFrame!);
  }, [isPlaying, audioContext]);

  // Audio Graph Management
  // This is complex. React state updates shouldn't rebuild the graph every time.
  // We need refs for audio nodes or careful management.
  // For this MVP, we will rebuild/update nodes when parameters change.
  // But to play, we need to start sources.

  // Helper to start playback
  const togglePlay = async () => {
      if (!audioContext) return;

      if (audioContext.state === "suspended") {
          await audioContext.resume();
      }

      if (isPlaying) {
          // Stop
          stems.forEach(s => {
              try { s.sourceNode?.stop(); } catch(e){}
          });
          setIsPlaying(false);
      } else {
          // Start
          const now = audioContext.currentTime;
          // Re-create sources because they are one-time use
          // We need to mutate the stems state or use refs.
          // Since we are inside component, let's use a ref for nodes if possible,
          // but sticking to state for simplicity of this snippet (though less performant).
          // Better: just rebuild graph.

          stems.forEach(stem => {
              if (!stem.buffer) return;

              const source = audioContext.createBufferSource();
              source.buffer = stem.buffer;

              const gain = audioContext.createGain();
              const pan = audioContext.createStereoPanner();
              const low = audioContext.createBiquadFilter();
              const mid = audioContext.createBiquadFilter();
              const high = audioContext.createBiquadFilter();
              const comp = audioContext.createDynamicsCompressor();

              // Config
              low.type = "lowshelf"; low.frequency.value = 320;
              mid.type = "peaking"; mid.frequency.value = 1000;
              high.type = "highshelf"; high.frequency.value = 3200;

              // Connect: Source -> Comp -> EQ -> Gain -> Pan -> Destination
              source.connect(comp);
              comp.connect(low);
              low.connect(mid);
              mid.connect(high);
              high.connect(gain);
              gain.connect(pan);
              pan.connect(audioContext.destination);

              // Apply values
              applyStemParams(stem, { gain, pan, low, mid, high, comp });

              source.start(0, currentTime % duration); // rudimentary seek

              // Store nodes in stem object (mutating state directly for audio graph is risky but okay for local refs)
              stem.sourceNode = source;
              stem.gainNode = gain;
              stem.panNode = pan;
              stem.eqNodes = { low, mid, high };
              stem.compNode = comp;
          });

          setIsPlaying(true);
      }
  };

  // Real-time parameter updates
  useEffect(() => {
      stems.forEach(stem => {
          if (stem.gainNode && stem.panNode && stem.eqNodes && stem.compNode) {
             applyStemParams(stem, {
                 gain: stem.gainNode,
                 pan: stem.panNode,
                 low: stem.eqNodes.low,
                 mid: stem.eqNodes.mid,
                 high: stem.eqNodes.high,
                 comp: stem.compNode
             });
          }
      });
  }, [stems]);

  function applyStemParams(stem: StemControl, nodes: any) {
      const isMuted = stem.mute;
      const isSoloed = stems.some(s => s.solo);
      const shouldPlay = isSoloed ? stem.solo : !isMuted;

      // Volume (dB to linear)
      const volumeLinear = Math.pow(10, stem.volume / 20);
      nodes.gain.gain.setTargetAtTime(shouldPlay ? volumeLinear : 0, audioContext!.currentTime, 0.05);

      nodes.pan.pan.setTargetAtTime(stem.pan, audioContext!.currentTime, 0.05);

      nodes.low.gain.setTargetAtTime(stem.eq.low, audioContext!.currentTime, 0.05);
      nodes.mid.gain.setTargetAtTime(stem.eq.mid, audioContext!.currentTime, 0.05);
      nodes.high.gain.setTargetAtTime(stem.eq.high, audioContext!.currentTime, 0.05);

      nodes.comp.threshold.setTargetAtTime(stem.compression.threshold, audioContext!.currentTime, 0.05);
      nodes.comp.ratio.setTargetAtTime(stem.compression.ratio, audioContext!.currentTime, 0.05);
  }

  // Handle Updates
  const updateStem = (index: number, updates: Partial<StemControl>) => {
      setStems(prev => {
          const next = [...prev];
          next[index] = { ...next[index], ...updates };
          return next;
      });
  };

  const updateEq = (index: number, band: 'low'|'mid'|'high', val: number) => {
      setStems(prev => {
          const next = [...prev];
          next[index].eq = { ...next[index].eq, [band]: val };
          return next;
      });
  };

  const updateComp = (index: number, param: 'threshold'|'ratio', val: number) => {
      setStems(prev => {
          const next = [...prev];
          next[index].compression = { ...next[index].compression, [param]: val };
          return next;
      });
  };

  const handleRender = async () => {
      setRendering(true);
      try {
          // Send correction to backend
          const corrections = stems.map(s => ({
              name: s.name,
              volume_db: s.volume,
              pan: s.pan,
              eq: s.eq,
              compression: s.compression,
              mute: s.mute,
              solo: s.solo // Note: solo is usually ephemeral, but if we want to render only soloed tracks...
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

          // Poll for completion or redirect to results
          // For now, let's just go back to results which will likely show processing status if we update it
          router.push(`/`);
      } catch (err) {
          console.error(err);
          alert("Error sending corrections");
      } finally {
          setRendering(false);
      }
  };

  // If checking auth, show minimal loader or nothing
  if (authLoading) {
      return <div className="min-h-screen bg-slate-950"></div>;
  }

  // If not authenticated, show empty background + modal
  if (!user) {
      return (
        <div className="min-h-screen bg-slate-950 flex items-center justify-center">
            <div className="text-slate-600">Please log in to access Studio.</div>
            <AuthModal isOpen={true} onClose={() => router.back()} />
        </div>
      );
  }

  if (loadingStems) {
      return <div className="min-h-screen flex items-center justify-center bg-slate-950 text-emerald-500">Loading Studio...</div>;
  }

  return (
    <div className="min-h-screen bg-slate-950 text-white font-sans selection:bg-emerald-500/30">
      {/* Header */}
      <header className="border-b border-white/10 bg-slate-900 px-6 py-4 flex items-center justify-between">
         <div className="flex items-center gap-4">
             <button onClick={() => router.back()} className="text-slate-400 hover:text-white">
                 ← Back
             </button>
             <h1 className="text-xl font-bold tracking-wider text-emerald-400">PIROOLA STUDIO</h1>
         </div>
         <div className="flex items-center gap-4">
             <div className="text-xs text-slate-500 uppercase tracking-widest">Manual Correction Mode</div>
             <button
                onClick={handleRender}
                disabled={rendering}
                className="bg-emerald-500 hover:bg-emerald-400 text-black px-6 py-2 rounded-full font-bold text-sm disabled:opacity-50"
             >
                 {rendering ? "Rendering..." : "RENDER MIX"}
             </button>
         </div>
      </header>

      {/* Main Mixer Area */}
      <main className="p-6 overflow-x-auto">
         <div className="flex gap-4 min-w-max pb-20">
             {stems.map((stem, i) => (
                 <div key={stem.name} className="w-48 bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col gap-4 shadow-xl">
                     {/* Header */}
                     <div className="text-center border-b border-slate-800 pb-2">
                         <h3 className="font-bold text-emerald-100 truncate" title={stem.name}>{stem.name}</h3>
                     </div>

                     {/* EQ Section */}
                     <div className="space-y-2 bg-slate-950/50 p-2 rounded">
                         <label className="text-[10px] text-slate-400 uppercase font-bold block mb-1">Equalizer</label>
                         <div className="flex justify-between gap-1">
                             <Knob label="Hi" value={stem.eq.high} min={-12} max={12} onChange={(v) => updateEq(i, 'high', v)} />
                             <Knob label="Mid" value={stem.eq.mid} min={-12} max={12} onChange={(v) => updateEq(i, 'mid', v)} />
                             <Knob label="Lo" value={stem.eq.low} min={-12} max={12} onChange={(v) => updateEq(i, 'low', v)} />
                         </div>
                     </div>

                     {/* Compression Section */}
                     <div className="space-y-2 bg-slate-950/50 p-2 rounded">
                         <label className="text-[10px] text-slate-400 uppercase font-bold block mb-1">Compressor</label>
                         <div className="flex justify-between gap-1">
                             <Knob label="Thresh" value={stem.compression.threshold} min={-60} max={0} onChange={(v) => updateComp(i, 'threshold', v)} />
                             <Knob label="Ratio" value={stem.compression.ratio} min={1} max={20} onChange={(v) => updateComp(i, 'ratio', v)} />
                         </div>
                     </div>

                     {/* Pan */}
                     <div className="py-2">
                        <label className="text-[10px] text-slate-500 flex justify-between">
                            <span>L</span> <span>PAN</span> <span>R</span>
                        </label>
                        <input
                           type="range" min="-1" max="1" step="0.05"
                           value={stem.pan}
                           onChange={(e) => updateStem(i, { pan: parseFloat(e.target.value) })}
                           className="w-full h-1 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-emerald-500"
                        />
                     </div>

                     {/* Mute / Solo */}
                     <div className="flex gap-2">
                         <button
                            onClick={() => updateStem(i, { mute: !stem.mute })}
                            className={`flex-1 py-1 text-xs font-bold rounded ${stem.mute ? 'bg-red-500/80 text-white' : 'bg-slate-800 text-slate-400'}`}
                         >
                             M
                         </button>
                         <button
                            onClick={() => updateStem(i, { solo: !stem.solo })}
                            className={`flex-1 py-1 text-xs font-bold rounded ${stem.solo ? 'bg-yellow-500/80 text-black' : 'bg-slate-800 text-slate-400'}`}
                         >
                             S
                         </button>
                     </div>

                     {/* Fader */}
                     <div className="flex-1 flex justify-center py-2 bg-slate-950/30 rounded-lg relative">
                         {/* Track meter background (fake) */}
                         <div className="absolute inset-y-2 w-1.5 bg-slate-800 rounded-full left-1/2 -ml-3"></div>

                         <input
                            type="range"
                            min="-60" max="12" step="0.1"
                            value={stem.volume}
                            onChange={(e) => updateStem(i, { volume: parseFloat(e.target.value) })}
                            className="h-full -rotate-90 origin-center w-32 appearance-none bg-transparent cursor-pointer accent-emerald-500 slider-vertical"
                            style={{ width: '150px' }} // Manual width override due to rotation
                         />
                     </div>
                     <div className="text-center text-xs font-mono text-emerald-400">
                         {stem.volume > 0 ? '+' : ''}{stem.volume.toFixed(1)} dB
                     </div>
                 </div>
             ))}
         </div>
      </main>

      {/* Transport Bar */}
      <div className="fixed bottom-0 left-0 right-0 bg-slate-900 border-t border-slate-800 p-4 flex justify-center gap-6 items-center z-40">
           <button
              onClick={togglePlay}
              className="w-12 h-12 rounded-full bg-emerald-500 flex items-center justify-center hover:bg-emerald-400 shadow-lg shadow-emerald-900/50"
           >
               {isPlaying ? (
                   <span className="block w-4 h-4 bg-black rounded-sm"></span>
               ) : (
                   <span className="block w-0 h-0 border-t-[8px] border-t-transparent border-l-[14px] border-l-black border-b-[8px] border-b-transparent ml-1"></span>
               )}
           </button>
           <div className="text-2xl font-mono text-emerald-500 tabular-nums">
               {formatTime(currentTime)} <span className="text-slate-600 text-lg">/ {formatTime(duration)}</span>
           </div>
      </div>

      <AuthModal isOpen={showAuthModal} onClose={() => setShowAuthModal(false)} />
    </div>
  );
}

function formatTime(s: number) {
    const min = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    const ms = Math.floor((s % 1) * 100);
    return `${min}:${sec.toString().padStart(2, '0')}.${ms.toString().padStart(2, '0')}`;
}

// Simple Knob Component
function Knob({ label, value, min, max, onChange }: { label: string, value: number, min: number, max: number, onChange: (v: number) => void }) {
    // A simplified interaction for knob: click and drag (vertical)
    // For MVP we use basic interaction
    const handleMouseDown = (e: React.MouseEvent) => {
        const startY = e.clientY;
        const startVal = value;
        const handleMove = (ev: MouseEvent) => {
            const dy = startY - ev.clientY;
            const range = max - min;
            const delta = (dy / 100) * range; // 100px for full range
            let newVal = startVal + delta;
            if (newVal < min) newVal = min;
            if (newVal > max) newVal = max;
            onChange(newVal);
        };
        const handleUp = () => {
            window.removeEventListener('mousemove', handleMove);
            window.removeEventListener('mouseup', handleUp);
        };
        window.addEventListener('mousemove', handleMove);
        window.addEventListener('mouseup', handleUp);
    };

    // Calculate rotation: -135deg to +135deg
    const pct = (value - min) / (max - min);
    const rotation = -135 + (pct * 270);

    return (
        <div className="flex flex-col items-center">
            <div
                onMouseDown={handleMouseDown}
                className="w-8 h-8 rounded-full bg-slate-700 relative cursor-ns-resize shadow-inner ring-1 ring-slate-600"
            >
                <div
                    className="absolute top-1/2 left-1/2 w-1 h-3 bg-emerald-500 origin-bottom -translate-x-1/2 -translate-y-full rounded-full"
                    style={{ transform: `translate(-50%, -50%) rotate(${rotation}deg)` }}
                ></div>
            </div>
            <span className="text-[9px] text-slate-500 mt-1">{label}</span>
            <span className="text-[8px] text-emerald-600 font-mono">{value.toFixed(0)}</span>
        </div>
    );
}
