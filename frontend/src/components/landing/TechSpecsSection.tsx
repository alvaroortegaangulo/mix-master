
import { useTranslations } from "next-intl";

export function TechSpecsSection({ className }: { className?: string }) {
    const t = useTranslations('TechSpecsSection');

    return (
      <section className={`py-24 overflow-hidden ${className || 'bg-slate-900'}`}>
        <div className="max-w-6xl mx-auto px-4 text-center">
          <h2 className="text-3xl font-bold text-white mb-12">{t('title')}</h2>

          <div className="max-w-4xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-8">
             <div className="p-6">
                <div className="text-4xl font-bold text-teal-400 mb-2">96k</div>
                <div className="text-sm font-medium text-slate-400 uppercase tracking-wide">{t('internalProcessing')}</div>
             </div>
             <div className="p-6">
                <div className="text-4xl font-bold text-purple-400 mb-2">32-bit</div>
                <div className="text-sm font-medium text-slate-400 uppercase tracking-wide">{t('floatDepth')}</div>
             </div>
             <div className="p-6">
                <div className="text-4xl font-bold text-amber-400 mb-2">10+</div>
                <div className="text-sm font-medium text-slate-400 uppercase tracking-wide">{t('processingStages')}</div>
             </div>
             <div className="p-6">
                <div className="text-4xl font-bold text-rose-400 mb-2">0s</div>
                <div className="text-sm font-medium text-slate-400 uppercase tracking-wide">{t('latency')}</div>
             </div>
          </div>
        </div>
      </section>
    );
  }
