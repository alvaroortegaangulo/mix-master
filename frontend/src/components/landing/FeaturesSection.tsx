"use client";

import { useState, useEffect, useRef } from "react";
import Image from "next/image";
import { useTranslations } from "next-intl";
import {
  PuzzlePieceIcon,
  ArrowRightIcon,
  ArrowRightStartOnRectangleIcon,
  SparklesIcon,
  AdjustmentsVerticalIcon,
  GlobeAmericasIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
} from "@heroicons/react/24/outline";

interface Feature {
  id: number;
  tabStep: string;
  tabTitle: string;
  slideLabel: string;
  title: string;
  description: string;
  image: string;
  color: "teal" | "purple" | "blue" | "orange";
  Icon: React.ElementType;
}

export function FeaturesSection({ className }: { className?: string }) {
  const [activeStep, setActiveStep] = useState(0);
  const t = useTranslations("FeaturesSection");
  const autoAdvanceRef = useRef<NodeJS.Timeout | null>(null);

  // Data Definition
  const features: Feature[] = [
    {
      id: 0,
      tabStep: t("steps.0.tabStep"),
      tabTitle: t("steps.0.tabTitle"),
      slideLabel: t("steps.0.slideLabel"),
      title: t("steps.0.title"),
      description: t("steps.0.description"),
      image: "/master_interface.webp",
      color: "teal",
      Icon: ArrowRightStartOnRectangleIcon,
    },
    {
      id: 1,
      tabStep: t("steps.1.tabStep"),
      tabTitle: t("steps.1.tabTitle"),
      slideLabel: t("steps.1.slideLabel"),
      title: t("steps.1.title"),
      description: t("steps.1.description"),
      image: "/intelligent_analysis.webp",
      color: "purple",
      Icon: SparklesIcon,
    },
    {
      id: 2,
      tabStep: t("steps.2.tabStep"),
      tabTitle: t("steps.2.tabTitle"),
      slideLabel: t("steps.2.slideLabel"),
      title: t("steps.2.title"),
      description: t("steps.2.description"),
      image: "/mastering_grade_polish.webp",
      color: "blue",
      Icon: AdjustmentsVerticalIcon,
    },
    {
      id: 3,
      tabStep: t("steps.3.tabStep"),
      tabTitle: t("steps.3.tabTitle"),
      slideLabel: t("steps.3.slideLabel"),
      title: t("steps.3.title"),
      description: t("steps.3.description"),
      image: "/creative_control.webp",
      color: "orange",
      Icon: GlobeAmericasIcon,
    },
  ];

  const resetTimer = () => {
    if (autoAdvanceRef.current) {
      clearInterval(autoAdvanceRef.current);
    }
    autoAdvanceRef.current = setInterval(() => {
      setActiveStep((prev) => (prev + 1) % features.length);
    }, 6000);
  };

  useEffect(() => {
    resetTimer();
    return () => {
      if (autoAdvanceRef.current) clearInterval(autoAdvanceRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [t]); // Added t as dependency to update text on locale change

  const handleStepChange = (index: number) => {
    setActiveStep(index);
    resetTimer();
  };

  const nextSlide = () => {
    setActiveStep((prev) => (prev + 1) % features.length);
    resetTimer();
  };

  const prevSlide = () => {
    setActiveStep((prev) => (prev - 1 + features.length) % features.length);
    resetTimer();
  };

  const activeFeature = features[activeStep];

  // Color mappings
  const colorMap = {
    teal: {
      text: "text-teal-400",
      bg: "bg-teal-500",
      groupHoverText: "group-hover:text-teal-400",
      groupHoverIcon: "group-hover:text-teal-400",
    },
    purple: {
      text: "text-purple-400",
      bg: "bg-purple-500",
      groupHoverText: "group-hover:text-purple-400",
      groupHoverIcon: "group-hover:text-purple-400",
    },
    blue: {
      text: "text-blue-400",
      bg: "bg-blue-500",
      groupHoverText: "group-hover:text-blue-400",
      groupHoverIcon: "group-hover:text-blue-400",
    },
    orange: {
      text: "text-orange-400",
      bg: "bg-orange-500",
      groupHoverText: "group-hover:text-orange-400",
      groupHoverIcon: "group-hover:text-orange-400",
    },
  };

  return (
    <section className={`py-8 md:py-12 ${className}`} id="features">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">

        {/* Section Header */}
        <div className="text-center mb-12 space-y-4 relative z-10">
          <h2 className="text-4xl md:text-5xl font-bold font-display text-white">
            {t.rich("title", {
              gradient: (chunks) => <span className="text-transparent bg-clip-text bg-gradient-to-r from-teal-400 to-blue-500">{chunks}</span>
            })}
          </h2>
          <p className="text-slate-400 max-w-2xl mx-auto text-lg">
            {t("subtitle")}
          </p>
        </div>

        {/* Main Card Container */}
        <div
          className="relative w-full aspect-[16/10] md:aspect-[21/9] lg:h-[600px] rounded-3xl overflow-hidden group shadow-2xl border border-white/5 bg-slate-950"
          id="slider-root"
        >
          {/* Background Images Layer */}
          <div className="absolute inset-0 bg-black" id="bg-container">
            {features.map((feature, idx) => (
              <div
                key={feature.id}
                className={`absolute inset-0 w-full h-full transition-opacity duration-1000 ${
                  activeStep === idx ? "opacity-100 z-10" : "opacity-0 z-0"
                }`}
              >
                 <Image
                    src={feature.image}
                    alt={feature.title}
                    fill
                    className={`object-cover ${activeStep === idx ? 'animate-zoom-slow' : ''}`}
                    priority={idx === 0}
                 />
              </div>
            ))}
          </div>

          {/* Vignette & Gradient Overlays */}
          <div className="absolute inset-0 bg-gradient-to-t from-[#0B0F19] via-transparent to-transparent opacity-90 z-10 pointer-events-none"></div>
          <div className="absolute inset-0 bg-gradient-to-r from-[#0B0F19]/80 via-transparent to-transparent opacity-60 z-10 pointer-events-none"></div>

          {/* Content Overlay (Text) */}
          <div className="absolute inset-0 flex flex-col justify-end md:justify-center px-6 md:px-16 pb-32 md:pb-0 z-20 pointer-events-none">
            <div
              className="glass-overlay p-6 md:p-10 rounded-2xl max-w-xl transform transition-all duration-500 pointer-events-auto backdrop-blur-md bg-slate-950/40 border border-white/10"
              key={activeStep}
              // Key forces re-mount for animation
            >
              <div className={`flex items-center gap-3 mb-4 ${colorMap[activeFeature.color].text}`}>
                <PuzzlePieceIcon className="w-6 h-6" />
                <span className="text-xs font-bold uppercase tracking-wider">
                  {activeFeature.slideLabel}
                </span>
              </div>
              <h3 className="text-2xl md:text-3xl font-display font-bold text-white mb-3 leading-tight animate-in fade-in slide-in-from-bottom-2 duration-500">
                {activeFeature.title}
              </h3>
              <p className="text-slate-300 text-sm md:text-lg leading-relaxed animate-in fade-in slide-in-from-bottom-3 duration-500 delay-100">
                {activeFeature.description}
              </p>
              <div className="mt-6 animate-in fade-in slide-in-from-bottom-4 duration-500 delay-200">
                <button className="flex items-center gap-2 text-white font-semibold hover:text-teal-400 transition-colors group/btn text-sm md:text-base">
                  Saber más
                  <ArrowRightIcon className="w-4 h-4 group-hover/btn:translate-x-1 transition-transform" />
                </button>
              </div>
            </div>
          </div>

          {/* Navigation Controls (Bottom Tabs) */}
          <div className="absolute bottom-0 left-0 w-full z-30 bg-[#0B0F19]/80 backdrop-blur-md border-t border-white/5">
            <div className="flex flex-col md:flex-row divide-y md:divide-y-0 md:divide-x divide-white/10 h-auto md:h-20">
              {features.map((feature, idx) => {
                 const isActive = activeStep === idx;
                 const colors = colorMap[feature.color];

                 return (
                  <button
                    key={feature.id}
                    className="nav-tab flex-1 flex items-center justify-between px-6 py-3 md:py-0 hover:bg-white/5 transition-colors text-left group relative outline-none focus:bg-white/5"
                    onClick={() => handleStepChange(idx)}
                  >
                    <div className="flex flex-col gap-1 z-10">
                      <span
                        className={`text-[10px] font-mono uppercase tracking-widest transition-colors ${
                           isActive ? colors.text : "text-slate-500 " + colors.groupHoverText
                        }`}
                      >
                        {feature.tabStep}
                      </span>
                      <span
                        className={`text-sm font-bold transition-colors ${
                          isActive ? "text-white" : "text-slate-300 group-hover:text-white"
                        }`}
                      >
                        {feature.tabTitle}
                      </span>
                    </div>

                    <feature.Icon
                        className={`w-6 h-6 transition-all duration-300 md:block hidden ${
                            isActive
                            ? `opacity-100 ${colors.text}`
                            : `opacity-0 group-hover:opacity-100 text-slate-600 ${colors.groupHoverIcon}`
                        }`}
                    />

                    {/* Progress Bar Background */}
                    <div className="absolute bottom-0 left-0 h-1 bg-white/10 w-full">
                      <div
                        className={`progress-fill h-full ${colors.bg}`}
                        style={{
                          width: isActive ? "100%" : "0%",
                          transition: isActive ? "width 6000ms linear" : "none",
                        }}
                      ></div>
                    </div>
                  </button>
                 )
              })}
            </div>
          </div>

          {/* Arrow Controls */}
          <button
            className="absolute top-1/2 left-4 -translate-y-1/2 z-30 p-3 rounded-full bg-black/20 hover:bg-black/50 backdrop-blur text-white/50 hover:text-white border border-white/5 transition-all hidden md:flex"
            onClick={prevSlide}
            aria-label="Previous Slide"
          >
            <ChevronLeftIcon className="w-6 h-6" />
          </button>
          <button
            className="absolute top-1/2 right-4 -translate-y-1/2 z-30 p-3 rounded-full bg-black/20 hover:bg-black/50 backdrop-blur text-white/50 hover:text-white border border-white/5 transition-all hidden md:flex"
            onClick={nextSlide}
            aria-label="Next Slide"
          >
            <ChevronRightIcon className="w-6 h-6" />
          </button>
        </div>
      </div>
    </section>
  );
}
