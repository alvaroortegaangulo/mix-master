"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";

type CanvasWaveformProps = {
  audioBuffer: AudioBuffer | null;
  peaksData?: number[] | null;
  currentTime: number;
  duration: number;
  onSeek: (time: number) => void;
  height?: number;
  waveColor?: string;
  progressColor?: string;
  cursorColor?: string;
  analyser?: AnalyserNode | null;
  isPlaying?: boolean;
};

export const CanvasWaveform: React.FC<CanvasWaveformProps> = ({
  audioBuffer,
  peaksData,
  currentTime,
  duration,
  onSeek,
  height = 300,
  waveColor = "#334155",
  progressColor = "#f59e0b", // Amber-500
  cursorColor = "#fbbf24",
  analyser = null,
  isPlaying = false,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const requestRef = useRef<number | null>(null);
  const [peaks, setPeaks] = useState<number[]>([]);
  const [canvasSize, setCanvasSize] = useState({ width: 0, height: 0 });

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

  // Calculate peaks when audioBuffer changes (unless provided)
  useEffect(() => {
    if (peaksData && peaksData.length > 0) {
      setPeaks(peaksData);
      return;
    }

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
  }, [audioBuffer, peaksData]);

  const setupCanvas = useCallback((ctx: CanvasRenderingContext2D, width: number, height: number) => {
    const dpr = window.devicePixelRatio || 1;
    const canvas = canvasRef.current;
    if (!canvas) return;

    // Ensure canvas dimensions match display size * pixel ratio
    if (canvas.width !== width * dpr || canvas.height !== height * dpr) {
      canvas.width = width * dpr;
      canvas.height = height * dpr;
    }

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    // Clear handled by caller usually, but setting fillStyle helpful
  }, []);

  const drawStaticWaveform = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const { width, height: hProp } = canvasSize;
    if (width === 0 || hProp === 0) return;

    setupCanvas(ctx, width, hProp);
    ctx.clearRect(0, 0, width, hProp);

    const midY = hProp / 2;

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
    const maxAmplitude = hProp / 2;
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
        ctx.fillStyle = isPlayed ? progressColor : waveColor;

        // Draw bar
        const barWidth = Math.max(1, step - barGap);

        const h = Math.max(1, val * 2);
        const y = midY - (h / 2);

        // Using round rect if available
        if ((ctx as any).roundRect) {
             ctx.beginPath();
             (ctx as any).roundRect(x, y, barWidth, h, 2);
             ctx.fill();
        } else {
             ctx.fillRect(x, y, barWidth, h);
        }
    }
  }, [canvasSize, peaks, currentTime, duration, waveColor, progressColor, setupCanvas]);

  const drawSpectrum = useCallback(() => {
    if (!analyser || !canvasRef.current) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const { width, height } = canvasSize;
    if (width === 0 || height === 0) return;

    setupCanvas(ctx, width, height);
    ctx.clearRect(0, 0, width, height);

    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    analyser.getByteFrequencyData(dataArray);

    const paddingX = 0;
    const availableWidth = width - paddingX * 2;
    const barWidth = 3; // Slightly wider for spectrum
    const gap = 1;
    const step = barWidth + gap;
    const maxBars = Math.floor(availableWidth / step);

    const midY = height / 2;
    const topMaxHeight = height * 0.45;
    const reflectFactor = 0.5;

    // Center line
    ctx.strokeStyle = "rgba(255,255,255,0.1)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(paddingX, midY + 0.5);
    ctx.lineTo(width - paddingX, midY + 0.5);
    ctx.stroke();

    const usableBins = Math.floor(bufferLength * 0.7); // Focus on lower/mid freqs
    const binsPerBar = Math.floor(usableBins / maxBars) || 1;

    // Progress based coloring: Amber vs White
    const progress = duration > 0 ? currentTime / duration : 0;

    // Unplayed color: White (as requested)
    const unplayedColor = "#ffffff";
    const unplayedReflection = "rgba(255, 255, 255, 0.3)";
    // Played color: Amber
    const playedColor = progressColor; // default #f59e0b
    const playedReflection = "rgba(245, 158, 11, 0.4)";

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
        // Boost low values for better visuals
        const boostedNorm = Math.pow(norm, 0.8);

        const barHeightTop = Math.max(1, boostedNorm * topMaxHeight);
        const barHeightBottom = barHeightTop * reflectFactor;
        const x = paddingX + i * step;

        // Color logic
        const barProgress = maxBars > 1 ? i / (maxBars - 1) : 0;
        const isPlayed = barProgress <= progress;

        ctx.fillStyle = isPlayed ? playedColor : unplayedColor;
        ctx.fillRect(x, midY - barHeightTop, barWidth, barHeightTop);

        ctx.fillStyle = isPlayed ? playedReflection : unplayedReflection;
        ctx.fillRect(x, midY + 1, barWidth, barHeightBottom);
    }

    requestRef.current = requestAnimationFrame(drawSpectrum);
  }, [analyser, canvasSize, currentTime, duration, progressColor, setupCanvas]);

  // Main Effect Loop
  useEffect(() => {
    if (isPlaying && analyser) {
      drawSpectrum();
    } else {
      if (requestRef.current) {
        cancelAnimationFrame(requestRef.current);
        requestRef.current = null;
      }
      drawStaticWaveform();
    }

    return () => {
      if (requestRef.current) {
        cancelAnimationFrame(requestRef.current);
        requestRef.current = null;
      }
    };
  }, [isPlaying, analyser, drawSpectrum, drawStaticWaveform]);

  // Redraw static when params change and not playing
  useEffect(() => {
      if (!isPlaying) {
          drawStaticWaveform();
      }
  }, [peaks, currentTime, canvasSize, isPlaying, drawStaticWaveform]);


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
