'use client';

import React, { useState, useEffect } from 'react';
import {
  ChartBarIcon,
  WrenchScrewdriverIcon,
  ArrowsPointingInIcon,
  WifiIcon,
  SparklesIcon
} from '@heroicons/react/24/outline';

const stepsData = [
  {
    title: "Análisis",
    icon: ChartBarIcon,
    colorClass: "text-cyan-400",
    bgClass: "bg-cyan-900/30",
    borderClass: "border-cyan-800",
    desc: "Antes de procesar, es crucial entender la materia prima. Utilizamos espectrómetros, medidores de correlación de fase y medidores LUFS para identificar problemas resonantes, desequilibrios tonales o problemas de fase.",
    tools: ["Analizador de Espectro", "Goniometro", "Medidor LUFS"],
    tip: "Escucha siempre en mono al principio para detectar cancelaciones de fase.",
    image: "/analysis.png"
  },
  {
    title: "Corrección",
    icon: WrenchScrewdriverIcon,
    colorClass: "text-purple-400",
    bgClass: "bg-purple-900/30",
    borderClass: "border-purple-800",
    desc: "La etapa quirúrgica. Aquí eliminamos frecuencias molestas con EQ sustractiva, reducimos el ruido de fondo y corregimos la afinación vocal si es necesario. El objetivo es limpiar antes de embellecer.",
    tools: ["EQ Paramétrico", "De-noiser", "Pitch Correction"],
    tip: "Corta frecuencias graves (High Pass) en instrumentos que no las necesitan para ganar claridad.",
    image: "/correction.png"
  },
  {
    title: "Dinámica",
    icon: ArrowsPointingInIcon,
    colorClass: "text-orange-400",
    bgClass: "bg-orange-900/30",
    borderClass: "border-orange-800",
    desc: "Controlamos el rango dinámico para que la mezcla suene consistente. Usamos compresores para pegar los elementos (glue) y limitadores suaves para controlar los picos rebeldes.",
    tools: ["Compresor VCA", "Compresor Multibanda", "De-esser", "Limiter"],
    tip: "Usa compresión en serie (varios compresores suaves) en lugar de uno solo agresivo para un sonido más natural.",
    image: "/dynamics.png"
  },
  {
    title: "Espacial",
    icon: WifiIcon,
    colorClass: "text-pink-400",
    bgClass: "bg-pink-900/30",
    borderClass: "border-pink-800",
    desc: "Creamos el mundo tridimensional de la canción. Colocamos instrumentos en el campo estéreo (panning) y añadimos profundidad con reverberación (Reverb) y eco (Delay).",
    tools: ["Reverb Plate/Hall", "Stereo Delay", "Stereo Widener", "Pan Pot"],
    tip: "Deja el bombo, bajo y voz principal al centro. Mueve los elementos rítmicos y armónicos a los lados.",
    image: "/spatial.png"
  },
  {
    title: "Mastering",
    icon: SparklesIcon,
    colorClass: "text-yellow-400",
    bgClass: "bg-yellow-900/30",
    borderClass: "border-yellow-800",
    desc: "El pulido final. Buscamos el volumen comercial competitivo, balance tonal global y nos aseguramos de que la canción suene bien en cualquier sistema de reproducción (coche, celular, club).",
    tools: ["Master Bus Comp", "EQ Lineal", "Maximizador", "Dithering"],
    tip: "Compara siempre tu master con canciones de referencia del mismo género (A/B testing).",
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
  const DisplayIcon = data.icon;

  return (
    <div className="w-full max-w-7xl mx-auto py-12 px-4 md:px-8 relative z-10">
      {/* Header */}
      <header className="text-center mb-16 relative z-10 max-w-4xl mx-auto">
        <div className="inline-block mb-4 px-4 py-1.5 rounded-full border border-cyan-500/30 bg-cyan-500/10 text-cyan-300 text-xs font-semibold tracking-wider uppercase">
          Audio Engineering Workflow
        </div>
        <h2 className="text-4xl md:text-6xl font-bold mb-4 bg-clip-text text-transparent bg-gradient-to-r from-white via-cyan-200 to-indigo-200 drop-shadow-lg">
          Pipeline de Mezcla & Masterización
        </h2>
        <p className="text-slate-400 text-lg max-w-2xl mx-auto">
          Explora interactivamente cada etapa del proceso de producción de audio, desde el análisis inicial hasta el pulido final.
        </p>
      </header>

      {/* Main Pipeline Diagram */}
      <div className="w-full relative z-10">

        {/* Steps Container */}
        <div className="flex flex-col lg:flex-row justify-between items-center gap-8 lg:gap-4 mb-16 relative">
          {stepsData.map((step, index) => {
            const isActive = index === currentStep;
            const Icon = step.icon;

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
                      <Icon className={`w-6 h-6 ${step.colorClass}`} />
                    </div>
                  </div>
                  <h3 className={`text-xl font-bold text-white mb-1 transition-colors ${isActive ? step.colorClass : 'group-hover:text-indigo-300'}`}>
                    {index + 1}. {step.title}
                  </h3>
                  <p className="text-sm text-slate-400 line-clamp-2">
                    {step.desc}
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
                <DisplayIcon className={`w-10 h-10 ${data.colorClass}`} />
                <h2 className="text-3xl md:text-4xl font-bold text-white font-display">
                  {data.title}
                </h2>
              </div>
              <p className="text-slate-300 text-lg leading-relaxed mb-6">
                {data.desc}
              </p>

              <div className="bg-slate-800/50 rounded-xl p-5 border border-slate-700">
                <h4 className="text-xs font-bold uppercase tracking-widest text-slate-500 mb-3">
                  Herramientas Clave
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
