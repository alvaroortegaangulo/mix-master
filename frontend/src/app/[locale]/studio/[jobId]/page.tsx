"use client";

import { useEffect, useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { getBackendBaseUrl, getStudioToken, signFileUrl } from "@/lib/mixApi";
import { AuthModal } from "@/components/AuthModal";
import { CanvasWaveform } from "@/components/studio/CanvasWaveform";
import { studioCache, AudioBufferData } from "@/lib/studioCache";
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
import { useTranslations } from "next-intl";

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

function buildAuthHeaders(extra?: HeadersInit): HeadersInit {
  const headers: Record<string, string> = {};
  const apiKey = process.env.NEXT_PUBLIC_MIXMASTER_API_KEY;
  if (apiKey) {
    headers["X-API-Key"] = apiKey;
  }
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("access_token");
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
  }
  return { ...headers, ...(extra || {}) };
}

export default function StudioPage() {
  const params = useParams();
  const jobId = params.jobId as string;
  const locale = params.locale as string;
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [showAuthModal, setShowAuthModal] = useState(false);
  const t = useTranslations('Studio');

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
  const [studioToken, setStudioToken] = useState<string | null>(null);

  const [visualBuffer, setVisualBuffer] = useState<AudioBuffer | null>(null);

  const selectedStem = stems[selectedStemIndex];

  const audioContextRef = useRef<AudioContext | null>(null);
  const masterGainNodeRef = useRef<GainNode | null>(null);
  const masterAnalyserNodeRef = useRef<AnalyserNode | null>(null);

  const audioElsRef = useRef<Map<string, HTMLAudioElement>>(new Map());
  const mediaNodesRef = useRef<Map<string, MediaElementAudioSourceNode>>(new Map());
  const gainNodesRef = useRef<Map<string, GainNode>>(new Map());
  const pannerNodesRef = useRef<Map<string, StereoPannerNode>>(new Map());
  const startTimeRef = useRef<number>(0);
  const pauseTimeRef = useRef<number>(0);

  const stopAllSources = () => {
      audioElsRef.current.forEach((el) => {
          try { el.pause(); } catch (e) { /* noop */ }
      });
  };

  const waitForMediaReady = (el: HTMLAudioElement, timeoutMs = 5000) => {
      if (el.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
          return Promise.resolve();
      }
      return new Promise<void>((resolve, reject) => {
          const onReady = () => {
              cleanup();
              resolve();
          };
          const onError = () => {
              cleanup();
              reject(new Error("media error"));
          };
          const cleanup = () => {
              el.removeEventListener("loadedmetadata", onReady);
              el.removeEventListener("canplay", onReady);
              el.removeEventListener("canplaythrough", onReady);
              el.removeEventListener("error", onError);
          };
          el.addEventListener("loadedmetadata", onReady);
          el.addEventListener("canplay", onReady);
          el.addEventListener("canplaythrough", onReady);
          el.addEventListener("error", onError);
          if (timeoutMs > 0) {
              setTimeout(() => {
                  cleanup();
                  resolve();
              }, timeoutMs);
          }
      });
  };

  useEffect(() => {
    if (!authLoading && !user) {
      setShowAuthModal(true);
    }
  }, [authLoading, user]);

  useEffect(() => {
    if (typeof window !== "undefined" && !audioContextRef.current) {
      try {
        const ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
        audioContextRef.current = ctx;

        // Create Master Chain
        const masterGain = ctx.createGain();
        masterGain.gain.value = masterVolume; // Init volume
        const analyser = ctx.createAnalyser();
        analyser.fftSize = 2048;
        analyser.smoothingTimeConstant = 0.85;

        // Connect Chain: MasterGain -> Analyser -> Destination
        masterGain.connect(analyser);
        analyser.connect(ctx.destination);

        masterGainNodeRef.current = masterGain;
        masterAnalyserNodeRef.current = analyser;

      } catch (e) {
        console.error("Studio: AudioContext init error", e);
      }
    }
    return () => {
        audioContextRef.current?.close();
    };
  }, []);

  // Update Master Volume
  useEffect(() => {
      if (masterGainNodeRef.current && audioContextRef.current) {
          masterGainNodeRef.current.gain.setTargetAtTime(
              masterVolume,
              audioContextRef.current.currentTime,
              0.05
          );
      }
  }, [masterVolume]);


  // Effect to load waveform data for selected stem
  useEffect(() => {
    if (!selectedStem || !audioContextRef.current) return;

    // If we have valid peaks (sum > 0), use them
    const hasPeaks = selectedStem.peaks && selectedStem.peaks.length > 0 && selectedStem.peaks.some(p => p > 0);
    if (hasPeaks) {
        setVisualBuffer(null);
        return;
    }

    let active = true;
    setVisualBuffer(null); // Clear while loading

    const loadAudio = async () => {
        try {
            const cacheKey = `${jobId}/${selectedStem.fileName}`;
            // Try cache first
            const cachedData = await studioCache.getAudioBuffer(cacheKey);
            if (active && cachedData) {
                const buffer = dataToAudioBuffer(audioContextRef.current!, cachedData);
                setVisualBuffer(buffer);
                return;
            }

            // Fetch and decode
            if (!selectedStem.url) return;
            const resp = await fetch(selectedStem.url);
            if (!resp.ok) return;
            const arrayBuffer = await resp.arrayBuffer();

            if (active && audioContextRef.current) {
                // Decode
                const audioBuffer = await audioContextRef.current.decodeAudioData(arrayBuffer);
                // Cache
                await studioCache.setAudioBuffer(cacheKey, audioBufferToData(audioBuffer));

                if (active) {
                    setVisualBuffer(audioBuffer);
                }
            }
        } catch (e) {
            console.warn("Waveform generation failed", e);
        }
    };

    loadAudio();
    return () => { active = false; };
  }, [selectedStem, jobId]);

  useEffect(() => {
    if (!jobId || !user) return;

    let cancelled = false;

    async function load() {
      try {
        setLoadingStems(true);
        setStudioReady(false);
        setStudioToken(null);
        stopAllSources();
        audioElsRef.current.forEach((el) => {
            try { el.pause(); } catch (_) { /* noop */ }
            try { el.src = ""; el.load(); } catch (_) { /* noop */ }
        });
        audioElsRef.current.clear();
        mediaNodesRef.current.clear();
        gainNodesRef.current.clear();
        pannerNodesRef.current.clear();
        pauseTimeRef.current = 0;
        setIsPlaying(false);
        setCurrentTime(0);
        setDuration(0);
        const baseUrl = getBackendBaseUrl();

        let tokenValue: string | null = null;
        try {
            const tokenResp = await getStudioToken(jobId);
            tokenValue = tokenResp.token;
            setStudioToken(tokenResp.token);
        } catch (e) {
            console.warn("Studio: could not fetch stable token", e);
        }

        const res = await fetch(`${baseUrl}/jobs/${jobId}/stems`, {
          headers: buildAuthHeaders(),
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

        const stageFallbacks = [
            "S6_MANUAL_CORRECTION",
            "S6_MANUAL_CORRECTION_ADJUSTMENT",
            "S12_SEPARATE_STEMS",
            "S5_LEADVOX_DYNAMICS",
            "S5_STEM_DYNAMICS_GENERIC",
            "S4_STEM_RESONANCE_CONTROL",
            "S0_SESSION_FORMAT",
            "S0_MIX_ORIGINAL"
        ];

        const resolvedStems: StemControl[] = [];

        for (const stem of finalStems) {
            const candidates: string[] = [];
            if (stem.stage) {
                candidates.push(`${stem.stage}/${stem.fileName}`);
            }
            stageFallbacks.forEach((stage) => candidates.push(`${stage}/${stem.fileName}`));
            candidates.push(stem.fileName);

            let resolvedUrl = stem.signedUrl || stem.url || "";
            if (!resolvedUrl) {
                try {
                    resolvedUrl = await signFileUrl(jobId, candidates[0] || stem.fileName, tokenValue || undefined);
                } catch (e) {
                    resolvedUrl = "";
                }
            }

            resolvedStems.push({
                ...stem,
                url: resolvedUrl || undefined,
            });
        }

        if (cancelled) return;

        // Asegurar peaks para la waveform (si no vienen en payload)
        const stemsWithPeaks = await Promise.all(
            resolvedStems.map(async (stem) => {
                if (stem.peaks && stem.peaks.length) return stem;
                const stemBase = stem.fileName.replace(/\.wav$/i, "");
                const peakCandidates: string[] = [];
                if (stem.stage) peakCandidates.push(`${stem.stage}/peaks/${stemBase}.peaks.json`);

                for (const rel of peakCandidates) {
                    try {
                        const url = await signFileUrl(jobId, rel, tokenValue || undefined);
                        const resp = await fetch(url);
                        if (resp.ok) {
                            const data = await resp.json();
                            if (Array.isArray(data) && data.length) {
                                return { ...stem, peaks: data.map((x: any) => Number(x) || 0) };
                            }
                        }
                    } catch (_) {
                        // continuar con siguiente candidato
                    }
                }
                return { ...stem, peaks: undefined };
            })
        );

        if (cancelled) return;
        setStems(stemsWithPeaks);
        // Mostrar UI aunque sigamos preparando audio; waveform puede usar peaks ya.
        setLoadingStems(false);

        const ensureAudioForStem = async (stem: StemControl) => {
            let audio = audioElsRef.current.get(stem.fileName);
            if (!audio) {
                audio = new Audio(stem.url || "");
                audio.preload = "auto";
                audio.crossOrigin = "anonymous";

                const ctx = audioContextRef.current;
                // Wait for master node to be ready (useEffect runs first but safe check)
                if (ctx && masterGainNodeRef.current && !mediaNodesRef.current.has(stem.fileName)) {
                    const mediaNode = ctx.createMediaElementSource(audio);
                    const gain = ctx.createGain();
                    const panner = ctx.createStereoPanner();
                    mediaNode.connect(gain);
                    gain.connect(panner);
                    // Connect to Master Bus instead of ctx.destination
                    panner.connect(masterGainNodeRef.current);

                    mediaNodesRef.current.set(stem.fileName, mediaNode);
                    gainNodesRef.current.set(stem.fileName, gain);
                    pannerNodesRef.current.set(stem.fileName, panner);
                }

                const candidates: string[] = [];
                if (stem.stage) candidates.push(`${stem.stage}/${stem.fileName}`);
                stageFallbacks.forEach((stage) => candidates.push(`${stage}/${stem.fileName}`));
                candidates.push(stem.fileName);
                let candidateIndex = 0;

                const updateUrl = async (index: number) => {
                    const path = candidates[index] || stem.fileName;
                    const newUrl = await signFileUrl(jobId, path, tokenValue || undefined);
                    audio!.src = newUrl;
                    audio!.load();
                    setStems(prev => prev.map(s => s.fileName === stem.fileName ? { ...s, url: newUrl } : s));
                };

                audio.addEventListener("loadedmetadata", () => {
                    setDuration(prev => Math.max(prev, isFinite(audio!.duration) ? audio!.duration : prev));
                });
                audio.addEventListener("canplay", () => {
                    setStems(prev => prev.map(s => s.fileName === stem.fileName ? { ...s, status: "ready" } : s));
                    setDuration(prev => Math.max(prev, isFinite(audio!.duration) ? audio!.duration : prev));
                });
                audio.addEventListener("ended", () => {
                    if (cancelled) return;
                    const anyPlaying = Array.from(audioElsRef.current.values()).some(a => !a.paused && !a.ended);
                    if (!anyPlaying) {
                        setIsPlaying(false);
                        pauseTimeRef.current = 0;
                        setCurrentTime(0);
                    }
                });
                audio.addEventListener("error", () => {
                    if (cancelled) return;
                    candidateIndex += 1;
                    if (candidateIndex < candidates.length) {
                        updateUrl(candidateIndex).catch(() => {
                            setStems(prev => prev.map(s => s.fileName === stem.fileName ? { ...s, status: "error" } : s));
                        });
                    } else {
                        setStems(prev => prev.map(s => s.fileName === stem.fileName ? { ...s, status: "error" } : s));
                    }
                });

                audioElsRef.current.set(stem.fileName, audio);
            } else if (stem.url && audio.src !== stem.url) {
                audio.src = stem.url;
                audio.load();
            }
            return audio;
        };

        const readyPromises = resolvedStems.map(async (stem) => {
            const el = await ensureAudioForStem(stem);
            try {
                await waitForMediaReady(el, 4000);
            } catch {
                // ignore timeout
            }
        });

        await Promise.all(readyPromises);

        if (!cancelled) {
            setStudioReady(true);
        }
      } catch (err) {
        console.error("Error loading stems:", err);
        setStudioReady(true);
        setLoadingStems(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [jobId, user]);

  // Removed WaveSurfer setup effect

  const togglePlay = async () => {
      const ctx = audioContextRef.current;
      if (!ctx || stems.length === 0) return;

      if (ctx.state === 'suspended') await ctx.resume();

      const activeAudios = stems
        .map((s) => audioElsRef.current.get(s.fileName))
        .filter((a): a is HTMLAudioElement => !!a);

      if (activeAudios.length === 0) return;

      const master = activeAudios[0];

      if (isPlaying) {
          activeAudios.forEach((a) => a.pause());
          pauseTimeRef.current = master.currentTime;
          setIsPlaying(false);
          return;
      }

      if (duration > 0 && pauseTimeRef.current >= duration) {
          pauseTimeRef.current = 0;
      }

      const offset = pauseTimeRef.current;
      activeAudios.forEach((a) => {
          try { a.currentTime = offset; } catch (_) { /* noop */ }
      });

      try {
          await Promise.all(activeAudios.map(a => a.play().catch(() => undefined)));
      } catch (_) {
          // ignore play errors (e.g. autoplay policies)
      }

      startTimeRef.current = ctx.currentTime - offset;
      setIsPlaying(true);
  };

  const seek = (time: number) => {
      const ctx = audioContextRef.current;
      if (!ctx) return;

      const activeAudios = stems
        .map((s) => audioElsRef.current.get(s.fileName))
        .filter((a): a is HTMLAudioElement => !!a);

      if (activeAudios.length === 0) return;

      const t = Math.max(0, Math.min(time, duration || time));
      const wasPlaying = isPlaying;

      activeAudios.forEach((a) => {
          try {
              a.pause();
              a.currentTime = t;
          } catch (_) { /* noop */ }
      });

      pauseTimeRef.current = t;
      setCurrentTime(t);

      if (wasPlaying) {
          setIsPlaying(false);
          setTimeout(async () => {
              if (ctx.state === 'suspended') await ctx.resume();
              try {
                  await Promise.all(activeAudios.map(a => a.play().catch(() => undefined)));
                  setIsPlaying(true);
              } catch (_) {
                  // ignore
              }
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
          if (isPlaying) {
              const master = stems
                .map((s) => audioElsRef.current.get(s.fileName))
                .find((a) => !!a) as HTMLAudioElement | undefined;
              if (master) {
                  setCurrentTime(master.currentTime || 0);
                  if (isFinite(master.duration) && master.duration > 0) {
                      setDuration((prev) => Math.max(prev, master.duration));
                  }
                  raf = requestAnimationFrame(update);
                  return;
              }
          }
      };
      if (isPlaying) update();
      return () => cancelAnimationFrame(raf);
  }, [isPlaying, duration, stems]);

  useEffect(() => {
      const anySolo = stems.some(s => s.solo);
      stems.forEach(stem => {
          const gainNode = gainNodesRef.current.get(stem.fileName);
          const pannerNode = pannerNodesRef.current.get(stem.fileName);

          if (gainNode) {
              let shouldMute = stem.mute;
              if (anySolo) shouldMute = !stem.solo;
              // Volume applied here is just the stem volume, not multiplied by masterVolume
              const vol = Math.pow(10, stem.volume / 20);
              gainNode.gain.setTargetAtTime(shouldMute ? 0 : vol, audioContextRef.current!.currentTime, 0.05);
          }
          if (pannerNode) {
               pannerNode.pan.setTargetAtTime(stem.pan.enabled ? stem.pan.value : 0, audioContextRef.current!.currentTime, 0.05);
          }
      });
  }, [stems]); // Removed masterVolume dependency here as it's handled in its own effect on masterGain

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
        const correctionRes = await fetch(`${baseUrl}/jobs/${jobId}/correction`, {
            method: 'POST',
            headers: buildAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ corrections })
        });
        if (!correctionRes.ok) {
            throw new Error(`Corrections failed (${correctionRes.status})`);
        }

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

        const startRes = await fetch(`${baseUrl}/mix/${jobId}/start`, {
             method: 'POST',
             headers: buildAuthHeaders({ 'Content-Type': 'application/json' }),
             body: JSON.stringify({ stages })
        });
        if (!startRes.ok) {
            throw new Error(`Pipeline restart failed (${startRes.status})`);
        }

          router.push(`/${locale}/mix?jobId=${encodeURIComponent(jobId)}`);
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
              headers: buildAuthHeaders()
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
              headers: buildAuthHeaders()
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

  // Waveform: use visualBuffer (client-side generated) or peaks (server-side)
  const currentVisualBuffer = visualBuffer;
  // Ensure we don't pass zero-filled peaks to CanvasWaveform, which would suppress AudioBuffer calculation
  const currentVisualPeaks = (selectedStem?.peaks && selectedStem.peaks.some(p => p > 0)) ? selectedStem.peaks : null;

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
            <div>{t('loading')}</div>
            <div className="text-xs text-slate-500">{t('loadingStems')}</div>
        </div>
      );
  }

  return (
    <div className="flex flex-col h-screen bg-[#0f111a] text-slate-300 font-sans overflow-hidden selection:bg-emerald-500/30">

      <header className="h-14 bg-[#1e293b]/50 border-b border-white/5 flex items-center justify-between px-4 shrink-0 backdrop-blur-md">
         <div className="flex items-center gap-6">
             <div className="flex items-center gap-2 text-emerald-400 font-bold tracking-wider">
                 <AdjustmentsHorizontalIcon className="w-5 h-5" />
                 <span>{t('title')}</span>
             </div>
             <div className="h-6 w-px bg-white/10 mx-2"></div>
             <div className="flex flex-col">
                 <span className="text-xs text-slate-500 uppercase tracking-wider">{t('project')}</span>
                 <span className="text-sm font-medium text-white">{jobId.substring(0,8)}...</span>
             </div>
         </div>
         <div className="flex items-center gap-4">
             <div className="flex flex-col items-end">
                 <button onClick={downloadStems} disabled={downloadingStems} className="px-3 py-1.5 text-xs font-medium text-slate-400 hover:text-white border border-white/10 rounded hover:bg-white/5 transition-colors flex items-center gap-2">
                     <ArrowDownTrayIcon className="w-3 h-3" /> {t('stemsZip')}
                 </button>
                 {downloadingStems && <span className="text-[10px] text-emerald-500 animate-pulse mt-1">{t('downloading')}</span>}
             </div>

             <div className="flex flex-col items-end">
                 <button onClick={downloadMixdown} disabled={downloadingMixdown} className="px-3 py-1.5 text-xs font-medium text-slate-400 hover:text-white border border-white/10 rounded hover:bg-white/5 transition-colors flex items-center gap-2">
                     <ArrowDownTrayIcon className="w-3 h-3" /> {t('mixdown')}
                 </button>
                 {downloadingMixdown && <span className="text-[10px] text-emerald-500 animate-pulse mt-1">{t('downloading')}</span>}
             </div>

             <div className="h-6 w-px bg-white/10 mx-2"></div>

             <button
                onClick={() => handleApplyCorrection(false)}
                disabled={rendering}
                className="px-4 py-1.5 bg-slate-700 hover:bg-slate-600 text-white text-xs font-bold rounded shadow-lg transition-all flex items-center gap-2"
             >
                <XMarkIcon className="w-3 h-3" />
                {t('finishHere')}
             </button>
             <button
                onClick={() => handleApplyCorrection(true)}
                disabled={rendering}
                className="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold rounded shadow-lg shadow-emerald-900/20 transition-all flex items-center gap-2"
             >
                {rendering ? <ArrowPathIcon className="w-3 h-3 animate-spin" /> : <CheckIcon className="w-3 h-3" />}
                {t('proceedMastering')}
             </button>
         </div>
      </header>

      <div className="flex flex-1 overflow-hidden">

          <aside className="w-72 bg-[#11131f] border-r border-white/5 flex flex-col shrink-0">
             <div className="p-4 border-b border-white/5 flex justify-between items-center">
                 <h2 className="text-xs font-bold text-slate-500 tracking-widest uppercase">{t('tracks')} ({stems.length})</h2>
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
                    analyser={masterAnalyserNodeRef.current}
                    isPlaying={isPlaying}
                 />
                 </div>

                 {!currentVisualBuffer && !currentVisualPeaks && (
                     <div className="absolute inset-0 flex items-center justify-center text-slate-600 font-mono pointer-events-none">
                         {loadingStems ? "Loading..." : t('selectTrack')}
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
                             <span>{t('masterOut')}</span>
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
                         <span className="text-[10px] text-slate-500 font-bold">{t('monitor')}</span>
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
                  <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-2">{t('selectedChannel')}</div>
                  <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded bg-emerald-500/10 flex items-center justify-center text-emerald-500">
                          <MusicalNoteIcon className="w-5 h-5" />
                      </div>
                      <h2 className="text-xl font-bold text-white truncate" title={selectedStem?.name}>{selectedStem?.name || t('noTrackSelected')}</h2>
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
                                <span className={`text-xs font-bold ${selectedStem.eq.enabled ? 'text-emerald-400' : 'text-slate-500'}`}>{t('parametricEq')}</span>
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
                                <span className={`text-xs font-bold ${selectedStem.compression.enabled ? 'text-emerald-400' : 'text-slate-500'}`}>{t('compressor')}</span>
                             </div>
                        </div>

                        <div className={`flex justify-around mb-4 transition-opacity ${selectedStem.compression.enabled ? 'opacity-100' : 'opacity-40 pointer-events-none'}`}>
                             <Knob label="THRESH" value={selectedStem.compression.threshold} min={-60} max={0} onChange={(v) => updateStem(selectedStemIndex, { compression: {...selectedStem.compression, threshold: v}})} />
                             <Knob label="RATIO" value={selectedStem.compression.ratio} min={1} max={20} onChange={(v) => updateStem(selectedStemIndex, { compression: {...selectedStem.compression, ratio: v}})} />
                        </div>
                    </div>

                    <div className="flex gap-2">
                        {/* Pan */}
                        <div className="flex-1 bg-[#1e2336] rounded-xl p-3 border border-white/5 shadow-lg min-w-0">
                            <div className="flex justify-between items-center mb-4">
                                <div className="flex items-center gap-2 overflow-hidden">
                                    <input
                                        type="checkbox"
                                        checked={selectedStem.pan.enabled}
                                        onChange={(e) => updateStem(selectedStemIndex, { pan: {...selectedStem.pan, enabled: e.target.checked}})}
                                        className="shrink-0 rounded border-slate-600 bg-slate-800 text-blue-500 focus:ring-blue-500"
                                    />
                                    <span className={`text-xs font-bold truncate ${selectedStem.pan.enabled ? 'text-blue-400' : 'text-slate-500'}`}>{t('panning')}</span>
                                </div>
                                <SpeakerWaveIcon className="w-4 h-4 text-slate-600 shrink-0" />
                            </div>
                            <div className={`flex justify-center transition-opacity ${selectedStem.pan.enabled ? 'opacity-100' : 'opacity-40 pointer-events-none'}`}>
                                <Knob label="L / R" value={selectedStem.pan.value} min={-1} max={1} step={0.1} onChange={(v) => updateStem(selectedStemIndex, { pan: {...selectedStem.pan, value: v}})} />
                            </div>
                        </div>

                        {/* Reverb */}
                        <div className="flex-1 bg-[#1e2336] rounded-xl p-3 border border-white/5 shadow-lg min-w-0">
                            <div className="flex justify-between items-center mb-4">
                                <div className="flex items-center gap-2 overflow-hidden">
                                    <input
                                        type="checkbox"
                                        checked={selectedStem.reverb.enabled}
                                        onChange={(e) => updateStem(selectedStemIndex, { reverb: {...selectedStem.reverb, enabled: e.target.checked}})}
                                        className="shrink-0 rounded border-slate-600 bg-slate-800 text-purple-500 focus:ring-purple-500"
                                    />
                                    <span className={`text-xs font-bold truncate ${selectedStem.reverb.enabled ? 'text-purple-400' : 'text-slate-500'}`}>{t('reverb')}</span>
                                </div>
                                <SparklesIcon className="w-4 h-4 text-slate-600 shrink-0" />
                            </div>
                            <div className={`flex justify-center transition-opacity ${selectedStem.reverb.enabled ? 'opacity-100' : 'opacity-40 pointer-events-none'}`}>
                                <Knob label="AMOUNT" value={selectedStem.reverb.amount} min={0} max={100} onChange={(v) => updateStem(selectedStemIndex, { reverb: {...selectedStem.reverb, amount: v}})} />
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

function audioBufferToData(buffer: AudioBuffer): AudioBufferData {
  const channels: Float32Array[] = [];
  for (let i = 0; i < buffer.numberOfChannels; i++) {
    channels.push(buffer.getChannelData(i));
  }
  return {
    sampleRate: buffer.sampleRate,
    length: buffer.length,
    duration: buffer.duration,
    numberOfChannels: buffer.numberOfChannels,
    channels: channels
  };
}

function dataToAudioBuffer(ctx: AudioContext, data: AudioBufferData): AudioBuffer {
  const buffer = ctx.createBuffer(data.numberOfChannels, data.length, data.sampleRate);
  for (let i = 0; i < data.numberOfChannels; i++) {
    buffer.copyToChannel(data.channels[i] as any, i);
  }
  return buffer;
}
