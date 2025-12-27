"use client";

import { useEffect, useRef, useState } from "react";
import type { PointerEvent } from "react";
import { useTranslations } from "next-intl";

export function TechSpecsSection({ className }: { className?: string }) {
    const t = useTranslations('TechSpecsSection');
    const marqueeRef = useRef<HTMLDivElement>(null);
    const dragStartXRef = useRef(0);
    const dragStartScrollLeftRef = useRef(0);
    const isDraggingRef = useRef(false);
    const [isDragging, setIsDragging] = useState(false);
    const specs = [
      { value: "96k", label: t("internalProcessing") },
      { value: "32-bit", label: t("floatDepth") },
      { value: "12+", label: t("processingStages") },
      { value: "0s", label: t("latency") },
      { value: "-14 LUFS", label: "OBJETIVO STREAMING" },
      { value: "-1.0 dBTP", label: "TRUE PEAK SEGURO" },
      { value: "WIDE", label: "IMAGEN ESTEREO" },
      { value: "12-16 dB", label: "RANGO DINAMICO" },
      { value: "AI-MATCH", label: "BALANCE TONAL" },
      { value: "+3.2 dB", label: "PUNCH TRANSIENTE" },
      { value: "OK", label: "PHASE CHECK" },
      { value: "-90 dB", label: "NOISE FLOOR" },
      { value: "DEPTH", label: "PROFUNDIDAD 3D" },
      { value: "SOFT", label: "SATURACION MUSICAL" },
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
      <section className={`py-8 md:py-10 lg:py-12 overflow-hidden ${className || 'bg-slate-900'}`}>
        <div className="max-w-6xl mx-auto px-4 text-center">
          <h2 className="text-2xl sm:text-3xl font-bold text-white mb-6">{t('title')}</h2>

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
                    <span className="text-sm sm:text-base font-semibold text-teal-300 tabular-nums">
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
        </div>
      </section>
    );
  }
