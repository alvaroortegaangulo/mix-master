"use client";

import { useEffect, useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { useModal } from "@/context/ModalContext";
import { getApiBaseUrl, getBackendBaseUrl, getStudioToken, signFileUrl } from "@/lib/mixApi";
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
  XMarkIcon
} from "@heroicons/react/24/solid";
import { useTranslations } from "next-intl";

// --- Tipos e Interfaces ---

interface StemControl {
  fileName: string;     // Nombre original o identificador
  cleanName?: string;   // Nombre normalizado (snake_case) para buscar en backend
  stage?: string;
  name: string;         // Nombre para mostrar en UI
  volume: number;
  pan: {
    value: number;
    enabled: boolean;
  };
  mute: boolean;
  solo: boolean;
  reverb: {
    amount: number;
    enabled: boolean;
  };
  stereoWidth: {
    amount: number;
    enabled: boolean;
  };
  saturation: {
    amount: number;
    enabled: boolean;
  };
  transient: {
    amount: number;
    enabled: boolean;
  };
  depth: {
    amount: number;
    enabled: boolean;
  };
  signedUrl?: string;
  previewUrl?: string | null;
  peaks?: number[];
  url?: string;
  status?: "idle" | "loading" | "ready" | "error";
}

// --- Utilidades Matemáticas y DSP ---

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

const normalizeStemSpeed = (value: number) => {
  if (!Number.isFinite(value)) return 1;
  return clamp(value, 0.5, 1.5);
};

// FIX #3: Utilidad para imitar la normalización del backend (snake_case)
const normalizeFileName = (fileName: string): string => {
  if (!fileName) return "";
  const namePart = fileName.replace(/\.wav$/i, "").replace(/\.mp3$/i, "").replace(/\.aiff?$/i, "");
  // Reemplazar caracteres no alfanuméricos por guion bajo y pasar a minúsculas
  let cleaned = namePart.replace(/[^a-zA-Z0-9]/g, "_").toLowerCase();
  // Eliminar guiones bajos duplicados
  cleaned = cleaned.replace(/_+/g, "_").replace(/^_|_$/g, "");
  return cleaned + ".wav"; 
};

const normalizeSignedUrl = (rawUrl: string) => {
  if (!rawUrl) return "";
  try {
    const base = typeof window !== "undefined" ? window.location.href : "http://localhost";
    const parsed = new URL(rawUrl, base);
    const backend = new URL(getBackendBaseUrl());
    parsed.protocol = backend.protocol;
    parsed.host = backend.host;
    parsed.port = backend.port;
    return parsed.toString();
  } catch {
    return rawUrl;
  }
};

const formatDb = (gain: number) => {
  if (!Number.isFinite(gain) || gain <= 0) return "-60.0";
  const db = 20 * Math.log10(gain);
  return clamp(db, -60, 0).toFixed(1);
};

// FIX #5: DSP Consistency - Reverb con Damping (LPF)
// Genera una respuesta al impulso que suena más natural y similar al algoritmo de Python
const createImpulseResponse = (ctx: AudioContext, durationSec = 2.0, decay = 2.0) => {
  const sampleRate = ctx.sampleRate;
  const length = Math.max(1, Math.floor(sampleRate * durationSec));
  const impulse = ctx.createBuffer(2, length, sampleRate);

  for (let channel = 0; channel < impulse.numberOfChannels; channel++) {
    const data = impulse.getChannelData(channel);
    let lastOut = 0;
    for (let i = 0; i < length; i++) {
      // Ruido blanco
      const noise = (Math.random() * 2 - 1);
      
      // Envelope exponencial
      const envelope = Math.pow(1 - i / length, decay);
      
      // Aplicar LowPass filter simple para damping (simula absorción de agudos)
      // Coeficiente 0.6 para suavizar
      const input = noise * envelope;
      const current = input * 0.4 + lastOut * 0.6;
      lastOut = current;
      
      data[i] = current;
    }
  }
  return impulse;
};

// Ambience: Reverb corta y oscura
const createAmbienceImpulseResponse = (ctx: AudioContext) =>
  createImpulseResponse(ctx, 0.8, 3.0);

const saturationCurveCache = new Map<number, Float32Array>();

// FIX #5: DSP Consistency - Saturación Tanh Estandarizada
// Coincide exactamente con np.tanh(k * x) del backend
const buildSaturationCurve = (drive: number) => {
  const amount = clamp(drive, 0, 100);

  const cachedCurve = saturationCurveCache.get(amount);
  if (cachedCurve) return cachedCurve;

  const n_samples = 4096;
  const curve = new Float32Array(n_samples);

  if (amount <= 0) {
    // Lineal (bypass)
    for (let i = 0; i < n_samples; i++) {
      curve[i] = (i / (n_samples - 1)) * 2 - 1;
    }
  } else {
    // Mapeo de 0-100 a factor de ganancia k (1 a 8)
    const k = 1 + (amount / 100) * 7;

    for (let i = 0; i < n_samples; i++) {
      const x = (i * 2) / n_samples - 1;
      curve[i] = Math.tanh(k * x);
    }
  }

  saturationCurveCache.set(amount, curve);
  return curve;
};

type StereoWidthNodes = {
  input: GainNode;
  output: ChannelMergerNode;
  widthGain: GainNode;
};

const createStereoWidthNodes = (ctx: AudioContext): StereoWidthNodes => {
  const input = ctx.createGain();
  const splitter = ctx.createChannelSplitter(2);
  const merger = ctx.createChannelMerger(2);

  const midSum = ctx.createGain();
  const sideSum = ctx.createGain();
  const sideGain = ctx.createGain();
  const leftOut = ctx.createGain();
  const rightOut = ctx.createGain();

  const lMid = ctx.createGain();
  lMid.gain.value = 0.5;
  const rMid = ctx.createGain();
  rMid.gain.value = 0.5;

  const lSide = ctx.createGain();
  lSide.gain.value = 0.5;
  const rSide = ctx.createGain();
  rSide.gain.value = -0.5;

  const sideInvert = ctx.createGain();
  sideInvert.gain.value = -1;

  input.connect(splitter);

  splitter.connect(lMid, 0);
  splitter.connect(rMid, 1);
  lMid.connect(midSum);
  rMid.connect(midSum);

  splitter.connect(lSide, 0);
  splitter.connect(rSide, 1);
  lSide.connect(sideSum);
  rSide.connect(sideSum);

  sideSum.connect(sideGain);
  sideGain.connect(leftOut);
  sideGain.connect(sideInvert);
  sideInvert.connect(rightOut);
  midSum.connect(leftOut);
  midSum.connect(rightOut);

  leftOut.connect(merger, 0, 0);
  rightOut.connect(merger, 0, 1);

  return { input, output: merger, widthGain: sideGain };
};

function buildAuthHeaders(extra?: HeadersInit): HeadersInit {
  const headers: Record<string, string> = {};
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("access_token");
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
  }
  return { ...headers, ...(extra || {}) };
}

// --- Componente Principal ---

export default function StudioPage() {
  const params = useParams();
  const jobId = params.jobId as string;
  const locale = params.locale as string;
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const { openAuthModal } = useModal();
  const t = useTranslations('Studio');

  // Estados
  const [stems, setStems] = useState<StemControl[]>([]);
  const [selectedStemIndex, setSelectedStemIndex] = useState<number>(0);
  const [loadingStems, setLoadingStems] = useState(true);
  const [studioReady, setStudioReady] = useState(false);
  const [rendering, setRendering] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [masterVolume, setMasterVolume] = useState(0.8);
  const [stemSpeed, setStemSpeed] = useState(1);
  const [downloadingStems, setDownloadingStems] = useState(false);
  const [downloadingMixdown, setDownloadingMixdown] = useState(false);
  const [studioToken, setStudioToken] = useState<string | null>(null);
  const [visualBuffer, setVisualBuffer] = useState<AudioBuffer | null>(null);

  const selectedStem = stems[selectedStemIndex];
  const safeStemSpeed = normalizeStemSpeed(stemSpeed);

  // Referencias (Audio Context & Nodes)
  const audioContextRef = useRef<AudioContext | null>(null);
  const masterGainNodeRef = useRef<GainNode | null>(null);
  const masterAnalyserNodeRef = useRef<AnalyserNode | null>(null);
  const reverbBufferRef = useRef<AudioBuffer | null>(null);
  const ambienceBufferRef = useRef<AudioBuffer | null>(null);
  const transientWorkletReadyRef = useRef<Promise<void> | null>(null);

  const audioElsRef = useRef<Map<string, HTMLAudioElement>>(new Map());
  const mediaNodesRef = useRef<Map<string, MediaElementAudioSourceNode>>(new Map());
  const gainNodesRef = useRef<Map<string, GainNode>>(new Map());
  const pannerNodesRef = useRef<Map<string, StereoPannerNode>>(new Map());
  const saturationNodesRef = useRef<Map<string, WaveShaperNode>>(new Map());
  const transientNodesRef = useRef<Map<string, { node: AudioNode; param?: AudioParam }>>(new Map());
  const stereoWidthGainNodesRef = useRef<Map<string, GainNode>>(new Map());
  const reverbNodesRef = useRef<Map<string, ConvolverNode>>(new Map());
  const reverbWetGainNodesRef = useRef<Map<string, GainNode>>(new Map());
  const reverbDryGainNodesRef = useRef<Map<string, GainNode>>(new Map());
  const depthConvolverNodesRef = useRef<Map<string, ConvolverNode>>(new Map());
  const depthWetGainNodesRef = useRef<Map<string, GainNode>>(new Map());
  const depthFilterNodesRef = useRef<Map<string, BiquadFilterNode>>(new Map());
  
  const startTimeRef = useRef<number>(0);
  const pauseTimeRef = useRef<number>(0);
  const stemsRef = useRef<StemControl[]>([]);
  const masterVolumeRef = useRef(masterVolume);
  const stemSpeedRef = useRef(safeStemSpeed);
  const audioEngineModeRef = useRef<"direct" | "webaudio">("direct");
  const enableWebAudioRef = useRef<Promise<void> | null>(null);

  // Refs para optimización de renderizado (evitar setState en loop)
  const playbackTimeRef = useRef(0);
  const timeDisplayRef = useRef<HTMLDivElement>(null);
  const progressBarRef = useRef<HTMLDivElement>(null);
  const scrubberHandleRef = useRef<HTMLDivElement>(null);

  // Sincronización de Refs
  useEffect(() => { stemsRef.current = stems; }, [stems]);
  useEffect(() => { masterVolumeRef.current = masterVolume; }, [masterVolume]);
  useEffect(() => { stemSpeedRef.current = safeStemSpeed; }, [safeStemSpeed]);

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
          const onReady = () => { cleanup(); resolve(); };
          const onError = () => { cleanup(); reject(new Error("media error")); };
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
              setTimeout(() => { cleanup(); resolve(); }, timeoutMs);
          }
      });
  };

  const getOrCreateAudioContext = () => {
    if (typeof window === "undefined") return null;

    const existing = audioContextRef.current;
    if (existing && existing.state !== "closed") {
      return existing;
    }

    try {
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      const ctx: AudioContext = new AudioCtx();
      audioContextRef.current = ctx;

      const masterGain = ctx.createGain();
      masterGain.gain.value = clamp(masterVolumeRef.current, 0, 1);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 2048;
      analyser.smoothingTimeConstant = 0.85;

      masterGain.connect(analyser);
      analyser.connect(ctx.destination);

      masterGainNodeRef.current = masterGain;
      masterAnalyserNodeRef.current = analyser;

      if (!reverbBufferRef.current) {
        reverbBufferRef.current = createImpulseResponse(ctx);
      }
      if (!ambienceBufferRef.current) {
        ambienceBufferRef.current = createAmbienceImpulseResponse(ctx);
      }

      if (ctx.audioWorklet && !transientWorkletReadyRef.current) {
        transientWorkletReadyRef.current = ctx.audioWorklet
          .addModule("/worklets/transient-shaper.js")
          .catch((err) => {
            console.warn("Studio: transient worklet failed to load", err);
            throw err;
          });
      }

      return ctx;
    } catch (e) {
      console.error("Studio: AudioContext init error", e);
      return null;
    }
  };

  // FIX #4: Lógica de Mezcla Directa (HTML Audio) vs Web Audio
  const applyDirectMixToMediaElements = (stemList: StemControl[]) => {
    const anySolo = stemList.some((s) => s.solo);

    stemList.forEach((stem) => {
      const audio = audioElsRef.current.get(stem.fileName);
      if (!audio) return;
      
      // Si el stem está gestionado por Web Audio, forzamos que el elemento HTML esté "abierto".
      // Esto evita que un mute anterior bloquee la señal que entra al grafo.
      if (mediaNodesRef.current.has(stem.fileName)) {
          if (audio.muted) audio.muted = false;
          if (audio.volume !== 1) audio.volume = 1;
          return;
      }

      // Lógica para modo Directo (sin Web Audio aún)
      let shouldMute = stem.mute;
      if (anySolo) shouldMute = !stem.solo;

      const stemGain = Math.pow(10, stem.volume / 20);
      const combined = shouldMute ? 0 : clamp(stemGain * masterVolumeRef.current, 0, 1);

      audio.muted = false;
      audio.volume = combined;
    });
  };

  const applyStemParamsToWebAudio = (stemList: StemControl[]) => {
    const ctx = audioContextRef.current;
    if (!ctx) return;
    const now = ctx.currentTime;
    const anySolo = stemList.some((s) => s.solo);

    stemList.forEach((stem) => {
      const gainNode = gainNodesRef.current.get(stem.fileName);
      const pannerNode = pannerNodesRef.current.get(stem.fileName);
      const saturationNode = saturationNodesRef.current.get(stem.fileName);
      const transientEntry = transientNodesRef.current.get(stem.fileName);
      const widthGainNode = stereoWidthGainNodesRef.current.get(stem.fileName);
      const wetGainNode = reverbWetGainNodesRef.current.get(stem.fileName);
      const dryGainNode = reverbDryGainNodesRef.current.get(stem.fileName);
      const depthWetGainNode = depthWetGainNodesRef.current.get(stem.fileName);

      if (gainNode) {
        let shouldMute = stem.mute;
        if (anySolo) shouldMute = !stem.solo;
        const vol = Math.pow(10, stem.volume / 20);
        gainNode.gain.setTargetAtTime(shouldMute ? 0 : vol, now, 0.05);
      }
      if (pannerNode) {
        pannerNode.pan.setTargetAtTime(stem.pan.enabled ? stem.pan.value : 0, now, 0.05);
      }
      if (saturationNode) {
        const drive = stem.saturation.enabled ? stem.saturation.amount : 0;
        saturationNode.curve = buildSaturationCurve(drive);
      }
      if (transientEntry?.param) {
        const punch = stem.transient.enabled ? clamp(stem.transient.amount / 100, -1, 1) : 0;
        transientEntry.param.setTargetAtTime(punch, now, 0.05);
      }
      if (widthGainNode) {
        const widthValue = stem.stereoWidth.enabled ? clamp(stem.stereoWidth.amount / 100, 0, 2) : 1;
        widthGainNode.gain.setTargetAtTime(widthValue, now, 0.05);
      }
      if (wetGainNode && dryGainNode) {
        const wetAmount = stem.reverb.enabled ? clamp(stem.reverb.amount / 100, 0, 1) : 0;
        const dryAmount = clamp(1 - wetAmount * 0.5, 0, 1);
        wetGainNode.gain.setTargetAtTime(wetAmount, now, 0.05);
        dryGainNode.gain.setTargetAtTime(dryAmount, now, 0.05);
      }
      if (depthWetGainNode) {
        const depthAmount = stem.depth.enabled ? clamp(stem.depth.amount / 100, 0, 1) : 0;
        depthWetGainNode.gain.setTargetAtTime(depthAmount, now, 0.05);
      }
    });
  };

  const buildWebAudioGraphForStem = async (stem: StemControl) => {
    const ctx = audioContextRef.current;
    const master = masterGainNodeRef.current;
    if (!ctx || !master || ctx.state !== "running") return false;

    const audio = audioElsRef.current.get(stem.fileName);
    if (!audio) return false;
    if (mediaNodesRef.current.has(stem.fileName)) return true;

    // Asegurar estado inicial correcto para input de Web Audio
    audio.muted = false;
    audio.volume = 1;
    audio.playbackRate = stemSpeedRef.current;
    audio.defaultPlaybackRate = stemSpeedRef.current;

    let mediaNode: MediaElementAudioSourceNode | null = null;
    try {
      mediaNode = ctx.createMediaElementSource(audio);

      const gain = ctx.createGain();
      const saturation = ctx.createWaveShaper();
      const panner = ctx.createStereoPanner();
      const dryGain = ctx.createGain();
      const convolver = ctx.createConvolver();
      const wetGain = ctx.createGain();
      const depthFilter = ctx.createBiquadFilter();
      const depthConvolver = ctx.createConvolver();
      const depthWetGain = ctx.createGain();

      saturation.oversample = "4x";
      saturation.curve = buildSaturationCurve(stem.saturation.enabled ? stem.saturation.amount : 0);

      const transientFallback = () => ({ node: ctx.createGain(), param: undefined as AudioParam | undefined });
      let transientEntry = transientFallback();

      if (ctx.audioWorklet && transientWorkletReadyRef.current) {
        try {
          // FIX #2: Race Condition Fix
          // Timeout de 1.5s para evitar bloqueo si el script falla o es lento
          const timeoutPromise = new Promise((_, reject) =>
            setTimeout(() => reject(new Error("Transient worklet load timeout")), 1500)
          );
          await Promise.race([transientWorkletReadyRef.current, timeoutPromise]);

          const transientNode = new AudioWorkletNode(ctx, "transient-shaper", {
            numberOfInputs: 1,
            numberOfOutputs: 1,
            outputChannelCount: [2],
          });
          transientNode.channelCountMode = "explicit";
          transientNode.channelCount = 2;
          const punchParam = transientNode.parameters.get("punch") ?? undefined;
          if (punchParam) {
            const punch = stem.transient.enabled ? clamp(stem.transient.amount / 100, -1, 1) : 0;
            punchParam.value = punch;
          }
          transientEntry = { node: transientNode, param: punchParam };
        } catch (err) {
          console.warn("Studio: transient worklet node failed or timed out, using bypass", err);
          transientEntry = transientFallback();
        }
      }

      const widthNodes = createStereoWidthNodes(ctx);
      const widthValue = stem.stereoWidth.enabled ? clamp(stem.stereoWidth.amount / 100, 0, 2) : 1;
      widthNodes.widthGain.gain.value = widthValue;

      const reverbBuffer = reverbBufferRef.current || createImpulseResponse(ctx);
      if (!reverbBufferRef.current) {
        reverbBufferRef.current = reverbBuffer;
      }
      convolver.buffer = reverbBuffer;
      convolver.normalize = true;

      const ambienceBuffer = ambienceBufferRef.current || createAmbienceImpulseResponse(ctx);
      if (!ambienceBufferRef.current) {
        ambienceBufferRef.current = ambienceBuffer;
      }
      depthConvolver.buffer = ambienceBuffer;
      depthConvolver.normalize = true;
      depthFilter.type = "lowpass";
      depthFilter.frequency.value = 8000;
      depthFilter.Q.value = 0.7;

      const wetAmount = stem.reverb.enabled ? clamp(stem.reverb.amount / 100, 0, 1) : 0;
      const dryAmount = clamp(1 - wetAmount * 0.5, 0, 1);
      const depthAmount = stem.depth.enabled ? clamp(stem.depth.amount / 100, 0, 1) : 0;
      wetGain.gain.value = wetAmount;
      dryGain.gain.value = dryAmount;
      depthWetGain.gain.value = depthAmount;

      const vol = Math.pow(10, stem.volume / 20);
      gain.gain.value = stem.mute ? 0 : vol;
      panner.pan.value = stem.pan.enabled ? stem.pan.value : 0;

      // Conexiones del Grafo
      mediaNode.connect(gain);
      gain.connect(saturation);
      saturation.connect(transientEntry.node);
      transientEntry.node.connect(widthNodes.input);
      widthNodes.output.connect(panner);
      
      // Dry Path
      panner.connect(dryGain);
      dryGain.connect(master);
      
      // Reverb Send
      panner.connect(convolver);
      convolver.connect(wetGain);
      wetGain.connect(master);
      
      // Depth Send
      panner.connect(depthFilter);
      depthFilter.connect(depthConvolver);
      depthConvolver.connect(depthWetGain);
      depthWetGain.connect(master);

      // Guardar Referencias
      mediaNodesRef.current.set(stem.fileName, mediaNode);
      gainNodesRef.current.set(stem.fileName, gain);
      saturationNodesRef.current.set(stem.fileName, saturation);
      transientNodesRef.current.set(stem.fileName, transientEntry);
      stereoWidthGainNodesRef.current.set(stem.fileName, widthNodes.widthGain);
      pannerNodesRef.current.set(stem.fileName, panner);
      reverbNodesRef.current.set(stem.fileName, convolver);
      reverbWetGainNodesRef.current.set(stem.fileName, wetGain);
      reverbDryGainNodesRef.current.set(stem.fileName, dryGain);
      depthConvolverNodesRef.current.set(stem.fileName, depthConvolver);
      depthWetGainNodesRef.current.set(stem.fileName, depthWetGain);
      depthFilterNodesRef.current.set(stem.fileName, depthFilter);

      return true;
    } catch (err) {
      console.warn("Studio: failed to build audio graph", err);
      try {
        // Fallback crítico: conectar directo si el procesado falla
        mediaNode?.connect(master);
        mediaNodesRef.current.set(stem.fileName, mediaNode!);
        return true;
      } catch (fallbackErr) {
        console.warn("Studio: audio graph fallback failed", fallbackErr);
        return false;
      }
    }
  };

  const ensureWebAudioGraphForAllStems = async () => {
    const ctx = audioContextRef.current;
    if (!ctx || ctx.state !== "running") return false;

    let built = 0;
    for (const stem of stemsRef.current) {
      const ok = await buildWebAudioGraphForStem(stem);
      if (ok) built += 1;
    }

    if (built > 0) {
      audioEngineModeRef.current = "webaudio";
      applyStemParamsToWebAudio(stemsRef.current);
      return true;
    }
    console.warn("Studio: WebAudio graph not created; staying in direct mode.");
    return false;
  };

  const requestEnableWebAudio = () => {
    if (enableWebAudioRef.current) return enableWebAudioRef.current;

    enableWebAudioRef.current = (async () => {
      const ctx = getOrCreateAudioContext();
      if (!ctx) return;

      if (ctx.state !== "running") {
        try {
          await ctx.resume();
        } catch (err) {
          console.warn("Studio: AudioContext resume failed; using direct audio output.", err);
          return;
        }
      }

      if (ctx.state !== "running") {
        console.warn(`Studio: AudioContext state is "${ctx.state}"; using direct audio output.`);
        return;
      }

      await ensureWebAudioGraphForAllStems();
    })().finally(() => {
      enableWebAudioRef.current = null;
    });

    return enableWebAudioRef.current;
  };

  useEffect(() => {
    return () => {
      stopAllSources();
      const ctx = audioContextRef.current;
      if (ctx && ctx.state !== "closed") {
        ctx.close().catch(() => undefined);
      }
      audioContextRef.current = null;
      masterGainNodeRef.current = null;
      masterAnalyserNodeRef.current = null;
      reverbBufferRef.current = null;
      ambienceBufferRef.current = null;
      transientWorkletReadyRef.current = null;
      enableWebAudioRef.current = null;
      audioEngineModeRef.current = "direct";
    };
  }, []);

  // Update Master Volume
  useEffect(() => {
      const ctx = audioContextRef.current;
      if (masterGainNodeRef.current && ctx) {
          masterGainNodeRef.current.gain.setTargetAtTime(masterVolume, ctx.currentTime, 0.05);
      }
      applyDirectMixToMediaElements(stemsRef.current);
  }, [masterVolume]);

  useEffect(() => {
      audioElsRef.current.forEach((el) => {
          el.playbackRate = safeStemSpeed;
          el.defaultPlaybackRate = safeStemSpeed;
      });
  }, [safeStemSpeed]);


  // Effect to load waveform data for selected stem
  useEffect(() => {
    if (!selectedStem || !audioContextRef.current) return;

    // Use peaks if available
    const hasPeaks = selectedStem.peaks && selectedStem.peaks.length > 0 && selectedStem.peaks.some(p => p > 0);
    if (hasPeaks) {
        setVisualBuffer(null);
        return;
    }

    let active = true;
    setVisualBuffer(null); 

    const loadAudio = async () => {
        try {
            const cacheKey = `${jobId}/${selectedStem.fileName}`;
            const cachedData = await studioCache.getAudioBuffer(cacheKey);
            if (active && cachedData) {
                const buffer = dataToAudioBuffer(audioContextRef.current!, cachedData);
                setVisualBuffer(buffer);
                return;
            }

            if (!selectedStem.url) return;
            const resp = await fetch(selectedStem.url);
            if (!resp.ok) return;
            const arrayBuffer = await resp.arrayBuffer();

            if (active && audioContextRef.current) {
                const audioBuffer = await audioContextRef.current.decodeAudioData(arrayBuffer);
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

  // Carga Inicial de Stems
  useEffect(() => {
    if (!jobId) return;

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
        saturationNodesRef.current.clear();
        transientNodesRef.current.clear();
        stereoWidthGainNodesRef.current.clear();
        reverbNodesRef.current.clear();
        reverbWetGainNodesRef.current.clear();
        reverbDryGainNodesRef.current.clear();
        depthConvolverNodesRef.current.clear();
        depthWetGainNodesRef.current.clear();
        depthFilterNodesRef.current.clear();
        pauseTimeRef.current = 0;
        setIsPlaying(false);
        setCurrentTime(0);
        setDuration(0);
        const baseUrl = getApiBaseUrl();

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
        }
        
        if (stemsFromApi.length === 0) {
            console.warn("Studio: No stems found via API.");
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

          // Compute normalized name to help finding backend file
          const cleanName = normalizeFileName(file);

          return {
            fileName: file,
            cleanName: cleanName,
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
            reverb: { amount: 0, enabled: false },
            stereoWidth: { amount: 100, enabled: false },
            saturation: { amount: 0, enabled: false },
            transient: { amount: 0, enabled: false },
            depth: { amount: 0, enabled: false },
            signedUrl,
            previewUrl,
            peaks,
            url: undefined,
            status: "idle"
          };
        });

        const resolvedStems: StemControl[] = [];

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

        // FIX #3: Búsqueda Exhaustiva de Archivos
        for (const stem of newStems) {
            // Pruebo variantes de nombre (original, normalizado, lowercase)
            const nameVariants = [
                stem.fileName,
                stem.cleanName,
                stem.fileName.toLowerCase()
            ].filter((v): v is string => !!v);
            
            const uniqueVariants = Array.from(new Set(nameVariants));
            const candidates: string[] = [];

            if (stem.stage) {
                 uniqueVariants.forEach(v => candidates.push(`${stem.stage}/${v}`));
            }

            stageFallbacks.forEach((stage) => {
                 uniqueVariants.forEach(v => candidates.push(`${stage}/${v}`));
            });

            uniqueVariants.forEach(v => candidates.push(v));

            const primaryPath = candidates[0] || stem.fileName;
            let resolvedUrl = "";
            if (tokenValue) {
                try {
                    resolvedUrl = await signFileUrl(jobId, primaryPath, tokenValue);
                } catch (e) {
                    resolvedUrl = "";
                }
            }
            if (!resolvedUrl) {
                const rawUrl = stem.signedUrl || stem.url || "";
                if (rawUrl) {
                    resolvedUrl = normalizeSignedUrl(rawUrl);
                }
            }
            if (!resolvedUrl) {
                try {
                    resolvedUrl = await signFileUrl(jobId, primaryPath);
                } catch (e) {
                    resolvedUrl = "";
                }
            }
            if (!resolvedUrl && stem.previewUrl) {
                resolvedUrl = normalizeSignedUrl(stem.previewUrl);
            }

            resolvedStems.push({
                ...stem,
                url: resolvedUrl || undefined,
            });
        }

        if (cancelled) return;

        // Cargar peaks (también con variantes de nombre)
        const stemsWithPeaks = await Promise.all(
            resolvedStems.map(async (stem) => {
                if (stem.peaks && stem.peaks.length) return stem;
                
                const basesToCheck = new Set<string>();
                basesToCheck.add(stem.fileName.replace(/\.wav$/i, ""));
                if (stem.cleanName) basesToCheck.add(stem.cleanName.replace(/\.wav$/i, ""));
                
                const peakCandidates: string[] = [];
                basesToCheck.forEach(base => {
                    if (stem.stage) peakCandidates.push(`${stem.stage}/peaks/${base}.peaks.json`);
                });

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
                    }
                }
                return { ...stem, peaks: undefined };
            })
        );

        if (cancelled) return;
        setStems(stemsWithPeaks);
        setLoadingStems(false);

        // Pre-carga de elementos de audio
        const ensureAudioForStem = async (stem: StemControl) => {
            let audio = audioElsRef.current.get(stem.fileName);
            if (!audio) {
                audio = new Audio();
                audio.preload = "auto";
                // FIX #1: CORS
                audio.crossOrigin = "anonymous";
                audio.muted = false;
                audio.playbackRate = safeStemSpeed;
                audio.defaultPlaybackRate = safeStemSpeed;

                // Lógica de candidatos repetida para el elemento Audio (retry)
                const nameVariants = [
                    stem.fileName,
                    stem.cleanName,
                    stem.fileName.toLowerCase()
                ].filter((v): v is string => !!v);
                const uniqueVariants = Array.from(new Set(nameVariants));
                const candidates: string[] = [];
                if (stem.stage) {
                     uniqueVariants.forEach(v => candidates.push(`${stem.stage}/${v}`));
                }
                stageFallbacks.forEach((stage) => {
                     uniqueVariants.forEach(v => candidates.push(`${stage}/${v}`));
                });
                uniqueVariants.forEach(v => candidates.push(v));

                let candidateIndex = 0;

                const updateUrl = async (index: number) => {
                    const path = candidates[index] || stem.fileName;
                    const newUrl = await signFileUrl(jobId, path, tokenValue || undefined);
                    audio!.src = newUrl;
                    audio!.load();
                    setStems(prev => prev.map(s => s.fileName === stem.fileName ? { ...s, url: newUrl } : s));
                };

                audio.src = stem.url || "";
                audio.load();

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
                 applyDirectMixToMediaElements(stemsRef.current);
             } else if (stem.url && audio.src !== stem.url) {
                 audio.src = stem.url;
                 audio.load();
             }
            audio.playbackRate = safeStemSpeed;
            audio.defaultPlaybackRate = safeStemSpeed;
            return audio;
        };

        const readyPromises = resolvedStems.map(async (stem) => {
            const el = await ensureAudioForStem(stem);
            try {
                await waitForMediaReady(el, 4000);
            } catch {
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
  }, [jobId]);

  const togglePlay = async () => {
      if (stems.length === 0) return;

      const activeAudios = stems
        .map((s) => audioElsRef.current.get(s.fileName))
        .filter((a): a is HTMLAudioElement => !!a);

      if (activeAudios.length === 0) return;

      const master = activeAudios[0];

      if (isPlaying) {
          activeAudios.forEach((a) => a.pause());
          pauseTimeRef.current = master.currentTime;
          // Sincronizar estado React al pausar
          setCurrentTime(master.currentTime);
          setIsPlaying(false);
          return;
      }

      if (duration > 0 && pauseTimeRef.current >= duration) {
          pauseTimeRef.current = 0;
      }

      const offset = pauseTimeRef.current;
      // Actualizar ref inmediatamente para que UI responda
      playbackTimeRef.current = offset;

      activeAudios.forEach((a) => {
          try { a.currentTime = offset; } catch (_) { /* noop */ }
      });

      applyDirectMixToMediaElements(stemsRef.current);
      await requestEnableWebAudio();

      const playResults = await Promise.all(
          activeAudios.map((a) => a.play().then(() => true).catch(() => false))
      );
      if (!playResults.some(Boolean)) {
          console.warn("Studio: playback blocked or failed to start.");
          setIsPlaying(false);
          return;
      }

      const ctx = audioContextRef.current;
      if (ctx) {
          startTimeRef.current = ctx.currentTime - offset;
      }
      setIsPlaying(true);
  };

  const seek = (time: number) => {
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
      // Sync ref for CanvasWaveform visibility
      playbackTimeRef.current = t;

      if (wasPlaying) {
          setIsPlaying(false);
          setTimeout(async () => {
              applyDirectMixToMediaElements(stemsRef.current);
              await requestEnableWebAudio();
              try {
                  const playResults = await Promise.all(
                      activeAudios.map((a) => a.play().then(() => true).catch(() => false))
                  );
                  setIsPlaying(playResults.some(Boolean));
              } catch (_) {
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
              // Use stemsRef to avoid stale closure
              const master = stemsRef.current
                .map((s) => audioElsRef.current.get(s.fileName))
                .find((a) => !!a) as HTMLAudioElement | undefined;

              if (master) {
                  const t = master.currentTime || 0;
                  // Use actual duration from element or state, preferring element to avoid stale state in closure
                  const d = (isFinite(master.duration) && master.duration > 0) ? master.duration : duration;

                  // Actualizar Refs en lugar de Estado React
                  playbackTimeRef.current = t;

                  // Actualizar DOM directamente
                  if (timeDisplayRef.current) {
                      timeDisplayRef.current.textContent = `${formatTime(t)} / ${formatTime(d)}`;
                  }

                  if (d > 0) {
                      const pct = (t / d) * 100;
                      if (progressBarRef.current) {
                          progressBarRef.current.style.width = `${pct}%`;
                      }
                      if (scrubberHandleRef.current) {
                          scrubberHandleRef.current.style.left = `${pct}%`;
                      }
                  }

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
      applyDirectMixToMediaElements(stems);
      applyStemParamsToWebAudio(stems);
  }, [stems]);

  const handleApplyCorrection = async (proceedToMastering: boolean) => {
      setRendering(true);
      try {
          const corrections = stems.map(s => ({
              name: s.fileName,
              volume_db: s.volume,
              pan: s.pan.enabled ? s.pan.value : 0,
              reverb: s.reverb.enabled ? s.reverb : undefined,
              stereo_width: s.stereoWidth,
              saturation: s.saturation,
              transient: s.transient,
              depth: s.depth,
              speed: safeStemSpeed,
              mute: s.mute,
              solo: s.solo
          }));

        const baseUrl = getApiBaseUrl();
        const correctionRes = await fetch(`${baseUrl}/jobs/${jobId}/correction`, {
            method: 'POST',
            headers: buildAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ corrections })
        });
        if (!correctionRes.ok) {
            throw new Error(`Corrections failed (${correctionRes.status})`);
        }

        const stagesPayload: { stages?: string[]; start_from_stage?: string } = {};
        if (!proceedToMastering) {
            stagesPayload.stages = [
                "S6_MANUAL_CORRECTION",
                "S11_REPORT_GENERATION"
            ];
        } else {
            stagesPayload.start_from_stage = "S6_MANUAL_CORRECTION";
        }

        const startRes = await fetch(`${baseUrl}/mix/${jobId}/start`, {
             method: 'POST',
             headers: buildAuthHeaders({ 'Content-Type': 'application/json' }),
             body: JSON.stringify(stagesPayload)
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
      if (!user) {
          openAuthModal();
          return;
      }
      setDownloadingStems(true);
      try {
          const baseUrl = getApiBaseUrl();
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
       if (!user) {
           openAuthModal();
           return;
       }
       setDownloadingMixdown(true);
       try {
          const baseUrl = getApiBaseUrl();
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

  const currentVisualBuffer = visualBuffer;
  const currentVisualPeaks = (selectedStem?.peaks && selectedStem.peaks.some(p => p > 0)) ? selectedStem.peaks : null;

  if (authLoading) return <div className="h-screen bg-[#0f111a]"></div>;

  if (loadingStems) {
      return (
        <div className="h-screen bg-[#0f111a] flex flex-col items-center justify-center text-teal-500 font-mono gap-3">
            <div className="h-10 w-10 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" />
            <div>{t('loading')}</div>
            <div className="text-xs text-slate-500">{t('loadingStems')}</div>
        </div>
      );
  }

  return (
    <div className="flex flex-col h-screen bg-[#0f111a] text-slate-300 font-sans overflow-hidden selection:bg-teal-500/30">

      <header className="h-14 bg-[#1e293b]/50 border-b border-white/5 flex items-center justify-between px-4 shrink-0 backdrop-blur-md">
         <div className="flex items-center gap-6">
             <div className="flex items-center gap-2 text-teal-400 font-bold tracking-wider">
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
                 {downloadingStems && <span className="text-[10px] text-teal-500 animate-pulse mt-1">{t('downloading')}</span>}
             </div>

             <div className="flex flex-col items-end">
                 <button onClick={downloadMixdown} disabled={downloadingMixdown} className="px-3 py-1.5 text-xs font-medium text-slate-400 hover:text-white border border-white/10 rounded hover:bg-white/5 transition-colors flex items-center gap-2">
                     <ArrowDownTrayIcon className="w-3 h-3" /> {t('mixdown')}
                 </button>
                 {downloadingMixdown && <span className="text-[10px] text-teal-500 animate-pulse mt-1">{t('downloading')}</span>}
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
                className="px-4 py-1.5 bg-teal-600 hover:bg-teal-500 text-white text-xs font-bold rounded shadow-lg shadow-teal-900/20 transition-all flex items-center gap-2"
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
                            ? 'bg-slate-800/80 border-teal-500/30 shadow-lg shadow-teal-900/10'
                            : 'bg-[#161b2e] border-transparent hover:bg-slate-800 hover:border-slate-700'
                        }`}
                     >
                         <div className="flex items-center justify-between mb-2">
                             <div className="flex items-center gap-2">
                                 <div className={`w-2 h-2 rounded-full ${selectedStemIndex === i ? 'bg-teal-400' : 'bg-slate-600'}`}></div>
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
                                className="w-full h-1 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-teal-500"
                             />
                         </div>
                     </div>
                 ))}
             </div>
          </aside>

          <main className="flex-1 flex flex-col relative bg-[#0f111a]">
             {/* Transport Section Moved to Top */}
             <div className="h-20 bg-[#11131f] border-b border-white/5 flex flex-col shrink-0 z-20">
                 <div className="flex-1 px-6 flex items-center justify-between">
                     <div className="flex flex-col gap-1 w-48">
                         <div className="flex justify-between text-[10px] text-slate-500 font-mono">
                             <span>{t('masterOut')}</span>
                             <span>{formatDb(masterVolume)} dB</span>
                         </div>
                         <div className="h-2 bg-slate-800 rounded-full overflow-hidden relative">
                             <div className="absolute top-0 left-0 bottom-0 bg-gradient-to-r from-teal-600 to-teal-400" style={{ width: `${masterVolume * 100}%` }}></div>
                         </div>
                     </div>

                     <div className="flex flex-col items-center gap-2">
                        {/* Time Display added to controls */}
                        <div
                            ref={timeDisplayRef}
                            className="text-[10px] font-mono text-teal-500 mb-1"
                        >
                             {formatTime(currentTime)} / {formatTime(duration)}
                        </div>
                         <div className="flex items-center gap-4">
                            <button onClick={() => { setIsPlaying(false); stopAllSources(); setCurrentTime(0); pauseTimeRef.current = 0; playbackTimeRef.current = 0; }} className="text-slate-500 hover:text-white transition-colors"><StopIcon className="w-4 h-4" /></button>
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

                 {/* Spotify-style Progress Bar */}
                 <div
                     className="h-1.5 w-full bg-slate-800/50 relative cursor-pointer group select-none"
                     onClick={handleTimelineClick}
                 >
                     {/* Background Track */}
                     <div className="absolute inset-0 bg-white/10 group-hover:bg-white/20 transition-colors rounded-r-full"></div>

                     {/* Progress Fill */}
                     <div
                         ref={progressBarRef}
                         className="absolute top-0 left-0 bottom-0 bg-white group-hover:bg-teal-400 transition-colors"
                         style={{ width: `${duration ? (currentTime / duration) * 100 : 0}%` }}
                     ></div>

                     {/* Scrubber Handle (Circle) */}
                     <div
                         ref={scrubberHandleRef}
                         className="absolute top-1/2 -translate-y-1/2 w-3 h-3 bg-white rounded-full shadow-lg opacity-100 group-hover:scale-125 transition-transform"
                          style={{ left: `${duration ? (currentTime / duration) * 100 : 0}%`, marginLeft: '-6px' }}
                     ></div>
                 </div>
             </div>

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
                    playbackRef={playbackTimeRef}
                 />
                 </div>

                 {!currentVisualBuffer && !currentVisualPeaks && (
                     <div className="absolute inset-0 flex items-center justify-center text-slate-600 font-mono pointer-events-none">
                         {loadingStems ? "Loading..." : t('selectTrack')}
                     </div>
                 )}
             </div>
          </main>

          <aside className="w-80 bg-[#161b2e] border-l border-white/5 flex flex-col shrink-0 p-4 space-y-3 overflow-y-auto">

              <div className="bg-[#1e2336] rounded-xl p-3 border border-white/5 shadow-lg">
                  <div className="flex items-center justify-between mb-2">
                      <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">{t('speed')}</span>
                      <span className="text-[10px] font-mono text-teal-400">{safeStemSpeed.toFixed(2)}x</span>
                  </div>
                  <input
                      type="range"
                      min="0.5"
                      max="1.5"
                      step="0.01"
                      value={safeStemSpeed}
                      onChange={(e) => setStemSpeed(normalizeStemSpeed(parseFloat(e.target.value)))}
                      className="w-full h-1 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-teal-500"
                  />
                  <div className="flex justify-between text-[9px] text-slate-600 mt-1">
                      <span>0.5x</span>
                      <span>1.0x</span>
                      <span>1.5x</span>
                  </div>
              </div>

              <div>
                  <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-2">{t('selectedChannel')}</div>
                  <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded bg-teal-500/10 flex items-center justify-center text-teal-500">
                          <MusicalNoteIcon className="w-5 h-5" />
                      </div>
                      <h2 className="text-xl font-bold text-white truncate" title={selectedStem?.name}>{selectedStem?.name || t('noTrackSelected')}</h2>
                  </div>
              </div>

              {selectedStem && (
                  <>
                    <div className="flex gap-2">
                        {/* Pan */}
                        <div className="flex-1 bg-[#1e2336] rounded-xl p-3 border border-white/5 shadow-lg min-w-0">
                            <div className="flex justify-between items-center mb-2">
                                <div className="flex items-center gap-2 overflow-hidden">
                                    <Toggle
                                        checked={selectedStem.pan.enabled}
                                        onChange={(v) => updateStem(selectedStemIndex, { pan: {...selectedStem.pan, enabled: v}})}
                                        colorClass="bg-blue-500"
                                    />
                                    <span className={`text-xs font-bold truncate ${selectedStem.pan.enabled ? 'text-blue-400' : 'text-slate-500'}`}>{t('panning')}</span>
                                </div>
                            </div>
                            <div className={`flex justify-center transition-opacity ${selectedStem.pan.enabled ? 'opacity-100' : 'opacity-40 pointer-events-none'}`}>
                                <Knob label="L / R" value={selectedStem.pan.value} min={-1} max={1} step={0.1} onChange={(v) => updateStem(selectedStemIndex, { pan: {...selectedStem.pan, value: v}})} />
                            </div>
                        </div>

                        {/* Reverb */}
                        <div className="flex-1 bg-[#1e2336] rounded-xl p-3 border border-white/5 shadow-lg min-w-0">
                            <div className="flex justify-between items-center mb-2">
                                <div className="flex items-center gap-2 overflow-hidden">
                                    <Toggle
                                        checked={selectedStem.reverb.enabled}
                                        onChange={(v) => updateStem(selectedStemIndex, { reverb: {...selectedStem.reverb, enabled: v}})}
                                        colorClass="bg-purple-500"
                                    />
                                    <span className={`text-xs font-bold truncate ${selectedStem.reverb.enabled ? 'text-purple-400' : 'text-slate-500'}`}>{t('reverb')}</span>
                                </div>
                            </div>
                        <div className={`flex justify-center transition-opacity ${selectedStem.reverb.enabled ? 'opacity-100' : 'opacity-40 pointer-events-none'}`}>
                                <Knob label="AMOUNT" value={selectedStem.reverb.amount} min={0} max={100} onChange={(v) => updateStem(selectedStemIndex, { reverb: {...selectedStem.reverb, amount: v}})} />
                            </div>
                        </div>
                    </div>

                    <div className="flex gap-2">
                        {/* Stereo Width */}
                        <div className="flex-1 bg-[#1e2336] rounded-xl p-3 border border-white/5 shadow-lg min-w-0">
                            <div className="flex justify-between items-center mb-2">
                                <div className="flex items-center gap-2 overflow-hidden">
                                    <Toggle
                                        checked={selectedStem.stereoWidth.enabled}
                                        onChange={(v) => updateStem(selectedStemIndex, { stereoWidth: {...selectedStem.stereoWidth, enabled: v}})}
                                        colorClass="bg-cyan-500"
                                    />
                                    <span className={`text-xs font-bold truncate ${selectedStem.stereoWidth.enabled ? 'text-cyan-400' : 'text-slate-500'}`}>{t('stereoWidth')}</span>
                                </div>
                                <span className="text-[10px] font-mono text-cyan-400">{Math.round(selectedStem.stereoWidth.amount)}%</span>
                            </div>
                            <div className={`transition-opacity ${selectedStem.stereoWidth.enabled ? 'opacity-100' : 'opacity-40 pointer-events-none'}`}>
                                <input
                                    type="range"
                                    min="0"
                                    max="200"
                                    step="1"
                                    value={selectedStem.stereoWidth.amount}
                                    onChange={(e) => updateStem(selectedStemIndex, { stereoWidth: {...selectedStem.stereoWidth, amount: parseFloat(e.target.value)}})}
                                    className="w-full h-1 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-cyan-500"
                                />
                                <div className="flex justify-between text-[9px] text-slate-600 mt-1">
                                    <span>0%</span>
                                    <span>100%</span>
                                    <span>200%</span>
                                </div>
                            </div>
                        </div>

                        {/* Saturation */}
                        <div className="flex-1 bg-[#1e2336] rounded-xl p-3 border border-white/5 shadow-lg min-w-0">
                            <div className="flex justify-between items-center mb-2">
                                <div className="flex items-center gap-2 overflow-hidden">
                                    <Toggle
                                        checked={selectedStem.saturation.enabled}
                                        onChange={(v) => updateStem(selectedStemIndex, { saturation: {...selectedStem.saturation, enabled: v}})}
                                        colorClass="bg-rose-500"
                                    />
                                    <span className={`text-xs font-bold truncate ${selectedStem.saturation.enabled ? 'text-rose-400' : 'text-slate-500'}`}>{t('saturation')}</span>
                                </div>
                            </div>
                            <div className={`flex justify-center transition-opacity ${selectedStem.saturation.enabled ? 'opacity-100' : 'opacity-40 pointer-events-none'}`}>
                                <Knob label="DRIVE" value={selectedStem.saturation.amount} min={0} max={100} step={1} onChange={(v) => updateStem(selectedStemIndex, { saturation: {...selectedStem.saturation, amount: v}})} />
                            </div>
                        </div>
                    </div>

                    <div className="flex gap-2">
                        {/* Transient */}
                        <div className="flex-1 bg-[#1e2336] rounded-xl p-3 border border-white/5 shadow-lg min-w-0">
                            <div className="flex justify-between items-center mb-2">
                                <div className="flex items-center gap-2 overflow-hidden">
                                    <Toggle
                                        checked={selectedStem.transient.enabled}
                                        onChange={(v) => updateStem(selectedStemIndex, { transient: {...selectedStem.transient, enabled: v}})}
                                        colorClass="bg-amber-500"
                                    />
                                    <span className={`text-xs font-bold truncate ${selectedStem.transient.enabled ? 'text-amber-400' : 'text-slate-500'}`}>{t('transient')}</span>
                                </div>
                            </div>
                            <div className={`flex justify-center transition-opacity ${selectedStem.transient.enabled ? 'opacity-100' : 'opacity-40 pointer-events-none'}`}>
                                <Knob label="PUNCH" value={selectedStem.transient.amount} min={-100} max={100} step={1} onChange={(v) => updateStem(selectedStemIndex, { transient: {...selectedStem.transient, amount: v}})} />
                            </div>
                        </div>

                        {/* Depth */}
                        <div className="flex-1 bg-[#1e2336] rounded-xl p-3 border border-white/5 shadow-lg min-w-0">
                            <div className="flex justify-between items-center mb-2">
                                <div className="flex items-center gap-2 overflow-hidden">
                                    <Toggle
                                        checked={selectedStem.depth.enabled}
                                        onChange={(v) => updateStem(selectedStemIndex, { depth: {...selectedStem.depth, enabled: v}})}
                                        colorClass="bg-emerald-500"
                                    />
                                    <span className={`text-xs font-bold truncate ${selectedStem.depth.enabled ? 'text-emerald-400' : 'text-slate-500'}`}>{t('depth')}</span>
                                </div>
                            </div>
                            <div className={`flex justify-center transition-opacity ${selectedStem.depth.enabled ? 'opacity-100' : 'opacity-40 pointer-events-none'}`}>
                                <Knob label="DEPTH" value={selectedStem.depth.amount} min={0} max={100} step={1} onChange={(v) => updateStem(selectedStemIndex, { depth: {...selectedStem.depth, amount: v}})} />
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

// --- Componentes Auxiliares ---

function Toggle({ checked, onChange, colorClass = "bg-teal-500" }: { checked: boolean, onChange: (v: boolean) => void, colorClass?: string }) {
    return (
        <div
            onClick={(e) => { e.stopPropagation(); onChange(!checked); }}
            className={`w-10 h-5 rounded-full p-1 cursor-pointer transition-colors duration-200 ease-in-out flex items-center ${checked ? colorClass : 'bg-slate-700'}`}
        >
            <div className={`w-3 h-3 bg-white rounded-full shadow-sm transform transition-transform duration-200 ${checked ? 'translate-x-5' : 'translate-x-0'}`} />
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
        <div className="flex flex-col items-center gap-1 group select-none">
            <div
                onMouseDown={handleMouseDown}
                className="w-9 h-9 rounded-full bg-[#11131f] relative cursor-ns-resize shadow-[inset_0_2px_4px_rgba(0,0,0,0.5)] border border-slate-700 hover:border-slate-500 transition-colors"
            >
                <div
                    className="absolute top-1/2 left-1/2 w-0.5 h-3 bg-teal-400 origin-bottom -translate-x-1/2 -translate-y-full rounded-full shadow-[0_0_5px_rgba(45,212,191,0.5)]"
                    style={{ transform: `translate(-50%, -50%) rotate(${rotation}deg)` }}
                ></div>
            </div>
            <div className="text-center">
                <span className="text-[9px] font-bold text-slate-500 block mb-0.5 tracking-wider">{label}</span>
                <span className={`text-[10px] font-mono transition-colors ${dragging ? 'text-teal-400' : 'text-slate-600'}`}>{value.toFixed(step && step < 1 ? 2 : 1)}</span>
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