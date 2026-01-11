import { useRef, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { ScrollReveal } from "./ScrollReveal";
import { PipelineBackground } from "./PipelineBackground";
import {
  BoltIcon,
  CheckCircleIcon,
  AdjustmentsVerticalIcon,
  ArrowsRightLeftIcon,
  SpeakerWaveIcon
} from "@heroicons/react/24/outline";

// Helper to draw a simulated equalizer animation (manual mode)
const drawEqualizerBars = (
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  frameCount: number
) => {
  ctx.clearRect(0, 0, width, height);

  const barCount = 48;
  const gap = Math.max(1, Math.floor(width / 200));
  const totalGap = gap * (barCount - 1);
  const barWidth = Math.max(2, (width - totalGap) / barCount);
  const t = frameCount * 0.06;
  const baseY = height - 4;
  const minHeight = height * 0.12;
  const maxHeight = height * 0.75;
  const modeAlpha = 0.75;

  ctx.shadowBlur = 12;

  for (let i = 0; i < barCount; i += 1) {
    const waveA = Math.sin(t + i * 0.35);
    const waveB = Math.sin(t * 0.6 + i * 0.18);
    const waveC = Math.sin(t * 1.3 + i * 0.05);
    const mix = (waveA * 0.6 + waveB * 0.3 + waveC * 0.1 + 1.5) / 3;
    const barHeight = Math.max(minHeight, minHeight + mix * maxHeight);
    const x = i * (barWidth + gap);
    const y = baseY - barHeight;
  const hue = 345 + (i / (barCount - 1)) * 12;
  const saturation = 68;
  const lightness = 56;
    const alpha = modeAlpha * (0.6 + 0.4 * Math.sin(t + i * 0.2));

    ctx.shadowColor = `hsla(${hue}, ${saturation}%, ${lightness}%, ${modeAlpha})`;
    ctx.fillStyle = `hsla(${hue}, ${saturation}%, ${lightness}%, ${alpha})`;
    ctx.fillRect(x, y, barWidth, barHeight);
  }

  ctx.shadowBlur = 0;
};

// Helper to draw a flowing wave spectrum (auto mode)
const drawSpectrumFlow = (
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  frameCount: number
) => {
  ctx.clearRect(0, 0, width, height);

  const barCount = 72;
  const gap = Math.max(1, Math.floor(width / 260));
  const totalGap = gap * (barCount - 1);
  const barWidth = Math.max(2, (width - totalGap) / barCount);
  const baseY = height - 6;
  const minHeight = height * 0.08;
  const maxHeight = height * 0.75;
  const time = frameCount * 0.055;
  const center = (barCount - 1) / 2;
  const spread = barCount * 0.42;
  const pulse = 0.85 + 0.15 * Math.sin(time * 0.7);

  ctx.shadowBlur = 14;

  for (let i = 0; i < barCount; i += 1) {
    const offset = i - center;
    const envelope = Math.exp(-Math.pow(offset / spread, 2) * 2.4);
    const waveA = Math.sin(i * 0.46 - time);
    const waveB = Math.sin(i * 0.15 + time * 1.3);
    const waveC = Math.sin(i * 0.08 - time * 0.6);
    const mix = Math.max(0, 0.58 + 0.32 * waveA + 0.2 * waveB + 0.1 * waveC);
    const heightFactor = Math.min(1, Math.max(0.05, (0.12 + envelope * 0.95) * mix * pulse));
    const barHeight = minHeight + heightFactor * maxHeight;
    const x = i * (barWidth + gap);
  const hue = 150 + (i / (barCount - 1)) * 20;
    const gradient = ctx.createLinearGradient(0, baseY - barHeight, 0, baseY);
    gradient.addColorStop(0, `hsla(${hue + 10}, 82%, 70%, 0.95)`);
    gradient.addColorStop(0.55, `hsla(${hue - 6}, 78%, 52%, 0.65)`);
    gradient.addColorStop(1, `hsla(${hue - 18}, 82%, 38%, 0.2)`);

    ctx.shadowColor = `hsla(${hue}, 82%, 55%, 0.6)`;
    ctx.fillStyle = gradient;
    ctx.fillRect(x, baseY - barHeight, barWidth, barHeight);

    const highlightHeight = Math.max(1, barHeight * 0.08);
    ctx.fillStyle = `hsla(${hue + 16}, 85%, 78%, 0.75)`;
    ctx.fillRect(x, baseY - barHeight, barWidth, highlightHeight);
  }

  ctx.shadowBlur = 0;
};


type BenefitsSectionProps = {
  className?: string;
};

export function BenefitsSection({ className }: BenefitsSectionProps) {
  const t = useTranslations('BenefitsSection');
  const headerTitle = t('headerTitle');
  const headerTitlePlain = headerTitle.replace(/<[^>]+>/g, "");
  const [isManual, setIsManual] = useState(true);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const requestRef = useRef<number>(0);
  const frameCountRef = useRef<number>(0);

  // Toggle Handler
  const toggleAI = () => {
    setIsManual(!isManual);
  };

  // Canvas Animation Loop
  useEffect(() => {
    const animate = () => {
      if (canvasRef.current) {
        const canvas = canvasRef.current;
        const ctx = canvas.getContext('2d');
        if (ctx) {
           // Handle resize or static size
           // Note: canvas width/height attributes are set in JSX
           if (isManual) {
             drawEqualizerBars(ctx, canvas.width, canvas.height, frameCountRef.current);
           } else {
             drawSpectrumFlow(ctx, canvas.width, canvas.height, frameCountRef.current);
           }
        }
      }
      frameCountRef.current += 1;
      requestRef.current = requestAnimationFrame(animate);
    };

    requestRef.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(requestRef.current);
  }, [isManual]);

  return (
    <section id="benefits" className={`lg:min-h-screen flex flex-col justify-center py-12 md:py-14 lg:py-16 2xl:py-20 relative isolate z-0 overflow-hidden ${className || 'bg-slate-950'}`}>
        {/* Fondo Animado Pro */}
        <div className="absolute inset-0 z-0 bg-gradient-to-b from-slate-950 via-rose-950/20 to-slate-950" />
        <PipelineBackground />

        <div className="relative z-10 max-w-7xl 2xl:max-w-[1600px] w-full mx-auto space-y-6 px-4 sm:px-6 lg:px-8 2xl:px-4">

            {/* Header */}
            <ScrollReveal className="text-right" delay={0.05}>
                <h2
                    className="text-3xl md:text-5xl 2xl:text-6xl font-bold tracking-tight text-white mb-4 font-['Orbitron'] glow-burgundy metallic-sheen"
                    data-text={headerTitlePlain}
                >
                    {t.rich('headerTitle', {
                      burgundy: (chunks) => (
                        <span className="text-transparent bg-clip-text bg-gradient-to-r from-rose-400 via-rose-500 to-rose-600 font-bold glow-burgundy">
                          {chunks}
                        </span>
                      ),
                    })}
                </h2>
                <p className="text-slate-400 text-sm sm:text-base max-w-2xl ml-auto font-light">
                    {t.rich('headerDesc', {
                      highlight: (chunks) => (
                        <span className="text-rose-400 font-bold">{chunks}</span>
                      ),
                    })}
                </p>
            </ScrollReveal>

            {/* Bento Grid Layout */}
            <div className="grid grid-cols-1 md:grid-cols-12 gap-3 auto-rows-[minmax(110px,auto)]">

                {/* Card 1: AI Efficiency (Interactive) - Spans 7 cols */}
                <ScrollReveal
                    className="md:col-span-7 bg-slate-900/60 backdrop-blur-md border border-slate-800 rounded-3xl p-4 relative overflow-hidden group flex flex-col justify-between min-h-[160px] 2xl:min-h-[240px] transition-transform duration-300 hover:-translate-y-1 hover:border-rose-500/70 hover:ring-1 hover:ring-rose-500/35"
                    delay={0.1}
                >
                    <div className="relative z-10">
                        <div className="flex items-center justify-between mb-3">
                        <div className="inline-flex items-center px-2 py-0.5 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[10px] font-bold uppercase tracking-wider">
                            <BoltIcon className="w-3 h-3 mr-1" /> {t('efficiencyBadge')}
                        </div>
                            {/* Interactive Toggle */}
                            <button
                                onClick={toggleAI}
                                className="flex items-center space-x-2 bg-slate-900/50 hover:bg-slate-800 border border-slate-700 rounded-full p-1 pl-3 transition-all duration-300 cursor-pointer"
                            >
                                <span className={`text-[11px] font-semibold uppercase tracking-wider transition-colors duration-300 ${isManual ? 'text-slate-400' : 'text-emerald-400'}`}>
                                    {isManual ? t('manual') : 'AUTO'}
                                </span>
                                <div className={`w-9 h-5 rounded-full relative transition-colors duration-300 ${isManual ? 'bg-slate-700' : 'bg-emerald-500'}`}>
                                    <div className={`absolute top-0.5 w-3.5 h-3.5 bg-white rounded-full shadow-lg transform transition-transform duration-300 ${isManual ? 'left-1' : 'translate-x-4 left-0'}`}></div>
                                </div>
                            </button>
                        </div>

                        <h3 className="text-lg md:text-2xl 2xl:text-4xl font-bold leading-tight mb-2 transition-all duration-500 font-['Orbitron']">
                            {t.rich('speedTitle', {
                                strike: (chunks) => (
                                  <span className="relative inline-block">
                                    <span className={`transition-[color,filter] duration-500 ${isManual ? 'text-slate-200 blur-0' : 'text-slate-500 blur-[1px]'}`}>
                                      {chunks}
                                    </span>
                                    <span
                                      aria-hidden="true"
                                      className={`pointer-events-none absolute left-0 top-1/2 h-[2px] w-full -translate-y-1/2 bg-slate-500/70 shadow-[0_0_6px_rgba(148,163,184,0.6)] transform origin-left transition-[transform,opacity] duration-500 ease-out ${isManual ? 'scale-x-0 opacity-0' : 'scale-x-100 opacity-100'}`}
                                    />
                                  </span>
                                ),
                                highlight: (chunks) => (
                                  <span className={`text-transparent bg-clip-text bg-gradient-to-r from-rose-400 via-rose-500 to-emerald-400 transition-all duration-500 ${!isManual ? 'opacity-100 blur-0' : 'opacity-50 blur-[1px]'}`}>
                                    {chunks}
                                  </span>
                                ),
                                brTag: () => " ",
                                br: () => " "
                            })}
                        </h3>
                        <p className="text-slate-300 text-[11px] md:text-xs 2xl:text-lg leading-relaxed w-full md:w-2/3">
                            {t('speedDescription')}
                        </p>
                    </div>

                    {/* Canvas Visualization */}
                    <div className="absolute bottom-0 left-0 right-0 h-20 w-full z-0 pointer-events-none opacity-60">
                        <canvas ref={canvasRef} className="w-full h-full" width="734" height="192"></canvas>
                    </div>

                    {/* Background Gradient overlay for text readability */}
                    <div className="absolute inset-0 bg-gradient-to-t from-slate-950 via-transparent to-transparent z-0 pointer-events-none"></div>
                </ScrollReveal>

                {/* Card 2: Visual Interface Scan - Spans 5 cols */}
                <ScrollReveal
                    className="md:col-span-5 bg-slate-900/60 backdrop-blur-md border border-slate-800 rounded-3xl relative overflow-hidden group min-h-[160px] 2xl:min-h-[240px] transition-transform duration-300 hover:-translate-y-1 hover:border-rose-500/70 hover:ring-1 hover:ring-rose-500/35"
                    delay={0.15}
                >
                    <img
                        src="/landing/benefits/hours_to_minutes.webp"
                        alt="Piroola Interface"
                        className="absolute inset-0 w-full h-full object-cover transition-transform duration-700 group-hover:scale-110 opacity-80 group-hover:opacity-40"
                    />
                    <div className="absolute inset-0 bg-slate-950/30 group-hover:bg-slate-950/80 transition-colors duration-500 z-10"></div>

                    {/* Scan Animation Line */}
                    <div className="absolute top-0 left-0 w-full h-[2px] bg-emerald-400 shadow-[0_0_15px_rgba(52,211,153,0.75)] z-20 animate-[scan_3s_ease-in-out_infinite] opacity-0 group-hover:opacity-100"></div>
                    <style jsx>{`
                        @keyframes scan {
                            0% { top: 0%; opacity: 0; }
                            10% { opacity: 1; }
                            90% { opacity: 1; }
                            100% { top: 100%; opacity: 0; }
                        }
                    `}</style>

                    <div className="absolute bottom-0 left-0 p-6 z-30 translate-y-3 group-hover:translate-y-0 transition-transform duration-500">
                        <h3 className="text-xl md:text-2xl font-bold text-white mb-2 font-['Orbitron']">{t('deepAnalysisTitle')}</h3>
                        <ul className="space-y-1.5 text-xs md:text-sm text-slate-300 opacity-0 group-hover:opacity-100 transition-opacity duration-500 delay-100">
                            <li className="flex items-center"><CheckCircleIcon className="w-4 h-4 text-emerald-400 mr-2" /> {t('deepAnalysisPoints.0')}</li>
                            <li className="flex items-center"><CheckCircleIcon className="w-4 h-4 text-emerald-400 mr-2" /> {t('deepAnalysisPoints.1')}</li>
                            <li className="flex items-center"><CheckCircleIcon className="w-4 h-4 text-emerald-400 mr-2" /> {t('deepAnalysisPoints.2')}</li>
                        </ul>
                    </div>
                </ScrollReveal>

                {/* Card 3: Quality Spectrum - Spans 4 cols */}
                <ScrollReveal
                    className="md:col-span-4 bg-slate-900/60 backdrop-blur-md border border-slate-800 rounded-3xl p-3 relative overflow-hidden flex flex-col justify-end min-h-[110px] group transition-transform duration-300 hover:-translate-y-1 hover:border-rose-500/70 hover:ring-1 hover:ring-rose-500/35"
                    delay={0.2}
                >
                    <img
                        src="/landing/benefits/accesible_quality.webp"
                        alt="Spectrum Analyzer"
                        className="absolute inset-0 w-full h-full object-cover opacity-60 transition-opacity duration-500 group-hover:opacity-80"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/40 to-transparent z-10"></div>
                    <div className="relative z-20">
                        <div className="inline-flex items-center px-2 py-0.5 rounded bg-rose-500/20 border border-rose-500/30 text-rose-300 text-[10px] font-bold uppercase tracking-wider mb-1.5">
                            {t('qualityBadge')}
                        </div>
                        <h3 className="text-lg font-bold text-white font-['Orbitron']">{t('qualityTitle')}</h3>
                        <p className="text-xs text-slate-400 mt-1 line-clamp-2">{t('qualityDescription')}</p>
                    </div>
                </ScrollReveal>

                <div className="grid grid-cols-2 gap-3 md:contents">
                    {/* Card 4: Feature List - Spans 4 cols */}
                    <ScrollReveal
                        className="md:col-span-4 bg-slate-900/60 backdrop-blur-md border border-slate-800 rounded-3xl p-2 sm:p-3 flex flex-col min-h-[120px] sm:min-h-[140px] transition-transform duration-300 hover:-translate-y-1 hover:border-rose-500/70 hover:ring-1 hover:ring-rose-500/35"
                        delay={0.25}
                    >
                        <h3 className="text-sm sm:text-base 2xl:text-lg font-bold text-white mb-1.5 sm:mb-2 flex items-center font-['Orbitron']">
                            <AdjustmentsVerticalIcon className="w-3 h-3 sm:w-3.5 sm:h-3.5 mr-2 text-emerald-400" />
                            {t('toolkitTitle')}
                        </h3>
                        <div className="space-y-0.5 sm:space-y-1 custom-scrollbar overflow-y-hidden max-h-[110px] sm:max-h-[120px] pr-1">
                            {/* Feature Item */}
                            <div className="group flex items-center gap-1.5 sm:gap-2 p-0.5 sm:p-1 rounded-lg hover:bg-white/5 transition-colors cursor-default">
                                <div className="w-5 h-5 sm:w-6 sm:h-6 rounded-full bg-emerald-500/20 flex items-center justify-center shrink-0 group-hover:bg-emerald-500 group-hover:text-white transition-colors text-emerald-400">
                                    <ArrowsRightLeftIcon className="w-2.5 h-2.5 sm:w-3 sm:h-3" />
                                </div>
                                <h4 className="text-[10px] sm:text-xs 2xl:text-sm font-semibold text-slate-200">{t('toolkitItems.0.title')}</h4>
                            </div>
                            {/* Feature Item */}
                            <div className="group flex items-center gap-1.5 sm:gap-2 p-0.5 sm:p-1 rounded-lg hover:bg-white/5 transition-colors cursor-default">
                                <div className="w-5 h-5 sm:w-6 sm:h-6 rounded-full bg-emerald-500/20 flex items-center justify-center shrink-0 group-hover:bg-emerald-500 group-hover:text-white transition-colors text-emerald-400">
                                    <AdjustmentsVerticalIcon className="w-2.5 h-2.5 sm:w-3 sm:h-3" />
                                </div>
                                <h4 className="text-[10px] sm:text-xs 2xl:text-sm font-semibold text-slate-200">{t('toolkitItems.1.title')}</h4>
                            </div>
                            {/* Feature Item */}
                            <div className="group flex items-center gap-1.5 sm:gap-2 p-0.5 sm:p-1 rounded-lg hover:bg-white/5 transition-colors cursor-default">
                                <div className="w-5 h-5 sm:w-6 sm:h-6 rounded-full bg-emerald-500/20 flex items-center justify-center shrink-0 group-hover:bg-emerald-500 group-hover:text-white transition-colors text-emerald-400">
                                    <SpeakerWaveIcon className="w-2.5 h-2.5 sm:w-3 sm:h-3" />
                                </div>
                                <h4 className="text-[10px] sm:text-xs 2xl:text-sm font-semibold text-slate-200">{t('toolkitItems.2.title')}</h4>
                            </div>
                        </div>
                    </ScrollReveal>

                    {/* Card 5: Export Targets - Spans 4 cols */}
                    <ScrollReveal
                        className="md:col-span-4 bg-slate-900/60 backdrop-blur-md border border-slate-800 rounded-3xl p-2 sm:p-3 flex flex-col justify-between relative overflow-hidden min-h-[120px] sm:min-h-[110px] transition-transform duration-300 hover:-translate-y-1 hover:border-rose-500/70 hover:ring-1 hover:ring-rose-500/35"
                        delay={0.3}
                    >
                        {/* Abstract BG */}
                        <div className="absolute top-0 right-0 w-32 h-32 bg-rose-500/10 rounded-full blur-3xl -mr-10 -mt-10"></div>

                        <h3 className="text-sm sm:text-base 2xl:text-lg font-bold text-white mb-1 sm:mb-1.5 relative z-10 font-['Orbitron']">{t('readyForWorldTitle')}</h3>
                        <p className="text-[10px] sm:text-xs 2xl:text-sm text-slate-400 mb-2 sm:mb-3 relative z-10">{t('readyForWorldDesc')}</p>

                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5 sm:gap-2 relative z-10">
                            <div className="flex items-center justify-center p-1.5 sm:p-2 rounded-full opacity-80 hover:opacity-100 hover:scale-105 transition-all duration-300">
                                <svg className="w-5 h-5 sm:w-6 sm:h-6 text-[#1ED760]" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                                    <path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z" />
                                </svg>
                                <span className="sr-only">Spotify</span>
                            </div>
                            <div className="flex items-center justify-center p-1.5 sm:p-2 rounded-full opacity-80 hover:opacity-100 hover:scale-105 transition-all duration-300">
                                <svg className="w-6 h-4 sm:w-7 sm:h-5 text-[#FF1A2D]" viewBox="0 0 576 512" fill="currentColor" aria-hidden="true">
                                    <path d="M451.46 244.71H576V172H451.46zm0-173.89v72.67H576V70.82zm0 275.06H576V273.2H451.46zM0 447.09h124.54v-72.67H0zm150.47 0H275v-72.67H150.47zm150.52 0H425.53v-72.67H301zm150.47 0H576v-72.67H451.46zM301 345.88h124.53V273.2H301zm-150.52 0H275V273.2H150.47zm0-101.17H275V172H150.47z" />
                                </svg>
                                <span className="sr-only">Deezer</span>
                            </div>
                            <div className="flex items-center justify-center p-1.5 sm:p-2 rounded-full opacity-80 hover:opacity-100 hover:scale-105 transition-all duration-300">
                                <svg className="w-5 h-5 sm:w-6 sm:h-6 text-[#FF5500]" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                                    <path d="M23.999 14.165c-.052 1.796-1.612 3.169-3.4 3.169h-8.18a.68.68 0 0 1-.675-.683V7.862a.747.747 0 0 1 .452-.724s.75-.513 2.333-.513a5.364 5.364 0 0 1 2.763.755 5.433 5.433 0 0 1 2.57 3.54c.282-.08.574-.121.868-.12.884 0 1.73.358 2.347.992s.948 1.49.922 2.373ZM10.721 8.421c.247 2.98.427 5.697 0 8.672a.264.264 0 0 1-.53 0c-.395-2.946-.22-5.718 0-8.672a.264.264 0 0 1 .53 0ZM9.072 9.448c.285 2.659.37 4.986-.006 7.655a.277.277 0 0 1-.55 0c-.331-2.63-.256-5.02 0-7.655a.277.277 0 0 1 .556 0Zm-1.663-.257c.27 2.726.39 5.171 0 7.904a.266.266 0 0 1-.532 0c-.38-2.69-.257-5.21 0-7.904a.266.266 0 0 1 .532 0Zm-1.647.77a26.108 26.108 0 0 1-.008 7.147.272.272 0 0 1-.542 0 27.955 27.955 0 0 1 0-7.147.275.275 0 0 1 .55 0Zm-1.67 1.769c.421 1.865.228 3.5-.029 5.388a.257.257 0 0 1-.514 0c-.21-1.858-.398-3.549 0-5.389a.272.272 0 0 1 .543 0Zm-1.655-.273c.388 1.897.26 3.508-.01 5.412-.026.28-.514.283-.54 0-.244-1.878-.347-3.54-.01-5.412a.283.283 0 0 1 .56 0Zm-1.668.911c.4 1.268.257 2.292-.026 3.572a.257.257 0 0 1-.514 0c-.241-1.262-.354-2.312-.023-3.572a.283.283 0 0 1 .563 0Z" />
                                </svg>
                                <span className="sr-only">SoundCloud</span>
                            </div>
                            <div className="flex items-center justify-center p-1.5 sm:p-2 rounded-full opacity-80 hover:opacity-100 hover:scale-105 transition-all duration-300">
                                <svg className="w-5 h-5 sm:w-6 sm:h-6 text-slate-100" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                                    <path d="M12.012 3.992L8.008 7.996 4.004 3.992 0 7.996 4.004 12l4.004-4.004L12.012 12l-4.004 4.004 4.004 4.004 4.004-4.004L12.012 12l4.004-4.004-4.004-4.004zM16.042 7.996l3.979-3.979L24 7.996l-3.979 3.979z" />
                                </svg>
                                <span className="sr-only">Tidal</span>
                            </div>
                        </div>
                    </ScrollReveal>
                </div>
            </div>
        </div>
    </section>
  );
}
