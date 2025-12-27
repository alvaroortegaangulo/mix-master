"use client";

import { useState, useEffect, useRef } from "react";
import type { PointerEvent } from "react";
import { LazyVideo } from "../LazyVideo";
import { useTranslations } from "next-intl";

export function FeaturesSection({ className }: { className?: string }) {
  const [activeStep, setActiveStep] = useState(0);
  const [dragOffset, setDragOffset] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const dragStartXRef = useRef(0);
  const dragDeltaXRef = useRef(0);
  const isDraggingRef = useRef(false);
  const t = useTranslations('FeaturesSection');
  const dragThreshold = 40;

  const features = [
    {
      id: 0,
      title: t('steps.0.title'),
      description: t('steps.0.description'),
      videoUrl: "/intelligent_analysis.webm",
      poster: "/analysis.webp",
    },
    {
      id: 1,
      title: t('steps.1.title'),
      description: t('steps.1.description'),
      videoUrl: "/precision_mixing.webm",
      poster: "/processing.webp",
    },
    {
      id: 2,
      title: t('steps.2.title'),
      description: t('steps.2.description'),
      videoUrl: "/creative_control.webm",
      poster: "/space_depth.webp",
    },
    {
      id: 3,
      title: t('steps.3.title'),
      description: t('steps.3.description'),
      videoUrl: "/mastering_grade_polish.webm",
      poster: "/mastering.webp",
    },
  ];

  useEffect(() => {
    if (isDragging) return;
    const timer = setInterval(() => {
      setActiveStep((prev) => (prev + 1) % features.length);
    }, 7000);
    return () => clearInterval(timer);
  }, [features.length, activeStep, isDragging]);

  const handlePointerDown = (event: PointerEvent<HTMLDivElement>) => {
    if (event.pointerType === "mouse" && event.button !== 0) return;
    const target = event.target as HTMLElement;
    if (target.closest("button")) return;
    isDraggingRef.current = true;
    dragStartXRef.current = event.clientX;
    dragDeltaXRef.current = 0;
    setIsDragging(true);
    setDragOffset(0);
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const handlePointerMove = (event: PointerEvent<HTMLDivElement>) => {
    if (!isDraggingRef.current) return;
    event.preventDefault();
    const delta = event.clientX - dragStartXRef.current;
    dragDeltaXRef.current = delta;
    setDragOffset(delta);
  };

  const handlePointerEnd = (event: PointerEvent<HTMLDivElement>) => {
    if (!isDraggingRef.current) return;
    isDraggingRef.current = false;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    const deltaX = dragDeltaXRef.current;
    dragDeltaXRef.current = 0;
    setDragOffset(0);
    setIsDragging(false);
    if (deltaX > dragThreshold) {
      setActiveStep((prev) => (prev - 1 + features.length) % features.length);
      return;
    }
    if (deltaX < -dragThreshold) {
      setActiveStep((prev) => (prev + 1) % features.length);
    }
  };

  return (
    <section className={`py-6 md:py-8 lg:py-10 2xl:py-12 ${className || 'bg-slate-950'}`} id="features">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div className="text-center mb-6">
          <div className="inline-block px-3 py-1 mb-3 text-xs font-semibold tracking-wider text-teal-400 uppercase rounded-full bg-teal-950/50 border border-teal-800/50">
            {t('workflow')}
          </div>
          <h2 className="text-2xl sm:text-3xl 2xl:text-4xl font-bold tracking-[-0.02em] leading-[1.05] text-white mb-3" dangerouslySetInnerHTML={{ __html: t.raw('title') }} />
          <p className="max-w-3xl mx-auto text-sm sm:text-base text-slate-300 leading-[1.55]">
            {t('subtitle')}
          </p>
        </div>

        {/* Carousel Container */}
        <div
          className="relative w-full h-[320px] sm:h-[360px] md:h-auto md:aspect-[21/9] lg:h-[340px] 2xl:h-[400px] bg-slate-900 rounded-3xl overflow-hidden shadow-2xl border border-slate-800 group cursor-grab active:cursor-grabbing"
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerEnd}
          onPointerCancel={handlePointerEnd}
          style={{ touchAction: "pan-y" }}
        >

          {/* Slides */}
          {features.map((feature, idx) => {
            const prevIndex = (activeStep - 1 + features.length) % features.length;
            const nextIndex = (activeStep + 1) % features.length;
            const isActive = activeStep === idx;
            const isPrev = prevIndex === idx;
            const isNext = nextIndex === idx;
            const isVisible = isActive || (isDragging && (isPrev || isNext));
            const baseOffset = isPrev ? -100 : isNext ? 100 : 0;
            const translate = isDragging
              ? `translateX(calc(${dragOffset}px + ${baseOffset}%))`
              : "translateX(0)";

            return (
              <div
                key={feature.id}
                className={`absolute inset-0 ease-in-out ${isVisible ? "opacity-100" : "opacity-0"} ${
                  isActive ? "z-20" : "z-10"
                }`}
                style={{
                  transform: translate,
                  transition: isDragging ? "none" : "transform 300ms ease, opacity 500ms ease",
                }}
              >
              {/* Background Video */}
              <div className="absolute inset-0">
                <LazyVideo
                  src={feature.videoUrl}
                  poster={feature.poster}
                  className="w-full h-full object-cover opacity-60"
                  isActive={activeStep === idx}
                />
                {/* Gradient Overlay for better text readability */}
                <div className="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/40 to-slate-950/80" />
              </div>

              {/* Content Overlay */}
              <div className="absolute inset-0 flex flex-col items-center justify-center p-4 md:p-6 text-center z-20">
                {/* Top: Title */}
                <div className="mb-auto mt-3 md:mt-6 animate-in fade-in slide-in-from-top-4 duration-700 delay-300 fill-mode-both">
                   <div className="mb-2">
                      <h3 className="text-xl sm:text-2xl lg:text-3xl font-bold text-white tracking-[-0.02em] leading-[1.1]">
                        {feature.title}
                      </h3>
                   </div>
                </div>

                {/* Center: Description */}
                <div className="bg-slate-950/60 backdrop-blur-md p-4 md:p-6 rounded-2xl border border-slate-800/50 max-w-3xl animate-in fade-in zoom-in-95 duration-700 delay-500 fill-mode-both shadow-xl">
                  <p className="text-xs sm:text-sm lg:text-base 2xl:text-lg text-slate-100 leading-[1.6] font-medium">
                    {feature.description}
                  </p>
                </div>

                {/* Bottom Spacer to balance layout */}
                <div className="mt-auto mb-6" />
              </div>
              </div>
            );
          })}

          {/* Navigation Arrows */}
          <button
            type="button"
            onClick={() => setActiveStep((prev) => (prev - 1 + features.length) % features.length)}
            className="absolute left-3 top-1/2 z-30 -translate-y-1/2 h-11 w-14 sm:h-12 sm:w-16 rounded-full border border-slate-700/60 bg-slate-900/60 text-2xl sm:text-3xl font-light leading-none text-white/70 backdrop-blur transition hover:bg-slate-800/70 hover:text-white hover:scale-105 focus-visible:text-white shadow-[0_8px_18px_rgba(15,23,42,0.35)]"
            aria-label="Previous slide"
          >
            <span aria-hidden="true">&lt;</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveStep((prev) => (prev + 1) % features.length)}
            className="absolute right-3 top-1/2 z-30 -translate-y-1/2 h-11 w-14 sm:h-12 sm:w-16 rounded-full border border-slate-700/60 bg-slate-900/60 text-2xl sm:text-3xl font-light leading-none text-white/70 backdrop-blur transition hover:bg-slate-800/70 hover:text-white hover:scale-105 focus-visible:text-white shadow-[0_8px_18px_rgba(15,23,42,0.35)]"
            aria-label="Next slide"
          >
            <span aria-hidden="true">&gt;</span>
          </button>

          {/* Navigation Dots */}
          <div className="absolute bottom-4 left-0 right-0 z-30 flex justify-center gap-2">
            {features.map((_, idx) => (
              <button
                key={idx}
                onClick={() => setActiveStep(idx)}
                className={`h-2.5 rounded-full transition-all duration-300 ${
                  activeStep === idx
                    ? "w-8 bg-teal-400"
                    : "w-2.5 bg-slate-600 hover:bg-slate-500"
                }`}
                aria-label={`Go to slide ${idx + 1}`}
                aria-current={activeStep === idx ? "true" : undefined}
              />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
