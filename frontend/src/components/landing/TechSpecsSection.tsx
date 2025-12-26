
import { useTranslations } from "next-intl";

export function TechSpecsSection({ className }: { className?: string }) {
    const t = useTranslations('TechSpecsSection');

    return (
      <section className={`py-8 md:py-10 lg:py-12 overflow-hidden ${className || 'bg-slate-900'}`}>
        <div className="max-w-6xl mx-auto px-4 text-center">
          <h2 className="text-2xl sm:text-3xl font-bold text-white mb-6">{t('title')}</h2>

          <div className="max-w-4xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-6">
             <div className="p-4">
                <div className="text-3xl 2xl:text-4xl font-bold text-teal-400 mb-2">96k</div>
                <div className="text-xs sm:text-sm font-medium text-slate-300 uppercase tracking-wide">{t('internalProcessing')}</div>
             </div>
             <div className="p-4">
                <div className="text-3xl 2xl:text-4xl font-bold text-violet-400 mb-2">32-bit</div>
                <div className="text-xs sm:text-sm font-medium text-slate-300 uppercase tracking-wide">{t('floatDepth')}</div>
             </div>
             <div className="p-4">
                <div className="text-3xl 2xl:text-4xl font-bold text-teal-400 mb-2">10+</div>
                <div className="text-xs sm:text-sm font-medium text-slate-300 uppercase tracking-wide">{t('processingStages')}</div>
             </div>
             <div className="p-4">
                <div className="text-3xl 2xl:text-4xl font-bold text-violet-400 mb-2">0s</div>
                <div className="text-xs sm:text-sm font-medium text-slate-300 uppercase tracking-wide">{t('latency')}</div>
             </div>
          </div>
        </div>
      </section>
    );
  }
