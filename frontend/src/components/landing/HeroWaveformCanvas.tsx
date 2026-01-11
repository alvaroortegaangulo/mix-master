"use client";

import { useEffect, useRef } from "react";

type HeroWaveformCanvasProps = {
  className?: string;
};

export function HeroWaveformCanvas({ className = "h-full w-full" }: HeroWaveformCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const frameRef = useRef<number | null>(null);
  const runningRef = useRef(false);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let width = 0;
    let height = 0;
    let dpr = window.devicePixelRatio || 1;

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      width = Math.max(1, rect.width);
      height = Math.max(1, rect.height);
      dpr = window.devicePixelRatio || 1;
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const bands = [
      { amplitude: 18, frequency: 0.006, speed: 0.9, y: 0.45, color: "rgba(34,211,238,0.35)", phase: 0.2 },
      { amplitude: 14, frequency: 0.008, speed: 1.15, y: 0.5, color: "rgba(139,92,246,0.28)", phase: 1.1 },
      { amplitude: 10, frequency: 0.012, speed: 0.75, y: 0.55, color: "rgba(45,212,191,0.22)", phase: 2.4 }
    ];

    const draw = (time: number) => {
      if (!runningRef.current) return;
      const t = time * 0.001;
      ctx.clearRect(0, 0, width, height);
      ctx.lineWidth = 1.35;
      ctx.lineJoin = "round";
      ctx.lineCap = "round";

      for (const band of bands) {
        ctx.beginPath();
        const baseY = height * band.y;
        const step = 6;

        for (let x = 0; x <= width; x += step) {
          const wave = Math.sin(x * band.frequency + t * band.speed + band.phase) * band.amplitude;
          const shimmer = Math.sin(x * band.frequency * 2.1 - t * band.speed * 1.4) * band.amplitude * 0.35;
          const y = baseY + wave + shimmer;
          if (x === 0) {
            ctx.moveTo(x, y);
          } else {
            ctx.lineTo(x, y);
          }
        }

        ctx.shadowColor = band.color;
        ctx.shadowBlur = 14;
        ctx.strokeStyle = band.color;
        ctx.stroke();
      }

      ctx.shadowBlur = 0;

      frameRef.current = window.requestAnimationFrame(draw);
    };

    const start = () => {
      if (runningRef.current) return;
      runningRef.current = true;
      resize();
      frameRef.current = window.requestAnimationFrame(draw);
    };

    const stop = () => {
      if (!runningRef.current) return;
      runningRef.current = false;
      if (frameRef.current) {
        window.cancelAnimationFrame(frameRef.current);
        frameRef.current = null;
      }
    };

    const isVisible = () => {
      const rect = canvas.getBoundingClientRect();
      return rect.bottom > 0 && rect.top < window.innerHeight;
    };

    let observer: IntersectionObserver | null = null;
    if (typeof IntersectionObserver !== "undefined") {
      observer = new IntersectionObserver(
        ([entry]) => {
          if (entry.isIntersecting) {
            start();
          } else {
            stop();
          }
        },
        { threshold: 0.1 }
      );
      observer.observe(canvas);
      if (isVisible()) {
        start();
      }
    } else {
      start();
    }

    window.addEventListener("resize", resize);

    return () => {
      window.removeEventListener("resize", resize);
      if (observer) observer.disconnect();
      stop();
    };
  }, []);

  return <canvas ref={canvasRef} className={className} aria-hidden="true" />;
}
