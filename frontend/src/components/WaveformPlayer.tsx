"use client";

import React, { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { gaEvent } from "../lib/ga";
import { PlayIcon, PauseIcon, ArrowDownTrayIcon } from "@heroicons/react/24/solid";

type WaveformPlayerProps = {
  src: string;
  compareSrc?: string; // Optional: Original source for A/B
  isCompareActive?: boolean; // Optional: Whether to play/show the compare source
  downloadFileName?: string;
  accentColor?: string; // color de la parte reproducida (por defecto naranja)
  className?: string;
};

type PeakArray = number[];

function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return "0:00";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export const WaveformPlayer: React.FC<WaveformPlayerProps> = ({
  src,
  compareSrc,
  isCompareActive = false,
  downloadFileName,
  accentColor = "#fb923c", // naranja cálido
  className = "",
}) => {
  // Audio Refs
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const compareAudioRef = useRef<HTMLAudioElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // Web Audio API refs
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const sourceRef = useRef<MediaElementAudioSourceNode | null>(null);
  const compareSourceRef = useRef<MediaElementAudioSourceNode | null>(null);
  const mainGainRef = useRef<GainNode | null>(null);
  const compareGainRef = useRef<GainNode | null>(null);
  const requestRef = useRef<number | null>(null);

  const [isPlaying, setIsPlaying] = useState(false);
  const [duration, setDuration] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);

  // Peaks state
  const [mainPeaks, setMainPeaks] = useState<PeakArray>([]);
  const [comparePeaks, setComparePeaks] = useState<PeakArray>([]);
  const [isLoadingPeaks, setIsLoadingPeaks] = useState(false);

  const [canvasSize, setCanvasSize] = useState({ width: 0, height: 0 });
  const [isDownloading, setIsDownloading] = useState(false);

  // Determine active peaks
  const peaks = isCompareActive && comparePeaks.length > 0 ? comparePeaks : mainPeaks;
  const activeSrc = isCompareActive && compareSrc ? compareSrc : src;

  // Resize Observer
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) {
        setCanvasSize({
          width: entry.contentRect.width,
          height: entry.contentRect.height,
        });
      }
    });

    observer.observe(canvas);
    return () => observer.disconnect();
  }, []);

  // ------------------------------------------------------------
  // Carga de audio (HTMLAudio) – Listeners
  // ------------------------------------------------------------
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    // Solo el audio principal controla el tiempo y duración visibles
    const onLoaded = () => setDuration(audio.duration || 0);
    const onTimeUpdate = () => {
        setCurrentTime(audio.currentTime || 0);

        // Sync check (solo si playing)
        if (compareAudioRef.current && !audio.paused) {
             const diff = Math.abs(compareAudioRef.current.currentTime - audio.currentTime);
             if (diff > 0.1) {
                 compareAudioRef.current.currentTime = audio.currentTime;
             }
        }
    };
    const onEnded = () => {
        setIsPlaying(false);
        if (compareAudioRef.current) {
            compareAudioRef.current.pause();
            compareAudioRef.current.currentTime = 0;
        }
    };

    audio.addEventListener("loadedmetadata", onLoaded);
    audio.addEventListener("timeupdate", onTimeUpdate);
    audio.addEventListener("ended", onEnded);

    // Cuando cambia src, reseteamos (solo si src cambia de verdad)
    // Nota: Si solo cambia compareSrc, no reseteamos el playback principal.

    return () => {
      audio.removeEventListener("loadedmetadata", onLoaded);
      audio.removeEventListener("timeupdate", onTimeUpdate);
      audio.removeEventListener("ended", onEnded);
    };
  }, [src]); // Solo re-bind si cambia el src principal

  // Reset state on src change
  useEffect(() => {
    setIsPlaying(false);
    setCurrentTime(0);
    if (requestRef.current) {
        cancelAnimationFrame(requestRef.current);
    }
  }, [src]);

  // Handle Compare Audio loading (solo para estar listos)
  useEffect(() => {
      if (!compareSrc) return;
      // Podríamos poner listeners aquí si quisiéramos debuggear
  }, [compareSrc]);

  // ------------------------------------------------------------
  // Cargar formas de onda (decodeAudioData) -> peaks
  // ------------------------------------------------------------
  const fetchPeaks = async (url: string): Promise<number[]> => {
      try {
        const res = await fetch(url);
        const arrayBuffer = await res.arrayBuffer();

        const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
        const audioCtx = new AudioCtx();
        const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);
        const channelData = audioBuffer.getChannelData(0);
        const totalSamples = channelData.length;
        const desiredBars = 400;
        const samplesPerBar = Math.max(1, Math.floor(totalSamples / desiredBars));

        const newPeaks: number[] = [];
        for (let i = 0; i < desiredBars; i++) {
          const start = i * samplesPerBar;
          let end = start + samplesPerBar;
          if (end > totalSamples) end = totalSamples;

          let sum = 0;
          let count = 0;
          for (let j = start; j < end; j++) {
            const v = channelData[j];
            sum += v * v;
            count++;
          }
          if (count === 0) {
            newPeaks.push(0);
          } else {
            const rms = Math.sqrt(sum / count);
            newPeaks.push(rms);
          }
        }
        audioCtx.close();
        return newPeaks;
      } catch (err) {
        console.error("Error loading waveform data for", url, err);
        return [];
      }
  };

  useEffect(() => {
    let cancelled = false;

    async function loadAllPeaks() {
        if (!src) return;
        setIsLoadingPeaks(true);

        const pMain = await fetchPeaks(src);
        if (cancelled) return;
        setMainPeaks(pMain);

        if (compareSrc) {
            const pCompare = await fetchPeaks(compareSrc);
            if (cancelled) return;
            setComparePeaks(pCompare);
        } else {
            setComparePeaks([]);
        }

        setIsLoadingPeaks(false);
    }

    loadAllPeaks();
    return () => { cancelled = true; };
  }, [src, compareSrc]);


  const progress = useMemo(
    () => (duration > 0 ? currentTime / duration : 0),
    [currentTime, duration],
  );

  // ------------------------------------------------------------
  // Dibujo
  // ------------------------------------------------------------

  const setupCanvas = useCallback((ctx: CanvasRenderingContext2D, width: number, height: number) => {
    const dpr = window.devicePixelRatio || 1;
    const canvas = canvasRef.current;
    if (canvas && (canvas.width !== width * dpr || canvas.height !== height * dpr)) {
      canvas.width = width * dpr;
      canvas.height = height * dpr;
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    // Fondo suave
    const bgGrad = ctx.createLinearGradient(0, 0, 0, height);
    bgGrad.addColorStop(0, "#020617");
    bgGrad.addColorStop(1, "#020617");
    ctx.fillStyle = bgGrad;
    ctx.fillRect(0, 0, width, height);
  }, []);

  const drawStaticWaveform = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const { width, height } = canvasSize;
    if (width === 0 || height === 0) return;

    setupCanvas(ctx, width, height);

    if (!peaks.length) {
      const midY = height / 2;
      ctx.strokeStyle = "rgba(0,0,0,0.75)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(8, midY + 0.5);
      ctx.lineTo(width - 8, midY + 0.5);
      ctx.stroke();
      return;
    }

    const paddingX = 8;
    const availableWidth = width - paddingX * 2;
    const barWidth = 2;
    const gap = 1;
    const step = barWidth + gap;
    const maxBars = Math.floor(availableWidth / step);
    const totalBars = Math.min(maxBars, peaks.length);
    const peaksPerBar = Math.max(1, Math.floor(peaks.length / totalBars));
    const midY = height / 2;
    const topMaxHeight = height * 0.45;
    const reflectFactor = 0.5;

    ctx.strokeStyle = "rgba(0,0,0,0.85)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(paddingX, midY + 0.5);
    ctx.lineTo(width - paddingX, midY + 0.5);
    ctx.stroke();

    const maxPeak = peaks.reduce((max, v) => (v > max ? v : max), Number.NEGATIVE_INFINITY);
    const normalizer = maxPeak > 0 ? maxPeak : 1;

    // Si estamos en modo compare, quizás cambiamos el color un poco?
    // De momento usamos el mismo accentColor.
    const playedColor = accentColor;
    const unplayedColor = "#e5e7eb";
    const playedReflection = "rgba(251, 146, 60, 0.35)";
    const unplayedReflection = "rgba(229, 231, 235, 0.18)";

    for (let i = 0; i < totalBars; i++) {
      let sum = 0;
      let count = 0;
      const peakStart = i * peaksPerBar;
      const peakEnd = Math.min(peakStart + peaksPerBar, peaks.length);
      for (let j = peakStart; j < peakEnd; j++) {
        sum += peaks[j];
        count++;
      }
      const avg = count > 0 ? sum / count : 0;
      const norm = Math.pow(avg / normalizer, 0.7);
      const barHeightTop = Math.max(2, norm * topMaxHeight);
      const barHeightBottom = barHeightTop * reflectFactor;
      const x = paddingX + i * step;
      const barProgress = totalBars > 1 ? i / (totalBars - 1) : 0;
      const isPlayed = barProgress <= progress + 0.001;

      ctx.fillStyle = isPlayed ? playedColor : unplayedColor;
      ctx.fillRect(x, midY - barHeightTop, barWidth, barHeightTop);

      ctx.fillStyle = isPlayed ? playedReflection : unplayedReflection;
      ctx.fillRect(x, midY + 1, barWidth, barHeightBottom);
    }
  }, [peaks, accentColor, progress, canvasSize, setupCanvas]);

  const drawSpectrum = useCallback(() => {
    if (!analyserRef.current || !canvasRef.current) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const { width, height } = canvasSize;
    if (width === 0 || height === 0) return;

    setupCanvas(ctx, width, height);

    const analyser = analyserRef.current;
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    analyser.getByteFrequencyData(dataArray);

    const paddingX = 8;
    const availableWidth = width - paddingX * 2;
    const barWidth = 2;
    const gap = 1;
    const step = barWidth + gap;
    const maxBars = Math.floor(availableWidth / step);

    const midY = height / 2;
    const topMaxHeight = height * 0.45;
    const reflectFactor = 0.5;

    ctx.strokeStyle = "rgba(0,0,0,0.85)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(paddingX, midY + 0.5);
    ctx.lineTo(width - paddingX, midY + 0.5);
    ctx.stroke();

    const usableBins = Math.floor(bufferLength * 0.7);
    const binsPerBar = Math.floor(usableBins / maxBars) || 1;

    // Colores para estado "tocado" vs "por tocar"
    const playedColor = accentColor;
    const unplayedColor = "#e5e7eb";
    const playedReflection = "rgba(251, 146, 60, 0.35)";
    const unplayedReflection = "rgba(229, 231, 235, 0.18)";

    // Calcular progreso actual directamente del audio para suavidad
    const audio = audioRef.current;
    const currentDuration = audio?.duration || 1;
    const currentT = audio?.currentTime || 0;
    const currentProgress = currentDuration > 0 ? currentT / currentDuration : 0;

    for (let i = 0; i < maxBars; i++) {
        let sum = 0;
        for (let j = 0; j < binsPerBar; j++) {
            const index = i * binsPerBar + j;
            if (index < bufferLength) {
                sum += dataArray[index];
            }
        }
        const avg = sum / binsPerBar;
        const norm = avg / 255;
        const boostedNorm = Math.pow(norm, 0.8);

        const barHeightTop = Math.max(1, boostedNorm * topMaxHeight);
        const barHeightBottom = barHeightTop * reflectFactor;
        const x = paddingX + i * step;

        // Determinar si esta barra corresponde a tiempo pasado
        const barProgress = maxBars > 1 ? i / (maxBars - 1) : 0;
        const isPlayed = barProgress <= currentProgress;

        ctx.fillStyle = isPlayed ? playedColor : unplayedColor;
        ctx.fillRect(x, midY - barHeightTop, barWidth, barHeightTop);
        ctx.fillStyle = isPlayed ? playedReflection : unplayedReflection;
        ctx.fillRect(x, midY + 1, barWidth, barHeightBottom);
    }

    requestRef.current = requestAnimationFrame(drawSpectrum);
  }, [canvasSize, accentColor, setupCanvas]);

  // ------------------------------------------------------------
  // Web Audio Context & Graph
  // ------------------------------------------------------------
  const initAudioContext = () => {
      if (!audioContextRef.current) {
          const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
          const ctx = new AudioCtx();
          audioContextRef.current = ctx;

          // Analyser Node (Shared)
          const analyser = ctx.createAnalyser();
          analyser.fftSize = 2048;
          analyser.smoothingTimeConstant = 0.85;
          analyser.connect(ctx.destination);
          analyserRef.current = analyser;
      }

      const ctx = audioContextRef.current;
      if (ctx.state === 'suspended') {
          ctx.resume();
      }

      // Main Source Setup
      if (!sourceRef.current && audioRef.current) {
          try {
             const source = ctx.createMediaElementSource(audioRef.current);
             const gain = ctx.createGain();
             source.connect(gain);
             gain.connect(analyserRef.current!);

             sourceRef.current = source;
             mainGainRef.current = gain;

             // Initial state
             gain.gain.setValueAtTime(isCompareActive ? 0 : 1, ctx.currentTime);
          } catch (e) {
             console.error("Error creating MediaElementSource Main:", e);
          }
      }

      // Compare Source Setup
      if (compareSrc && compareAudioRef.current && !compareSourceRef.current) {
          try {
              const source = ctx.createMediaElementSource(compareAudioRef.current);
              const gain = ctx.createGain();
              source.connect(gain);
              gain.connect(analyserRef.current!);

              compareSourceRef.current = source;
              compareGainRef.current = gain;

              // Initial state
              gain.gain.setValueAtTime(isCompareActive ? 1 : 0, ctx.currentTime);
          } catch (e) {
              console.error("Error creating MediaElementSource Compare:", e);
          }
      }
  };

  // ------------------------------------------------------------
  // Effects
  // ------------------------------------------------------------

  // Handle Playback State
  useEffect(() => {
    if (isPlaying) {
        initAudioContext();
        drawSpectrum();
    } else {
        if (requestRef.current) {
            cancelAnimationFrame(requestRef.current);
        }
        drawStaticWaveform();
    }
    return () => {
        if (requestRef.current) {
            cancelAnimationFrame(requestRef.current);
        }
    };
  }, [isPlaying, compareSrc, drawSpectrum, drawStaticWaveform]);

  // Re-draw static when stopped and state changes
  useEffect(() => {
    if (!isPlaying) {
        drawStaticWaveform();
    }
  }, [isPlaying, drawStaticWaveform, progress, peaks]);

  // Handle A/B Switching (Gain Control)
  useEffect(() => {
     const ctx = audioContextRef.current;
     if (ctx && mainGainRef.current) {
         const now = ctx.currentTime;
         // Crossfade duration very short (instant but no pop)
         const rampTime = now + 0.05;

         // Ensure we cancel any scheduled changes to avoid conflicts
         mainGainRef.current.gain.cancelScheduledValues(now);
         mainGainRef.current.gain.setValueAtTime(mainGainRef.current.gain.value, now);

         if (isCompareActive) {
             mainGainRef.current.gain.linearRampToValueAtTime(0, rampTime);
             if (compareGainRef.current) {
                 compareGainRef.current.gain.cancelScheduledValues(now);
                 compareGainRef.current.gain.setValueAtTime(compareGainRef.current.gain.value, now);
                 compareGainRef.current.gain.linearRampToValueAtTime(1, rampTime);
             }
         } else {
             mainGainRef.current.gain.linearRampToValueAtTime(1, rampTime);
             if (compareGainRef.current) {
                 compareGainRef.current.gain.cancelScheduledValues(now);
                 compareGainRef.current.gain.setValueAtTime(compareGainRef.current.gain.value, now);
                 compareGainRef.current.gain.linearRampToValueAtTime(0, rampTime);
             }
         }
     }
  }, [isCompareActive, compareSrc, isPlaying]); // Added isPlaying to ensure gains are applied on play start


  // ------------------------------------------------------------
  // Interaction
  // ------------------------------------------------------------
  const togglePlay = () => {
    const audio = audioRef.current;
    if (!audio) return;

    if (isPlaying) {
      audio.pause();
      if (compareAudioRef.current) compareAudioRef.current.pause();
      setIsPlaying(false);
    } else {
      if (audioContextRef.current && audioContextRef.current.state === 'suspended') {
          audioContextRef.current.resume();
      }

      // Ensure sync before start
      if (compareAudioRef.current) {
          compareAudioRef.current.currentTime = audio.currentTime;
          compareAudioRef.current.play().catch(e => console.error("Compare play failed", e));
      }

      audio.play().catch(e => console.error("Main play failed", e));
      setIsPlaying(true);
    }
  };

  const handleWaveformClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const audio = audioRef.current;
    if (!audio || !duration) return;

    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const ratio = x / rect.width;
    const newTime = Math.max(0, Math.min(duration * ratio, duration));

    audio.currentTime = newTime;
    if (compareAudioRef.current) {
        compareAudioRef.current.currentTime = newTime;
    }

    setCurrentTime(newTime);
  };

  const handleDownload = async () => {
    if (!activeSrc || isDownloading) return;

    // Track download
    gaEvent("download_result", {
      file_name: downloadFileName || "mix.wav",
      url: activeSrc,
    });

    setIsDownloading(true);
    try {
      const response = await fetch(activeSrc);
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);

      const a = document.createElement("a");
      a.style.display = "none";
      a.href = url;
      a.download = downloadFileName || "mix.wav";
      document.body.appendChild(a);
      a.click();

      // Cleanup
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error("Download failed:", error);
      const a = document.createElement("a");
      a.href = activeSrc;
      a.download = downloadFileName || "mix.wav";
      a.target = "_blank";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <div
      className={[
        "flex items-center gap-3 rounded-3xl bg-slate-950/90 px-3 py-2 shadow-md shadow-black/40",
        className,
      ].join(" ")}
    >
      {/* Audio principal - crossOrigin anonymous is crucial for Web Audio */}
      <audio ref={audioRef} src={src} crossOrigin="anonymous" className="hidden" />

      {/* Audio comparativa (opcional) */}
      {compareSrc && (
          <audio ref={compareAudioRef} src={compareSrc} crossOrigin="anonymous" className="hidden" />
      )}

      {/* Botón Play/Pause */}
      <button
        type="button"
        onClick={togglePlay}
        className="flex h-9 w-9 items-center justify-center rounded-full bg-amber-500 text-slate-950 shadow hover:bg-amber-400 transition"
      >
        {isPlaying ? (
          <PauseIcon className="h-5 w-5" />
        ) : (
          <PlayIcon className="h-5 w-5" />
        )}
      </button>

      {/* Waveform + tiempos */}
      <div className="relative flex-1" onClick={handleWaveformClick}>
        <canvas
          ref={canvasRef}
          className="h-10 w-full cursor-pointer rounded-xl bg-transparent"
        />
        {/* tiempos izquierda / derecha */}
        <div className="pointer-events-none absolute inset-x-2 top-1 flex justify-between text-[10px] font-medium text-slate-100">
          <span className="px-1 py-[1px] bg-black/80 rounded-sm">
            {formatTime(currentTime)}
          </span>
          <span className="px-1 py-[1px] bg-black/80 rounded-sm">
            {isLoadingPeaks && !duration ? "…" : formatTime(duration)}
          </span>
        </div>
      </div>

      {/* Botón descarga */}
      <button
        type="button"
        onClick={handleDownload}
        disabled={isDownloading}
        className={`flex h-9 w-9 items-center justify-center rounded-full bg-amber-500 text-slate-950 shadow hover:bg-amber-400 transition disabled:opacity-50 ${isDownloading ? "cursor-wait" : ""}`}
        title="Download"
      >
        {isDownloading ? (
           <span className="block h-4 w-4 animate-spin rounded-full border-2 border-slate-950 border-t-transparent"></span>
        ) : (
           <ArrowDownTrayIcon className="h-5 w-5" />
        )}
      </button>
    </div>
  );
};
