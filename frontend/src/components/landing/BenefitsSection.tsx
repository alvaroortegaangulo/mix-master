import { LazyVideo } from "../LazyVideo";
import { useTranslations } from "next-intl";

type BenefitsSectionProps = {
  className?: string;
};

export function BenefitsSection({ className }: BenefitsSectionProps) {
    const t = useTranslations('BenefitsSection');

    return (
      <section className={`py-24 overflow-hidden ${className || 'bg-slate-950'}`}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">

          {/* Benefit 1: Speed */}
          <div className="flex flex-col lg:flex-row items-center gap-16 mb-24">
            <div className="flex-1 order-2 lg:order-1">
               {/* Image Placeholder */}
               <div className="w-full aspect-video rounded-2xl bg-gradient-to-br from-slate-800 to-slate-900 border border-slate-700 flex items-center justify-center relative shadow-2xl overflow-hidden group">
                  <LazyVideo
                    src="/master_interface.webm"
                    className="w-full h-full object-cover"
                  />
               </div>
            </div>
            <div className="flex-1 order-1 lg:order-2">
              <h3 className="text-3xl font-bold text-white mb-6">
                {t('speedTitle')}
              </h3>
              <p className="text-lg text-slate-400 mb-6 leading-relaxed">
                {t('speedDescription')}
              </p>
              <ul className="space-y-3 text-slate-300">
                <li className="flex items-center gap-3">
                  <span className="h-2 w-2 rounded-full bg-teal-500" />
                  {t('speedPoints.0')}
                </li>
                <li className="flex items-center gap-3">
                  <span className="h-2 w-2 rounded-full bg-teal-500" />
                  {t('speedPoints.1')}
                </li>
                <li className="flex items-center gap-3">
                  <span className="h-2 w-2 rounded-full bg-teal-500" />
                  {t('speedPoints.2')}
                </li>
              </ul>
            </div>
          </div>

          {/* Benefit 2: Quality */}
          <div className="flex flex-col lg:flex-row items-center gap-16">
            <div className="flex-1">
              <h3 className="text-3xl font-bold text-white mb-6">
                {t('qualityTitle')}
              </h3>
              <p className="text-lg text-slate-400 mb-6 leading-relaxed">
                {t('qualityDescription')}
              </p>
              <div className="flex gap-4">
                 <div className="px-4 py-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 text-sm font-medium">
                    {t('spotifyReady')}
                 </div>
                 <div className="px-4 py-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 text-sm font-medium">
                    {t('appleMusicReady')}
                 </div>
              </div>
            </div>
            <div className="flex-1">
               {/* Image Placeholder */}
               <div className="w-full aspect-video rounded-2xl bg-gradient-to-br from-purple-900/20 to-slate-900 border border-slate-700 flex items-center justify-center relative shadow-2xl overflow-hidden">
                  <LazyVideo
                    src="/spectral_analysis.webm"
                    className="w-full h-full object-cover"
                  />
               </div>
            </div>
          </div>

        </div>
      </section>
    );
  }
