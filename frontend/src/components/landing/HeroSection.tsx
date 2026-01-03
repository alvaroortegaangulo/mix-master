"use client";

import { useEffect, useRef } from "react";
import Image from "next/image";
import { PlayCircleIcon, StarIcon } from "@heroicons/react/24/solid";
import { useTranslations } from 'next-intl';
import { Link } from '../../i18n/routing';
import { ScrollReveal } from "./ScrollReveal";

export function HeroSection({ onTryIt }: { onTryIt: () => void }) {
  const t = useTranslations('HeroSection');
  const perfectedByAI = t('perfectedByAI');
  const waveformRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = waveformRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let frameId = 0;
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

      frameId = window.requestAnimationFrame(draw);
    };

    resize();
    window.addEventListener("resize", resize);
    frameId = window.requestAnimationFrame(draw);

    return () => {
      window.removeEventListener("resize", resize);
      if (frameId) {
        window.cancelAnimationFrame(frameId);
      }
    };
  }, []);

  return (
    <section className="relative flex min-h-[70vh] lg:min-h-[75vh] 2xl:min-h-[85vh] flex-col items-center justify-center overflow-hidden bg-slate-950 px-4 text-center py-8 md:py-10 lg:py-16 2xl:py-20">
      {/* Background gradients/blobs */}
      <div className="absolute top-0 left-0 h-full w-full overflow-hidden pointer-events-none z-0">
        <div className="absolute -top-[20%] -left-[10%] h-[50%] w-[50%] rounded-full bg-teal-500/10 blur-[120px]" />
        <div className="absolute top-[40%] -right-[10%] h-[60%] w-[60%] rounded-full bg-violet-600/10 blur-[120px]" />
      </div>

      <div className="relative z-10 max-w-5xl space-y-2 sm:space-y-3 lg:space-y-4 flex flex-col items-center">
        {/* Logo */}
        <ScrollReveal className="mx-auto flex justify-center mb-1">
          <Image
            src="/logo.webp"
            alt="Piroola logo"
            width={96}
            height={96}
            sizes="96px"
            className="h-14 w-14 sm:h-16 sm:w-16"
            priority
          />
        </ScrollReveal>

        {/* Main Heading - LCP Element (No entrance animation to minimize render delay) */}
        <h1 className="flex flex-col text-4xl font-extrabold tracking-[-0.02em] sm:text-5xl lg:text-6xl 2xl:text-7xl gap-1 font-['Orbitron']">
          <span className="text-white leading-[0.95]">
            {t('studioSound')}
          </span>
          <span
            className="bg-gradient-to-r from-teal-400 to-violet-500 bg-clip-text text-transparent leading-[0.95] metallic-sheen"
            data-text={perfectedByAI}
          >
            {perfectedByAI}
          </span>
        </h1>

        <ScrollReveal delay={0.1}>
          <p className="mx-auto max-w-3xl text-xs font-light leading-[1.5] text-slate-300 sm:text-sm lg:text-base">
            {t('description')}
          </p>
        </ScrollReveal>

        <ScrollReveal
          className="beta-badge flex items-center gap-2 px-3 py-1.5 text-[9px] font-semibold uppercase tracking-[0.18em] text-violet-100 backdrop-blur-sm leading-none sm:text-[10px]"
          delay={0.15}
        >
          <span className="beta-dot" aria-hidden="true" />
          <span>{t('alertConstruction')}</span>
        </ScrollReveal>

        <ScrollReveal
          className="flex flex-col items-center gap-3 sm:gap-4 sm:flex-row sm:justify-center mt-2 sm:mt-3"
          delay={0.2}
        >
          {/* Button 1: Mezclar mi Track */}
          <button
            onClick={onTryIt}
            className="group relative inline-flex items-center justify-center gap-2 overflow-hidden rounded-full bg-teal-400 px-4 py-2 text-xs font-bold text-slate-950 transition-all hover:bg-teal-300 hover:scale-105 focus:outline-none focus:ring-4 focus:ring-teal-500/30 sm:px-5 sm:py-2.5 sm:text-sm glow-pulse"
          >
            {/* Simple Circle Icon */}
            <svg
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
              className="stroke-current stroke-2"
              aria-hidden="true"
              focusable="false"
            >
              <circle cx="12" cy="12" r="9" />
            </svg>
            <span>{t('mixMyTracks')}</span>
          </button>

          {/* Button 2: Escuchar Demos */}
          <Link
            href="/examples"
            className="group relative inline-flex items-center justify-center gap-2 overflow-hidden rounded-full bg-slate-800/80 px-4 py-2 text-xs font-semibold text-white transition-all hover:bg-slate-700 hover:scale-105 focus:outline-none focus:ring-4 focus:ring-violet-500/30 border border-slate-700 sm:px-5 sm:py-2.5 sm:text-sm"
          >
            <PlayCircleIcon className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-white" aria-hidden="true" />
            <span>{t('listenToDemos')}</span>
          </Link>
        </ScrollReveal>

        <style jsx>{`
          .glow-pulse {
            box-shadow: 0 0 16px rgba(45, 212, 191, 0.55), 0 0 32px rgba(45, 212, 191, 0.35);
            animation: pulse-glow 2.6s ease-in-out infinite;
          }

          @keyframes pulse-glow {
            0%,
            100% {
              box-shadow: 0 0 14px rgba(45, 212, 191, 0.45), 0 0 26px rgba(45, 212, 191, 0.25);
            }
            50% {
              box-shadow: 0 0 20px rgba(45, 212, 191, 0.7), 0 0 40px rgba(45, 212, 191, 0.4);
            }
          }

          .hero-faq-pop {
            animation: hero-faq-pop 0.75s cubic-bezier(0.22, 1.2, 0.32, 1) 0.2s both;
          }

          @keyframes hero-faq-pop {
            0% {
              transform: scale(0);
              opacity: 0;
            }
            65% {
              transform: scale(1.06);
              opacity: 1;
            }
            85% {
              transform: scale(0.98);
            }
            100% {
              transform: scale(1);
            }
          }
        `}</style>

        {/* Rating Section */}
        <ScrollReveal
          className="flex items-center gap-2 text-[11px] font-medium text-slate-300 mt-1 sm:mt-2 sm:text-xs"
          delay={0.25}
        >
          <div className="flex items-center gap-1 text-amber-300">
            <StarIcon className="h-3.5 w-3.5 sm:h-4 sm:w-4" aria-hidden="true" />
            <span>{t('rating')}</span>
          </div>
          <span className="text-slate-400">&bull;</span>
          <span>{t('tracksMastered')}</span>
        </ScrollReveal>
      </div>

      <div className="absolute inset-0 opacity-[0.55] pointer-events-none mix-blend-screen z-[1]">
        <canvas
          ref={waveformRef}
          className="h-full w-full"
          aria-hidden="true"
        />
      </div>

      <div className="absolute bottom-4 right-4 sm:bottom-6 sm:right-6 z-30">
        <div className="hero-faq-pop group w-[min(90vw,340px)] origin-bottom-right">
          <div className="relative rounded-2xl border border-slate-800 bg-slate-950/90 p-4 text-left shadow-2xl shadow-black/40 backdrop-blur">
            <div className="flex items-start gap-2">
              <span className="mt-0.5 inline-flex h-5 w-5 items-center justify-center rounded-full border border-emerald-400/70 bg-emerald-500/15 text-[11px] font-bold text-emerald-200">
                i
              </span>
              <p className="text-sm font-semibold text-white">
                ¿Cuál es la diferencia entre Mezcla y Masterización?
              </p>
            </div>
            <div className="overflow-hidden opacity-0 max-h-0 mt-0 transition-all duration-300 group-hover:opacity-100 group-hover:max-h-64 group-hover:mt-3">
              <p className="text-[11px] text-slate-300 leading-relaxed">
                La mezcla implica equilibrar pistas individuales (stems) para formar una canción, incluyendo ajustar niveles, paneo y añadir efectos. La masterización es el paso final que pule la canción mezclada, asegurando que suene consistente y lo suficientemente fuerte para el lanzamiento comercial.
              </p>
              <Link
                href="/faq"
                className="mt-3 inline-flex items-center justify-center rounded-full border border-emerald-400/40 bg-emerald-500/10 px-3 py-1.5 text-[11px] font-semibold text-emerald-200 transition hover:bg-emerald-500/20"
              >
                Ir a FAQ
              </Link>
            </div>
            <div className="absolute left-1/2 -bottom-2 h-0 w-0 -translate-x-1/2 border-l-[7px] border-r-[7px] border-t-[9px] border-l-transparent border-r-transparent border-t-slate-950/90 pointer-events-none" />
          </div>
        </div>
      </div>
    </section>
  );
}
