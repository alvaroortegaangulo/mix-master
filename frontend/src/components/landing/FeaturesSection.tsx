"use client";

import { useState } from "react";
import {
  ArrowUpTrayIcon,
  CpuChipIcon,
  AdjustmentsHorizontalIcon,
  RocketLaunchIcon,
} from "@heroicons/react/24/outline";

export function FeaturesSection({ className }: { className?: string }) {
  const [activeStep, setActiveStep] = useState(0);

  const features = [
    {
      id: 0,
      title: "Intelligent Analysis",
      description:
        "Our AI scans your tracks to understand key, tempo, genre, and instrumentation, creating a custom mixing strategy.",
      icon: ArrowUpTrayIcon,
      colorClass: "text-cyan-400",
      borderClass: "border-cyan-400",
      bgClass: "bg-cyan-950/30",
      placeholderBg: "bg-cyan-900/20",
      borderColor: "border-cyan-500/30",
      videoUrl: "/intelligent_analysis.mp4",
    },
    {
      id: 1,
      title: "Precision Mixing",
      description:
        "Piroola applies surgical EQ, dynamic compression, and spatial enhancements tailored to each stem's role in the mix.",
      icon: CpuChipIcon,
      colorClass: "text-purple-400",
      borderClass: "border-purple-400",
      bgClass: "bg-purple-950/30",
      placeholderBg: "bg-purple-900/20",
      borderColor: "border-purple-500/30",
      videoUrl: "/precision_mixing.mp4",
    },
    {
      id: 2,
      title: "Creative Control",
      description:
        "Adjust the workflow to your needs for optimal sound. Configure your instruments and musical styles to their fullest potential.",
      icon: AdjustmentsHorizontalIcon,
      colorClass: "text-pink-400",
      borderClass: "border-pink-400",
      bgClass: "bg-pink-950/30",
      placeholderBg: "bg-pink-900/20",
      borderColor: "border-pink-500/30",
      videoUrl: "/creative_control.mp4",
    },
    {
      id: 3,
      title: "Mastering Grade Polish",
      description:
        "Finalizes your track with industry-standard loudness matching, stereo widening, and limiter safety.",
      icon: RocketLaunchIcon,
      colorClass: "text-amber-400",
      borderClass: "border-amber-400",
      bgClass: "bg-amber-950/30",
      placeholderBg: "bg-amber-900/20",
      borderColor: "border-amber-500/30",
      videoUrl: "/mastering_grade_polish.mp4",
    },
  ];

  return (
    <section className={`py-24 ${className || 'bg-slate-950'}`} id="features">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="text-center mb-20">
          <div className="inline-block px-3 py-1 mb-6 text-xs font-semibold tracking-wider text-cyan-400 uppercase rounded-full bg-cyan-950/50 border border-cyan-800/50">
            WORKFLOW
          </div>
          <h2 className="text-4xl md:text-5xl font-bold tracking-tight text-white mb-6">
            From your DAW to the <span className="text-cyan-400">World</span>.
          </h2>
          <p className="max-w-3xl mx-auto text-lg md:text-xl text-slate-400 leading-relaxed">
            We have simplified the complex engineering process.
            No infinite menus, only superior sonic results.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-start">
          {/* Left Column: Interactive Menu */}
          <div className="space-y-2 relative">
             {/* Connecting Line */}
             <div className="absolute left-[51px] top-12 bottom-12 w-0.5 bg-slate-800 hidden md:block z-0" />

            {features.map((feature, idx) => {
              const isActive = activeStep === idx;
              return (
                <div
                  key={feature.id}
                  onMouseEnter={() => setActiveStep(idx)}
                  className={`relative z-10 group cursor-pointer rounded-r-2xl border-l-[3px] p-6 transition-all duration-300 ease-in-out ${
                    isActive
                      ? `${feature.borderClass} bg-slate-900/80 shadow-lg`
                      : "border-transparent hover:bg-slate-900/40"
                  }`}
                >
                  <div className="flex items-start gap-6">
                    {/* Icon Bubble */}
                    <div
                      className={`relative shrink-0 flex h-12 w-12 items-center justify-center rounded-full border transition-all duration-300 ${
                         isActive
                         ? `${feature.bgClass} ${feature.borderColor} ${feature.colorClass}`
                         : "bg-slate-900 border-slate-800 text-slate-400 group-hover:border-slate-700 group-hover:text-slate-300"
                      }`}
                    >
                      <feature.icon className="h-6 w-6" />
                    </div>

                    <div className="pt-1">
                      <h3
                        className={`text-lg font-bold mb-2 transition-colors duration-300 ${
                          isActive ? "text-white" : "text-slate-300 group-hover:text-slate-200"
                        }`}
                      >
                        {idx + 1}. {feature.title}
                      </h3>
                      <p
                        className={`text-sm leading-relaxed transition-colors duration-300 ${
                          isActive ? "text-slate-300" : "text-slate-400 group-hover:text-slate-300"
                        }`}
                      >
                        {feature.description}
                      </p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Right Column: Dynamic Video Display */}
          <div className="relative aspect-[4/3] w-full rounded-2xl border border-slate-800 bg-slate-900 overflow-hidden shadow-2xl">
            {features.map((feature, idx) => (
                <div
                    key={feature.id}
                    className={`absolute inset-0 top-10 transition-all duration-500 ease-in-out transform ${
                        activeStep === idx
                            ? 'opacity-100 scale-100 z-10'
                            : 'opacity-0 scale-95 z-0'
                    }`}
                >
                     <video
                        src={feature.videoUrl}
                        autoPlay
                        loop
                        muted
                        playsInline
                        className="w-full h-full object-cover"
                     />
                </div>
            ))}

            {/* Top Bar Decoration for the "App Window" look */}
            <div className="absolute top-0 left-0 right-0 h-10 bg-slate-950 border-b border-slate-800 flex items-center px-4 gap-2 z-20">
                <div className="w-3 h-3 rounded-full bg-slate-700"></div>
                <div className="w-3 h-3 rounded-full bg-slate-700"></div>
                <div className="w-3 h-3 rounded-full bg-slate-700"></div>
                <div className="ml-auto text-[10px] text-slate-400 font-mono">piroola.ai/mix</div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
