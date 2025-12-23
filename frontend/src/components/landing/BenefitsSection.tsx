import { LazyVideo } from "../LazyVideo";
import { useTranslations } from "next-intl";
import { BoltIcon, StarIcon } from "@heroicons/react/24/solid";

type BenefitsSectionProps = {
  className?: string;
};

// SVG Icons for Spotify and Apple Music
const SpotifyIcon = ({ className }: { className?: string }) => (
  <svg
    viewBox="0 0 24 24"
    fill="currentColor"
    className={className}
    aria-hidden="true"
    focusable="false"
  >
    <path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.019.6-1.141 4.32-1.32 9.78-.6 13.5 1.62.42.181.6.719.3 1.141zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 14.82 1.14.54.3.719.96.42 1.5-.239.54-.899.72-1.44.36z"/>
  </svg>
);

const AppleMusicIcon = ({ className }: { className?: string }) => (
  <svg
    viewBox="0 0 24 24"
    fill="currentColor"
    className={className}
    aria-hidden="true"
    focusable="false"
  >
    {/* Generic Musical Note for Apple Music */}
    <path d="M15 4v7.71c0 2.22-1.57 3.59-3.21 3.59-1.55 0-2.79-1.19-2.79-2.87 0-1.63 1.35-2.79 2.91-2.79.46 0 .91.1 1.32.28V6.44L9.04 7.62v7.71c0 2.22-1.57 3.59-3.21 3.59-1.55 0-2.79-1.19-2.79-2.87 0-1.63 1.35-2.79 2.91-2.79.46 0 .91.1 1.32.28V4l12-3.6V4z"/>
  </svg>
);


export function BenefitsSection({ className }: BenefitsSectionProps) {
    const t = useTranslations('BenefitsSection');

    return (
      <section className={`py-12 md:py-24 overflow-hidden ${className || 'bg-slate-950'}`}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">

          {/* Benefit 1: Speed */}
          <div className="flex flex-col lg:flex-row items-center gap-10 md:gap-16 mb-12 md:mb-24">
            <div className="flex-1 order-2 lg:order-1">
               {/* Image Placeholder */}
               <div className="w-full aspect-video rounded-2xl bg-gradient-to-br from-slate-800 to-slate-900 border border-slate-700 flex items-center justify-center relative shadow-2xl overflow-hidden group">
                  <LazyVideo
                    src="/master_interface.webm"
                    poster="/result.webp"
                    className="w-full h-full object-cover"
                  />
               </div>
            </div>
            <div className="flex-1 order-1 lg:order-2">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-teal-500/10 border border-teal-500/20 text-teal-400 text-xs font-semibold tracking-wider mb-6">
                 <BoltIcon className="w-4 h-4" aria-hidden="true" />
                 {t('efficiencyBadge')}
              </div>

              <h2 className="text-4xl sm:text-5xl font-bold text-white mb-6 leading-[1.05] tracking-[-0.02em]">
                {t.rich('speedTitle', {
                  highlight: (chunks) => <span className="text-transparent bg-clip-text bg-gradient-to-r from-teal-400 to-violet-500">{chunks}</span>
                })}
              </h2>
              <p className="text-lg text-slate-300 mb-8 leading-[1.7]">
                {t('speedDescription')}
              </p>
              <ul className="space-y-4 text-slate-300">
                <li className="flex items-center gap-3">
                  <span className="h-2 w-2 rounded-full bg-teal-500 shadow-[0_0_10px_rgba(20,184,166,0.5)]" />
                  {t('speedPoints.0')}
                </li>
                <li className="flex items-center gap-3">
                  <span className="h-2 w-2 rounded-full bg-teal-500 shadow-[0_0_10px_rgba(20,184,166,0.5)]" />
                  {t('speedPoints.1')}
                </li>
                <li className="flex items-center gap-3">
                  <span className="h-2 w-2 rounded-full bg-teal-500 shadow-[0_0_10px_rgba(20,184,166,0.5)]" />
                  {t('speedPoints.2')}
                </li>
              </ul>
            </div>
          </div>

          {/* Benefit 2: Quality */}
          <div className="flex flex-col lg:flex-row items-center gap-16">
            <div className="flex-1">
               <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-violet-500/10 border border-violet-500/20 text-violet-400 text-xs font-semibold tracking-wider mb-6">
                 <StarIcon className="w-4 h-4" aria-hidden="true" />
                 {t('qualityBadge')}
              </div>

              <h2 className="text-4xl sm:text-5xl font-bold text-white mb-6 leading-[1.05] tracking-[-0.02em]">
                 {t.rich('qualityTitle', {
                    highlight: (chunks) => <span className="text-transparent bg-clip-text bg-gradient-to-r from-violet-400 to-violet-500">{chunks}</span>
                  })}
              </h2>
              <p className="text-lg text-slate-300 mb-8 leading-[1.7]">
                {t('qualityDescription')}
              </p>

              <div className="flex flex-wrap gap-4">
                 {/* Spotify Badge */}
                 <div className="flex items-center gap-4 px-5 py-3 rounded-xl bg-slate-900/80 border border-slate-800/60 shadow-lg backdrop-blur-sm min-w-[180px]">
                    <SpotifyIcon className="w-8 h-8 text-[#1DB954]" />
                    <div className="flex flex-col">
                        <span className="text-[10px] uppercase tracking-wider text-slate-300 font-semibold">{t('readyFor')}</span>
                        <span className="text-base font-bold text-white">{t('spotifyReady')}</span>
                    </div>
                 </div>

                 {/* Apple Music Badge */}
                 <div className="flex items-center gap-4 px-5 py-3 rounded-xl bg-slate-900/80 border border-slate-800/60 shadow-lg backdrop-blur-sm min-w-[180px]">
                    <AppleMusicIcon className="w-8 h-8 text-white" /> {/* Apple Music is usually white or pinkish/red */}
                    <div className="flex flex-col">
                        <span className="text-[10px] uppercase tracking-wider text-slate-300 font-semibold">{t('readyFor')}</span>
                        <span className="text-base font-bold text-white">{t('appleMusicReady')}</span>
                    </div>
                 </div>
              </div>
            </div>
            <div className="flex-1">
               {/* Image Placeholder */}
               <div className="w-full aspect-video rounded-2xl bg-gradient-to-br from-violet-900/20 to-slate-900 border border-slate-700 flex items-center justify-center relative shadow-2xl overflow-hidden">
                  <LazyVideo
                    src="/spectral_analysis.webm"
                    poster="/analysis.webp"
                    className="w-full h-full object-cover"
                  />
               </div>
            </div>
          </div>

        </div>
      </section>
    );
  }
