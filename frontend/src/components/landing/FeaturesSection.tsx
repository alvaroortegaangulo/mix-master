"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";

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

  // Logical mapping of existing content (S0-S3) to new visual themes
  const features = [
    {
      // Step 0: Precise Correction -> Integration/DAW (Sky)
      // Matches "Integración sin fisuras" in es.json
      id: "correction",
      Icon: AdjustmentsHorizontalIcon,
      videoUrl: "/integration.mp4",
      color: "14, 165, 233", // Sky-500
      twColor: "text-sky-400",
      btnColor: "text-sky-400",
      glowColor: "14, 165, 233",
    },
    {
      // Step 1: Intelligent Analysis -> Neural (Purple)
      // Matches "Inteligencia Sonora" in es.json
      id: "analysis",
      Icon: CpuChipIcon,
      videoUrl: "/neural.mp4",
      color: "168, 85, 247", // Purple-500
      twColor: "text-purple-400",
      btnColor: "text-purple-400",
      glowColor: "168, 85, 247",
    },
    {
      // Step 2: Mastering -> Mastering Grade (Amber)
      // Matches "Pulido de Grado Mastering" in es.json
      id: "mastering",
      Icon: ChartBarIcon,
      videoUrl: "/mastering_grade.mp4",
      color: "245, 158, 11", // Amber-500
      twColor: "text-amber-400",
      btnColor: "text-amber-400",
      glowColor: "245, 158, 11",
    },
    {
      // Step 3: Export -> Ready World (Emerald)
      // Matches "Listo para el Mundo" in es.json
      id: "export",
      Icon: GlobeAmericasIcon,
      videoUrl: "/ready_world.mp4",
      color: "16, 185, 129", // Emerald-500
      twColor: "text-emerald-400",
      btnColor: "text-emerald-400",
      glowColor: "16, 185, 129",
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

  const getGradientColors = (index: number) => {
    switch (index) {
      case 0: return "from-teal-400 to-cyan-400";      // Integration/Correction
      case 1: return "from-purple-400 to-fuchsia-400"; // Neural
      case 2: return "from-amber-400 to-orange-400";   // Mastering
      case 3: return "from-emerald-400 to-teal-400";   // Export
      default: return "from-slate-400 to-white";
    }
  };

  return (
    <section id="features" className={`min-h-screen flex items-center justify-center p-4 bg-slate-950 text-white ${className || ''}`}>
      <div className="max-w-7xl w-full mx-auto">

        {/* Header */}
        <div className="text-center mb-10 space-y-4">
          <h2 className="text-4xl md:text-6xl font-black font-['Orbitron'] tracking-wide">
            {t.rich("title", {
              gradient: (chunks) => (
                <span className={`text-transparent bg-clip-text bg-gradient-to-r ${getGradientColors(currentIndex)} transition-all duration-500`}>
                  {chunks}
                </span>
              ),
            })}
          </h2>
          <p className="text-slate-400 text-lg md:text-xl max-w-2xl mx-auto font-light leading-relaxed font-['Orbitron']">
            {t("subtitle")}
          </p>
        </div>

        {/* Main Interactive Component */}
        <div className="relative w-full rounded-2xl overflow-hidden shadow-[0_0_50px_rgba(0,0,0,0.5)] border border-slate-800 bg-slate-900">

          {/* Video Display Area */}
          <div className="relative h-[400px] md:h-[550px] w-full overflow-hidden bg-black group">
             {/* Background Video */}
            <video
              key={currentFeature.videoUrl} // Key forces re-render/fade for new source
              src={currentFeature.videoUrl}
              autoPlay
              muted
              loop
              playsInline
              className="absolute inset-0 w-full h-full object-cover"
              style={{ animation: 'fadeIn 1s ease-out forwards' }}
            />

            <style jsx>{`
              @keyframes fadeIn {
                from { opacity: 0; transform: scale(1.05); }
                to { opacity: 0.6; transform: scale(1); } /* 0.6 opacity to blend with bg */
              }
            `}</style>

            {/* Overlay Gradients */}
            <div className="absolute inset-0 bg-gradient-to-r from-slate-950/90 via-slate-950/40 to-transparent z-10 pointer-events-none"></div>
            <div className="absolute inset-0 bg-gradient-to-t from-slate-950 via-transparent to-transparent z-10 pointer-events-none"></div>

            {/* Neural Scanline Effect (Only for Neural/Analysis step) */}
            {currentIndex === 1 && (
              <div className="scanline"></div>
            )}

            {/* Floating Content Card */}
            <div className="absolute top-1/2 -translate-y-1/2 left-6 md:left-16 z-20 max-w-lg w-full pr-4">
              <div className="glass-card p-8 rounded-2xl floating transition-all duration-500 hover:scale-[1.02]">
                <div className="flex items-center gap-3 mb-4">
                  <span className={`text-3xl animate-pulse ${currentFeature.twColor}`}>
                    <currentFeature.Icon className="w-8 h-8" />
                  </span>
                  <h3
                    className={`text-2xl md:text-3xl font-bold font-['Orbitron'] ${currentFeature.twColor} glow-text`}
                    style={{ '--glow-color': currentFeature.glowColor } as React.CSSProperties}
                  >
                    {t(`steps.${currentIndex}.title`)}
                  </h3>
                </div>
                <p className="text-slate-300 text-base md:text-lg leading-relaxed">
                  {t(`steps.${currentIndex}.description`)}
                </p>
              </div>
            </div>
          </div>

          {/* Bottom Navigation Bar */}
          <div className="grid grid-cols-2 md:grid-cols-4 bg-slate-950 border-t border-slate-800">
            {features.map((feature, index) => (
              <button
                key={index}
                onClick={() => manualSwitch(index)}
                style={{ '--glow-color': feature.glowColor } as React.CSSProperties}
                className={`relative p-4 md:p-6 flex flex-col md:flex-row items-center justify-center md:justify-start gap-3 transition-all duration-300 group hover:bg-slate-900 border-r border-slate-800 last:border-r-0 ${
                  index === currentIndex
                    ? "nav-item-active" // Uses global css class for gradient & border
                    : "text-slate-500 hover:text-slate-300"
                }`}
              >
                <span className={`transition-colors group-hover:scale-110 ${
                   index === currentIndex ? feature.twColor : "text-slate-600 group-hover:text-slate-400"
                }`}>
                  <feature.Icon className="w-6 h-6 md:w-8 md:h-8" />
                </span>

                <div className="text-center md:text-left">
                  <span className={`block text-xs md:text-sm font-bold uppercase tracking-wider font-['Orbitron'] ${
                     index === currentIndex ? "text-white" : "text-slate-500"
                  }`}>
                    {t(`steps.${index}.title`)}
                  </span>
                </div>

                {/* Progress Bar for this tab */}
                <div className="absolute bottom-0 left-0 h-[2px] w-full bg-slate-800">
                  <div
                    className="h-full w-0 transition-none"
                    style={{
                      backgroundColor: `rgb(${feature.color})`,
                      width: index === currentIndex ? `${progress}%` : "0%",
                    }}
                  />
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
