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

        <div className="relative z-10 max-w-7xl w-full mx-auto space-y-12 px-6">

            {/* Header */}
            <div className="text-center space-y-4">
                <h2 className="text-4xl md:text-6xl font-display font-bold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-white via-violet-100 to-slate-400 pb-2">
                    {t('headerTitle')}
                </h2>
                <p className="text-slate-400 text-lg max-w-2xl mx-auto font-light">
                    {t('headerDesc')}
                </p>
            </div>

            {/* Bento Grid Layout */}
            <div className="grid grid-cols-1 md:grid-cols-12 gap-6 auto-rows-[minmax(200px,auto)]">

                {/* Card 1: AI Efficiency (Interactive) - Spans 7 cols */}
                <div className="md:col-span-7 bg-slate-900/60 backdrop-blur-md border border-slate-800 rounded-3xl p-8 relative overflow-hidden group flex flex-col justify-between min-h-[400px]">
                    <div className="relative z-10">
                        <div className="flex items-center justify-between mb-6">
                            <div className="inline-flex items-center px-3 py-1 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-bold uppercase tracking-wider">
                                <BoltIcon className="w-4 h-4 mr-1" /> {t('efficiencyBadge')}
                            </div>
                            {/* Interactive Toggle */}
                            <button
                                onClick={toggleAI}
                                className="flex items-center space-x-3 bg-slate-900/50 hover:bg-slate-800 border border-slate-700 rounded-full p-1 pl-4 transition-all duration-300 cursor-pointer"
                            >
                                <span className={`text-xs font-semibold uppercase tracking-wider transition-colors duration-300 ${isManual ? 'text-slate-400' : 'text-cyan-400'}`}>
                                    {isManual ? t('manual') : 'AUTO'}
                                </span>
                                <div className={`w-10 h-6 rounded-full relative transition-colors duration-300 ${isManual ? 'bg-slate-700' : 'bg-cyan-500'}`}>
                                    <div className={`absolute top-1 w-4 h-4 bg-white rounded-full shadow-lg transform transition-transform duration-300 ${isManual ? 'left-1' : 'translate-x-5 left-0'}`}></div>
                                </div>
                            </button>
                        </div>

                        <h3 className="text-3xl md:text-5xl font-display font-bold leading-tight mb-4 transition-all duration-500">
                            {t.rich('speedTitle', {
                                strike: (chunks) => <span className={`text-slate-500 line-through decoration-slate-600 decoration-2 transition-opacity duration-500 ${!isManual ? 'opacity-100' : 'opacity-100'}`}>{chunks}</span>,
                                highlight: (chunks) => <span className={`text-transparent bg-clip-text bg-gradient-to-r from-violet-400 to-cyan-400 transition-all duration-500 ${!isManual ? 'opacity-100 blur-0' : 'opacity-50 blur-[1px]'}`}>{chunks}</span>,
                                brTag: () => <br />
                            })}
                        </h3>
                        <p className="text-slate-300 leading-relaxed max-w-md">
                            {t('speedDescription')}
                        </p>
                    </div>

                    {/* Canvas Visualization */}
                    <div className="absolute bottom-0 left-0 right-0 h-48 w-full z-0 pointer-events-none opacity-60">
                        <canvas ref={canvasRef} className="w-full h-full" width="734" height="192"></canvas>
                    </div>

                    {/* Background Gradient overlay for text readability */}
                    <div className="absolute inset-0 bg-gradient-to-t from-slate-950 via-transparent to-transparent z-0 pointer-events-none"></div>
                </div>

                {/* Card 2: Visual Interface Scan - Spans 5 cols */}
                <div className="md:col-span-5 bg-slate-900/60 backdrop-blur-md border border-slate-800 rounded-3xl relative overflow-hidden group min-h-[400px]">
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

                    <div className="absolute bottom-0 left-0 p-8 z-30 translate-y-4 group-hover:translate-y-0 transition-transform duration-500">
                        <h3 className="text-2xl font-display font-bold text-white mb-2">{t('deepAnalysisTitle')}</h3>
                        <ul className="space-y-2 text-sm text-slate-300 opacity-0 group-hover:opacity-100 transition-opacity duration-500 delay-100">
                            <li className="flex items-center"><CheckCircleIcon className="w-4 h-4 text-cyan-400 mr-2" /> {t('deepAnalysisPoints.0')}</li>
                            <li className="flex items-center"><CheckCircleIcon className="w-4 h-4 text-cyan-400 mr-2" /> {t('deepAnalysisPoints.1')}</li>
                            <li className="flex items-center"><CheckCircleIcon className="w-4 h-4 text-cyan-400 mr-2" /> {t('deepAnalysisPoints.2')}</li>
                        </ul>
                    </div>
                </div>

                {/* Card 3: Quality Spectrum - Spans 4 cols */}
                <div className="md:col-span-4 bg-slate-900/60 backdrop-blur-md border border-slate-800 rounded-3xl p-6 relative overflow-hidden flex flex-col justify-end min-h-[240px] group">
                    <img
                        src="/accesible_quality.webp"
                        alt="Spectrum Analyzer"
                        className="absolute inset-0 w-full h-full object-cover opacity-60 transition-opacity duration-500 group-hover:opacity-80"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/40 to-transparent z-10"></div>
                    <div className="relative z-20">
                        <div className="inline-flex items-center px-2 py-1 rounded bg-amber-500/20 border border-amber-500/30 text-amber-500 text-[10px] font-bold uppercase tracking-wider mb-2">
                            {t('qualityBadge')}
                        </div>
                        <h3 className="text-xl font-display font-bold text-white">{t('qualityTitle')}</h3>
                        <p className="text-xs text-slate-400 mt-1 line-clamp-2">{t('qualityDescription')}</p>
                    </div>
                </div>

                {/* Card 4: Feature List - Spans 4 cols */}
                <div className="md:col-span-4 bg-slate-900/60 backdrop-blur-md border border-slate-800 rounded-3xl p-6 flex flex-col">
                    <h3 className="text-lg font-display font-bold text-white mb-4 flex items-center">
                        <AdjustmentsVerticalIcon className="w-5 h-5 mr-2 text-violet-400" />
                        {t('toolkitTitle')}
                    </h3>
                    <div className="space-y-3 custom-scrollbar overflow-y-auto max-h-[160px] pr-2">
                        {/* Feature Item */}
                        <div className="group flex items-start p-2 rounded-lg hover:bg-white/5 transition-colors cursor-default">
                            <div className="w-8 h-8 rounded-full bg-violet-500/20 flex items-center justify-center mr-3 shrink-0 group-hover:bg-violet-500 group-hover:text-white transition-colors text-violet-400">
                                <ArrowsRightLeftIcon className="w-4 h-4" />
                            </div>
                            <div>
                                <h4 className="text-sm font-semibold text-slate-200">{t('toolkitItems.0.title')}</h4>
                                <p className="text-xs text-slate-500">{t('toolkitItems.0.desc')}</p>
                            </div>
                        </div>
                        {/* Feature Item */}
                        <div className="group flex items-start p-2 rounded-lg hover:bg-white/5 transition-colors cursor-default">
                            <div className="w-8 h-8 rounded-full bg-violet-500/20 flex items-center justify-center mr-3 shrink-0 group-hover:bg-violet-500 group-hover:text-white transition-colors text-violet-400">
                                <AdjustmentsVerticalIcon className="w-4 h-4" />
                            </div>
                            <div>
                                <h4 className="text-sm font-semibold text-slate-200">{t('toolkitItems.1.title')}</h4>
                                <p className="text-xs text-slate-500">{t('toolkitItems.1.desc')}</p>
                            </div>
                        </div>
                        {/* Feature Item */}
                        <div className="group flex items-start p-2 rounded-lg hover:bg-white/5 transition-colors cursor-default">
                            <div className="w-8 h-8 rounded-full bg-violet-500/20 flex items-center justify-center mr-3 shrink-0 group-hover:bg-violet-500 group-hover:text-white transition-colors text-violet-400">
                                <SpeakerWaveIcon className="w-4 h-4" />
                            </div>
                            <div>
                                <h4 className="text-sm font-semibold text-slate-200">{t('toolkitItems.2.title')}</h4>
                                <p className="text-xs text-slate-500">{t('toolkitItems.2.desc')}</p>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Card 5: Export Targets - Spans 4 cols */}
                <div className="md:col-span-4 bg-slate-900/60 backdrop-blur-md border border-slate-800 rounded-3xl p-6 flex flex-col justify-between relative overflow-hidden">
                    {/* Abstract BG */}
                    <div className="absolute top-0 right-0 w-32 h-32 bg-violet-500/10 rounded-full blur-3xl -mr-10 -mt-10"></div>

                    <h3 className="text-lg font-display font-bold text-white mb-2 relative z-10">{t('readyForWorldTitle')}</h3>
                    <p className="text-xs text-slate-400 mb-6 relative z-10">{t('readyForWorldDesc')}</p>

                    <div className="grid grid-cols-2 gap-3 relative z-10">
                        <button className="flex flex-col items-center justify-center p-3 rounded-xl bg-[#1DB954]/10 hover:bg-[#1DB954]/20 border border-[#1DB954]/20 transition-all group cursor-default">
                            <svg className="w-6 h-6 mb-2 opacity-80 group-hover:opacity-100 group-hover:scale-110 transition-transform text-[#1DB954]" viewBox="0 0 24 24" fill="currentColor">
                                <path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.019.6-1.141 4.32-1.32 9.78-.6 13.5 1.62.42.181.6.719.3 1.141zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 14.82 1.14.54.3.719.96.42 1.5-.239.54-.899.72-1.44.36z"/>
                            </svg>
                            <span className="text-[10px] font-bold text-[#1DB954] uppercase tracking-wider">{t('spotify')}</span>
                        </button>
                        <button className="flex flex-col items-center justify-center p-3 rounded-xl bg-[#FB233B]/10 hover:bg-[#FB233B]/20 border border-[#FB233B]/20 transition-all group cursor-default">
                            <svg className="w-6 h-6 mb-2 text-[#FB233B] opacity-80 group-hover:opacity-100 group-hover:scale-110 transition-transform" viewBox="0 0 24 24" fill="currentColor">
                                <path d="M17.8 11.2c.1 0 .2 0 .3-.1.6-.4 1-1 1.2-1.7h-3c.2.7.7 1.3 1.5 1.8zM12 2C6.5 2 2 6.5 2 12s4.5 10 10 10 10-4.5 10-10S17.5 2 12 2zm4.7 15.3c-.5.6-1.1 1-1.8 1.3-.7.3-1.5.4-2.2.3-.8 0-1.5-.2-2.2-.6-.6-.4-1.1-.9-1.5-1.5-.4-.6-.6-1.3-.6-2 0-.8.2-1.5.5-2.2.4-.6.9-1.1 1.5-1.5.7-.4 1.4-.6 2.2-.6.7 0 1.5.1 2.2.4.6.3 1.1.8 1.6 1.3.1.2.2.3.2.5 0 .2-.1.4-.2.5-.2.1-.4.2-.6.2-.1 0-.3 0-.4-.1-.4-.3-.8-.5-1.3-.6-.5-.1-1-.1-1.5 0-.5.1-1 .3-1.4.6-.4.3-.7.7-.9 1.1-.2.5-.3 1-.3 1.5 0 .5.1 1 .3 1.5.2.4.6.8.9 1.1.4.3.9.5 1.4.6.5.1 1 .1 1.5 0 .5-.1.9-.3 1.3-.6.1-.1.2-.1.4-.1.2 0 .4.1.5.2.1.1.2.3.2.5 0 .1-.1.3-.2.4z"></path>
                            </svg>
                            <span className="text-[10px] font-bold text-[#FB233B] uppercase tracking-wider">{t('appleMusic')}</span>
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </section>
  );
}
