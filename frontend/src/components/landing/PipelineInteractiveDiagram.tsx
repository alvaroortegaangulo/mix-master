'use client';

import React, { useState } from 'react';
import {
  ChartBarIcon,
  AdjustmentsHorizontalIcon,
  ArrowsPointingInIcon,
  WifiIcon,
  SparklesIcon,
  WrenchScrewdriverIcon,
  SpeakerWaveIcon,
  GlobeAltIcon,
  CpuChipIcon
} from '@heroicons/react/24/outline';
import {
  ChartBarIcon as ChartBarSolid,
  AdjustmentsHorizontalIcon as AdjustmentsSolid,
  ArrowsPointingInIcon as ArrowsSolid,
  WifiIcon as WifiSolid,
  SparklesIcon as SparklesSolid
} from '@heroicons/react/24/solid';

const steps = [
  {
    id: 1,
    title: "Análisis",
    subtitle: "Diagnóstico de frecuencias, fase y rango dinámico.",
    description: "Antes de procesar, escuchamos y analizamos. Identificamos problemas de fase, resonancias molestas y desequilibrios tonales.",
    tools: ["Analizador de Espectro", "Medidor de Fase", "Medidor LUFS", "Detección de Tonalidad"],
    proTip: "Un buen análisis ahorra horas de corrección. Si la grabación es mala, mejor volver a grabar.",
    icon: ChartBarIcon,
    solidIcon: ChartBarSolid,
    color: "cyan",
    borderColor: "border-cyan-400",
    textColor: "text-cyan-400",
    bgColor: "bg-cyan-400/10",
    gradient: "from-cyan-500/20 to-blue-600/20"
  },
  {
    id: 2,
    title: "Corrección",
    subtitle: "Limpieza, EQ sustractiva y reducción de ruido.",
    description: "Eliminamos lo que no sirve. Filtramos frecuencias graves innecesarias (Low Cut), atenuamos resonancias y limpiamos ruidos de fondo.",
    tools: ["EQ Paramétrico", "De-noise", "De-click", "Filtros HPF/LPF"],
    proTip: "Corta antes de añadir. Eliminar frecuencias 'barrosas' da claridad instantánea.",
    icon: WrenchScrewdriverIcon, // Using Wrench as a proxy for the sliders/tools
    solidIcon: AdjustmentsSolid,
    color: "indigo",
    borderColor: "border-indigo-400",
    textColor: "text-indigo-400",
    bgColor: "bg-indigo-400/10",
    gradient: "from-indigo-500/20 to-purple-600/20"
  },
  {
    id: 3,
    title: "Dinámica",
    subtitle: "Control de transitorios, compresión y balance.",
    description: "Controlamos el rango dinámico para que la mezcla suene consistente. Usamos compresores para dar 'pegada' (punch) y limitadores suaves para controlar picos.",
    tools: ["Compresor VCA", "Compresor Multibanda", "De-esser", "Limiter"],
    proTip: "Usa compresión en serie: varios compresores haciendo poco trabajo suenan más naturales que uno solo trabajando mucho.",
    icon: SpeakerWaveIcon, // Represents dynamics/volume
    solidIcon: ArrowsSolid,
    color: "amber",
    borderColor: "border-amber-400",
    textColor: "text-amber-400",
    bgColor: "bg-amber-400/10",
    gradient: "from-amber-500/20 to-orange-600/20"
  },
  {
    id: 4,
    title: "Espacial",
    subtitle: "Profundidad, reverberación e imagen estéreo.",
    description: "Creamos el mundo tridimensional de la canción. Colocamos instrumentos en el campo estéreo (panning) y añadimos profundidad con reverberación (Reverb) y eco (Delay).",
    tools: ["Reverb Plate/Hall", "Stereo Delay", "Stereo Widener", "Pan Pot"],
    proTip: "Deja el bombo, bajo y voz principal al centro. Mueve los elementos rítmicos y armónicos a los lados.",
    icon: WifiIcon, // Represents waves/space
    solidIcon: WifiSolid,
    color: "fuchsia",
    borderColor: "border-fuchsia-400",
    textColor: "text-fuchsia-400",
    bgColor: "bg-fuchsia-400/10",
    gradient: "from-fuchsia-500/20 to-pink-600/20"
  },
  {
    id: 5,
    title: "Mastering",
    subtitle: "Loudness, cohesión final y formatos de entrega.",
    description: "El pulido final. Buscamos el volumen comercial competitivo, balance tonal global y nos aseguramos de que la canción suene bien en cualquier sistema de reproducción (coche, celular, club).",
    tools: ["Master Bus Comp", "EQ Lineal", "Maximizador", "Dithering"],
    proTip: "Compara siempre tu master con canciones de referencia del mismo género (A/B testing).",
    icon: SparklesIcon,
    solidIcon: SparklesSolid,
    color: "yellow",
    borderColor: "border-yellow-400",
    textColor: "text-yellow-400",
    bgColor: "bg-yellow-400/10",
    gradient: "from-yellow-500/20 to-amber-600/20"
  }
];

export default function PipelineInteractiveDiagram() {
  const [activeStep, setActiveStep] = useState(0);
  const currentStep = steps[activeStep];

  return (
    <div className="w-full max-w-6xl mx-auto py-12 px-4">
      {/* Header */}
      <div className="text-center mb-12">
        <div className="inline-block px-3 py-1 mb-4 text-xs font-semibold tracking-wider text-blue-300 uppercase bg-blue-900/30 rounded-full border border-blue-800">
          Audio Engineering Workflow
        </div>
        <h2 className="text-4xl md:text-5xl font-bold text-white mb-4 tracking-tight">
          Pipeline de Mezcla & <br className="hidden md:block" />
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-blue-500">
            Masterización
          </span>
        </h2>
        <p className="text-slate-400 max-w-2xl mx-auto text-lg">
          Explora interactivamente cada etapa del proceso de producción de audio, desde el análisis inicial hasta el pulido final.
        </p>
      </div>

      {/* Steps Navigation Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
        {steps.map((step, index) => {
          const isActive = index === activeStep;
          const StepIcon = step.icon;

          return (
            <button
              key={step.id}
              onClick={() => setActiveStep(index)}
              className={`relative flex flex-col items-start p-4 rounded-xl text-left transition-all duration-300 border-2 group h-full
                ${isActive
                  ? `${step.borderColor} bg-slate-800/80 shadow-[0_0_20px_rgba(0,0,0,0.3)]`
                  : 'border-slate-800 bg-slate-900/50 hover:border-slate-700 hover:bg-slate-800'
                }
              `}
            >
              {/* Image Placeholder area for card */}
              <div className={`w-full h-24 mb-4 rounded-lg overflow-hidden relative ${isActive ? 'opacity-100' : 'opacity-60 group-hover:opacity-80'}`}>
                 <div className={`absolute inset-0 bg-gradient-to-br ${step.gradient} flex items-center justify-center`}>
                    <StepIcon className={`w-10 h-10 text-white/50`} />
                 </div>
                 {/* Visual indicator for active state selection cursor (optional visual cue from video) */}
                 {isActive && (
                    <div className="absolute inset-0 ring-1 ring-white/10" />
                 )}
              </div>

              <div className="mt-auto">
                <div className={`text-sm font-bold mb-1 flex items-center gap-2 ${isActive ? 'text-white' : 'text-slate-400'}`}>
                   <span className={isActive ? step.textColor : ''}>{step.id}.</span> {step.title}
                </div>
                <p className="text-xs text-slate-500 line-clamp-2 leading-relaxed">
                  {step.subtitle}
                </p>
              </div>

              {/* Connecting line (hide for last item) */}
              {index < steps.length - 1 && (
                 <div className="hidden md:block absolute -right-3 top-1/2 w-2 h-[2px] bg-slate-800 -translate-y-1/2 z-10" />
              )}
            </button>
          );
        })}
      </div>

      {/* Detail Panel */}
      <div className="bg-slate-900 rounded-3xl border border-slate-800 overflow-hidden shadow-2xl relative transition-all duration-500 ease-in-out">

        {/* Background glow effect based on active color */}
        <div className={`absolute top-0 left-0 w-full h-1 bg-gradient-to-r ${currentStep.gradient} opacity-50`} />

        <div className="grid md:grid-cols-2 gap-0">

          {/* Left Column: Text Content */}
          <div className="p-8 md:p-12 flex flex-col justify-center relative z-10">
            <div className="flex items-center gap-4 mb-6">
              <div className={`p-3 rounded-2xl ${currentStep.bgColor}`}>
                <currentStep.solidIcon className={`w-8 h-8 ${currentStep.textColor}`} />
              </div>
              <h3 className="text-3xl font-bold text-white">
                {currentStep.title}
              </h3>
            </div>

            <p className="text-slate-300 text-lg leading-relaxed mb-8">
              {currentStep.description}
            </p>

            <div className="space-y-4">
              <h4 className="text-xs font-bold text-slate-500 uppercase tracking-widest">
                Herramientas Clave
              </h4>
              <div className="flex flex-wrap gap-2">
                {currentStep.tools.map((tool, i) => (
                  <span
                    key={i}
                    className="px-3 py-1.5 bg-slate-800 text-slate-300 text-sm rounded-lg border border-slate-700/50 hover:border-slate-600 transition-colors"
                  >
                    {tool}
                  </span>
                ))}
              </div>
            </div>
          </div>

          {/* Right Column: Visual/Pro Tip */}
          <div className="relative min-h-[300px] md:min-h-full">
            {/* Main Visual Background */}
            <div className={`absolute inset-0 bg-gradient-to-br ${currentStep.gradient} opacity-20`} />
            <div className="absolute inset-0 bg-[url('/grid-pattern.svg')] opacity-10" /> {/* Optional pattern if available, otherwise just gradient */}

            {/* Center Icon (Large) */}
            <div className="absolute inset-0 flex items-center justify-center">
               <currentStep.icon className={`w-48 h-48 ${currentStep.textColor} opacity-10 rotate-12 transform transition-transform duration-700 ease-out`} />
            </div>

            {/* Pro Tip Overlay Card */}
            <div className="absolute bottom-6 left-6 right-6 bg-slate-950/80 backdrop-blur-sm p-6 rounded-xl border border-slate-800/50 shadow-xl">
               <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-2 flex items-center gap-2">
                  <span className="w-1 h-1 rounded-full bg-slate-400" />
                  Pro Tip
               </div>
               <p className="text-slate-200 text-sm italic font-medium leading-relaxed">
                 "{currentStep.proTip}"
               </p>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
