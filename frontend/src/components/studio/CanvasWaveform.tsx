"use client";

import React, { useEffect, useRef, useState } from "react";

type CanvasWaveformProps = {
  audioBuffer: AudioBuffer | null;
  currentTime: number;
  duration: number;
  onSeek: (time: number) => void;
  height?: number;
  waveColor?: string;
  progressColor?: string;
  cursorColor?: string;
};

export const CanvasWaveform: React.FC<CanvasWaveformProps> = ({
  audioBuffer,
  currentTime,
  duration,
  onSeek,
  height = 300,
  waveColor = "#334155",
  progressColor = "#10b981",
  cursorColor = "#fbbf24",
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [peaks, setPeaks] = useState<number[]>([]);

  // Calculate peaks when audioBuffer changes
  useEffect(() => {
    if (!audioBuffer) {
      setPeaks([]);
      return;
    }

    const channelData = audioBuffer.getChannelData(0);
    const totalSamples = channelData.length;
    // We want enough resolution for drawing, but not too heavy.
    // 1000 bars is usually enough for a desktop view.
    const desiredBars = 1000;
    const samplesPerBar = Math.floor(totalSamples / desiredBars);

    if (samplesPerBar < 1) {
        // Audio is too short or weird
        setPeaks([]);
        return;
    }

    const newPeaks: number[] = [];

    // Simple RMS or Peak calculation
    for (let i = 0; i < desiredBars; i++) {
      const start = i * samplesPerBar;
      let end = start + samplesPerBar;
      if (end > totalSamples) end = totalSamples;

      let sum = 0;
      for (let j = start; j < end; j++) {
        const val = channelData[j];
        sum += val * val;
      }
      const count = end - start;
      const rms = count > 0 ? Math.sqrt(sum / count) : 0;
      newPeaks.push(rms);
    }

    setPeaks(newPeaks);

  }, [audioBuffer]);

  // Draw the waveform
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();

    // Ensure canvas dimensions match display size * pixel ratio
    if (canvas.width !== rect.width * dpr || canvas.height !== rect.height * dpr) {
        canvas.width = rect.width * dpr;
        canvas.height = rect.height * dpr;
    }

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, rect.width, rect.height);

    const width = rect.width;
    const heightProp = rect.height;

    // Center line
    const midY = heightProp / 2;

    if (!peaks.length) {
       ctx.strokeStyle = waveColor;
       ctx.beginPath();
       ctx.moveTo(0, midY);
       ctx.lineTo(width, midY);
       ctx.stroke();
       return;
    }

    // Drawing parameters
    const barGap = 1;
    const totalBars = peaks.length;

    // Normalized progress
    const progress = duration > 0 ? currentTime / duration : 0;
    const progressX = width * progress;

    // We draw mirrored bars
    const maxAmplitude = heightProp / 2;
    // Normalize peaks to maximize vertical usage (optional)
    const maxPeak = Math.max(...peaks, 0.01);
    const scale = 1 / maxPeak;

    const step = width / totalBars;

    ctx.lineWidth = Math.max(1, step - 0.5); // Ensure visible

    for (let i = 0; i < totalBars; i++) {
        const x = i * step;
        const val = peaks[i] * scale * maxAmplitude * 0.9; // 0.9 margin

        // Determine color
        const isPlayed = x <= progressX;
        ctx.strokeStyle = isPlayed ? progressColor : waveColor;
        ctx.fillStyle = isPlayed ? progressColor : waveColor;

        // Draw bar
        const barWidth = Math.max(1, step - barGap);

        // Top bar
        ctx.beginPath();

        // We draw a single rounded rectangle for the whole bar (top+bottom)
        const h = val * 2;
        const y = midY - val;

        // Using round rect if available
        if ((ctx as any).roundRect) {
             ctx.beginPath();
             (ctx as any).roundRect(x, y, barWidth, h, 2);
             ctx.fill();
        } else {
             ctx.fillRect(x, y, barWidth, h);
        }
    }

  }, [peaks, currentTime, duration, waveColor, progressColor, cursorColor]);

  const handleClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
      if (!duration) return;
      const rect = e.currentTarget.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const pct = Math.max(0, Math.min(1, x / rect.width));
      onSeek(pct * duration);
  };

  return (
    <canvas
        ref={canvasRef}
        style={{ width: "100%", height: "100%" }}
        onClick={handleClick}
        className="cursor-pointer"
    />
  );
};
