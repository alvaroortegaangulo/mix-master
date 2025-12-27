'use client';

import React, { useState } from 'react';
import { useTranslations } from 'next-intl';

export function PipelineInteractiveDiagram({ className }: { className?: string }) {
  const [activeStep, setActiveStep] = useState<number | null>(null);
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

  const handleStepClick = (index: number) => {
    setActiveStep(activeStep === index ? null : index);
  };

  const getPopupPositionClass = (index: number) => {
    // Default (Mobile/Tablet): Centered/Full width logic handled by stacking
    // Desktop:
    if (index <= 2) return "lg:left-0 lg:origin-bottom-left";
    return "lg:right-0 lg:origin-bottom-right";
  };

  return (
    <section className={`py-6 md:py-8 lg:py-10 2xl:py-12 relative z-20 ${className || 'bg-slate-900'}`}>
    <div className="w-full max-w-7xl mx-auto px-4 md:px-8 relative z-10">
      {/* Header */}
      <header className="text-center mx-auto mb-6 relative z-10 max-w-4xl">
        <div className="inline-block mb-3 px-3 py-1 rounded-full border border-teal-500/30 bg-teal-500/10 text-teal-300 text-xs font-semibold tracking-wider uppercase">
          {t('label')}
        </div>
        <h2 className="text-3xl sm:text-4xl lg:text-5xl 2xl:text-6xl font-bold mb-4 bg-clip-text text-transparent bg-gradient-to-r from-white via-teal-200 to-violet-200 drop-shadow-lg">
          {t('title')}
        </h2>
        <p className="text-slate-300 text-base sm:text-lg max-w-2xl mx-auto">
          {t('description')}
        </p>
      </header>

      {/* Main Pipeline Diagram */}
      <div className="w-full relative z-10">

        {/* Steps Container */}
        <div className="flex flex-col lg:flex-row justify-between items-start gap-6 lg:gap-4 relative">
          {stepsData.map((step, index) => {
            const isActive = index === activeStep;

            return (
              <div
                key={index}
                className="relative group w-full lg:w-1/5"
                onMouseEnter={() => setActiveStep(index)}
                onMouseLeave={() => setActiveStep(null)}
                onClick={() => handleStepClick(index)}
              >
                <div
                  className={`step-card cursor-pointer rounded-2xl p-3 h-full flex flex-col transition-all duration-300 ease-[cubic-bezier(0.4,0,0.2,1)] backdrop-blur-xl border border-white/10
                    ${isActive
                      ? 'border-teal-400 bg-slate-800/70 shadow-[0_0_30px_rgba(45,212,191,0.15)] opacity-100 scale-105 -translate-y-2'
                      : 'bg-slate-800/40 opacity-70 group-hover:-translate-y-2 group-hover:scale-105 group-hover:border-violet-500/50 group-hover:shadow-xl'
                    }`}
                >
                  <div className="relative h-24 sm:h-28 w-full overflow-hidden rounded-xl mb-4">
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
                  <h3 className={`text-lg sm:text-xl font-bold text-white mb-1 transition-colors ${isActive ? step.colorClass : 'group-hover:text-violet-300'}`}>
                    {index + 1}. {step.title}
                  </h3>
                  <p className="text-sm text-slate-300 line-clamp-2">
                    {step.shortDesc}
                  </p>
                </div>

                {/* Connector */}
                {index < stepsData.length - 1 && (
                  <div className="connector-line hidden lg:block absolute top-1/2 -right-4 w-8 h-0.5 bg-slate-700 -z-10"></div>
                )}

                {/* Floating Detail Popup */}
                {isActive && (
                  <div className={`
                    z-50 w-full lg:w-[520px] 2xl:w-[600px]
                    ${/* Mobile: Relative (Accordion) */ "relative top-0 mt-4"}
                    ${/* Desktop: Absolute (Popup) */ "lg:absolute lg:bottom-full lg:mb-4"}
                    ${getPopupPositionClass(index)}
                  `}>
                    <div className="relative bg-slate-900/95 border border-slate-700/50 rounded-2xl p-5 2xl:p-6 shadow-2xl backdrop-blur-xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
                      {/* Decorative Background Elements */}
                      <div className="absolute top-0 right-0 w-32 h-32 bg-teal-500/10 rounded-full blur-2xl -mr-10 -mt-10 pointer-events-none"></div>
                      <div className="absolute bottom-0 left-0 w-32 h-32 bg-violet-500/10 rounded-full blur-2xl -ml-10 -mb-10 pointer-events-none"></div>

                      <div className="relative z-10 grid grid-cols-1 md:grid-cols-2 gap-6">
                        {/* Text Info */}
                        <div className="text-left">
                          <div className="flex items-center gap-3 mb-3">
                            <img
                              src={step.icon}
                              alt=""
                              className="w-8 h-8 object-contain"
                            />
                            <h3 className="text-xl sm:text-2xl font-bold text-white font-display leading-tight">
                              {step.title}
                            </h3>
                          </div>
                          <p className="text-slate-300 text-sm leading-relaxed mb-4">
                            {step.desc}
                          </p>

                          <div className="bg-slate-800/50 rounded-lg p-3 border border-slate-700">
                            <h3 className="text-[10px] font-bold uppercase tracking-widest text-slate-300 mb-2">
                              {t('keyTools')}
                            </h3>
                            <div className="flex flex-wrap gap-1.5">
                              {step.tools.map((tool, idx) => (
                                <span
                                  key={idx}
                                  className={`px-2 py-0.5 ${step.bgClass} text-[10px] md:text-xs rounded-full border ${step.borderClass} text-white/90`}
                                >
                                  {tool}
                                </span>
                              ))}
                            </div>
                          </div>
                        </div>

                        {/* Visual Context */}
                        <div className="relative rounded-xl overflow-hidden border border-slate-700/50 shadow-lg min-h-[160px] sm:min-h-[180px] md:min-h-0">
                            <img
                              src={step.image}
                              className="absolute inset-0 w-full h-full object-cover"
                              alt={step.title}
                            />
                            <div className="absolute inset-0 bg-gradient-to-t from-slate-900 via-transparent to-transparent opacity-80"></div>
                            <div className="absolute bottom-3 left-3 right-3">
                              <div className="text-[10px] text-white/70 font-mono bg-black/50 inline-block px-1.5 py-0.5 rounded mb-1">
                                {t('proTip')}
                              </div>
                              <p className="text-xs font-medium text-white italic leading-tight">
                                "{step.tip}"
                              </p>
                            </div>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
    </section>
  );
}
