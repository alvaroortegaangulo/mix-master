// frontend/src/components/WaveformPlayer.tsx
"use client";

import type React from "react";
import { useEffect, useRef, useState } from "react";

type WaveformPlayerProps = {
  src: string;
  className?: string;
};

function formatTime(sec: number | null): string {
  if (sec == null || !Number.isFinite(sec)) return "0:00";
  const total = Math.max(0, Math.floor(sec));
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

export function WaveformPlayer({ src, className = "" }: WaveformPlayerProps) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [duration, setDuration] = useState<number | null>(null);
  const [currentTime, setCurrentTime] = useState<number | null>(null);

  const progress =
    duration && currentTime != null && duration > 0
      ? currentTime / duration
      : 0;

  // Listeners de audio
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const handleLoaded = () => {
      setDuration(audio.duration || 0);
    };

    const handleTimeUpdate = () => {
      setCurrentTime(audio.currentTime || 0);
    };

    const handleEnded = () => {
      setIsPlaying(false);
    };

    audio.addEventListener("loadedmetadata", handleLoaded);
    audio.addEventListener("timeupdate", handleTimeUpdate);
    audio.addEventListener("ended", handleEnded);

    return () => {
      audio.removeEventListener("loadedmetadata", handleLoaded);
      audio.removeEventListener("timeupdate", handleTimeUpdate);
      audio.removeEventListener("ended", handleEnded);
    };
  }, [src]);

  // Reset cuando cambia el src
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    audio.pause();
    audio.currentTime = 0;
    setIsPlaying(false);
    setCurrentTime(0);
    setDuration(null);
    audio.load();
  }, [src]);

  const togglePlay = async () => {
    const audio = audioRef.current;
    if (!audio) return;

    if (isPlaying) {
      audio.pause();
      setIsPlaying(false);
    } else {
      try {
        await audio.play();
        setIsPlaying(true);
      } catch (err) {
        console.error("Failed to play audio", err);
      }
    }
  };

  const handleScrub = (e: React.MouseEvent<HTMLDivElement>) => {
    const audio = audioRef.current;
    if (!audio || !duration) return;

    const rect = e.currentTarget.getBoundingClientRect();
    const ratio = (e.clientX - rect.left) / rect.width;
    const newTime = Math.max(0, Math.min(duration, duration * ratio));

    audio.currentTime = newTime;
    setCurrentTime(newTime);
  };

  // Estilos de barras tipo SoundCloud
  const baseWaveform =
    "repeating-linear-gradient(to right, rgba(248,250,252,0.92) 0px, rgba(248,250,252,0.92) 2px, transparent 2px, transparent 4px)";
  const playedWaveform =
    "repeating-linear-gradient(to right, rgb(249,115,22) 0px, rgb(249,115,22) 2px, transparent 2px, transparent 4px)";

  return (
    <div
      className={`flex items-center gap-3 rounded-2xl bg-slate-950 px-3 py-2 text-[11px] text-slate-50 ${className}`}
    >
      {/* Botón Play/Pause */}
      <button
        type="button"
        onClick={togglePlay}
        className="flex h-8 w-8 items-center justify-center rounded-full bg-emerald-400 text-black shadow hover:bg-emerald-300"
        aria-label={isPlaying ? "Pause" : "Play"}
      >
        {isPlaying ? (
          <span className="flex gap-0.5">
            <span className="h-3.5 w-0.5 bg-black" />
            <span className="h-3.5 w-0.5 bg-black" />
          </span>
        ) : (
          <span className="ml-0.5 h-0 w-0 border-y-4 border-y-transparent border-l-[8px] border-l-black" />
        )}
      </button>

      {/* Waveform estilo SoundCloud */}
      <div
        className="relative flex-1 cursor-pointer select-none py-1"
        onClick={handleScrub}
      >
        <div className="relative h-10 overflow-hidden rounded-md bg-black">
          {/* barras no reproducidas */}
          <div
            className="absolute inset-0"
            style={{ backgroundImage: baseWaveform }}
          />
          {/* barras reproducidas */}
          <div
            className="absolute inset-y-0 left-0 overflow-hidden"
            style={{ width: `${(progress || 0) * 100}%` }}
          >
            <div
              className="h-full"
              style={{ backgroundImage: playedWaveform }}
            />
          </div>
        </div>

        {/* tiempos en cajitas negras a izquierda y derecha */}
        <div className="pointer-events-none absolute inset-0 flex items-center justify-between px-1 text-[10px] font-semibold text-slate-100">
          <span className="rounded-sm bg-black/90 px-1.5 py-0.5">
            {formatTime(currentTime)}
          </span>
          <span className="rounded-sm bg-black/90 px-1.5 py-0.5">
            {formatTime(duration)}
          </span>
        </div>
      </div>

      {/* Botón descargar */}
      <a
        href={src}
        download
        className="flex h-8 w-8 items-center justify-center rounded-full border border-slate-500/70 bg-slate-900/90 text-[15px] hover:bg-slate-800"
        aria-label="Download audio"
      >
        ⬇
      </a>

      <audio ref={audioRef} src={src} preload="metadata" className="hidden" />
    </div>
  );
}
