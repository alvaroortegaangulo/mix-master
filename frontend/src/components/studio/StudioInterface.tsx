// frontend/src/components/studio/StudioInterface.tsx
"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import {
    MixResult,
    signFileUrl,
    getBackendBaseUrl,
    applyManualCorrection
} from "@/lib/mixApi";
import {
    PlayIcon,
    PauseIcon,
    ArrowPathIcon,
    SpeakerWaveIcon,
    SpeakerXMarkIcon,
    ArrowLeftIcon,
    ArrowDownTrayIcon
} from "@heroicons/react/24/solid";

// Stem definition
type Stem = {
    name: string;
    url: string; // Signed URL
    loaded: boolean;
};

// State for each track
type TrackState = {
    volume: number; // 0 to 1
    muted: boolean;
    soloed: boolean;
    pan: number; // -1 to 1
    eq: {
        low: number; // dB
        mid: number; // dB
        high: number; // dB
    };
    compressor: {
        enabled: boolean;
        threshold: number;
        ratio: number;
    }
};

const STEM_NAMES = ["drums", "bass", "other", "vocals"];

export function StudioInterface({ job }: { job: MixResult }) {
    const router = useRouter();
    const [stems, setStems] = useState<Stem[]>([]);
    const [trackStates, setTrackStates] = useState<Record<string, TrackState>>({});
    const [isPlaying, setIsPlaying] = useState(false);
    const [currentTime, setCurrentTime] = useState(0);
    const [duration, setDuration] = useState(0);
    const [selectedTrack, setSelectedTrack] = useState<string>("drums");
    const [loadingStems, setLoadingStems] = useState(true);
    const [exporting, setExporting] = useState(false);

    // Audio Context Refs
    const audioCtxRef = useRef<AudioContext | null>(null);
    const sourcesRef = useRef<Record<string, AudioBufferSourceNode>>({});
    const gainNodesRef = useRef<Record<string, GainNode>>({});
    const panNodesRef = useRef<Record<string, StereoPannerNode>>({});
    const eqNodesRef = useRef<Record<string, { low: BiquadFilterNode; mid: BiquadFilterNode; high: BiquadFilterNode }>>({});
    const compressorNodesRef = useRef<Record<string, DynamicsCompressorNode>>({});
    const audioBuffersRef = useRef<Record<string, AudioBuffer>>({});
    const startTimeRef = useRef<number>(0);
    const pauseTimeRef = useRef<number>(0);

    // Initial Load
    useEffect(() => {
        const init = async () => {
            // 1. Prepare Stems
            const loadedStems: Stem[] = [];
            const initialStates: Record<string, TrackState> = {};

            const modelName = "htdemucs_ft";

            for (const name of STEM_NAMES) {
                const path = `S12_SEPARATE_STEMS/${modelName}/${name}.wav`;
                const signed = await signFileUrl(job.jobId, path);
                loadedStems.push({
                    name,
                    url: signed,
                    loaded: false
                });

                initialStates[name] = {
                    volume: 0.8,
                    muted: false,
                    soloed: false,
                    pan: 0,
                    eq: { low: 0, mid: 0, high: 0 },
                    compressor: { enabled: false, threshold: -20, ratio: 4 }
                };
            }
            setStems(loadedStems);
            setTrackStates(initialStates);

            // 2. Load Audio Buffers
            try {
                const ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
                audioCtxRef.current = ctx;

                const buffers: Record<string, AudioBuffer> = {};
                let maxDur = 0;

                for (const stem of loadedStems) {
                    try {
                        const resp = await fetch(stem.url);
                        if(!resp.ok) throw new Error(`Failed to fetch ${stem.name}`);
                        const arrayBuffer = await resp.arrayBuffer();
                        const audioBuffer = await ctx.decodeAudioData(arrayBuffer);
                        buffers[stem.name] = audioBuffer;
                        if(audioBuffer.duration > maxDur) maxDur = audioBuffer.duration;

                        setStems(prev => prev.map(s => s.name === stem.name ? { ...s, loaded: true } : s));
                    } catch (e) {
                        console.warn(`Could not load stem ${stem.name}`, e);
                    }
                }

                audioBuffersRef.current = buffers;
                setDuration(maxDur);
                setLoadingStems(false);

            } catch (e) {
                console.error("Audio initialization failed", e);
                setLoadingStems(false);
            }
        };

        init();

        return () => {
            stopAudio();
            audioCtxRef.current?.close();
        };
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [job.jobId]);

    // Playback Logic
    const playAudio = () => {
        if (!audioCtxRef.current || !Object.keys(audioBuffersRef.current).length) return;

        if (audioCtxRef.current.state === 'suspended') {
            audioCtxRef.current.resume();
        }

        const start = audioCtxRef.current.currentTime;
        startTimeRef.current = start - pauseTimeRef.current;

        // Create nodes
        Object.entries(audioBuffersRef.current).forEach(([name, buffer]) => {
            const ctx = audioCtxRef.current!;
            const src = ctx.createBufferSource();
            src.buffer = buffer;

            // Effect Chain: Source -> EQ -> Compressor -> Gain -> Panner -> Destination

            // EQ
            const low = ctx.createBiquadFilter();
            low.type = "lowshelf";
            low.frequency.value = 100;

            const mid = ctx.createBiquadFilter();
            mid.type = "peaking";
            mid.frequency.value = 1000;
            mid.Q.value = 1.0;

            const high = ctx.createBiquadFilter();
            high.type = "highshelf";
            high.frequency.value = 10000;

            // Compressor
            const comp = ctx.createDynamicsCompressor();

            // Gain & Pan
            const gain = ctx.createGain();
            const panner = ctx.createStereoPanner();

            // Connect
            src.connect(low);
            low.connect(mid);
            mid.connect(high);
            high.connect(comp);
            comp.connect(gain);
            gain.connect(panner);
            panner.connect(ctx.destination);

            // Apply current state
            const state = trackStates[name];
            applyNodeState(gain, panner, { low, mid, high }, comp, state, name);

            src.start(0, pauseTimeRef.current);

            sourcesRef.current[name] = src;
            gainNodesRef.current[name] = gain;
            panNodesRef.current[name] = panner;
            eqNodesRef.current[name] = { low, mid, high };
            compressorNodesRef.current[name] = comp;
        });

        setIsPlaying(true);
        requestAnimationFrame(updateProgress);
    };

    const stopAudio = () => {
        Object.values(sourcesRef.current).forEach(src => {
            try { src.stop(); } catch(e){}
        });
        sourcesRef.current = {};
        if(audioCtxRef.current) pauseTimeRef.current = audioCtxRef.current.currentTime - startTimeRef.current;
        setIsPlaying(false);
    };

    const togglePlay = () => {
        if (isPlaying) stopAudio();
        else playAudio();
    };

    const updateProgress = () => {
        if (!isPlaying || !audioCtxRef.current) return;
        const now = audioCtxRef.current.currentTime - startTimeRef.current;
        setCurrentTime(now);
        if (now < duration) requestAnimationFrame(updateProgress);
        else {
            setIsPlaying(false);
            pauseTimeRef.current = 0;
            setCurrentTime(0);
        }
    };

    // Audio Node Updates
    const applyNodeState = (
        gainNode: GainNode,
        panNode: StereoPannerNode,
        eqNodes: { low: BiquadFilterNode; mid: BiquadFilterNode; high: BiquadFilterNode },
        compNode: DynamicsCompressorNode,
        state: TrackState,
        trackName: string
    ) => {
        // Solo Logic
        const anySolo = Object.values(trackStates).some(s => s.soloed);
        const isMuted = state.muted || (anySolo && !state.soloed);

        // Gain & Pan
        gainNode.gain.value = isMuted ? 0 : state.volume;
        panNode.pan.value = state.pan;

        // EQ
        eqNodes.low.gain.value = state.eq.low;
        eqNodes.mid.gain.value = state.eq.mid;
        eqNodes.high.gain.value = state.eq.high;

        // Compressor
        if (state.compressor.enabled) {
            compNode.threshold.value = state.compressor.threshold;
            compNode.ratio.value = state.compressor.ratio;
        } else {
            // Bypass compressor roughly by setting high threshold and ratio 1
            compNode.threshold.value = 0;
            compNode.ratio.value = 1;
        }
    };

    useEffect(() => {
        // Update live nodes when state changes
        Object.entries(gainNodesRef.current).forEach(([name, gainNode]) => {
            const panNode = panNodesRef.current[name];
            const eqNodes = eqNodesRef.current[name];
            const compNode = compressorNodesRef.current[name];

            if (gainNode && panNode && eqNodes && compNode) {
                applyNodeState(gainNode, panNode, eqNodes, compNode, trackStates[name], name);
            }
        });
    }, [trackStates]);


    // UI Handlers
    const updateTrack = (name: string, update: Partial<TrackState>) => {
        setTrackStates(prev => ({
            ...prev,
            [name]: { ...prev[name], ...update }
        }));
    };

    const formatTime = (t: number) => {
        const m = Math.floor(t / 60);
        const s = Math.floor(t % 60);
        const ms = Math.floor((t % 1) * 100);
        return `${m.toString().padStart(2,'0')}:${s.toString().padStart(2,'0')}.${ms.toString().padStart(2,'0')}`;
    };

    const handleExport = async () => {
        setExporting(true);
        try {
            // Build changes.json structure
            const changes = {
                stems: {} as Record<string, any>
            };

            Object.entries(trackStates).forEach(([name, state]) => {
                changes.stems[name] = {
                    gain_db: 20 * Math.log10(Math.max(0.0001, state.volume)), // Convert linear to dB
                    mute: state.muted,
                    solo: state.soloed,
                    pan: state.pan,
                    eq: state.eq,
                    compressor: state.compressor
                };
            });

            await applyManualCorrection(job.jobId, changes);

            // Navigate back to results or show success
            // For now, redirect to result page to wait for processing
            router.push(`/?jobId=${job.jobId}`); // Assuming homepage handles reloading

        } catch (e) {
            console.error("Export failed", e);
            alert("Export failed. See console.");
        } finally {
            setExporting(false);
        }
    };

    const activeTrackState = trackStates[selectedTrack];

    return (
        <div className="flex h-full flex-col bg-slate-900 text-slate-100 font-sans">
            {/* Header */}
            <header className="flex h-16 items-center justify-between border-b border-slate-800 bg-slate-950 px-6">
                <div className="flex items-center gap-4">
                    <button onClick={() => router.back()} className="text-slate-400 hover:text-white">
                        <ArrowLeftIcon className="h-5 w-5" />
                    </button>
                    <h1 className="text-xl font-bold text-emerald-400">Piroola Studio</h1>
                    <span className="text-xs text-slate-500 uppercase tracking-wider border-l border-slate-700 pl-4 ml-2">
                        Project: {job.jobId.slice(0, 8)}...
                    </span>
                </div>

                <div className="flex items-center gap-4">
                     <div className="flex items-center gap-2 rounded bg-slate-800 px-3 py-1 text-sm font-mono text-emerald-400">
                        {formatTime(currentTime)}
                     </div>
                     <button className="text-slate-400 hover:text-white" title="Undo (Not implemented)">Undo</button>
                     <button
                        onClick={handleExport}
                        disabled={exporting}
                        className="flex items-center gap-2 rounded bg-emerald-600 px-4 py-1.5 text-sm font-bold text-white hover:bg-emerald-500 disabled:opacity-50"
                     >
                        {exporting ? <ArrowPathIcon className="h-4 w-4 animate-spin"/> : <ArrowDownTrayIcon className="h-4 w-4"/>}
                        Export
                     </button>
                </div>
            </header>

            {/* Main Workspace */}
            <div className="flex flex-1 overflow-hidden">
                {/* Left Sidebar: Tracks */}
                <aside className="w-80 border-r border-slate-800 bg-slate-925 flex flex-col">
                    <div className="flex items-center justify-between p-4 border-b border-slate-800">
                         <span className="text-xs font-bold text-slate-500">TRACKS ({stems.length})</span>
                    </div>
                    <div className="flex-1 overflow-y-auto">
                        {stems.map((stem) => {
                            const state = trackStates[stem.name];
                            if(!state) return null;
                            const isSelected = selectedTrack === stem.name;

                            return (
                                <div
                                    key={stem.name}
                                    onClick={() => setSelectedTrack(stem.name)}
                                    className={`group flex flex-col gap-2 border-b border-slate-800 p-4 transition cursor-pointer ${isSelected ? 'bg-slate-800/50' : 'hover:bg-slate-800/20'}`}
                                >
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-2">
                                            <div className={`h-3 w-3 rounded-full ${stem.loaded ? 'bg-emerald-500' : 'bg-slate-600 animate-pulse'}`} />
                                            <span className="font-semibold capitalize text-slate-200">{stem.name}</span>
                                        </div>
                                        <div className="flex gap-1">
                                            <button
                                                onClick={(e) => { e.stopPropagation(); updateTrack(stem.name, { muted: !state.muted }); }}
                                                className={`h-6 w-6 rounded flex items-center justify-center text-xs font-bold ${state.muted ? 'bg-red-500 text-white' : 'bg-slate-700 text-slate-400'}`}
                                            >M</button>
                                            <button
                                                onClick={(e) => { e.stopPropagation(); updateTrack(stem.name, { soloed: !state.soloed }); }}
                                                className={`h-6 w-6 rounded flex items-center justify-center text-xs font-bold ${state.soloed ? 'bg-yellow-500 text-black' : 'bg-slate-700 text-slate-400'}`}
                                            >S</button>
                                        </div>
                                    </div>

                                    {/* Volume Slider */}
                                    <div className="flex items-center gap-2">
                                        <SpeakerWaveIcon className="h-3 w-3 text-slate-500" />
                                        <input
                                            type="range"
                                            min="0" max="1" step="0.01"
                                            value={state.volume}
                                            onChange={(e) => updateTrack(stem.name, { volume: parseFloat(e.target.value) })}
                                            className="h-1 flex-1 cursor-pointer appearance-none rounded-full bg-slate-700 accent-emerald-500"
                                            onClick={(e) => e.stopPropagation()}
                                        />
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </aside>

                {/* Center: Waveform Visualization */}
                <main className="flex-1 flex flex-col bg-slate-950 relative">
                     {/* Timeline Ruler (Fake) */}
                     <div className="h-6 w-full border-b border-slate-800 bg-slate-900 flex text-[10px] text-slate-500 px-4 items-center justify-between select-none">
                         <span>0:00</span><span>0:15</span><span>0:30</span><span>0:45</span><span>1:00</span>
                     </div>

                     {/* Visualization Area */}
                     <div className="flex-1 flex items-center justify-center relative group">
                        {loadingStems ? (
                             <div className="text-emerald-500 animate-pulse">Loading Stems...</div>
                        ) : (
                             <div className="w-full h-64 flex items-center px-10 gap-1 opacity-50">
                                 {/* Fake waveform bars */}
                                 {Array.from({length: 60}).map((_,i) => (
                                     <div
                                        key={i}
                                        className="bg-emerald-500/40 w-full rounded-full transition-all duration-100"
                                        style={{ height: `${Math.random() * 80 + 20}%`}}
                                     />
                                 ))}
                             </div>
                        )}

                        {/* Playhead */}
                        {duration > 0 && (
                            <div
                                className="absolute top-0 bottom-0 w-0.5 bg-yellow-400 shadow-[0_0_10px_rgba(250,204,21,0.5)] transition-all linear"
                                style={{ left: `${(currentTime / duration) * 100}%` }}
                            />
                        )}
                     </div>

                     {/* Transport */}
                     <div className="h-16 border-t border-slate-800 bg-slate-900 flex items-center justify-center gap-6">
                         <button className="text-slate-400 hover:text-white"><ArrowPathIcon className="h-5 w-5" /></button>
                         <button onClick={togglePlay} className="h-12 w-12 rounded-full bg-white text-black flex items-center justify-center hover:scale-105 transition shadow-lg shadow-white/20">
                            {isPlaying ? <PauseIcon className="h-6 w-6" /> : <PlayIcon className="h-6 w-6 ml-1" />}
                         </button>
                         <div className="w-32 flex items-center gap-2">
                             <SpeakerWaveIcon className="h-4 w-4 text-slate-400" />
                             <input type="range" className="h-1 flex-1 bg-slate-600 rounded-lg accent-slate-300" />
                         </div>
                     </div>
                </main>

                {/* Right Sidebar: Controls */}
                <aside className="w-80 border-l border-slate-800 bg-slate-925 p-4 flex flex-col gap-6 overflow-y-auto">
                    <div>
                        <span className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-4 block">Selected Channel</span>
                        <h2 className="text-xl font-bold text-emerald-100 capitalize flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full bg-emerald-500" />
                            {selectedTrack}
                        </h2>
                    </div>

                    {activeTrackState && (
                        <>
                            {/* EQ */}
                            <div className="bg-slate-900 rounded-xl p-4 border border-slate-800">
                                <div className="flex items-center justify-between mb-4">
                                    <h3 className="text-sm font-semibold text-slate-300">Parametric EQ</h3>
                                    <div className="h-3 w-6 bg-emerald-500/20 rounded-full relative">
                                        <div className="absolute right-0.5 top-0.5 h-2 w-2 bg-emerald-500 rounded-full" />
                                    </div>
                                </div>

                                {/* EQ Knobs (Fake UI but updates state) */}
                                <div className="grid grid-cols-3 gap-2">
                                    {['low', 'mid', 'high'].map(band => (
                                        <div key={band} className="flex flex-col items-center gap-2">
                                            <div className="relative w-12 h-12 rounded-full border-2 border-slate-700 flex items-center justify-center">
                                                <div
                                                    className="w-1 h-3 bg-emerald-500 rounded-full origin-bottom absolute bottom-1/2"
                                                    style={{ transform: `rotate(${activeTrackState.eq[band as keyof typeof activeTrackState.eq] * 5}deg)` }} // Scale for visual
                                                />
                                            </div>
                                            <label className="text-[10px] uppercase text-slate-500">{band}</label>
                                            <input
                                                type="number"
                                                className="w-12 bg-transparent text-center text-xs border-b border-slate-700 focus:border-emerald-500 outline-none"
                                                value={activeTrackState.eq[band as keyof typeof activeTrackState.eq]}
                                                onChange={(e) => updateTrack(selectedTrack, {
                                                    eq: { ...activeTrackState.eq, [band]: parseFloat(e.target.value) }
                                                })}
                                            />
                                        </div>
                                    ))}
                                </div>
                            </div>

                            {/* Compressor */}
                            <div className="bg-slate-900 rounded-xl p-4 border border-slate-800">
                                <div className="flex items-center justify-between mb-4">
                                    <h3 className="text-sm font-semibold text-slate-300">Compressor</h3>
                                    <button
                                        onClick={() => updateTrack(selectedTrack, { compressor: { ...activeTrackState.compressor, enabled: !activeTrackState.compressor.enabled } })}
                                        className={`h-3 w-6 rounded-full relative transition ${activeTrackState.compressor.enabled ? 'bg-emerald-500' : 'bg-slate-700'}`}
                                    >
                                        <div className={`absolute top-0.5 h-2 w-2 bg-white rounded-full transition-all ${activeTrackState.compressor.enabled ? 'right-0.5' : 'left-0.5'}`} />
                                    </button>
                                </div>

                                <div className="grid grid-cols-2 gap-4">
                                     <div className="flex flex-col gap-1">
                                         <label className="text-[10px] uppercase text-slate-500">Threshold</label>
                                         <input
                                            type="range" min="-60" max="0"
                                            value={activeTrackState.compressor.threshold}
                                            onChange={(e) => updateTrack(selectedTrack, { compressor: { ...activeTrackState.compressor, threshold: parseFloat(e.target.value) } })}
                                            className="accent-emerald-500 h-1 bg-slate-700 rounded appearance-none"
                                         />
                                         <span className="text-xs text-right">{activeTrackState.compressor.threshold} dB</span>
                                     </div>
                                     <div className="flex flex-col gap-1">
                                         <label className="text-[10px] uppercase text-slate-500">Ratio</label>
                                         <input
                                            type="range" min="1" max="20" step="0.5"
                                            value={activeTrackState.compressor.ratio}
                                            onChange={(e) => updateTrack(selectedTrack, { compressor: { ...activeTrackState.compressor, ratio: parseFloat(e.target.value) } })}
                                            className="accent-emerald-500 h-1 bg-slate-700 rounded appearance-none"
                                         />
                                         <span className="text-xs text-right">{activeTrackState.compressor.ratio}:1</span>
                                     </div>
                                </div>
                            </div>
                        </>
                    )}
                </aside>
            </div>
        </div>
    );
}
