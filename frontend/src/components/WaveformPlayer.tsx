// frontend/src/components/WaveformPlayer.tsx
"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import { gaEvent } from "../lib/ga";

type WaveformPlayerProps = {
  src: string;
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
  downloadFileName,
  accentColor = "#fb923c", // naranja cálido
  className = "",
}) => {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const [isPlaying, setIsPlaying] = useState(false);
  const [duration, setDuration] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);
  const [peaks, setPeaks] = useState<PeakArray>([]);
  const [isLoadingPeaks, setIsLoadingPeaks] = useState(false);

  // ------------------------------------------------------------
  // Carga de audio (HTMLAudio) – solo para reproducción
  // ------------------------------------------------------------
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const onLoaded = () => setDuration(audio.duration || 0);
    const onTimeUpdate = () => setCurrentTime(audio.currentTime || 0);
    const onEnded = () => setIsPlaying(false);

    audio.addEventListener("loadedmetadata", onLoaded);
    audio.addEventListener("timeupdate", onTimeUpdate);
    audio.addEventListener("ended", onEnded);

    // si cambiamos de src, reseteamos estado
    setIsPlaying(false);
    setCurrentTime(0);

    return () => {
      audio.removeEventListener("loadedmetadata", onLoaded);
      audio.removeEventListener("timeupdate", onTimeUpdate);
      audio.removeEventListener("ended", onEnded);
    };
  }, [src]);

  // ------------------------------------------------------------
  // Cargar forma de onda (decodeAudioData) -> peaks
  // ------------------------------------------------------------
  useEffect(() => {
    let cancelled = false;

    async function loadPeaks() {
      if (!src) return;
      try {
        setIsLoadingPeaks(true);
        const res = await fetch(src);
        const arrayBuffer = await res.arrayBuffer();

        const AudioCtx =
          window.AudioContext || (window as any).webkitAudioContext;
        const audioCtx = new AudioCtx();
        const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);

        if (cancelled) {
          audioCtx.close();
          return;
        }

        const channelData = audioBuffer.getChannelData(0); // mono para análisis
        const totalSamples = channelData.length;

        // Queremos muchas barras finas para ver bien la forma de onda.
        const desiredBars = 400;
        const samplesPerBar = Math.max(
          1,
          Math.floor(totalSamples / desiredBars),
        );

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
            // rms -> 0..1 aprox
            const rms = Math.sqrt(sum / count);
            newPeaks.push(rms);
          }
        }

        audioCtx.close();
        if (!cancelled) {
          setPeaks(newPeaks);
        }
      } catch (err) {
        console.error("Error loading waveform data", err);
        if (!cancelled) {
          setPeaks([]);
        }
      } finally {
        if (!cancelled) setIsLoadingPeaks(false);
      }
    }

    loadPeaks();

    return () => {
      cancelled = true;
    };
  }, [src]);

  const progress = useMemo(
    () => (duration > 0 ? currentTime / duration : 0),
    [currentTime, duration],
  );

  // ------------------------------------------------------------
  // Dibujo en canvas: barras rectangulares + reflejo
  // ------------------------------------------------------------
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;

    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const width = rect.width;
    const height = rect.height;

    // Fondo suave
    const bgGrad = ctx.createLinearGradient(0, 0, 0, height);
    bgGrad.addColorStop(0, "#020617");
    bgGrad.addColorStop(1, "#020617");
    ctx.fillStyle = bgGrad;
    ctx.fillRect(0, 0, width, height);

    // Si no hay datos de forma de onda aún, no dibujamos barras
    if (!peaks.length) {
      // línea central igualmente
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

    // barras finas: 2px + 1px de gap
    const barWidth = 2;
    const gap = 1;
    const step = barWidth + gap;
    const maxBars = Math.floor(availableWidth / step);

    // Ajustamos número de barras usando los peaks ya calculados
    const totalBars = Math.min(maxBars, peaks.length);
    const peaksPerBar = Math.max(1, Math.floor(peaks.length / totalBars));

    const midY = height / 2;
    const topMaxHeight = height * 0.45; // parte superior
    const reflectFactor = 0.5; // la parte de abajo será la mitad de alta

    // centro: línea negra
    ctx.strokeStyle = "rgba(0,0,0,0.85)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(paddingX, midY + 0.5);
    ctx.lineTo(width - paddingX, midY + 0.5);
    ctx.stroke();

    // calculamos máximo peak para normalizar
    const maxPeak = peaks.reduce(
      (max, v) => (v > max ? v : max),
      Number.NEGATIVE_INFINITY,
    );
    const normalizer = maxPeak > 0 ? maxPeak : 1;

    const playedColor = accentColor; // parte superior reproducida
    const unplayedColor = "#e5e7eb"; // gris claro
    const playedReflection = "rgba(251, 146, 60, 0.35)";
    const unplayedReflection = "rgba(229, 231, 235, 0.18)";

    for (let i = 0; i < totalBars; i++) {
      // agregamos varios peaks en uno solo
      let sum = 0;
      let count = 0;
      const peakStart = i * peaksPerBar;
      const peakEnd = Math.min(peakStart + peaksPerBar, peaks.length);
      for (let j = peakStart; j < peakEnd; j++) {
        sum += peaks[j];
        count++;
      }
      const avg = count > 0 ? sum / count : 0;

      // curva suave para que sea más orgánico
      const norm = Math.pow(avg / normalizer, 0.7); // 0..1
      const barHeightTop = Math.max(2, norm * topMaxHeight);
      const barHeightBottom = barHeightTop * reflectFactor;

      const x = paddingX + i * step;

      const barProgress = totalBars > 1 ? i / (totalBars - 1) : 0;
      const isPlayed = barProgress <= progress + 0.001;

      // parte superior
      ctx.fillStyle = isPlayed ? playedColor : unplayedColor;
      ctx.fillRect(x, midY - barHeightTop, barWidth, barHeightTop);

      // reflejo inferior
      ctx.fillStyle = isPlayed ? playedReflection : unplayedReflection;
      ctx.fillRect(x, midY + 1, barWidth, barHeightBottom);
    }
  }, [peaks, currentTime, duration, accentColor, progress]);

  // ------------------------------------------------------------
  // Interacción
  // ------------------------------------------------------------
  const togglePlay = () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (isPlaying) {
      audio.pause();
      setIsPlaying(false);
    } else {
      void audio.play();
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
    setCurrentTime(newTime);
  };

  const handleDownload = () => {
    if (!src) return;

    // Track download
    gaEvent("download_result", {
      file_name: downloadFileName || "mix.wav",
      url: src,
    });

    const a = document.createElement("a");
    a.href = src;
    a.download = downloadFileName || "mix.wav";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  return (
    <div
      className={[
        "flex items-center gap-3 rounded-3xl bg-slate-950/90 px-3 py-2 shadow-md shadow-black/40",
        className,
      ].join(" ")}
    >
      {/* Audio oculto para controlar playback */}
      <audio ref={audioRef} src={src} className="hidden" />

      {/* Botón Play/Pause */}
      <button
        type="button"
        onClick={togglePlay}
        className="flex h-9 w-9 items-center justify-center rounded-full bg-emerald-400 text-slate-950 shadow hover:bg-emerald-300 transition"
      >
        {isPlaying ? (
          <span className="h-3 w-3 flex items-center justify-between">
            <span className="block h-3 w-[3px] bg-slate-950" />
            <span className="block h-3 w-[3px] bg-slate-950" />
          </span>
        ) : (
          <span className="ml-[2px] inline-block h-0 w-0 border-y-4 border-l-6 border-y-transparent border-l-slate-950" />
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
        className="flex h-9 w-9 items-center justify-center rounded-full border border-slate-600 bg-slate-900 text-slate-100 hover:bg-slate-800 transition"
        title="Download"
      >
        <span className="block h-3 w-[2px] bg-slate-100 relative">
          <span className="absolute bottom-[-4px] left-1/2 h-0 w-0 -translate-x-1/2 border-x-4 border-t-4 border-x-transparent border-t-slate-100" />
        </span>
      </button>
    </div>
  );
};
