import { useRef, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import {
  BoltIcon,
  CheckCircleIcon,
  AdjustmentsVerticalIcon,
  ArrowsRightLeftIcon,
  SpeakerWaveIcon
} from "@heroicons/react/24/outline";

// Helper to draw a simulated equalizer animation
const drawEqualizer = (
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  isManual: boolean,
  frameCount: number
) => {
  ctx.clearRect(0, 0, width, height);

  const barCount = 48;
  const gap = Math.max(1, Math.floor(width / 200));
  const totalGap = gap * (barCount - 1);
  const barWidth = Math.max(2, (width - totalGap) / barCount);
  const t = frameCount * 0.06;
  const baseY = height - 4;
  const minHeight = height * (isManual ? 0.03 : 0.12);
  const maxHeight = height * (isManual ? 0.18 : 0.75);
  const modeAlpha = isManual ? 0.08 : 0.75;

  ctx.shadowBlur = isManual ? 0 : 12;

  for (let i = 0; i < barCount; i += 1) {
    const waveA = Math.sin(t + i * 0.35);
    const waveB = Math.sin(t * 0.6 + i * 0.18);
    const waveC = Math.sin(t * 1.3 + i * 0.05);
    const mix = (waveA * 0.6 + waveB * 0.3 + waveC * 0.1 + 1.5) / 3;
    const barHeight = Math.max(minHeight, minHeight + mix * maxHeight);
    const x = i * (barWidth + gap);
    const y = baseY - barHeight;
    const hue = 190 + (i / (barCount - 1)) * 70;
    const saturation = isManual ? 35 : 70;
    const lightness = isManual ? 55 : 60;
    const alpha = modeAlpha * (0.6 + 0.4 * Math.sin(t + i * 0.2));

    ctx.shadowColor = `hsla(${hue}, ${saturation}%, ${lightness}%, ${modeAlpha})`;
    ctx.fillStyle = `hsla(${hue}, ${saturation}%, ${lightness}%, ${alpha})`;
    ctx.fillRect(x, y, barWidth, barHeight);
  }

  ctx.shadowBlur = 0;
};


type BenefitsSectionProps = {
  className?: string;
};

export function BenefitsSection({ className }: BenefitsSectionProps) {
  const t = useTranslations('BenefitsSection');
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
           drawEqualizer(ctx, canvas.width, canvas.height, isManual, frameCountRef.current);
        }
      }
      frameCountRef.current += 1;
      requestRef.current = requestAnimationFrame(animate);
    };

    requestRef.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(requestRef.current);
  }, [isManual]);

  return (
    <section id="benefits" className={`py-24 relative overflow-hidden ${className || 'bg-slate-950'}`}>
        {/* Background Elements */}
        <div className="absolute top-0 left-0 w-full h-full bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-slate-900 via-slate-950 to-slate-950 pointer-events-none"></div>

        <div className="relative z-10 max-w-7xl w-full mx-auto space-y-6 px-6">

            {/* Header */}
            <div className="text-center space-y-4">
                <h2 className="text-2xl md:text-4xl font-display font-bold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-white via-violet-100 to-slate-400 pb-2">
                    {t('headerTitle')}
                </h2>
                <p className="text-slate-400 text-sm max-w-2xl mx-auto font-light">
                    {t('headerDesc')}
                </p>
            </div>

            {/* Bento Grid Layout */}
            <div className="grid grid-cols-1 md:grid-cols-12 gap-6 auto-rows-[minmax(110px,auto)]">

                {/* Card 1: AI Efficiency (Interactive) - Spans 7 cols */}
                <div className="md:col-span-7 bg-slate-900/60 backdrop-blur-md border border-slate-800 rounded-3xl p-4 relative overflow-hidden group flex flex-col justify-between min-h-[200px]">
                    <div className="relative z-10">
                        <div className="flex items-center justify-between mb-3">
                            <div className="inline-flex items-center px-3 py-1 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-bold uppercase tracking-wider">
                                <BoltIcon className="w-4 h-4 mr-1" /> {t('efficiencyBadge')}
                            </div>
                            {/* Interactive Toggle */}
                            <button
                                onClick={toggleAI}
                                className="flex items-center space-x-2 bg-slate-900/50 hover:bg-slate-800 border border-slate-700 rounded-full p-1 pl-3 transition-all duration-300 cursor-pointer"
                            >
                                <span className={`text-[11px] font-semibold uppercase tracking-wider transition-colors duration-300 ${isManual ? 'text-slate-400' : 'text-cyan-400'}`}>
                                    {isManual ? t('manual') : 'AUTO'}
                                </span>
                                <div className={`w-9 h-5 rounded-full relative transition-colors duration-300 ${isManual ? 'bg-slate-700' : 'bg-cyan-500'}`}>
                                    <div className={`absolute top-0.5 w-3.5 h-3.5 bg-white rounded-full shadow-lg transform transition-transform duration-300 ${isManual ? 'left-1' : 'translate-x-4 left-0'}`}></div>
                                </div>
                            </button>
                        </div>

                        <h3 className="text-lg md:text-2xl font-display font-bold leading-tight mb-2 transition-all duration-500">
                            {t.rich('speedTitle', {
                                strike: (chunks) => <span className={`text-slate-500 line-through decoration-slate-600 decoration-2 transition-opacity duration-500 ${!isManual ? 'opacity-100' : 'opacity-100'}`}>{chunks}</span>,
                                highlight: (chunks) => <span className={`text-transparent bg-clip-text bg-gradient-to-r from-violet-400 to-cyan-400 transition-all duration-500 ${!isManual ? 'opacity-100 blur-0' : 'opacity-50 blur-[1px]'}`}>{chunks}</span>,
                                brTag: () => " ",
                                br: () => " "
                            })}
                        </h3>
                        <p className="text-slate-300 text-[11px] md:text-xs leading-relaxed w-full md:w-2/3">
                            {t('speedDescription')}
                        </p>
                    </div>

                    {/* Canvas Visualization */}
                    <div className="absolute bottom-0 left-0 right-0 h-20 w-full z-0 pointer-events-none opacity-60">
                        <canvas ref={canvasRef} className="w-full h-full" width="734" height="192"></canvas>
                    </div>

                    {/* Background Gradient overlay for text readability */}
                    <div className="absolute inset-0 bg-gradient-to-t from-slate-950 via-transparent to-transparent z-0 pointer-events-none"></div>
                </div>

                {/* Card 2: Visual Interface Scan - Spans 5 cols */}
                <div className="md:col-span-5 bg-slate-900/60 backdrop-blur-md border border-slate-800 rounded-3xl relative overflow-hidden group min-h-[200px]">
                    <img
                        src="/hours_to_minutes.webp"
                        alt="Piroola Interface"
                        className="absolute inset-0 w-full h-full object-cover transition-transform duration-700 group-hover:scale-110 opacity-80 group-hover:opacity-40"
                    />
                    <div className="absolute inset-0 bg-slate-950/30 group-hover:bg-slate-950/80 transition-colors duration-500 z-10"></div>

                    {/* Scan Animation Line */}
                    <div className="absolute top-0 left-0 w-full h-[2px] bg-cyan-500 shadow-[0_0_15px_#06b6d4] z-20 animate-[scan_3s_ease-in-out_infinite] opacity-0 group-hover:opacity-100"></div>
                    <style jsx>{`
                        @keyframes scan {
                            0% { top: 0%; opacity: 0; }
                            10% { opacity: 1; }
                            90% { opacity: 1; }
                            100% { top: 100%; opacity: 0; }
                        }
                    `}</style>

                    <div className="absolute bottom-0 left-0 p-6 z-30 translate-y-3 group-hover:translate-y-0 transition-transform duration-500">
                        <h3 className="text-xl md:text-2xl font-display font-bold text-white mb-2">{t('deepAnalysisTitle')}</h3>
                        <ul className="space-y-1.5 text-xs md:text-sm text-slate-300 opacity-0 group-hover:opacity-100 transition-opacity duration-500 delay-100">
                            <li className="flex items-center"><CheckCircleIcon className="w-4 h-4 text-cyan-400 mr-2" /> {t('deepAnalysisPoints.0')}</li>
                            <li className="flex items-center"><CheckCircleIcon className="w-4 h-4 text-cyan-400 mr-2" /> {t('deepAnalysisPoints.1')}</li>
                            <li className="flex items-center"><CheckCircleIcon className="w-4 h-4 text-cyan-400 mr-2" /> {t('deepAnalysisPoints.2')}</li>
                        </ul>
                    </div>
                </div>

                {/* Card 3: Quality Spectrum - Spans 4 cols */}
                <div className="md:col-span-4 bg-slate-900/60 backdrop-blur-md border border-slate-800 rounded-3xl p-3 relative overflow-hidden flex flex-col justify-end min-h-[110px] group">
                    <img
                        src="/accesible_quality.webp"
                        alt="Spectrum Analyzer"
                        className="absolute inset-0 w-full h-full object-cover opacity-60 transition-opacity duration-500 group-hover:opacity-80"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/40 to-transparent z-10"></div>
                    <div className="relative z-20">
                        <div className="inline-flex items-center px-2 py-0.5 rounded bg-amber-500/20 border border-amber-500/30 text-amber-500 text-[8px] font-bold uppercase tracking-wider mb-1.5">
                            {t('qualityBadge')}
                        </div>
                        <h3 className="text-base font-display font-bold text-white">{t('qualityTitle')}</h3>
                        <p className="text-[10px] text-slate-400 mt-1 line-clamp-2">{t('qualityDescription')}</p>
                    </div>
                </div>

                {/* Card 4: Feature List - Spans 4 cols */}
                <div className="md:col-span-4 bg-slate-900/60 backdrop-blur-md border border-slate-800 rounded-3xl p-3 flex flex-col min-h-[140px]">
                    <h3 className="text-sm font-display font-bold text-white mb-2 flex items-center">
                        <AdjustmentsVerticalIcon className="w-3.5 h-3.5 mr-2 text-violet-400" />
                        {t('toolkitTitle')}
                    </h3>
                    <div className="space-y-1 custom-scrollbar overflow-y-hidden max-h-[120px] pr-1">
                        {/* Feature Item */}
                        <div className="group flex items-center gap-2 p-1 rounded-lg hover:bg-white/5 transition-colors cursor-default">
                            <div className="w-6 h-6 rounded-full bg-violet-500/20 flex items-center justify-center shrink-0 group-hover:bg-violet-500 group-hover:text-white transition-colors text-violet-400">
                                <ArrowsRightLeftIcon className="w-3 h-3" />
                            </div>
                            <h4 className="text-xs font-semibold text-slate-200">{t('toolkitItems.0.title')}</h4>
                        </div>
                        {/* Feature Item */}
                        <div className="group flex items-center gap-2 p-1 rounded-lg hover:bg-white/5 transition-colors cursor-default">
                            <div className="w-6 h-6 rounded-full bg-violet-500/20 flex items-center justify-center shrink-0 group-hover:bg-violet-500 group-hover:text-white transition-colors text-violet-400">
                                <AdjustmentsVerticalIcon className="w-3 h-3" />
                            </div>
                            <h4 className="text-xs font-semibold text-slate-200">{t('toolkitItems.1.title')}</h4>
                        </div>
                        {/* Feature Item */}
                        <div className="group flex items-center gap-2 p-1 rounded-lg hover:bg-white/5 transition-colors cursor-default">
                            <div className="w-6 h-6 rounded-full bg-violet-500/20 flex items-center justify-center shrink-0 group-hover:bg-violet-500 group-hover:text-white transition-colors text-violet-400">
                                <SpeakerWaveIcon className="w-3 h-3" />
                            </div>
                            <h4 className="text-xs font-semibold text-slate-200">{t('toolkitItems.2.title')}</h4>
                        </div>
                    </div>
                </div>

                {/* Card 5: Export Targets - Spans 4 cols */}
                <div className="md:col-span-4 bg-slate-900/60 backdrop-blur-md border border-slate-800 rounded-3xl p-3 flex flex-col justify-between relative overflow-hidden min-h-[110px]">
                    {/* Abstract BG */}
                    <div className="absolute top-0 right-0 w-32 h-32 bg-violet-500/10 rounded-full blur-3xl -mr-10 -mt-10"></div>

                    <h3 className="text-sm font-display font-bold text-white mb-1.5 relative z-10">{t('readyForWorldTitle')}</h3>
                    <p className="text-[10px] text-slate-400 mb-3 relative z-10">{t('readyForWorldDesc')}</p>

                    <div className="grid grid-cols-4 gap-2 relative z-10">
                        <div className="flex items-center justify-center p-2 rounded-lg bg-[#1DB954]/10 border border-[#1DB954]/20">
                            <svg className="w-4 h-4 text-[#1DB954]" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                                <path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z" />
                            </svg>
                            <span className="sr-only">Spotify</span>
                        </div>
                        <div className="flex items-center justify-center p-2 rounded-lg bg-[#A4CC35]/10 border border-[#A4CC35]/20">
                            <svg className="w-4 h-4 text-[#A4CC35]" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                                <path d="M18.81 4.16v3.03H24V4.16h-5.19zM6.27 8.38v3.027h5.189V8.38h-5.19zm12.54 0v3.027H24V8.38h-5.19zM6.27 12.594v3.027h5.189v-3.027h-5.19zm6.271 0v3.027h5.19v-3.027h-5.19zm6.27 0v3.027H24v-3.027h-5.19zM0 16.81v3.029h5.19v-3.03H0zm6.27 0v3.029h5.189v-3.03h-5.19zm6.271 0v3.029h5.19v-3.03h-5.19zm6.27 0v3.029H24v-3.03h-5.19Z" />
                            </svg>
                            <span className="sr-only">Deezer</span>
                        </div>
                        <div className="flex items-center justify-center p-2 rounded-lg bg-[#FF5500]/10 border border-[#FF5500]/20">
                            <svg className="w-4 h-4 text-[#FF5500]" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                                <path d="M23.999 14.165c-.052 1.796-1.612 3.169-3.4 3.169h-8.18a.68.68 0 0 1-.675-.683V7.862a.747.747 0 0 1 .452-.724s.75-.513 2.333-.513a5.364 5.364 0 0 1 2.763.755 5.433 5.433 0 0 1 2.57 3.54c.282-.08.574-.121.868-.12.884 0 1.73.358 2.347.992s.948 1.49.922 2.373ZM10.721 8.421c.247 2.98.427 5.697 0 8.672a.264.264 0 0 1-.53 0c-.395-2.946-.22-5.718 0-8.672a.264.264 0 0 1 .53 0ZM9.072 9.448c.285 2.659.37 4.986-.006 7.655a.277.277 0 0 1-.55 0c-.331-2.63-.256-5.02 0-7.655a.277.277 0 0 1 .556 0Zm-1.663-.257c.27 2.726.39 5.171 0 7.904a.266.266 0 0 1-.532 0c-.38-2.69-.257-5.21 0-7.904a.266.266 0 0 1 .532 0Zm-1.647.77a26.108 26.108 0 0 1-.008 7.147.272.272 0 0 1-.542 0 27.955 27.955 0 0 1 0-7.147.275.275 0 0 1 .55 0Zm-1.67 1.769c.421 1.865.228 3.5-.029 5.388a.257.257 0 0 1-.514 0c-.21-1.858-.398-3.549 0-5.389a.272.272 0 0 1 .543 0Zm-1.655-.273c.388 1.897.26 3.508-.01 5.412-.026.28-.514.283-.54 0-.244-1.878-.347-3.54-.01-5.412a.283.283 0 0 1 .56 0Zm-1.668.911c.4 1.268.257 2.292-.026 3.572a.257.257 0 0 1-.514 0c-.241-1.262-.354-2.312-.023-3.572a.283.283 0 0 1 .563 0Z" />
                            </svg>
                            <span className="sr-only">SoundCloud</span>
                        </div>
                        <div className="flex items-center justify-center p-2 rounded-lg bg-[#00D2FF]/10 border border-[#00D2FF]/20">
                            <svg className="w-4 h-4 text-[#00D2FF]" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                                <path d="M12.012 3.992L8.008 7.996 4.004 3.992 0 7.996 4.004 12l4.004-4.004L12.012 12l-4.004 4.004 4.004 4.004 4.004-4.004L12.012 12l4.004-4.004-4.004-4.004zM16.042 7.996l3.979-3.979L24 7.996l-3.979 3.979z" />
                            </svg>
                            <span className="sr-only">Tidal</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </section>
  );
}
