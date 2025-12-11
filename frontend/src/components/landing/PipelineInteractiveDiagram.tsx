'use client';

import React, { useState } from 'react';

const stepsData = [
  {
    title: "Analysis",
    icon: "/icon_analysis.png",
    colorClass: "text-cyan-400",
    bgClass: "bg-cyan-900/30",
    borderClass: "border-cyan-800",
    shortDesc: "Frequency, phase, and dynamic range diagnosis.",
    desc: "Before processing, understanding the source material is crucial. We use spectrum analyzers, phase correlation meters, and LUFS meters to identify resonant issues, tonal imbalances, or phase problems.",
    tools: ["Spectrum Analyzer", "Goniometer", "LUFS Meter"],
    tip: "Always listen in mono initially to detect phase cancellations.",
    image: "/analysis.png"
  },
  {
    title: "Correction",
    icon: "/icon_correction.png",
    colorClass: "text-purple-400",
    bgClass: "bg-purple-900/30",
    borderClass: "border-purple-800",
    shortDesc: "Cleaning, subtractive EQ, and noise reduction.",
    desc: "The surgical stage. We remove problematic frequencies with subtractive EQ, reduce background noise, and correct vocal pitch if necessary. The goal is to clean before enhancing.",
    tools: ["Parametric EQ", "De-noiser", "Pitch Correction"],
    tip: "Cut low frequencies (High Pass) on instruments that don't need them to gain clarity.",
    image: "/correction.png"
  },
  {
    title: "Dynamics",
    icon: "/icon_dynamics.png",
    colorClass: "text-orange-400",
    bgClass: "bg-orange-900/30",
    borderClass: "border-orange-800",
    shortDesc: "Transient control, compression, and balance.",
    desc: "We control the dynamic range for a consistent mix. We use compressors to glue elements together and soft limiters to tame unruly peaks.",
    tools: ["VCA Compressor", "Multiband Compressor", "De-esser", "Limiter"],
    tip: "Use serial compression (multiple gentle compressors) instead of a single aggressive one for a more natural sound.",
    image: "/dynamics.png"
  },
  {
    title: "Spatial",
    icon: "/icon_spatial.png",
    colorClass: "text-pink-400",
    bgClass: "bg-pink-900/30",
    borderClass: "border-pink-800",
    shortDesc: "Depth, reverberation, and stereo image.",
    desc: "We create the song's 3D world. We place instruments in the stereo field (panning) and add depth with reverb and delay.",
    tools: ["Reverb Plate/Hall", "Stereo Delay", "Stereo Widener", "Pan Pot"],
    tip: "Keep the kick, bass, and lead vocal in the center. Move rhythmic and harmonic elements to the sides.",
    image: "/spatial.png"
  },
  {
    title: "Mastering",
    icon: "/icon_mastering.png",
    colorClass: "text-yellow-400",
    bgClass: "bg-yellow-900/30",
    borderClass: "border-yellow-800",
    shortDesc: "Loudness, final cohesion, and delivery formats.",
    desc: "The final polish. We aim for competitive commercial loudness, global tonal balance, and ensure the song translates well to any playback system (car, phone, club).",
    tools: ["Master Bus Comp", "Linear EQ", "Maximizer", "Dithering"],
    tip: "Always compare your master with reference songs of the same genre (A/B testing).",
    image: "/mastering.png"
  }
];

export default function PipelineInteractiveDiagram() {
  const [currentStep, setCurrentStep] = useState(0);
  const [isFadingOut, setIsFadingOut] = useState(false);
  // Separate state for display data to handle transition delay
  const [displayStep, setDisplayStep] = useState(0);

  // Handle step selection with animation timing
  const handleStepClick = (index: number) => {
    if (index === currentStep) return;

    // Start fade out
    setIsFadingOut(true);
    setCurrentStep(index);

    // Update displayed content after fade out
    setTimeout(() => {
      setDisplayStep(index);
      setIsFadingOut(false);
    }, 400); // 400ms delay matches the transition duration
  };

  const data = stepsData[displayStep];

  return (
    <div className="w-full max-w-7xl mx-auto py-12 px-4 md:px-8 relative z-10">
      {/* Header */}
      <header className="text-left mb-16 relative z-10 max-w-4xl">
        <div className="inline-block mb-4 px-4 py-1.5 rounded-full border border-cyan-500/30 bg-cyan-500/10 text-cyan-300 text-xs font-semibold tracking-wider uppercase">
          Audio Engineering Workflow
        </div>
        <h2 className="text-4xl md:text-6xl font-bold mb-4 bg-clip-text text-transparent bg-gradient-to-r from-white via-cyan-200 to-indigo-200 drop-shadow-lg">
          Mixing & Mastering Pipeline
        </h2>
        <p className="text-slate-400 text-lg max-w-2xl">
          Interactively explore each stage of the audio production process, from initial analysis to final polishing.
        </p>
      </header>

      {/* Main Pipeline Diagram */}
      <div className="w-full relative z-10">

        {/* Steps Container */}
        <div className="flex flex-col lg:flex-row justify-between items-center gap-8 lg:gap-4 mb-16 relative">
          {stepsData.map((step, index) => {
            const isActive = index === currentStep;

            return (
              <div
                key={index}
                className="relative group w-full lg:w-1/5"
                onClick={() => handleStepClick(index)}
              >
                <div
                  className={`step-card cursor-pointer rounded-2xl p-3 h-full flex flex-col transition-all duration-400 ease-[cubic-bezier(0.4,0,0.2,1)] backdrop-blur-xl border border-white/10
                    ${isActive
                      ? 'border-cyan-400 bg-slate-800/70 shadow-[0_0_30px_rgba(34,211,238,0.15)] opacity-100'
                      : 'bg-slate-800/40 opacity-70 hover:-translate-y-2 hover:scale-105 hover:border-indigo-500/50 hover:shadow-xl'
                    }`}
                >
                  <div className="relative h-40 w-full overflow-hidden rounded-xl mb-4">
                    <img
                      src={step.image}
                      alt={step.title}
                      className="object-cover w-full h-full transform transition duration-700 group-hover:scale-110"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-slate-900 to-transparent opacity-60"></div>
                    <div className="absolute bottom-2 left-2 flex items-center gap-2">
                      <img
                        src={step.icon}
                        alt=""
                        className="w-6 h-6 object-contain"
                      />
                    </div>
                  </div>
                  <h3 className={`text-xl font-bold text-white mb-1 transition-colors ${isActive ? step.colorClass : 'group-hover:text-indigo-300'}`}>
                    {index + 1}. {step.title}
                  </h3>
                  <p className="text-sm text-slate-400 line-clamp-2">
                    {step.shortDesc}
                  </p>
                </div>
                {/* Connector */}
                {index < stepsData.length - 1 && (
                  <div className="connector-line hidden lg:block"></div>
                )}
              </div>
            );
          })}
        </div>

        {/* Detail Inspector Panel */}
        <div className="relative w-full bg-slate-900/50 border border-slate-700/50 rounded-3xl p-6 md:p-10 backdrop-blur-xl overflow-hidden min-h-[300px]">
          {/* Decorative Background Elements */}
          <div className="absolute top-0 right-0 w-64 h-64 bg-cyan-500/10 rounded-full blur-3xl -mr-20 -mt-20 pointer-events-none"></div>
          <div className="absolute bottom-0 left-0 w-64 h-64 bg-indigo-500/10 rounded-full blur-3xl -ml-20 -mb-20 pointer-events-none"></div>

          {/* Content Area */}
          <div
            className={`relative z-10 grid grid-cols-1 md:grid-cols-2 gap-8 items-center transition-all duration-500 ease-in-out
              ${isFadingOut
                ? 'opacity-0 translate-y-5 pointer-events-none absolute'
                : 'opacity-100 translate-y-0 relative'
              }`}
          >
            {/* Left: Text Info */}
            <div>
              <div className="flex items-center gap-3 mb-4">
                <img
                  src={data.icon}
                  alt=""
                  className="w-10 h-10 object-contain"
                />
                <h2 className="text-3xl md:text-4xl font-bold text-white font-display">
                  {data.title}
                </h2>
              </div>
              <p className="text-slate-300 text-lg leading-relaxed mb-6">
                {data.desc}
              </p>

              <div className="bg-slate-800/50 rounded-xl p-5 border border-slate-700">
                <h4 className="text-xs font-bold uppercase tracking-widest text-slate-500 mb-3">
                  Key Tools
                </h4>
                <div className="flex flex-wrap gap-2">
                  {data.tools.map((tool, idx) => (
                    <span
                      key={idx}
                      className={`px-3 py-1 ${data.bgClass} text-xs md:text-sm rounded-full border ${data.borderClass} text-white/90`}
                    >
                      {tool}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            {/* Right: Visual Context */}
            <div className="h-full min-h-[250px] relative rounded-2xl overflow-hidden border border-slate-700/50 shadow-2xl">
                <img
                  src={data.image}
                  className="absolute inset-0 w-full h-full object-cover"
                  alt={data.title}
                />
                <div className="absolute inset-0 bg-gradient-to-t from-slate-900 via-transparent to-transparent opacity-80"></div>
                <div className="absolute bottom-4 left-4 right-4">
                  <div className="text-xs text-white/70 font-mono bg-black/50 inline-block px-2 py-1 rounded mb-1">
                    PRO TIP
                  </div>
                  <p className="text-sm font-medium text-white italic">
                    "{data.tip}"
                  </p>
                </div>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
