"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { ScrollReveal } from "./ScrollReveal";

// Define icons locally to avoid import issues
const CpuChipIcon = (props: React.SVGProps<SVGSVGElement>) => (
  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" {...props}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 3v1.5M4.5 8.25H3m18 0h-1.5M4.5 12H3m18 0h-1.5m-15 3.75H3m18 0h-1.5M8.25 19.5V21M12 3v1.5m0 15V21m3.75-18v1.5m0 15V21m-9-1.5h10.5a2.25 2.25 0 0 0 2.25-2.25V6.75a2.25 2.25 0 0 0-2.25-2.25H6.75A2.25 2.25 0 0 0 4.5 6.75v10.5a2.25 2.25 0 0 0 2.25 2.25Zm.75-12h9v9h-9v-9Z" />
  </svg>
);

const AdjustmentsHorizontalIcon = (props: React.SVGProps<SVGSVGElement>) => (
  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" {...props}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 6h9.75M10.5 6a1.5 1.5 0 1 1-3 0m3 0a1.5 1.5 0 1 0-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 0-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 0-3 0m-9.75 0h9.75" />
  </svg>
);

const ChartBarIcon = (props: React.SVGProps<SVGSVGElement>) => (
  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" {...props}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z" />
  </svg>
);

const GlobeAmericasIcon = (props: React.SVGProps<SVGSVGElement>) => (
  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" {...props}>
    <path strokeLinecap="round" strokeLinejoin="round" d="m6.115 5.19.319 1.913A6 6 0 0 0 8.11 10.36L9.75 12l-.387.775c-.217.433-.132.956.21 1.298l1.348 1.348c.21.21.329.497.329.795v1.089c0 .426.24.815.622 1.006l.153.076c.433.217.956.132 1.298-.21l.723-.723a8.7 8.7 0 0 0 2.288-4.042 1.087 1.087 0 0 0-.358-1.099l-1.33-1.108c-.251-.21-.582-.299-.905-.245l-1.17.195a1.125 1.125 0 0 1-.98-.314l-.295-.295a1.125 1.125 0 0 1 0-1.591l.13-.132a1.125 1.125 0 0 1 1.3-.21l.603.302a.809.809 0 0 0 1.086-1.086L14.25 7.5l1.256-.837a4.5 4.5 0 0 0 1.528-1.732l.146-.292M6.115 5.19A9 9 0 1 0 17.18 4.64M6.115 5.19A8.965 8.965 0 0 1 12 3c1.929 0 3.716.607 5.18 1.64" />
  </svg>
);

export function FeaturesSection({ className }: { className?: string }) {
  const t = useTranslations("FeaturesSection");
  const [currentIndex, setCurrentIndex] = useState(0);
  const [progress, setProgress] = useState(0);
  const titleText = t("title");
  const titlePlain = titleText.replace(/<[^>]+>/g, "");

  // Logical mapping of existing content (S0-S3) to new visual themes
  const features = [
    {
      // Step 0: Precise Correction -> Integration/DAW (Sky)
      // Matches "Integración sin fisuras" in es.json
      id: "correction",
      Icon: AdjustmentsHorizontalIcon,
      imageUrl: "/integration.webp",
      color: "249, 115, 22", // Orange-500
      glowColor: "249, 115, 22",
    },
    {
      // Step 1: Intelligent Analysis -> Neural (Purple)
      // Matches "Inteligencia Sonora" in es.json
      id: "analysis",
      Icon: CpuChipIcon,
      imageUrl: "/neural.webp",
      color: "245, 158, 11", // Amber-500
      glowColor: "245, 158, 11",
    },
    {
      // Step 2: Mastering -> Mastering Grade (Amber)
      // Matches "Pulido de Grado Mastering" in es.json
      id: "mastering",
      Icon: ChartBarIcon,
      imageUrl: "/mastering_grade.webp",
      color: "217, 119, 6", // Amber-600
      glowColor: "217, 119, 6",
    },
    {
      // Step 3: Export -> Ready World (Emerald)
      // Matches "Listo para el Mundo" in es.json
      id: "export",
      Icon: GlobeAmericasIcon,
      imageUrl: "/ready_world.webp",
      color: "234, 88, 12", // Orange-600
      glowColor: "234, 88, 12",
    },
  ];

  const duration = 6000; // 6 seconds per slide

  useEffect(() => {
    let animationFrameId: number;
    let startTime: number | null = null;

    const animate = (timestamp: number) => {
      if (!startTime) startTime = timestamp;
      const elapsed = timestamp - startTime;
      const newProgress = Math.min((elapsed / duration) * 100, 100);

      setProgress(newProgress);

      if (elapsed < duration) {
        animationFrameId = requestAnimationFrame(animate);
        return;
      }

      setCurrentIndex((prev) => (prev + 1) % features.length);
      setProgress(0);
      startTime = null;
      animationFrameId = requestAnimationFrame(animate);
    };

    animationFrameId = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(animationFrameId);
  }, [currentIndex, duration, features.length]);

  const manualSwitch = (index: number) => {
    setCurrentIndex(index);
    setProgress(0);
    // Note: The effect will restart the timer naturally because state changed.
  };

  const currentFeature = features[currentIndex];
  const stats = [
    { label: t("stats.labels.latency"), value: t(`stats.values.${currentIndex}.latency`) },
    { label: t("stats.labels.processing"), value: t(`stats.values.${currentIndex}.processing`) },
    { label: t("stats.labels.status"), value: t(`stats.values.${currentIndex}.status`) },
  ];

  const getGradientColors = () => "from-amber-300 via-amber-400 to-orange-400";

  return (
    <section id="features" className={`relative min-h-screen flex items-center justify-center px-4 py-10 md:py-14 lg:py-16 2xl:py-20 text-white overflow-hidden ${className || 'bg-[#050508]'}`}>
      <div className="absolute inset-0 pointer-events-none z-0">
        <div className="absolute inset-0 bg-[#050508]" />
        <div className="absolute inset-0 grid-landing-diagonal" />
        <div className="absolute inset-0 grid-landing-vignette" />
        <div className="absolute -top-[22%] left-1/2 h-[42%] w-[42%] -translate-x-1/2 rounded-full bg-amber-500/12 blur-[140px]" />
        <div className="absolute top-[6%] left-1/2 h-[28%] w-[28%] -translate-x-1/2 rounded-full bg-orange-400/12 blur-[120px]" />
      </div>
      <div className="relative z-10 max-w-7xl w-full mx-auto">

        {/* Header */}
        <ScrollReveal className="text-left mb-8 max-w-3xl" delay={0.05}>
          <h2
            className="text-3xl md:text-5xl font-black font-['Orbitron'] tracking-wide mb-4 glow-amber metallic-sheen"
            data-text={titlePlain}
          >
            {t.rich("title", {
              daw: (chunks) => (
                <span className={`text-transparent bg-clip-text bg-gradient-to-r ${getGradientColors()} transition-all duration-500`}>
                  {chunks}
                </span>
              ),
              gradient: (chunks) => <span>{chunks}</span>,
            })}
          </h2>
          <p className="text-slate-400 text-sm sm:text-base max-w-2xl font-light leading-relaxed">
            {t("subtitle")}
          </p>
        </ScrollReveal>

        {/* Main Interactive Component */}
        <ScrollReveal
          className="relative w-full md:w-4/5 max-w-6xl mx-auto rounded-[28px] overflow-hidden border border-amber-500/20 bg-slate-950/70 shadow-[0_40px_90px_rgba(0,0,0,0.65)]"
          delay={0.1}
        >

          {/* Image Display Area */}
          <div className="relative h-[260px] sm:h-[160px] md:h-[240px] lg:h-[280px] 2xl:h-[450px] w-full overflow-hidden bg-black group">
            <img
              key={currentFeature.imageUrl}
              src={currentFeature.imageUrl}
              alt={t(`steps.${currentIndex}.title`)}
              className="absolute inset-0 w-full h-full object-cover features-fade-in"
              loading="lazy"
            />

            {/* Overlay Gradients */}
            <div className="absolute inset-0 bg-gradient-to-r from-black/85 via-black/40 to-transparent z-10 pointer-events-none"></div>
            <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-transparent to-transparent z-10 pointer-events-none"></div>

            {/* Scanline Effect */}
            <div className="scanline"></div>

            {/* Floating Content Card */}
            <div className="absolute top-1/2 -translate-y-1/2 left-5 md:left-10 lg:left-12 z-20 w-[88%] sm:w-[70%] md:w-[440px] lg:w-[480px] 2xl:w-[600px]">
              <div className="relative rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-4 md:px-6 md:py-6 shadow-[0_22px_60px_rgba(0,0,0,0.6)] backdrop-blur-xl">
                <div className="absolute inset-0 rounded-2xl ring-1 ring-amber-500/15 pointer-events-none" />
                <div className="relative flex items-center gap-3 mb-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-amber-500/30 bg-amber-500/15 text-amber-300 shadow-[0_0_12px_rgba(251,146,60,0.35)]">
                    <currentFeature.Icon className="h-5 w-5" />
                  </div>
                  <div>
                    <span className="block text-[9px] uppercase tracking-[0.35em] text-amber-300/70">
                      {t(`steps.${currentIndex}.slideLabel`)}
                    </span>
                    <h3
                      className="text-lg md:text-2xl 2xl:text-4xl font-semibold font-['Orbitron'] text-white glow-text"
                      style={{ '--glow-color': currentFeature.glowColor } as React.CSSProperties}
                    >
                      {t(`steps.${currentIndex}.title`)}
                    </h3>
                  </div>
                </div>
                <p className="text-slate-200 text-[11px] md:text-sm 2xl:text-lg leading-relaxed">
                  {t(`steps.${currentIndex}.description`)}
                </p>
                <div className="mt-4 border-t border-white/10 pt-3 grid grid-cols-3 gap-3">
                  {stats.map((stat, index) => (
                    <div key={stat.label} className="space-y-1">
                      <div className="text-[9px] 2xl:text-xs uppercase tracking-[0.22em] text-amber-300/70">
                        {stat.label}
                      </div>
                      <div className={`text-[10px] md:text-xs 2xl:text-sm font-semibold tabular-nums ${index === 2 ? "text-emerald-300" : "text-slate-200"}`}>
                        {stat.value}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Bottom Navigation Bar */}
          <div className="grid grid-cols-2 md:grid-cols-4 bg-slate-950/90 border-t border-white/10">
            {features.map((feature, index) => {
              const isActive = index === currentIndex;
              return (
                <button
                key={index}
                onClick={() => manualSwitch(index)}
                style={{ '--glow-color': feature.glowColor } as React.CSSProperties}
                className={`group relative flex items-center gap-3 px-3 py-3 md:py-4 text-left transition-colors duration-300 border-r border-white/10 last:border-r-0 ${
                  isActive
                    ? "bg-gradient-to-b from-amber-500/15 via-slate-950 to-slate-950 text-white"
                    : "bg-slate-950/60 text-slate-500 hover:text-slate-200"
                }`}
              >
                <span className={`flex h-9 w-9 2xl:h-12 2xl:w-12 items-center justify-center rounded-xl border transition-colors ${
                  isActive
                    ? "border-amber-500/30 bg-amber-500/15 text-amber-300 shadow-[0_0_12px_rgba(251,146,60,0.25)]"
                    : "border-slate-800 bg-slate-900/80 text-slate-500 group-hover:text-amber-300/80"
                }`}>
                  <feature.Icon className="h-4 w-4 2xl:h-6 2xl:w-6" />
                </span>

                <div className="min-w-0">
                  <span className={`block text-[10px] 2xl:text-sm font-semibold uppercase tracking-wider font-['Orbitron'] ${
                    isActive ? "text-amber-200" : "text-slate-400"
                  }`}>
                    {t(`steps.${index}.tabTitle`)}
                  </span>
                  <span className={`block text-[9px] 2xl:text-xs truncate ${
                    isActive ? "text-slate-300" : "text-slate-600"
                  }`}>
                    {t(`steps.${index}.title`)}
                  </span>
                </div>

                {/* Progress Bar for this tab */}
                <div className="absolute bottom-0 left-0 h-[2px] w-full bg-slate-800/70">
                  <div
                    className="h-full w-0 transition-none"
                    style={{
                      backgroundColor: `rgb(${feature.color})`,
                      width: isActive ? `${progress}%` : "0%",
                    }}
                  />
                </div>
                </button>
              );
            })}
          </div>
        </ScrollReveal>
      </div>

    </section>
  );
}
