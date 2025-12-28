import { useRef, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import {
  BoltIcon,
  CheckCircleIcon,
  AdjustmentsVerticalIcon,
  ArrowsRightLeftIcon,
  SpeakerWaveIcon
} from "@heroicons/react/24/outline";

// Helper to draw a simulated waveform
const drawWaveform = (
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  isManual: boolean,
  frameCount: number
) => {
  ctx.clearRect(0, 0, width, height);

  // Settings based on mode
  const color = isManual ? '#64748b' : '#22d3ee'; // Slate-500 vs Cyan-400
  const lineWidth = 2;
  const amplitude = isManual ? height * 0.15 : height * 0.35; // Manual is quiet/dynamic, AI is mastered/loud
  const frequency = 0.02;
  const speed = 0.1;

  ctx.beginPath();
  ctx.lineWidth = lineWidth;
  ctx.strokeStyle = color;

  const centerY = height / 2;

  // Draw multiple sine waves combined to simulate audio
  for (let x = 0; x < width; x++) {
    const t = x * frequency + frameCount * speed;
    let y = centerY;

    if (isManual) {
        // Messy, irregular wave
        y += Math.sin(t) * amplitude * (Math.sin(t * 0.5) + 0.5);
        y += Math.sin(t * 2.5) * (amplitude * 0.3);
    } else {
        // Maximized, consistent wave (mastered)
        y += Math.sin(t) * amplitude;
        y += Math.sin(t * 3) * (amplitude * 0.2);
        // Soft clipping simulation
        if (y > centerY + amplitude * 0.9) y = centerY + amplitude * 0.9 + Math.random();
        if (y < centerY - amplitude * 0.9) y = centerY - amplitude * 0.9 - Math.random();
    }

    if (x === 0) {
      ctx.moveTo(x, y);
    } else {
      ctx.lineTo(x, y);
    }
  }

  ctx.stroke();

  // Draw a second mirrored line for "stereo" look or just fill
  ctx.beginPath();
  ctx.strokeStyle = isManual ? 'rgba(100, 116, 139, 0.3)' : 'rgba(34, 211, 238, 0.3)';
  for (let x = 0; x < width; x++) {
    const t = x * frequency + frameCount * speed;
    let y = centerY;
    // Mirrored slightly
     if (isManual) {
        y -= Math.sin(t) * amplitude * (Math.sin(t * 0.5) + 0.5);
    } else {
        y -= Math.sin(t) * amplitude;
    }

    if (x === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.stroke();
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
           drawWaveform(ctx, canvas.width, canvas.height, isManual, frameCountRef.current);
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
                <h2 className="text-3xl md:text-5xl font-display font-bold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-white via-violet-100 to-slate-400 pb-2">
                    {t('headerTitle')}
                </h2>
                <p className="text-slate-400 text-base max-w-2xl mx-auto font-light">
                    {t('headerDesc')}
                </p>
            </div>

            {/* Bento Grid Layout */}
            <div className="grid grid-cols-1 md:grid-cols-12 gap-6 auto-rows-[minmax(110px,auto)]">

                {/* Card 1: AI Efficiency (Interactive) - Spans 7 cols */}
                <div className="md:col-span-7 bg-slate-900/60 backdrop-blur-md border border-slate-800 rounded-3xl p-5 relative overflow-hidden group flex flex-col justify-between min-h-[220px]">
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

                        <h3 className="text-xl md:text-3xl font-display font-bold leading-tight mb-2 transition-all duration-500">
                            {t.rich('speedTitle', {
                                strike: (chunks) => <span className={`text-slate-500 line-through decoration-slate-600 decoration-2 transition-opacity duration-500 ${!isManual ? 'opacity-100' : 'opacity-100'}`}>{chunks}</span>,
                                highlight: (chunks) => <span className={`text-transparent bg-clip-text bg-gradient-to-r from-violet-400 to-cyan-400 transition-all duration-500 ${!isManual ? 'opacity-100 blur-0' : 'opacity-50 blur-[1px]'}`}>{chunks}</span>,
                                brTag: () => <br />
                            })}
                        </h3>
                        <p className="text-slate-300 text-xs md:text-sm leading-relaxed max-w-2xl">
                            {t('speedDescription')}
                        </p>
                    </div>

                    {/* Canvas Visualization */}
                    <div className="absolute bottom-0 left-0 right-0 h-24 w-full z-0 pointer-events-none opacity-60">
                        <canvas ref={canvasRef} className="w-full h-full" width="734" height="192"></canvas>
                    </div>

                    {/* Background Gradient overlay for text readability */}
                    <div className="absolute inset-0 bg-gradient-to-t from-slate-950 via-transparent to-transparent z-0 pointer-events-none"></div>
                </div>

                {/* Card 2: Visual Interface Scan - Spans 5 cols */}
                <div className="md:col-span-5 bg-slate-900/60 backdrop-blur-md border border-slate-800 rounded-3xl relative overflow-hidden group min-h-[220px]">
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
                <div className="md:col-span-4 bg-slate-900/60 backdrop-blur-md border border-slate-800 rounded-3xl p-3 flex flex-col">
                    <h3 className="text-sm font-display font-bold text-white mb-2 flex items-center">
                        <AdjustmentsVerticalIcon className="w-3.5 h-3.5 mr-2 text-violet-400" />
                        {t('toolkitTitle')}
                    </h3>
                    <div className="space-y-1 custom-scrollbar overflow-y-auto max-h-[96px] pr-1">
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
                                <path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.019.6-1.141 4.32-1.32 9.78-.6 13.5 1.62.42.181.6.719.3 1.141zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 14.82 1.14.54.3.719.96.42 1.5-.239.54-.899.72-1.44.36z"/>
                            </svg>
                            <span className="sr-only">Spotify</span>
                        </div>
                        <div className="flex items-center justify-center p-2 rounded-lg bg-[#FB233B]/10 border border-[#FB233B]/20">
                            <svg className="w-4 h-4 text-[#FB233B]" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                                <path d="M14 4v9.2a2.3 2.3 0 1 1-1-2V7.3l-5 1.2v6.3a2.3 2.3 0 1 1-1-2V6.4L14 4z"/>
                            </svg>
                            <span className="sr-only">Apple Music</span>
                        </div>
                        <div className="flex items-center justify-center p-2 rounded-lg bg-[#FF0000]/10 border border-[#FF0000]/20">
                            <svg className="w-4 h-4 text-[#FF0000]" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                                <path d="M21.6 7.2c-.2-.8-.8-1.4-1.6-1.6C18.3 5 12 5 12 5s-6.3 0-8 0.6c-.8.2-1.4.8-1.6 1.6C2 8.9 2 12 2 12s0 3.1.4 4.8c.2.8.8 1.4 1.6 1.6 1.7.6 8 .6 8 .6s6.3 0 8-.6c.8-.2 1.4-.8 1.6-1.6.4-1.7.4-4.8.4-4.8s0-3.1-.4-4.8zM10 15V9l5 3-5 3z"/>
                            </svg>
                            <span className="sr-only">YouTube Music</span>
                        </div>
                        <div className="flex items-center justify-center p-2 rounded-lg bg-[#00A8E1]/10 border border-[#00A8E1]/20">
                            <svg className="w-4 h-4 text-[#00A8E1]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                                <path d="M5 15c3 2.2 11 2.2 14 0" />
                                <path d="M16 14.5l2.2.5-1.2-2" />
                            </svg>
                            <span className="sr-only">Amazon Music</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </section>
  );
}
