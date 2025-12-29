"use client";

import { useEffect, useRef, useState } from "react";
import type { PointerEvent } from "react";
import { useTranslations } from "next-intl";
import { ScrollReveal } from "./ScrollReveal";

export function TechSpecsSection({ className }: { className?: string }) {
    const t = useTranslations('TechSpecsSection');
    const title = t('title');
    const marqueeRef = useRef<HTMLDivElement>(null);
    const dragStartXRef = useRef(0);
    const dragStartScrollLeftRef = useRef(0);
    const isDraggingRef = useRef(false);
    const [isDragging, setIsDragging] = useState(false);
    const specs = [
      { value: "96 kHz", label: t("internalProcessing") },
      { value: "32-bit", label: t("floatDepth") },
      { value: "12", label: t("processingStages") },
      { value: "0 ms", label: t("latency") },
      { value: "-14 LUFS", label: "OBJETIVO LOUDNESS" },
      { value: "-1.0 dBTP", label: "TRUE PEAK MAX" },
      { value: "110 dB", label: "SNR" },
      { value: "0.01%", label: "THD+N" },
      { value: "20-20 kHz", label: "RESPUESTA FREQ" },
      { value: "0.02 deg", label: "ERROR DE FASE" },
      { value: "0.90", label: "CORRELACION ESTEREO" },
      { value: "4096", label: "TAPS EQ LINEAL" },
      { value: "4x", label: "OVERSAMPLING" },
      { value: "0", label: "EVENTOS CLIPPING" },
      { value: "0.2 dB", label: "TOLERANCIA RMS" },
      { value: "-90 dBFS", label: "PISO DE RUIDO" },
    ];
    const valueColors = [
      "text-cyan-300",
      "text-teal-300",
      "text-emerald-300",
      "text-violet-300",
      "text-purple-300",
      "text-fuchsia-300",
      "text-orange-300",
      "text-amber-300",
      "text-rose-300",
      "text-cyan-400",
      "text-emerald-400",
      "text-violet-400",
      "text-orange-400",
      "text-amber-400",
      "text-teal-400",
      "text-pink-400",
    ];
    const marqueeSpecs = [...specs, ...specs];

    useEffect(() => {
      const marquee = marqueeRef.current;
      if (!marquee) return;

      const durationMs = 44000;
      let frameId: number | null = null;
      let lastTime = performance.now();

      const setStartPosition = () => {
        const halfWidth = marquee.scrollWidth / 2;
        if (halfWidth > 0) {
          marquee.scrollLeft = halfWidth;
        }
      };

      setStartPosition();

      const step = (time: number) => {
        const delta = time - lastTime;
        lastTime = time;

        if (!isDraggingRef.current) {
          const halfWidth = marquee.scrollWidth / 2;
          if (halfWidth > 0) {
            const move = (halfWidth * delta) / durationMs;
            marquee.scrollLeft -= move;
            if (marquee.scrollLeft <= 0) {
              marquee.scrollLeft += halfWidth;
            } else if (marquee.scrollLeft >= halfWidth) {
              marquee.scrollLeft -= halfWidth;
            }
          }
        }

        frameId = requestAnimationFrame(step);
      };

      frameId = requestAnimationFrame(step);

      let resizeObserver: ResizeObserver | null = null;
      if (typeof ResizeObserver !== "undefined") {
        resizeObserver = new ResizeObserver(() => {
          if (!isDraggingRef.current) {
            setStartPosition();
          }
        });
        resizeObserver.observe(marquee);
      }

      return () => {
        if (frameId) {
          cancelAnimationFrame(frameId);
        }
        resizeObserver?.disconnect();
      };
    }, []);

    const normalizeScroll = () => {
      const marquee = marqueeRef.current;
      if (!marquee) return;
      const halfWidth = marquee.scrollWidth / 2;
      if (halfWidth <= 0) return;
      if (marquee.scrollLeft <= 0) {
        marquee.scrollLeft += halfWidth;
      } else if (marquee.scrollLeft >= halfWidth) {
        marquee.scrollLeft -= halfWidth;
      }
    };

    const handlePointerDown = (event: PointerEvent<HTMLDivElement>) => {
      if (event.pointerType === "mouse" && event.button !== 0) return;
      const marquee = marqueeRef.current;
      if (!marquee) return;
      marquee.setPointerCapture(event.pointerId);
      isDraggingRef.current = true;
      setIsDragging(true);
      dragStartXRef.current = event.clientX;
      dragStartScrollLeftRef.current = marquee.scrollLeft;
    };

    const handlePointerMove = (event: PointerEvent<HTMLDivElement>) => {
      if (!isDraggingRef.current) return;
      const marquee = marqueeRef.current;
      if (!marquee) return;
      event.preventDefault();
      const delta = event.clientX - dragStartXRef.current;
      marquee.scrollLeft = dragStartScrollLeftRef.current - delta;
    };

    const handlePointerUp = (event: PointerEvent<HTMLDivElement>) => {
      if (!isDraggingRef.current) return;
      const marquee = marqueeRef.current;
      if (!marquee) return;
      isDraggingRef.current = false;
      setIsDragging(false);
      if (marquee.hasPointerCapture(event.pointerId)) {
        marquee.releasePointerCapture(event.pointerId);
      }
      normalizeScroll();
    };

    return (
      <section className={`py-10 md:py-14 lg:py-16 2xl:py-20 relative overflow-hidden ${className || 'bg-slate-950'}`}>
        <div className="absolute top-0 left-0 h-full w-full overflow-hidden pointer-events-none z-0">
          <div className="absolute -top-[20%] -left-[10%] h-[50%] w-[50%] rounded-full bg-teal-500/10 blur-[120px]" />
          <div className="absolute top-[40%] -right-[10%] h-[60%] w-[60%] rounded-full bg-violet-600/10 blur-[120px]" />
        </div>
        <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <ScrollReveal delay={0.05}>
            <h2
              className="text-3xl md:text-5xl font-bold mb-8 font-['Orbitron'] text-transparent bg-clip-text bg-gradient-to-r from-emerald-300 via-emerald-400 to-emerald-500 glow-emerald metallic-sheen"
              data-text={title}
            >
              {title}
            </h2>
          </ScrollReveal>

          <ScrollReveal delay={0.1}>
            <div className="relative max-w-5xl mx-auto">
              <div className="pointer-events-none absolute inset-y-0 left-0 w-16 bg-gradient-to-r from-slate-950 to-transparent" />
              <div className="pointer-events-none absolute inset-y-0 right-0 w-16 bg-gradient-to-l from-slate-950 to-transparent" />
              <div
                ref={marqueeRef}
                className={`overflow-hidden select-none ${isDragging ? "cursor-grabbing" : "cursor-grab"}`}
                onPointerDown={handlePointerDown}
                onPointerMove={handlePointerMove}
                onPointerUp={handlePointerUp}
                onPointerCancel={handlePointerUp}
                style={{ touchAction: "pan-y" }}
              >
                <div className="flex w-max gap-3 py-2">
                  {marqueeSpecs.map((spec, index) => (
                    <div
                      key={`${spec.label}-${index}`}
                      aria-hidden={index >= specs.length ? "true" : undefined}
                      className="flex items-center gap-3 rounded-full border border-slate-800/80 bg-slate-900/60 px-4 py-2 shadow-sm"
                    >
                      <span className={`text-sm sm:text-base font-semibold tabular-nums ${valueColors[index % valueColors.length]}`}>
                        {spec.value}
                      </span>
                      <span className="text-[10px] sm:text-xs font-medium uppercase tracking-widest text-slate-300">
                        {spec.label}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </ScrollReveal>
        </div>
      </section>
    );
  }
