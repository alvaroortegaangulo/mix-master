'use client';

import React, { memo, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { useTranslations } from 'next-intl';
import { ScrollReveal } from "./ScrollReveal";
import { StarBackground } from "./StarBackground";
import {
  PresentationChartLineIcon,
  WrenchScrewdriverIcon,
  ArrowsPointingInIcon,
  GlobeAltIcon,
  CheckBadgeIcon,
  AdjustmentsVerticalIcon,
  CpuChipIcon,
  BoltIcon,
  MusicalNoteIcon,
  ScissorsIcon,
  SignalIcon,
  AdjustmentsHorizontalIcon,
  SwatchIcon,
  FireIcon,
  SparklesIcon,
  ArrowPathIcon,
  ArrowsRightLeftIcon,
  ArrowUpTrayIcon,
  Cog6ToothIcon,
  ScaleIcon,
  LightBulbIcon
} from '@heroicons/react/24/outline';

type PipelineColor = 'violet';

type PipelineTool = {
  name: string;
  icon: React.ElementType;
};

type PipelineStep = {
  id: string;
  title: string;
  subtitle: string;
  description: string;
  tools: PipelineTool[];
  proTip: string;
  icon: React.ElementType;
  color: PipelineColor;
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
  violet: {
    text: 'text-violet-400',
    textSoft: 'text-amber-300',
    border: 'border-violet-500',
    borderSoft: 'border-violet-500/30',
    ringBorder: 'border-violet-500/50',
    ringBg: 'bg-violet-500/10',
    hoverBorder: 'hover:border-amber-400/50',
    hoverBg: 'hover:bg-violet-900/40',
    hoverText: 'group-hover:text-amber-300',
    toolHoverText: 'group-hover/tool:text-amber-300',
    toolHoverBorder: 'hover:border-amber-400/50',
    toolHoverBg: 'hover:bg-amber-500/10',
    gradientFrom: 'from-violet-900/25',
    particle: '#fbbf24',
    shadow: 'rgba(167, 139, 250, 0.3)',
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

function PipelineInteractiveDiagramComponent({ className }: { className?: string }) {
  const [activeStep, setActiveStep] = useState(0);
  const [panelHeight, setPanelHeight] = useState<number | null>(null);
  const activePanelRef = useRef<HTMLButtonElement | null>(null);
  const t = useTranslations('PipelineInteractiveDiagram');
  const title = t('title');
  const titlePlain = title.replace(/<[^>]+>/g, "");

  const steps = useMemo<PipelineStep[]>(
    () => [
      {
        id: 'analisis',
        title: t('steps.0.title'),
        subtitle: t('steps.0.shortDesc'),
        description: t('steps.0.desc'),
        tools: [
          { name: t('steps.0.tools.0'), icon: AdjustmentsVerticalIcon },
          { name: t('steps.0.tools.1'), icon: CpuChipIcon },
          { name: t('steps.0.tools.2'), icon: BoltIcon },
        ],
        proTip: t('steps.0.tip'),
        icon: PresentationChartLineIcon,
        color: 'violet',
      },
      {
        id: 'correccion',
        title: t('steps.1.title'),
        subtitle: t('steps.1.shortDesc'),
        description: t('steps.1.desc'),
        tools: [
          { name: t('steps.1.tools.0'), icon: MusicalNoteIcon },
          { name: t('steps.1.tools.1'), icon: ScissorsIcon },
          { name: t('steps.1.tools.2'), icon: SignalIcon },
        ],
        proTip: t('steps.1.tip'),
        icon: WrenchScrewdriverIcon,
        color: 'violet',
      },
      {
        id: 'dinamica',
        title: t('steps.2.title'),
        subtitle: t('steps.2.shortDesc'),
        description: t('steps.2.desc'),
        tools: [
          { name: t('steps.2.tools.0'), icon: AdjustmentsHorizontalIcon },
          { name: t('steps.2.tools.1'), icon: SwatchIcon },
          { name: t('steps.2.tools.2'), icon: FireIcon },
        ],
        proTip: t('steps.2.tip'),
        icon: ArrowsPointingInIcon,
        color: 'violet',
      },
      {
        id: 'espacial',
        title: t('steps.3.title'),
        subtitle: t('steps.3.shortDesc'),
        description: t('steps.3.desc'),
        tools: [
          { name: t('steps.3.tools.0'), icon: SparklesIcon },
          { name: t('steps.3.tools.1'), icon: ArrowPathIcon },
          { name: t('steps.3.tools.2'), icon: ArrowsRightLeftIcon },
        ],
        proTip: t('steps.3.tip'),
        icon: GlobeAltIcon,
        color: 'violet',
      },
      {
        id: 'mastering',
        title: t('steps.4.title'),
        subtitle: t('steps.4.shortDesc'),
        description: t('steps.4.desc'),
        tools: [
          { name: t('steps.4.tools.0'), icon: ArrowUpTrayIcon },
          { name: t('steps.4.tools.1'), icon: Cog6ToothIcon },
          { name: t('steps.4.tools.2'), icon: ScaleIcon },
        ],
        proTip: t('steps.4.tip'),
        icon: CheckBadgeIcon,
        color: 'violet',
      },
    ],
    [t]
  );

  const particles = useMemo(() => buildParticles(activeStep + 1), [activeStep]);

  useLayoutEffect(() => {
    const panel = activePanelRef.current;
    if (!panel) return;

    // Use a small timeout or requestAnimationFrame to ensure layout is settled after animation frame
    // though for height calculation on expand, measuring after render is usually fine.
    const updateHeight = () => {
      if (panel) {
        const nextHeight = Math.ceil(panel.getBoundingClientRect().height);
        setPanelHeight((prev) => (prev === nextHeight ? prev : nextHeight));
      }
    };

    updateHeight();

    if (typeof ResizeObserver === 'undefined') return;

    const observer = new ResizeObserver(updateHeight);
    observer.observe(panel);
    return () => observer.disconnect();
  }, [activeStep]);

  const panelHeightStyle = panelHeight
    ? ({ '--panel-height': `${panelHeight}px` } as React.CSSProperties)
    : undefined;

  return (
    <section
      id="pipeline-diagram"
      className={`relative isolate z-0 min-h-[400px] lg:min-h-screen flex flex-col items-center justify-center px-2 lg:px-4 py-12 md:py-14 lg:py-16 2xl:py-20 selection:bg-violet-500 selection:text-white overflow-hidden ${className || 'bg-gradient-to-b from-black via-purple-900/40 to-black'}`}
    >
      <StarBackground />

      <div className="relative z-10 w-full max-w-7xl 2xl:max-w-[1600px]">
        {/* 1. Header Animation */}
        <ScrollReveal delay={0.05} direction="up">
          <header className="text-left mb-6 lg:mb-8 relative z-10 max-w-3xl">
            <h2
              className="text-3xl md:text-5xl 2xl:text-6xl font-black font-['Orbitron'] tracking-wide mb-4 text-white glow-violet metallic-sheen"
              data-text={titlePlain}
            >
              {t.rich('title', {
                violet: (chunks) => <span className="text-violet-400">{chunks}</span>,
              })}
            </h2>
            <p className="text-slate-400 text-sm sm:text-base 2xl:text-lg font-light leading-relaxed">
              {t.rich('description', {
                highlight: (chunks) => <span className="text-amber-400 font-bold">{chunks}</span>,
              })}
            </p>
          </header>
        </ScrollReveal>

        {/* 2. Main Panel Animation */}
        <ScrollReveal delay={0.2} direction="up" className="w-full">
          <main
            className="w-full max-w-7xl 2xl:max-w-[1600px] flex flex-col md:flex-row gap-2 md:gap-4 relative z-10 md:items-stretch"
            style={panelHeightStyle}
          >
            {steps.map((step, index) => {
              const isActive = index === activeStep;
              const colors = colorStyles[step.color];

              return (
                <button
                  key={step.id}
                  ref={isActive ? activePanelRef : undefined}
                  type="button"
                  aria-expanded={isActive}
                  onClick={() => {
                    if (!isActive) setActiveStep(index);
                  }}
                  className={`panel-transition relative overflow-hidden rounded-2xl border border-opacity-50 cursor-pointer bg-slate-950/35 backdrop-blur-md group select-none md:h-[var(--panel-height)] ${isActive ? `flex-[5] lg:flex-[3] brightness-100 ${colors.border}` : `flex-[1] lg:flex-[0.5] hover:flex-[1.2] brightness-50 hover:brightness-75 border-slate-800 hover:border-slate-600`}`}
                  style={isActive ? { boxShadow: `0 0 30px ${colors.shadow}` } : undefined}
                >
                  <div
                    className={`absolute inset-0 bg-gradient-to-t from-slate-950/90 via-slate-900/55 to-slate-900/20 ${isActive ? 'opacity-90' : 'opacity-80'}`}
                  ></div>

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

                  <div className="relative p-2 lg:p-3 flex h-full flex-col gap-[0.5cm] z-10">
                    {!isActive ? (
                      // Collapsed State (Simple fade in for text is handled by parent transition usually, keeping simple)
                      <div className="w-full">
                        <div className="relative flex items-center py-2 md:hidden">
                          <step.icon className={`absolute left-0 w-6 h-6 ${colors.text} group-hover:scale-110 transition-transform duration-300 drop-shadow-lg`} />
                          <h3 className="w-full text-center text-[11px] font-bold tracking-widest text-slate-400 group-hover:text-white transition-colors font-['Orbitron'] uppercase whitespace-nowrap">
                            {step.title}
                          </h3>
                        </div>
                        <div className="hidden md:flex h-full w-full flex-col items-center pt-4 pb-4">
                          <step.icon className={`w-6 h-6 lg:w-8 lg:h-8 ${colors.text} group-hover:scale-125 transition-transform duration-300 drop-shadow-lg`} />
                          <div className="flex-1 flex items-center justify-center">
                            <h3 className="vertical-text text-[10px] lg:text-sm font-bold tracking-widest text-slate-400 group-hover:text-white transition-colors font-['Orbitron'] uppercase">
                              {step.title}
                            </h3>
                          </div>
                        </div>
                      </div>
                    ) : (
                      // Expanded State with Staggered Animations
                      <>
                        {/* 1. Icon + Title Header: Slides in from LEFT */}
                        <ScrollReveal 
                            className="flex items-center justify-start gap-2 text-left"
                            direction="left"
                            delay={0.1}
                            x={20}
                        >
                          <div className={`w-9 h-9 lg:w-10 lg:h-10 rounded-full border ${colors.ringBorder} flex items-center justify-center ${colors.ringBg} backdrop-blur-md icon-pulse`}>
                            <step.icon className={`w-5 h-5 lg:w-6 lg:h-6 ${colors.text}`} />
                          </div>
                          <div>
                            <h3 className="text-xl lg:text-3xl 2xl:text-4xl font-black text-white font-['Orbitron'] mb-0.5 tracking-wide glow-text">
                              {step.title}
                            </h3>
                            <p className={`${colors.textSoft} font-medium tracking-wider text-[10px] lg:text-xs 2xl:text-sm uppercase opacity-90 leading-tight`}>
                              {step.subtitle}
                            </p>
                          </div>
                        </ScrollReveal>

                        <div className="flex flex-col items-start py-1 lg:py-2 space-y-0 text-left w-full">
                          
                          {/* 2. Description: Fades UP */}
                          <ScrollReveal direction="up" delay={0.2} className="w-full">
                            <p className={`text-xs lg:text-sm 2xl:text-base text-slate-200 leading-snug max-w-2xl border-l-2 ${colors.border} pl-3 bg-gradient-to-r ${colors.gradientFrom} to-transparent p-1.5 rounded-r-lg`}>
                              {step.description}
                            </p>
                          </ScrollReveal>

                          {/* 3. Tools Grid: Staggered items */}
                          <div className="grid grid-cols-3 gap-1 sm:gap-2.5 max-w-lg text-left mt-2 w-full sm:w-auto">
                            {step.tools.map((tool, i) => (
                              <ScrollReveal 
                                key={tool.name} 
                                delay={0.3 + (i * 0.1)} // Cascading delay: 0.3, 0.4, 0.5
                                direction="up"
                                className={`flex flex-col items-start justify-center p-1.5 lg:p-2 rounded-xl bg-slate-800/50 ${colors.toolHoverBg} border border-slate-700/50 ${colors.toolHoverBorder} transition-all duration-300 group/tool backdrop-blur-sm`}
                              >
                                <tool.icon className={`w-4 h-4 lg:w-5 lg:h-5 text-slate-400 ${colors.toolHoverText} mb-0.5 lg:mb-1 transition-colors`} />
                                <span className="text-[9px] sm:text-[10px] font-semibold text-left text-slate-300 group-hover/tool:text-white uppercase leading-tight">
                                  {tool.name}
                                </span>
                              </ScrollReveal>
                            ))}
                          </div>
                        </div>

                        {/* 4. Pro Tip Box: Appears LAST */}
                        <ScrollReveal direction="up" delay={0.5} className="w-full">
                          <div className={`shine-box relative overflow-hidden rounded-lg bg-slate-800/80 border ${colors.borderSoft} p-2.5 lg:p-3 shadow-lg text-left`}>
                            <div className="flex items-start gap-2 relative z-10">
                              <LightBulbIcon className={`w-4 h-4 lg:w-5 lg:h-5 ${colors.text} mt-1`} aria-hidden="true" />
                              <div>
                                <h4 className={`${colors.text} font-bold text-[10px] 2xl:text-xs uppercase tracking-widest mb-1`}>
                                  {t('proTip')}
                                </h4>
                                <p className="text-[10px] lg:text-xs 2xl:text-sm text-slate-200 italic font-medium">
                                  &quot;{step.proTip}&quot;
                                </p>
                              </div>
                            </div>
                          </div>
                        </ScrollReveal>
                      </>
                    )}
                  </div>
                </button>
              );
            })}
          </main>
        </ScrollReveal>

      </div>
    </section>
  );
}

export const PipelineInteractiveDiagram = memo(PipelineInteractiveDiagramComponent);