"use client";

import React, { useState, useRef, useEffect } from "react";
import { PlayIcon, PauseIcon } from "@heroicons/react/24/solid";

interface BlogAudioPlayerProps {
  beforeSrc?: string; // Optional for now, assuming standard URLs if provided
  afterSrc?: string;
  labelBefore?: string;
  labelAfter?: string;
  title: string;
}

// Since I don't have real audio files for the blog, I will simulate the visual
// component for now. In a real app, this would use an <audio> tag.
// For the purpose of "professional look", a visualizer placeholder is key.

export default function BlogAudioPlayer({
  title,
  labelBefore = "Original",
  labelAfter = "Piroola Master",
}: BlogAudioPlayerProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [mode, setMode] = useState<"before" | "after">("after");
  const [progress, setProgress] = useState(30); // Simulated progress

  // Simulate playback
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (isPlaying) {
      interval = setInterval(() => {
        setProgress((p) => (p >= 100 ? 0 : p + 0.5));
      }, 50);
    }
    return () => clearInterval(interval);
  }, [isPlaying]);

  return (
    <div className="not-prose my-10 overflow-hidden rounded-2xl border border-slate-700 bg-slate-900 shadow-2xl">
      <div className="flex items-center justify-between border-b border-slate-800 bg-slate-950/50 px-4 py-3">
        <h4 className="text-sm font-bold text-slate-200 flex items-center gap-2">
          <span className="flex h-2 w-2 relative">
             <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-teal-400 opacity-75"></span>
             <span className="relative inline-flex rounded-full h-2 w-2 bg-teal-500"></span>
          </span>
          {title}
        </h4>
        <div className="flex rounded-lg bg-slate-800 p-1">
          <button
            onClick={() => setMode("before")}
            className={`rounded-md px-3 py-1 text-xs font-semibold transition ${
              mode === "before"
                ? "bg-slate-700 text-white shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            {labelBefore}
          </button>
          <button
            onClick={() => setMode("after")}
            className={`rounded-md px-3 py-1 text-xs font-semibold transition ${
              mode === "after"
                ? "bg-teal-600 text-white shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            {labelAfter}
          </button>
        </div>
      </div>

      <div className="relative h-32 w-full bg-slate-900 px-4 py-8">
        {/* Fake Waveform Visualization */}
        <div className="flex h-full items-center justify-center gap-[2px] opacity-80">
          {Array.from({ length: 60 }).map((_, i) => {
             // Create a fake "waveform" pattern
             const height = Math.max(10, Math.sin(i * 0.2) * 40 + Math.random() * 30 + 10);
             const active = (i / 60) * 100 < progress;
             return (
               <div
                 key={i}
                 className={`w-1.5 rounded-full transition-colors duration-75 ${
                    active
                      ? mode === 'after' ? 'bg-teal-500' : 'bg-slate-400'
                      : 'bg-slate-800'
                 }`}
                 style={{ height: `${height}%` }}
               />
             );
          })}
        </div>
      </div>

      <div className="flex items-center gap-4 bg-slate-950 px-4 py-3">
        <button
          onClick={() => setIsPlaying(!isPlaying)}
          className="flex h-10 w-10 items-center justify-center rounded-full bg-white text-slate-900 transition hover:scale-105 hover:bg-slate-200"
        >
          {isPlaying ? (
            <PauseIcon className="h-5 w-5" />
          ) : (
            <PlayIcon className="h-5 w-5 ml-0.5" />
          )}
        </button>

        <div className="relative h-1 flex-1 overflow-hidden rounded-full bg-slate-800">
            <div
                className={`absolute h-full rounded-full transition-all duration-75 ${mode === 'after' ? 'bg-teal-500' : 'bg-slate-400'}`}
                style={{ width: `${progress}%` }}
            />
        </div>

        <span className="text-xs font-mono text-slate-400">
           00:{Math.floor(progress / 100 * 30).toString().padStart(2, '0')} / 00:30
        </span>
      </div>
    </div>
  );
}
