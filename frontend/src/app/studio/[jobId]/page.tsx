"use client";

import { useEffect, useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { getBackendBaseUrl, signFileUrl } from "@/lib/mixApi";
import { AuthModal } from "@/components/AuthModal";
import { CanvasWaveform } from "@/components/studio/CanvasWaveform";
import { StudioCache, AudioBufferData } from "@/lib/studioCache";
import {
  PlayIcon,
  PauseIcon,
  ArrowPathIcon,
  MusicalNoteIcon,
  AdjustmentsHorizontalIcon,
  StopIcon,
  ArrowDownTrayIcon,
  CheckIcon,
  XMarkIcon,
  SpeakerWaveIcon,
  SparklesIcon
} from "@heroicons/react/24/solid";

interface StemControl {
  fileName: string;
  stage?: string;
  name: string;
  volume: number;
  pan: {
    value: number;
    enabled: boolean;
  };
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
  signedUrl?: string;
  previewUrl?: string | null;
  peaks?: number[];
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
  const [studioReady, setStudioReady] = useState(false);
  const [rendering, setRendering] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [masterVolume, setMasterVolume] = useState(0.8);
  const [downloadingStems, setDownloadingStems] = useState(false);
  const [downloadingMixdown, setDownloadingMixdown] = useState(false);
  const [mixdownUrl, setMixdownUrl] = useState<string | null>(null);

  // Mixdown buffer now separate from WaveSurfer logic
  const [mixdownBuffer, setMixdownBuffer] = useState<AudioBuffer | null>(null);

  const selectedStem = stems[selectedStemIndex];

  // Removed WaveSurfer refs
  // const waveformRef = useRef<HTMLDivElement>(null);
  // const wavesurferRef = useRef<WaveSurfer | null>(null);

  const audioContextRef = useRef<AudioContext | null>(null);
  const sourceNodesRef = useRef<Map<string, AudioBufferSourceNode>>(new Map());
  const gainNodesRef = useRef<Map<string, GainNode>>(new Map());
  const pannerNodesRef = useRef<Map<string, StereoPannerNode>>(new Map());
  const audioBuffersRef = useRef<Map<string, AudioBuffer>>(new Map());
  const startTimeRef = useRef<number>(0);
  const pauseTimeRef = useRef<number>(0);

  const stopAllSources = () => {
      sourceNodesRef.current.forEach((node) => {
          try { node.stop(); } catch (e) { /* noop */ }
      });
      sourceNodesRef.current.clear();
      gainNodesRef.current.clear();
      pannerNodesRef.current.clear();
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
      try {
        setLoadingStems(true);
        setStudioReady(false);
        setMixdownUrl(null);
        setMixdownBuffer(null);
        stopAllSources();
        audioBuffersRef.current.clear();
        gainNodesRef.current.clear();
        pannerNodesRef.current.clear();
        pauseTimeRef.current = 0;
        setIsPlaying(false);
        setCurrentTime(0);
        setDuration(0);
        const baseUrl = getBackendBaseUrl();

        const res = await fetch(`${baseUrl}/jobs/${jobId}/stems`, {
          headers: {
            "X-API-Key": process.env.NEXT_PUBLIC_MIXMASTER_API_KEY || "",
          },
        });

        let stemsFromApi: any[] = [];
        if (res.ok) {
          const data = await res.json();
          if (Array.isArray(data.stems)) {
            stemsFromApi = data.stems;
          }
        } else {
          stemsFromApi = ["vocals.wav", "drums.wav", "bass.wav", "other.wav"];
        }

        const newStems: StemControl[] = stemsFromApi.map((entry: any) => {
          const file =
            (typeof entry === "string" ? entry : entry?.file || entry?.fileName || entry?.name) ||
            "stem.wav";
          const signedUrl =
            (typeof entry === "object" && entry
              ? entry.url || entry.signedUrl || entry.signed_url
              : undefined) || undefined;
          const previewUrl =
            typeof entry === "object" && entry
              ? entry.preview_url || entry.previewUrl || null
              : null;
          const peaks =
            typeof entry === "object" && Array.isArray(entry?.peaks)
              ? entry.peaks.map((p: any) => Number(p) || 0)
              : undefined;

          return {
            fileName: file,
            stage: typeof entry === "object" && entry?.stage ? entry.stage : undefined,
            name:
              file
                .replace(".wav", "")
                .replace(/_/g, " ")
                .replace("S11", "")
                .replace("S10", "")
                .trim() || file,
            volume: 0,
            pan: { value: 0, enabled: false },
            mute: false,
            solo: false,
            eq: { low: 0, mid: 0, high: 0, enabled: false },
            compression: { threshold: -20, ratio: 2, enabled: false },
            reverb: { amount: 0, enabled: false },
            signedUrl,
            previewUrl,
            peaks,
            url: undefined,
            status: "idle"
          };
        });

        const fallbackStems: StemControl[] = ["vocals.wav", "drums.wav", "bass.wav", "other.wav"].map(
          (file) => ({
            fileName: file,
            name: file.replace(".wav", "").replace(/_/g, " ") || file,
            volume: 0,
            pan: { value: 0, enabled: false },
            mute: false,
            solo: false,
            eq: { low: 0, mid: 0, high: 0, enabled: false },
            compression: { threshold: -20, ratio: 2, enabled: false },
            reverb: { amount: 0, enabled: false },
            signedUrl: undefined,
            previewUrl: null,
            peaks: undefined,
            url: undefined,
            status: "idle" as const
          }),
        );

        const finalStems: StemControl[] = newStems.length ? newStems : fallbackStems;

        const stemFiles = finalStems.map((s) => s.fileName);

        setStems(finalStems);
        setLoadingStems(false); // UI ready while descargas/decodificaciones siguen en background

        const loadAssets = async () => {
          if (!audioContextRef.current) return;
          const metaByFile = new Map(finalStems.map((s) => [s.fileName, s]));

          const loadSingleStem = async (file: string) => {
            if (cancelled) return;
            try {
                // Try cache first
                const cacheKey = `pirola-studio-cache-v1-${jobId}-${file}`;
                const cacheKeyDecoded = `${cacheKey}-decoded`;

                const meta = metaByFile.get(file);

                // Try loading decoded buffer directly
                const cachedDecoded = await StudioCache.getAudioBufferData(cacheKeyDecoded);

                if (cachedDecoded) {
                  // Reconstruct AudioBuffer from cached PCM data
                  const buffer = audioContextRef.current!.createBuffer(
                      cachedDecoded.numberOfChannels,
                      cachedDecoded.length,
                      cachedDecoded.sampleRate
                  );

                  for (let i = 0; i < cachedDecoded.numberOfChannels; i++) {
                      // Note: getChannelData returns a Float32Array, which we can set directly
                      if (cachedDecoded.channels[i]) {
                          buffer.getChannelData(i).set(cachedDecoded.channels[i]);
                      }
                  }

                  audioBuffersRef.current.set(file, buffer);
                  setStems(prev => prev.map(s => {
                      if (s.fileName === file) return { ...s, url: "cached-decoded", status: "ready" };
                      return s;
                  }));
                  setDuration(prev => Math.max(prev, buffer.duration));
                  return; // Done
                }

                // If no decoded cache, try raw file cache or fetch
                let ab: ArrayBuffer | null = await StudioCache.getCachedArrayBuffer(cacheKey);
                let fetchUrl = meta?.signedUrl || meta?.url;
                let usedUrl = fetchUrl || "";

                if (!ab) {
                    // Cache miss, fetch
                    let resp: Response | null = null;
                    if (fetchUrl) {
                        try {
                            resp = await fetch(fetchUrl);
                        } catch (e) {
                            resp = null;
                        }
                    }

                    const stageCandidates = [
                        meta?.stage,
                        "S6_MANUAL_CORRECTION",
                        "S6_MANUAL_CORRECTION_ADJUSTMENT",
                        "S12_SEPARATE_STEMS",
                        "S5_LEADVOX_DYNAMICS",
                        "S5_STEM_DYNAMICS_GENERIC",
                        "S4_STEM_RESONANCE_CONTROL",
                        "S0_SESSION_FORMAT",
                        "S0_MIX_ORIGINAL"
                    ].filter(Boolean) as string[];

                    let fallbackSignedUrl = fetchUrl || "";

                    if (!resp || !resp.ok) {
                        for (const stage of stageCandidates) {
                            fallbackSignedUrl = await signFileUrl(jobId, `${stage}/${file}`);
                            resp = await fetch(fallbackSignedUrl);
                            if (resp.ok) {
                                usedUrl = fallbackSignedUrl;
                                break;
                            }
                        }
                    } else {
                        usedUrl = fetchUrl || "";
                    }

                    if (resp && resp.ok) {
                        ab = await resp.arrayBuffer();
                        // Store in cache (background)
                        StudioCache.cacheArrayBuffer(cacheKey, ab).catch(e => console.warn("Background cache error", e));
                    } else {
                        throw new Error(`Failed to fetch stem ${file}`);
                    }
                }

                if (ab && !cancelled) {
                    const decodePromise = audioContextRef.current!.decodeAudioData(ab.slice(0)); // slice to clone if needed
                    const timeoutPromise = new Promise<AudioBuffer>((_, reject) =>
                        setTimeout(() => reject(new Error("Audio decoding timed out")), 15000)
                    );

                    const decoded = await Promise.race([decodePromise, timeoutPromise]);
                    audioBuffersRef.current.set(file, decoded);

                    // Cache decoded data for next time
                    const channels: Float32Array[] = [];
                    for(let i=0; i<decoded.numberOfChannels; i++) {
                        channels.push(decoded.getChannelData(i));
                    }
                    const decodedData: AudioBufferData = {
                        sampleRate: decoded.sampleRate,
                        length: decoded.length,
                        numberOfChannels: decoded.numberOfChannels,
                        channels: channels
                    };
                    StudioCache.cacheAudioBufferData(cacheKeyDecoded, decodedData).catch(e => console.warn("Background decoded cache error", e));

                    setStems(prev => prev.map(s => {
                        if (s.fileName === file) return { ...s, url: usedUrl || "cached", status: "ready" };
                        return s;
                    }));

                    setDuration(prev => Math.max(prev, decoded.duration));
                }
            } catch (e) {
                console.error("Failed to load stem", file, e);
                setStems(prev => prev.map(s => {
                    if (s.fileName === file) return { ...s, status: "error" };
                    return s;
                }));
            }
          };

          const queue: string[] = [...stemFiles];
          // Parallelism: use more workers
          const concurrency =
            typeof navigator !== "undefined"
              ? Math.min(4, Math.max(1, navigator.hardwareConcurrency || 4))
              : 4;
          const workers = Array.from({ length: Math.min(concurrency, queue.length) }, async () => {
            while (!cancelled && queue.length > 0) {
                const next = queue.shift();
                if (!next) break;
                await loadSingleStem(next);
            }
          });
          await Promise.all(workers);

          // Load mixdown for fallback waveform
          // Also try to cache mixdown buffer
          if (!cancelled) {
              const preferredMixdownPaths = [
                  "S5_LEADVOX_DYNAMICS/full_song.wav",
                  "S5_STEM_DYNAMICS_GENERIC/full_song.wav",
                  "S4_STEM_RESONANCE_CONTROL/full_song.wav",
                  "S3_MIXBUS_HEADROOM/full_song.wav",
                  "S3_LEADVOX_AUDIBILITY/full_song.wav",
                  "S0_SESSION_FORMAT/full_song.wav",
                  "S0_MIX_ORIGINAL/full_song.wav"
              ];

              const mixCacheKey = `pirola-studio-cache-v1-${jobId}-mixdown`;
              const mixCacheKeyDecoded = `${mixCacheKey}-decoded`;

              let mixDecoded = await StudioCache.getAudioBufferData(mixCacheKeyDecoded);
              let mixAb: ArrayBuffer | null = null;

              if (mixDecoded && audioContextRef.current) {
                   const buffer = audioContextRef.current.createBuffer(
                      mixDecoded.numberOfChannels,
                      mixDecoded.length,
                      mixDecoded.sampleRate
                  );
                  for (let i = 0; i < mixDecoded.numberOfChannels; i++) {
                      if (mixDecoded.channels[i]) {
                          buffer.getChannelData(i).set(mixDecoded.channels[i]);
                      }
                  }
                  setMixdownBuffer(buffer);
                  if (!duration) setDuration(buffer.duration);
              } else {
                  // Fallback to file cache
                  mixAb = await StudioCache.getCachedArrayBuffer(mixCacheKey);

                  if (!mixAb) {
                     for (const relPath of preferredMixdownPaths) {
                        if (cancelled) break;
                        try {
                            const signedUrl = await signFileUrl(jobId, relPath);
                            const resp = await fetch(signedUrl);
                            if (resp.ok) {
                                mixAb = await resp.arrayBuffer();
                                setMixdownUrl(signedUrl);
                                StudioCache.cacheArrayBuffer(mixCacheKey, mixAb).catch(console.warn);
                                break;
                            }
                        } catch (e) {
                             // continue
                        }
                     }
                  }

                  if (mixAb && audioContextRef.current) {
                      try {
                          const decoded = await audioContextRef.current.decodeAudioData(mixAb.slice(0));
                          setMixdownBuffer(decoded);

                          const channels: Float32Array[] = [];
                          for(let i=0; i<decoded.numberOfChannels; i++) {
                             channels.push(decoded.getChannelData(i));
                          }
                          StudioCache.cacheAudioBufferData(mixCacheKeyDecoded, {
                             sampleRate: decoded.sampleRate,
                             length: decoded.length,
                             numberOfChannels: decoded.numberOfChannels,
                             channels
                          }).catch(console.warn);

                          if (!duration) setDuration(decoded.duration);
                      } catch (e) {
                          console.warn("Failed to decode mixdown", e);
                      }
                  }
              }
          }

          if (!cancelled) {
            setStudioReady(true);
            setLoadingStems(false);
          }
        };

        loadAssets().catch(err => console.error("Studio: background load error", err));
      } catch (err) {
        console.error("Error loading stems:", err);
        setStudioReady(true);
        setLoadingStems(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [jobId, user]);

  // Load stem when selected if not loaded (same logic, add cache)
  useEffect(() => {
    const ctx = audioContextRef.current;
    const stem = selectedStem;
    if (!ctx || !jobId || !user || !stem) return;
    if (stem.status === "loading" || stem.status === "error") return;
    if (stem.status === "ready" && audioBuffersRef.current.has(stem.fileName)) return;

    let cancelled = false;

    const loadStem = async () => {
        try {
            setStems(prev => prev.map((s, i) => i === selectedStemIndex ? { ...s, status: "loading" } : s));

            const cacheKey = `pirola-studio-cache-v1-${jobId}-${stem.fileName}`;
            const cacheKeyDecoded = `${cacheKey}-decoded`;

            // Try decoded first
            const cachedDecoded = await StudioCache.getAudioBufferData(cacheKeyDecoded);

            if (cachedDecoded && !cancelled) {
                 const buffer = ctx.createBuffer(
                      cachedDecoded.numberOfChannels,
                      cachedDecoded.length,
                      cachedDecoded.sampleRate
                  );
                  for (let i = 0; i < cachedDecoded.numberOfChannels; i++) {
                      if (cachedDecoded.channels[i]) {
                          buffer.getChannelData(i).set(cachedDecoded.channels[i]);
                      }
                  }
                  audioBuffersRef.current.set(stem.fileName, buffer);
                  setStems(prev => prev.map((s, i) => i === selectedStemIndex ? { ...s, url: "cached-decoded", status: "ready" } : s));
                  setDuration(prev => Math.max(prev, buffer.duration));
                  return;
            }

            let ab: ArrayBuffer | null = await StudioCache.getCachedArrayBuffer(cacheKey);
            let usedUrl = stem.signedUrl || stem.url || "";

            if (!ab) {
                let resp: Response | null = null;
                if (stem.signedUrl) {
                    try {
                        resp = await fetch(stem.signedUrl);
                        usedUrl = stem.signedUrl;
                    } catch (e) {
                        resp = null;
                    }
                }

                const stageCandidates = [
                    stem.stage,
                    "S6_MANUAL_CORRECTION",
                    "S6_MANUAL_CORRECTION_ADJUSTMENT",
                    "S12_SEPARATE_STEMS",
                    "S5_LEADVOX_DYNAMICS",
                    "S5_STEM_DYNAMICS_GENERIC",
                    "S4_STEM_RESONANCE_CONTROL",
                    "S0_SESSION_FORMAT",
                    "S0_MIX_ORIGINAL"
                ].filter(Boolean) as string[];

                if (!resp || !resp.ok) {
                    for (const stage of stageCandidates) {
                        const candidateUrl = await signFileUrl(jobId, `${stage}/${stem.fileName}`);
                        resp = await fetch(candidateUrl);
                        if (resp.ok) {
                            usedUrl = candidateUrl;
                            break;
                        }
                    }
                }

                if (!resp || !resp.ok) {
                    throw new Error(`Failed to fetch stem ${stem.fileName}`);
                }

                ab = await resp.arrayBuffer();
                StudioCache.cacheArrayBuffer(cacheKey, ab).catch(console.warn);
            }

            if (!cancelled && ab) {
                const decoded = await ctx.decodeAudioData(ab.slice(0));
                if (cancelled) return;

                audioBuffersRef.current.set(stem.fileName, decoded);

                // Cache decoded
                const channels: Float32Array[] = [];
                for(let i=0; i<decoded.numberOfChannels; i++) {
                   channels.push(decoded.getChannelData(i));
                }
                StudioCache.cacheAudioBufferData(cacheKeyDecoded, {
                     sampleRate: decoded.sampleRate,
                     length: decoded.length,
                     numberOfChannels: decoded.numberOfChannels,
                     channels
                }).catch(console.warn);

                setStems(prev => prev.map((s, i) => i === selectedStemIndex ? { ...s, url: usedUrl || "cached", status: "ready" } : s));
                setDuration(prev => Math.max(prev, decoded.duration));
            }
        } catch (err) {
            if (!cancelled) {
                console.error("Failed to load stem", stem.fileName, err);
                setStems(prev => prev.map((s, i) => i === selectedStemIndex ? { ...s, status: "error" } : s));
            }
        }
    };

    loadStem();
    return () => { cancelled = true; };
  }, [jobId, user, selectedStemIndex, selectedStem, duration]);

  // Removed WaveSurfer setup effect

  const togglePlay = async () => {
      const ctx = audioContextRef.current;
      if (!ctx || stems.length === 0) return;

      if (ctx.state === 'suspended') await ctx.resume();

      if (isPlaying) {
          stopAllSources();
          pauseTimeRef.current = ctx.currentTime - startTimeRef.current;
          setIsPlaying(false);
          return;
      }

      const activeStems = stems.filter(s => audioBuffersRef.current.has(s.fileName));
      // if (activeStems.length === 0) return; // Allow playing if only mixdown loaded?
      // Current logic relies on stems. If mixdown fallback is needed for playback, it would need changes.
      // But user has stems here usually.

      stopAllSources();

      if (duration > 0 && pauseTimeRef.current >= duration) {
          pauseTimeRef.current = 0;
      }

      const offset = pauseTimeRef.current;
      startTimeRef.current = ctx.currentTime - offset;

      const anySolo = stems.some(s => s.solo);

      activeStems.forEach(stem => {
          const buffer = audioBuffersRef.current.get(stem.fileName);
          if (!buffer) return;

          const source = ctx.createBufferSource();
          source.buffer = buffer;

          const gain = ctx.createGain();
          let shouldMute = stem.mute;
          if (anySolo) shouldMute = !stem.solo;

          const vol = Math.pow(10, stem.volume / 20) * masterVolume;
          gain.gain.value = shouldMute ? 0 : vol;

          const panner = ctx.createStereoPanner();
          panner.pan.value = stem.pan.enabled ? stem.pan.value : 0;

          source.connect(gain);
          gain.connect(panner);
          panner.connect(ctx.destination);

          source.start(0, offset);

          sourceNodesRef.current.set(stem.fileName, source);
          gainNodesRef.current.set(stem.fileName, gain);
          pannerNodesRef.current.set(stem.fileName, panner);
      });

      setIsPlaying(true);
  };

  const seek = (time: number) => {
      const ctx = audioContextRef.current;
      if (!ctx) return;

      let t = Math.max(0, Math.min(time, duration));

      const wasPlaying = isPlaying;
      if (wasPlaying) {
          stopAllSources();
      }

      pauseTimeRef.current = t;
      setCurrentTime(t);

      if (wasPlaying) {
          setIsPlaying(false);
          setTimeout(() => {
             if (ctx.state === 'suspended') ctx.resume();

             const activeStems = stems.filter(s => audioBuffersRef.current.has(s.fileName));
             if (activeStems.length === 0) {
                 setIsPlaying(true);
                 return;
             }

             const offset = t;
             startTimeRef.current = ctx.currentTime - offset;
             const anySolo = stems.some(s => s.solo);

             activeStems.forEach(stem => {
                const buffer = audioBuffersRef.current.get(stem.fileName);
                if (!buffer) return;
                const source = ctx.createBufferSource();
                source.buffer = buffer;
                const gain = ctx.createGain();
                let shouldMute = stem.mute;
                if (anySolo) shouldMute = !stem.solo;
                const vol = Math.pow(10, stem.volume / 20) * masterVolume;
                gain.gain.value = shouldMute ? 0 : vol;
                const panner = ctx.createStereoPanner();
                panner.pan.value = stem.pan.enabled ? stem.pan.value : 0;
                source.connect(gain);
                gain.connect(panner);
                panner.connect(ctx.destination);
                source.start(0, offset);
                sourceNodesRef.current.set(stem.fileName, source);
                gainNodesRef.current.set(stem.fileName, gain);
                pannerNodesRef.current.set(stem.fileName, panner);
             });
             setIsPlaying(true);
          }, 0);
      }
  };

  const handleTimelineClick = (e: React.MouseEvent<HTMLDivElement>) => {
      const rect = e.currentTarget.getBoundingClientRect();
      const pct = (e.clientX - rect.left) / rect.width;
      seek(pct * duration);
  };

  useEffect(() => {
      let raf: number;
      const update = () => {
          if (isPlaying && audioContextRef.current) {
              const now = audioContextRef.current.currentTime - startTimeRef.current;
              if (duration > 0 && now >= duration) {
                  setIsPlaying(false);
                  stopAllSources();
                  pauseTimeRef.current = 0;
                  setCurrentTime(0);
              } else {
                  setCurrentTime(now);
                  raf = requestAnimationFrame(update);
              }
          }
      };
      if (isPlaying) update();
      return () => cancelAnimationFrame(raf);
  }, [isPlaying, duration]);

  useEffect(() => {
      const anySolo = stems.some(s => s.solo);
      stems.forEach(stem => {
          const gainNode = gainNodesRef.current.get(stem.fileName);
          const pannerNode = pannerNodesRef.current.get(stem.fileName);

          if (gainNode) {
              let shouldMute = stem.mute;
              if (anySolo) shouldMute = !stem.solo;
              const vol = Math.pow(10, stem.volume / 20) * masterVolume;
              gainNode.gain.setTargetAtTime(shouldMute ? 0 : vol, audioContextRef.current!.currentTime, 0.05);
          }
          if (pannerNode) {
               pannerNode.pan.setTargetAtTime(stem.pan.enabled ? stem.pan.value : 0, audioContextRef.current!.currentTime, 0.05);
          }
      });
  }, [stems, masterVolume]);

  const handleApplyCorrection = async (proceedToMastering: boolean) => {
      setRendering(true);
      try {
          const corrections = stems.map(s => ({
              name: s.name,
              volume_db: s.volume,
              pan: s.pan.enabled ? s.pan.value : 0,
              eq: s.eq.enabled ? s.eq : undefined,
              compression: s.compression.enabled ? s.compression : undefined,
              reverb: s.reverb.enabled ? s.reverb : undefined,
              mute: s.mute,
              solo: s.solo
          }));

          const baseUrl = getBackendBaseUrl();
          await fetch(`${baseUrl}/jobs/${jobId}/correction`, {
              method: 'POST',
              headers: {
                  'Content-Type': 'application/json',
                  "X-API-Key": process.env.NEXT_PUBLIC_MIXMASTER_API_KEY || "",
              },
              body: JSON.stringify({ corrections })
          });

          let stages: string[] = [];
          if (proceedToMastering) {
              stages = [
                  "S6_MANUAL_CORRECTION",
                  "S7_MIXBUS_TONAL_BALANCE",
                  "S8_MIXBUS_COLOR_GENERIC",
                  "S9_MASTER_GENERIC",
                  "S10_MASTER_FINAL_LIMITS",
                  "S11_REPORT_GENERATION"
              ];
          } else {
              stages = [
                  "S6_MANUAL_CORRECTION",
                  "S11_REPORT_GENERATION"
              ];
          }

          await fetch(`${baseUrl}/mix/${jobId}/start`, {
               method: 'POST',
               headers: {
                   'Content-Type': 'application/json',
                   "X-API-Key": process.env.NEXT_PUBLIC_MIXMASTER_API_KEY || ""
               },
               body: JSON.stringify({ stages })
          });

          router.push(`/?view=tool&jobId=${encodeURIComponent(jobId)}`);
      } catch (err) {
          console.error(err);
          alert("Error sending corrections");
      } finally {
          setRendering(false);
      }
  };

  const downloadStems = async () => {
      setDownloadingStems(true);
      try {
          const baseUrl = getBackendBaseUrl();
          const url = `${baseUrl}/jobs/${jobId}/download-stems-zip`;
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
      } finally {
          setDownloadingStems(false);
      }
  };

  const downloadMixdown = async () => {
       setDownloadingMixdown(true);
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
       } finally {
           setDownloadingMixdown(false);
       }
  };

  const updateStem = (index: number, updates: Partial<StemControl>) => {
      setStems(prev => {
          const next = [...prev];
          next[index] = { ...next[index], ...updates };
          return next;
      });
  };

  // Get current stem buffer or mixdown for visualization
  const currentVisualBuffer = selectedStem && audioBuffersRef.current.get(selectedStem.fileName)
        ? audioBuffersRef.current.get(selectedStem.fileName)
        : mixdownBuffer;
  const currentVisualPeaks = selectedStem?.peaks;

  if (authLoading) return <div className="h-screen bg-[#0f111a]"></div>;

  if (!user) {
      return (
        <div className="h-screen bg-[#0f111a] flex items-center justify-center text-slate-500">
            <AuthModal isOpen={true} onClose={() => router.push('/')} />
        </div>
      );
  }

  if (loadingStems) {
      return (
        <div className="h-screen bg-[#0f111a] flex flex-col items-center justify-center text-emerald-500 font-mono gap-3">
            <div className="h-10 w-10 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
            <div>Loading Piroola Studio...</div>
            <div className="text-xs text-slate-500">Cargando stems y forma de onda</div>
        </div>
      );
  }

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
             <div className="flex flex-col items-end">
                 <button onClick={downloadStems} disabled={downloadingStems} className="px-3 py-1.5 text-xs font-medium text-slate-400 hover:text-white border border-white/10 rounded hover:bg-white/5 transition-colors flex items-center gap-2">
                     <ArrowDownTrayIcon className="w-3 h-3" /> Stems (ZIP)
                 </button>
                 {downloadingStems && <span className="text-[10px] text-emerald-500 animate-pulse mt-1">Descargando...</span>}
             </div>

             <div className="flex flex-col items-end">
                 <button onClick={downloadMixdown} disabled={downloadingMixdown} className="px-3 py-1.5 text-xs font-medium text-slate-400 hover:text-white border border-white/10 rounded hover:bg-white/5 transition-colors flex items-center gap-2">
                     <ArrowDownTrayIcon className="w-3 h-3" /> Mixdown
                 </button>
                 {downloadingMixdown && <span className="text-[10px] text-emerald-500 animate-pulse mt-1">Descargando...</span>}
             </div>

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

             <div className="flex-1 relative flex items-center justify-center p-10">

                 {/* Interactive Waveform Main Display */}
                 <div className="w-full h-[300px] opacity-80 cursor-pointer">
                 <CanvasWaveform
                    audioBuffer={currentVisualBuffer || null}
                    peaksData={currentVisualPeaks || null}
                    currentTime={currentTime}
                    duration={duration}
                    onSeek={seek}
                 />
                 </div>

                 {!currentVisualBuffer && !currentVisualPeaks && (
                     <div className="absolute inset-0 flex items-center justify-center text-slate-600 font-mono pointer-events-none">
                         {loadingStems ? "Loading..." : "Select a track to view waveform"}
                     </div>
                 )}
             </div>

             {/* Footer Transport Section */}
             <div className="h-28 bg-[#11131f] border-t border-white/5 flex flex-col shrink-0 z-20">

                 {/* New Timeline Bar placement */}
                 <div
                     className="h-6 w-full bg-[#0f111a] border-b border-white/5 relative cursor-pointer group select-none hover:bg-[#161b2e] transition-colors"
                     onClick={handleTimelineClick}
                 >
                     {/* Background Grid */}
                     <div className="absolute inset-0 opacity-20 flex justify-between px-2">
                         {Array.from({length: 40}).map((_, i) => (
                             <div key={i} className="w-px h-full bg-white/20"></div>
                         ))}
                     </div>

                     {/* Progress Fill */}
                     <div className="absolute top-0 left-0 bottom-0 bg-emerald-500/20 pointer-events-none transition-all duration-75" style={{ width: `${duration ? (currentTime / duration) * 100 : 0}%` }}></div>

                     {/* Playhead */}
                     <div className="absolute top-0 bottom-0 w-0.5 bg-yellow-400 z-10 pointer-events-none shadow-[0_0_10px_rgba(250,204,21,0.5)] transition-all duration-75" style={{ left: `${duration ? (currentTime / duration) * 100 : 0}%` }}></div>

                     <div className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] font-mono text-emerald-500">
                         {formatTime(currentTime)} / {formatTime(duration)}
                     </div>
                 </div>

                 <div className="flex-1 px-6 flex items-center justify-between">
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
                         <div className="flex items-center gap-4">
                            <button onClick={() => { setIsPlaying(false); stopAllSources(); setCurrentTime(0); pauseTimeRef.current = 0; }} className="text-slate-500 hover:text-white transition-colors"><StopIcon className="w-4 h-4" /></button>
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
                    {/* EQ */}
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
                             {/* ... visualizer placeholder ... */}
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

                    {/* Compressor */}
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

                    {/* Pan */}
                    <div className="bg-[#1e2336] rounded-xl p-4 border border-white/5 shadow-lg">
                        <div className="flex justify-between items-center mb-4">
                            <div className="flex items-center gap-2">
                                <input
                                    type="checkbox"
                                    checked={selectedStem.pan.enabled}
                                    onChange={(e) => updateStem(selectedStemIndex, { pan: {...selectedStem.pan, enabled: e.target.checked}})}
                                    className="rounded border-slate-600 bg-slate-800 text-blue-500 focus:ring-blue-500"
                                />
                                <span className={`text-xs font-bold ${selectedStem.pan.enabled ? 'text-blue-400' : 'text-slate-500'}`}>Panning</span>
                            </div>
                            <SpeakerWaveIcon className="w-4 h-4 text-slate-600" />
                        </div>
                        <div className={`flex justify-center transition-opacity ${selectedStem.pan.enabled ? 'opacity-100' : 'opacity-40 pointer-events-none'}`}>
                             <Knob label="L / R" value={selectedStem.pan.value} min={-1} max={1} step={0.1} onChange={(v) => updateStem(selectedStemIndex, { pan: {...selectedStem.pan, value: v}})} />
                        </div>
                    </div>

                    {/* Reverb */}
                    <div className="bg-[#1e2336] rounded-xl p-4 border border-white/5 shadow-lg">
                        <div className="flex justify-between items-center mb-4">
                            <div className="flex items-center gap-2">
                                <input
                                    type="checkbox"
                                    checked={selectedStem.reverb.enabled}
                                    onChange={(e) => updateStem(selectedStemIndex, { reverb: {...selectedStem.reverb, enabled: e.target.checked}})}
                                    className="rounded border-slate-600 bg-slate-800 text-purple-500 focus:ring-purple-500"
                                />
                                <span className={`text-xs font-bold ${selectedStem.reverb.enabled ? 'text-purple-400' : 'text-slate-500'}`}>Reverb</span>
                            </div>
                            <SparklesIcon className="w-4 h-4 text-slate-600" />
                        </div>
                        <div className={`flex justify-center transition-opacity ${selectedStem.reverb.enabled ? 'opacity-100' : 'opacity-40 pointer-events-none'}`}>
                             <Knob label="AMOUNT" value={selectedStem.reverb.amount} min={0} max={100} onChange={(v) => updateStem(selectedStemIndex, { reverb: {...selectedStem.reverb, amount: v}})} />
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
