"use client";

import { useState, useEffect } from "react";
import { LazyVideo } from "../LazyVideo";
import { useTranslations } from "next-intl";

export function FeaturesSection({ className }: { className?: string }) {
  const [activeStep, setActiveStep] = useState(0);
  const t = useTranslations('FeaturesSection');

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
    const timer = setInterval(() => {
      setActiveStep((prev) => (prev + 1) % features.length);
    }, 7000);
    return () => clearInterval(timer);
  }, [features.length, activeStep]);

  return (
    <section className={`py-8 md:py-12 ${className || 'bg-slate-950'}`} id="features">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div className="text-center mb-8">
          <div className="inline-block px-3 py-1 mb-4 text-xs font-semibold tracking-wider text-teal-400 uppercase rounded-full bg-teal-950/50 border border-teal-800/50">
            {t('workflow')}
          </div>
          <h2 className="text-4xl md:text-5xl font-bold tracking-[-0.02em] leading-[1.05] text-white mb-6" dangerouslySetInnerHTML={{ __html: t.raw('title') }} />
          <p className="max-w-3xl mx-auto text-lg md:text-xl text-slate-300 leading-[1.7]">
            {t('subtitle')}
          </p>
        </div>

        {/* Carousel Container */}
        <div className="relative w-full h-[450px] md:h-auto md:aspect-[21/9] lg:h-[400px] bg-slate-900 rounded-3xl overflow-hidden shadow-2xl border border-slate-800 group">

          {/* Slides */}
          {features.map((feature, idx) => (
            <div
              key={feature.id}
              className={`absolute inset-0 transition-opacity duration-1000 ease-in-out ${
                activeStep === idx ? "opacity-100 z-10" : "opacity-0 z-0"
              }`}
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
              <div className="absolute inset-0 flex flex-col items-center justify-center p-6 md:p-8 text-center z-20">
                {/* Top: Title */}
                <div className="mb-auto mt-4 md:mt-8 animate-in fade-in slide-in-from-top-4 duration-700 delay-300 fill-mode-both">
                   <div className="mb-2">
                      <h3 className="text-3xl md:text-4xl font-bold text-white tracking-[-0.02em] leading-[1.1]">
                        {feature.title}
                      </h3>
                   </div>
                </div>

                {/* Center: Description */}
                <div className="bg-slate-950/60 backdrop-blur-md p-6 md:p-8 rounded-2xl border border-slate-800/50 max-w-3xl animate-in fade-in zoom-in-95 duration-700 delay-500 fill-mode-both shadow-xl">
                  <p className="text-lg md:text-2xl text-slate-100 leading-[1.6] font-medium">
                    {feature.description}
                  </p>
                </div>

                {/* Bottom Spacer to balance layout */}
                <div className="mt-auto mb-8" />
              </div>
            </div>
          ))}

          {/* Navigation Dots */}
          <div className="absolute bottom-6 left-0 right-0 z-30 flex justify-center gap-3">
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
