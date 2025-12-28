'use client';

import React, { useState } from 'react';
import { useTranslations } from 'next-intl';

export function PipelineInteractiveDiagram({ className }: { className?: string }) {
  const [activeStep, setActiveStep] = useState(0);
  const t = useTranslations('PipelineInteractiveDiagram');

  const stepsData = [
    {
      title: t('steps.0.title'),
      icon: "/icon_analysis.webp",
      colorClass: "text-teal-400",
      bgClass: "bg-teal-900/30",
      borderClass: "border-teal-800",
      shortDesc: t('steps.0.shortDesc'),
      desc: t('steps.0.desc'),
      tools: [t('steps.0.tools.0'), t('steps.0.tools.1'), t('steps.0.tools.2')],
      tip: t('steps.0.tip'),
      image: "/analysis.webp"
    },
    {
      title: t('steps.1.title'),
      icon: "/icon_correction.webp",
      colorClass: "text-violet-400",
      bgClass: "bg-violet-900/30",
      borderClass: "border-violet-800",
      shortDesc: t('steps.1.shortDesc'),
      desc: t('steps.1.desc'),
      tools: [t('steps.1.tools.0'), t('steps.1.tools.1'), t('steps.1.tools.2')],
      tip: t('steps.1.tip'),
      image: "/correction.webp"
    },
    {
      title: t('steps.2.title'),
      icon: "/icon_dynamics.webp",
      colorClass: "text-teal-400",
      bgClass: "bg-teal-900/30",
      borderClass: "border-teal-800",
      shortDesc: t('steps.2.shortDesc'),
      desc: t('steps.2.desc'),
      tools: [t('steps.2.tools.0'), t('steps.2.tools.1'), t('steps.2.tools.2'), t('steps.2.tools.3')],
      tip: t('steps.2.tip'),
      image: "/dynamics.webp"
    },
    {
      title: t('steps.3.title'),
      icon: "/icon_spatial.webp",
      colorClass: "text-violet-400",
      bgClass: "bg-violet-900/30",
      borderClass: "border-violet-800",
      shortDesc: t('steps.3.shortDesc'),
      desc: t('steps.3.desc'),
      tools: [t('steps.3.tools.0'), t('steps.3.tools.1'), t('steps.3.tools.2'), t('steps.3.tools.3')],
      tip: t('steps.3.tip'),
      image: "/spatial.webp"
    },
    {
      title: t('steps.4.title'),
      icon: "/icon_mastering.webp",
      colorClass: "text-teal-400",
      bgClass: "bg-teal-900/30",
      borderClass: "border-teal-800",
      shortDesc: t('steps.4.shortDesc'),
      desc: t('steps.4.desc'),
      tools: [t('steps.4.tools.0'), t('steps.4.tools.1'), t('steps.4.tools.2'), t('steps.4.tools.3')],
      tip: t('steps.4.tip'),
      image: "/mastering.webp"
    }
  ];

  return (
    <section className={`py-6 md:py-8 lg:py-10 2xl:py-12 relative z-20 ${className || 'bg-slate-900'}`}>
    <div className="w-full max-w-7xl mx-auto px-4 md:px-8 relative z-10">
      {/* Header */}
      <header className="text-center mx-auto mb-6 relative z-10 max-w-4xl">
        <h2 className="text-2xl sm:text-3xl lg:text-4xl 2xl:text-5xl font-bold mb-3 bg-clip-text text-transparent bg-gradient-to-r from-white via-teal-200 to-violet-200 drop-shadow-lg">
          {t('title')}
        </h2>
        <p className="text-slate-300 text-sm sm:text-base max-w-2xl mx-auto">
          {t('description')}
        </p>
      </header>

      {/* Main Pipeline Diagram */}
      <div className="w-full relative z-10">
        {/* Steps Container */}
        <div className="flex flex-col lg:flex-row items-stretch gap-4 lg:gap-5 lg:h-[340px]">
          {stepsData.map((step, index) => {
            const isActive = index === activeStep;

            return (
              <button
                key={index}
                type="button"
                aria-expanded={isActive}
                onClick={() => setActiveStep(index)}
                className={`relative w-full lg:self-stretch lg:h-full overflow-hidden rounded-2xl border border-white/5 text-left backdrop-blur-xl transition-all lg:transition-[flex,background-color,box-shadow] duration-300 ease-[cubic-bezier(0.4,0,0.2,1)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-400/70
                  ${isActive
                    ? 'bg-slate-950/90 lg:flex-[3] shadow-[inset_0_1px_0_rgba(255,255,255,0.08),_inset_0_-1px_0_rgba(0,0,0,0.65),_0_0_28px_rgba(34,211,238,0.18),_0_0_46px_rgba(139,92,246,0.14)]'
                    : 'bg-slate-950/70 hover:bg-slate-950/80 lg:flex-[1] shadow-[inset_0_1px_0_rgba(255,255,255,0.05),_inset_0_-1px_0_rgba(0,0,0,0.7),_0_0_22px_rgba(34,211,238,0.08),_0_0_30px_rgba(139,92,246,0.08)]'
                  }`}
              >
                <div className="absolute inset-0">
                  <img
                    src={step.image}
                    alt=""
                    className={`h-full w-full object-cover transition duration-700 ${isActive ? 'scale-110' : 'scale-100 grayscale brightness-75 opacity-70'}`}
                  />
                  <div
                    className={`absolute inset-0 ${isActive
                      ? 'bg-gradient-to-br from-slate-950/95 via-slate-950/80 to-slate-900/60'
                      : 'bg-gradient-to-br from-slate-950/98 via-slate-950/85 to-slate-900/70'
                    }`}
                  ></div>
                </div>

                <div className="relative z-10 flex h-full min-h-[180px] flex-col p-4 sm:p-5 lg:p-6">
                  <div className="flex items-start gap-3">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-slate-600/70 bg-slate-900/60 shadow-sm">
                      <img
                        src={step.icon}
                        alt=""
                        className={`h-5 w-5 object-contain ${isActive ? '' : 'grayscale brightness-75 opacity-60'}`}
                      />
                    </div>
                    <div className={`flex flex-col ${isActive ? '' : 'lg:hidden'}`}>
                      <h3 className={`text-lg sm:text-xl font-bold text-white ${isActive ? step.colorClass : ''}`}>
                        {step.title}
                      </h3>
                      <p className="text-xs sm:text-sm text-slate-300">
                        {step.shortDesc}
                      </p>
                    </div>
                  </div>

                  <div className={`mt-4 space-y-4 ${isActive ? 'block' : 'hidden lg:hidden'}`}>
                    <p className="text-sm text-slate-200/90 leading-relaxed">
                      {step.desc}
                    </p>

                    <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-slate-200/90">
                      {step.tools.map((tool, idx) => (
                        <span key={idx} className="font-medium">
                          {tool}
                        </span>
                      ))}
                    </div>

                    <div className={`rounded-lg border ${step.borderClass} bg-slate-900/70 p-3`}>
                      <div className={`text-[10px] font-bold uppercase tracking-widest mb-2 ${step.colorClass}`}>
                        {t('proTip')}
                      </div>
                      <p className="text-xs text-white/90 italic leading-relaxed">
                        "{step.tip}"
                      </p>
                    </div>
                  </div>

                  <div className={`hidden lg:flex mt-6 ${isActive ? 'lg:hidden' : ''}`}>
                    <span
                      className="text-xs uppercase tracking-[0.4em] text-slate-200/70"
                      style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)' }}
                    >
                      {step.title}
                    </span>
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </div>
    </div>
    </section>
  );
}
