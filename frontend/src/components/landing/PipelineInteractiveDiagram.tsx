'use client';

import React, { useMemo, useState } from 'react';
import { useTranslations } from 'next-intl';

type PipelineColor = 'cyan' | 'blue' | 'indigo' | 'violet' | 'fuchsia';

type PipelineTool = {
  name: string;
  icon: string;
};

type PipelineStep = {
  id: string;
  title: string;
  subtitle: string;
  description: string;
  tools: PipelineTool[];
  proTip: string;
  icon: string;
  color: PipelineColor;
  bgImage: string;
};

const colorStyles: Record<
  PipelineColor,
  {
    text: string;
    textSoft: string;
    border: string;
    borderSoft: string;
    ringBorder: string;
    ringBg: string;
    hoverBorder: string;
    hoverBg: string;
    hoverText: string;
    toolHoverText: string;
    toolHoverBorder: string;
    toolHoverBg: string;
    gradientFrom: string;
    particle: string;
    shadow: string;
  }
> = {
  cyan: {
    text: 'text-cyan-400',
    textSoft: 'text-cyan-300',
    border: 'border-cyan-500',
    borderSoft: 'border-cyan-500/30',
    ringBorder: 'border-cyan-500/50',
    ringBg: 'bg-cyan-500/10',
    hoverBorder: 'hover:border-cyan-500/50',
    hoverBg: 'hover:bg-cyan-900/40',
    hoverText: 'group-hover:text-cyan-400',
    toolHoverText: 'group-hover/tool:text-cyan-400',
    toolHoverBorder: 'hover:border-cyan-500/50',
    toolHoverBg: 'hover:bg-cyan-900/40',
    gradientFrom: 'from-cyan-900/20',
    particle: '#22d3ee',
    shadow: 'rgba(34, 211, 238, 0.25)',
  },
  blue: {
    text: 'text-blue-400',
    textSoft: 'text-blue-300',
    border: 'border-blue-500',
    borderSoft: 'border-blue-500/30',
    ringBorder: 'border-blue-500/50',
    ringBg: 'bg-blue-500/10',
    hoverBorder: 'hover:border-blue-500/50',
    hoverBg: 'hover:bg-blue-900/40',
    hoverText: 'group-hover:text-blue-400',
    toolHoverText: 'group-hover/tool:text-blue-400',
    toolHoverBorder: 'hover:border-blue-500/50',
    toolHoverBg: 'hover:bg-blue-900/40',
    gradientFrom: 'from-blue-900/20',
    particle: '#ffffff',
    shadow: 'rgba(96, 165, 250, 0.25)',
  },
  indigo: {
    text: 'text-indigo-400',
    textSoft: 'text-indigo-300',
    border: 'border-indigo-500',
    borderSoft: 'border-indigo-500/30',
    ringBorder: 'border-indigo-500/50',
    ringBg: 'bg-indigo-500/10',
    hoverBorder: 'hover:border-indigo-500/50',
    hoverBg: 'hover:bg-indigo-900/40',
    hoverText: 'group-hover:text-indigo-400',
    toolHoverText: 'group-hover/tool:text-indigo-400',
    toolHoverBorder: 'hover:border-indigo-500/50',
    toolHoverBg: 'hover:bg-indigo-900/40',
    gradientFrom: 'from-indigo-900/20',
    particle: '#ffffff',
    shadow: 'rgba(129, 140, 248, 0.25)',
  },
  violet: {
    text: 'text-violet-400',
    textSoft: 'text-violet-300',
    border: 'border-violet-500',
    borderSoft: 'border-violet-500/30',
    ringBorder: 'border-violet-500/50',
    ringBg: 'bg-violet-500/10',
    hoverBorder: 'hover:border-violet-500/50',
    hoverBg: 'hover:bg-violet-900/40',
    hoverText: 'group-hover:text-violet-400',
    toolHoverText: 'group-hover/tool:text-violet-400',
    toolHoverBorder: 'hover:border-violet-500/50',
    toolHoverBg: 'hover:bg-violet-900/40',
    gradientFrom: 'from-violet-900/20',
    particle: '#ffffff',
    shadow: 'rgba(167, 139, 250, 0.25)',
  },
  fuchsia: {
    text: 'text-fuchsia-400',
    textSoft: 'text-fuchsia-300',
    border: 'border-fuchsia-500',
    borderSoft: 'border-fuchsia-500/30',
    ringBorder: 'border-fuchsia-500/50',
    ringBg: 'bg-fuchsia-500/10',
    hoverBorder: 'hover:border-fuchsia-500/50',
    hoverBg: 'hover:bg-fuchsia-900/40',
    hoverText: 'group-hover:text-fuchsia-400',
    toolHoverText: 'group-hover/tool:text-fuchsia-400',
    toolHoverBorder: 'hover:border-fuchsia-500/50',
    toolHoverBg: 'hover:bg-fuchsia-900/40',
    gradientFrom: 'from-fuchsia-900/20',
    particle: '#e879f9',
    shadow: 'rgba(232, 121, 249, 0.25)',
  },
};

const seededValue = (value: number) => {
  const next = Math.sin(value) * 10000;
  return next - Math.floor(next);
};

const buildParticles = (seed: number) =>
  Array.from({ length: 8 }, (_, index) => {
    const base = seed * 97 + index * 11;
    const size = 2 + seededValue(base + 1) * 5;
    return {
      left: `${seededValue(base + 2) * 100}%`,
      size: `${size}px`,
      duration: `${4 + seededValue(base + 3) * 3}s`,
      delay: `${seededValue(base + 4) * 2}s`,
    };
  });

export function PipelineInteractiveDiagram({ className }: { className?: string }) {
  const [activeStep, setActiveStep] = useState(0);
  const t = useTranslations('PipelineInteractiveDiagram');

  const steps = useMemo<PipelineStep[]>(
    () => [
      {
        id: 'analisis',
        title: t('steps.0.title'),
        subtitle: t('steps.0.shortDesc'),
        description: t('steps.0.desc'),
        tools: [
          { name: t('steps.0.tools.0'), icon: 'equalizer' },
          { name: t('steps.0.tools.1'), icon: 'leak_add' },
          { name: t('steps.0.tools.2'), icon: 'speed' },
        ],
        proTip: t('steps.0.tip'),
        icon: 'query_stats',
        color: 'cyan',
        bgImage: '/analysis.webp',
      },
      {
        id: 'correccion',
        title: t('steps.1.title'),
        subtitle: t('steps.1.shortDesc'),
        description: t('steps.1.desc'),
        tools: [
          { name: t('steps.1.tools.0'), icon: 'tune' },
          { name: t('steps.1.tools.1'), icon: 'cut' },
          { name: t('steps.1.tools.2'), icon: 'waves' },
        ],
        proTip: t('steps.1.tip'),
        icon: 'build',
        color: 'blue',
        bgImage: '/correction.webp',
      },
      {
        id: 'dinamica',
        title: t('steps.2.title'),
        subtitle: t('steps.2.shortDesc'),
        description: t('steps.2.desc'),
        tools: [
          { name: t('steps.2.tools.0'), icon: 'graphic_eq' },
          { name: t('steps.2.tools.1'), icon: 'hub' },
          { name: t('steps.2.tools.2'), icon: 'local_fire_department' },
        ],
        proTip: t('steps.2.tip'),
        icon: 'compress',
        color: 'indigo',
        bgImage: '/dynamics.webp',
      },
      {
        id: 'espacial',
        title: t('steps.3.title'),
        subtitle: t('steps.3.shortDesc'),
        description: t('steps.3.desc'),
        tools: [
          { name: t('steps.3.tools.0'), icon: 'church' },
          { name: t('steps.3.tools.1'), icon: 'repeat' },
          { name: t('steps.3.tools.2'), icon: 'panorama_horizontal' },
        ],
        proTip: t('steps.3.tip'),
        icon: 'surround_sound',
        color: 'violet',
        bgImage: '/spatial.webp',
      },
      {
        id: 'mastering',
        title: t('steps.4.title'),
        subtitle: t('steps.4.shortDesc'),
        description: t('steps.4.desc'),
        tools: [
          { name: t('steps.4.tools.0'), icon: 'vertical_align_top' },
          { name: t('steps.4.tools.1'), icon: 'settings_input_component' },
          { name: t('steps.4.tools.2'), icon: 'compare_arrows' },
        ],
        proTip: t('steps.4.tip'),
        icon: 'album',
        color: 'fuchsia',
        bgImage: '/mastering.webp',
      },
    ],
    [t]
  );

  const particles = useMemo(() => buildParticles(activeStep + 1), [activeStep]);

  return (
    <section
      className={`relative min-h-screen flex flex-col items-center justify-center p-4 lg:p-8 overflow-x-hidden selection:bg-cyan-500 selection:text-white ${className || ''} bg-[#050508]`}
    >
      <div className="absolute inset-0 pointer-events-none z-0">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-cyan-900/20 rounded-full blur-[120px]"></div>
        <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-blue-900/20 rounded-full blur-[120px]"></div>
      </div>

      <div className="relative z-10 w-full max-w-7xl">
        <header className="text-center mb-8 lg:mb-12 relative z-10 animate-fade-in-down">
          <h2 className="text-4xl md:text-6xl font-bold font-orbitron mb-4 bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 to-blue-500 glow-text">
            {t('title')}
          </h2>
          <p className="text-slate-400 text-lg max-w-2xl mx-auto font-light">
            {t.rich('description', {
              highlight: (chunks) => <span className="text-cyan-400 font-medium">{chunks}</span>,
            })}
          </p>
        </header>

        <main className="w-full max-w-7xl h-[80vh] min-h-[600px] flex flex-col md:flex-row gap-2 md:gap-4 relative z-10">
          {steps.map((step, index) => {
            const isActive = index === activeStep;
            const colors = colorStyles[step.color];
            const stepNumber = `0${index + 1}`;

            return (
              <button
                key={step.id}
                type="button"
                aria-expanded={isActive}
                onClick={() => {
                  if (!isActive) setActiveStep(index);
                }}
                className={`panel-transition relative overflow-hidden rounded-2xl border border-opacity-50 cursor-pointer bg-slate-900 group select-none ${isActive ? `flex-[5] lg:flex-[3] brightness-100 ${colors.border}` : `flex-[1] lg:flex-[0.5] hover:flex-[1.2] brightness-50 hover:brightness-75 border-slate-800 hover:border-slate-600`}`}
                style={isActive ? { boxShadow: `0 0 30px ${colors.shadow}` } : undefined}
              >
                <img
                  src={step.bgImage}
                  alt={`${step.title} Background`}
                  className={`absolute inset-0 w-full h-full object-cover transition-transform duration-1000 ${isActive ? 'scale-110' : 'scale-100 opacity-60'}`}
                />

                <div className={`absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-900/80 to-slate-900/40 ${isActive ? 'opacity-90' : 'opacity-80'}`}></div>

                {isActive && (
                  <div className="particles">
                    {particles.map((particle, particleIndex) => (
                      <div
                        key={`${step.id}-particle-${particleIndex}`}
                        className="particle"
                        style={{
                          left: particle.left,
                          width: particle.size,
                          height: particle.size,
                          animationDuration: particle.duration,
                          animationDelay: particle.delay,
                          background: colors.particle,
                        }}
                      />
                    ))}
                  </div>
                )}

                <div className="absolute inset-0 p-6 flex flex-col justify-between h-full z-10">
                  {!isActive ? (
                    <div className="h-full flex flex-col items-center justify-center py-4">
                      <span className={`material-symbols-outlined text-3xl mb-8 ${colors.text} group-hover:scale-125 transition-transform duration-300 drop-shadow-lg`}>
                        {step.icon}
                      </span>
                      <div className="flex-grow flex items-center justify-center">
                        <h3 className="vertical-text text-xl lg:text-2xl font-bold tracking-widest text-slate-400 group-hover:text-white transition-colors font-orbitron uppercase">
                          {step.title}
                        </h3>
                      </div>
                      <div className={`text-xs font-mono text-slate-600 mt-8 ${colors.hoverText}`}>{stepNumber}</div>
                    </div>
                  ) : (
                    <>
                      <div className="flex items-start justify-between animate-fade-in">
                        <div className="flex items-center gap-4">
                          <div className={`w-12 h-12 rounded-full border ${colors.ringBorder} flex items-center justify-center ${colors.ringBg} backdrop-blur-md icon-pulse`}>
                            <span className={`material-symbols-outlined ${colors.text} text-2xl`}>{step.icon}</span>
                          </div>
                          <div>
                            <h3 className="text-3xl lg:text-5xl font-bold text-white font-orbitron mb-1 tracking-wide glow-text">
                              {step.title}
                            </h3>
                            <p className={`${colors.textSoft} font-medium tracking-wider text-sm uppercase opacity-90`}>
                              {step.subtitle}
                            </p>
                          </div>
                        </div>
                        <span className="text-6xl font-black text-slate-800 opacity-30 select-none font-orbitron hidden sm:block">
                          {stepNumber}
                        </span>
                      </div>

                      <div className="flex-grow flex flex-col justify-center py-4 space-y-6">
                        <p className={`text-lg text-slate-200 leading-relaxed max-w-2xl border-l-2 ${colors.border} pl-4 bg-gradient-to-r ${colors.gradientFrom} to-transparent p-2 rounded-r-lg`}>
                          {step.description}
                        </p>

                        <div className="grid grid-cols-3 gap-2 sm:gap-4 max-w-lg">
                          {step.tools.map((tool) => (
                            <div
                              key={tool.name}
                              className={`flex flex-col items-center justify-center p-3 rounded-xl bg-slate-800/50 ${colors.toolHoverBg} border border-slate-700/50 ${colors.toolHoverBorder} transition-all duration-300 group/tool backdrop-blur-sm`}
                            >
                              <span className={`material-symbols-outlined text-slate-400 ${colors.toolHoverText} mb-2 transition-colors`}>
                                {tool.icon}
                              </span>
                              <span className="text-[10px] sm:text-xs font-semibold text-center text-slate-300 group-hover/tool:text-white uppercase leading-tight">
                                {tool.name}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>

                      <div className="mt-auto">
                        <div className={`shine-box relative overflow-hidden rounded-lg bg-slate-800/80 border ${colors.borderSoft} p-4 lg:p-5 shadow-lg`}>
                          <div className="flex items-start gap-3 relative z-10">
                            <span className={`material-symbols-outlined ${colors.text} mt-1`}>lightbulb</span>
                            <div>
                              <h4 className={`${colors.text} font-bold text-xs uppercase tracking-widest mb-1`}>
                                {t('proTip')}
                              </h4>
                              <p className="text-sm lg:text-base text-slate-200 italic font-medium">
                                &quot;{step.proTip}&quot;
                              </p>
                            </div>
                          </div>
                        </div>
                      </div>
                    </>
                  )}
                </div>
              </button>
            );
          })}
        </main>

        <div className="mt-8 text-slate-600 text-sm flex gap-2 justify-center items-center">
          <span>{t('verified')}</span>
          <span className="material-symbols-outlined text-xs">check_circle</span>
        </div>
      </div>
    </section>
  );
}
