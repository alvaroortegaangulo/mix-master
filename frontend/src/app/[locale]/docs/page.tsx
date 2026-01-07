import { Link } from "../../../i18n/routing";
import type { Metadata } from "next";
import Script from "next/script";
import { useTranslations } from "next-intl";
import { getTranslations } from "next-intl/server";
import PipelineViewer from "../../../components/docs/PipelineViewer";
import HowToUseStepper from "../../../components/docs/HowToUseStepper";
import {
  SparklesIcon,
  CpuChipIcon,
  TrophyIcon,
  DocumentChartBarIcon
} from "@heroicons/react/24/outline";

const fallbackSiteUrl = "https://music-mix-master.com";
const siteUrl = (() => {
  const envUrl = process.env.NEXT_PUBLIC_SITE_URL?.trim();
  if (!envUrl) return fallbackSiteUrl;
  try {
    return new URL(envUrl).origin;
  } catch {
    return fallbackSiteUrl;
  }
})();

type Props = {
  params: Promise<{ locale: string }>;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: 'Docs' });
  return {
    title: t('title'),
    description: t('description'),
    alternates: { canonical: "/docs" },
  };
}

const breadcrumbsJsonLd = {
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  itemListElement: [
    {
      "@type": "ListItem",
      position: 1,
      name: "Home",
      item: `${siteUrl}/`,
    },
    {
      "@type": "ListItem",
      position: 2,
      name: "How it works",
      item: `${siteUrl}/docs`,
    },
  ],
};

export default function DocsPage() {
  const t = useTranslations('Docs');

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-teal-500/30">

      {/* 1. Hero / Intro Section */}
      <section className="relative py-20 lg:py-32 px-4 overflow-hidden">
        <div className="absolute top-0 left-0 w-full h-full bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-teal-900/20 via-slate-950 to-slate-950 -z-10" />
        <div className="max-w-4xl mx-auto text-center space-y-8">
            <h1 className="text-4xl lg:text-6xl font-extrabold tracking-tight text-white mb-6">
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-teal-400 to-emerald-500">
                {t('intro.title')}
              </span>
            </h1>
            <div className="text-lg lg:text-xl text-slate-300 leading-relaxed max-w-2xl mx-auto space-y-6">
                <p dangerouslySetInnerHTML={{ __html: t.raw('intro.p1') }} />
                <p className="text-slate-400 text-base">{t('intro.p2')}</p>
            </div>
        </div>
      </section>

      <div className="max-w-7xl mx-auto w-full px-4 lg:px-8 pb-24 space-y-32">

        {/* 2. How to Use (Interactive Stepper) */}
        <section id="how-to-use" className="scroll-mt-24">
            <div className="text-center mb-16">
                <h2 className="text-3xl font-bold text-white mb-4">{t('howToUse.title')}</h2>
                <div className="h-1 w-20 bg-gradient-to-r from-teal-500 to-emerald-500 mx-auto rounded-full" />
            </div>
            <HowToUseStepper />
        </section>

        {/* 3. Pipeline Deep Dive (Interactive Viewer) */}
        <section id="pipeline-overview" className="scroll-mt-24">
            <div className="text-center mb-16 max-w-3xl mx-auto">
                <h2 className="text-3xl font-bold text-white mb-6">{t('pipeline.title')}</h2>
                <p className="text-slate-400">{t('pipeline.desc')}</p>
            </div>
            <PipelineViewer />
        </section>

        {/* 4. Features Grid (Modern Cards) */}
        <section id="features" className="scroll-mt-24">
            <div className="text-center mb-16">
                <h2 className="text-3xl font-bold text-white mb-4">{t('features.title')}</h2>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                {[
                    { key: 'smartAnalysis', icon: SparklesIcon, color: 'text-amber-400', bg: 'bg-amber-400/10' },
                    { key: 'autoMixing', icon: CpuChipIcon, color: 'text-cyan-400', bg: 'bg-cyan-400/10' },
                    { key: 'aiMastering', icon: TrophyIcon, color: 'text-purple-400', bg: 'bg-purple-400/10' },
                    { key: 'detailedReports', icon: DocumentChartBarIcon, color: 'text-emerald-400', bg: 'bg-emerald-400/10' },
                ].map((feature) => (
                    <div key={feature.key} className="group relative bg-slate-900/50 hover:bg-slate-900 border border-slate-800 hover:border-slate-700 p-8 rounded-2xl transition-all duration-300 hover:-translate-y-1">
                        <div className={`w-12 h-12 rounded-xl ${feature.bg} flex items-center justify-center mb-6 group-hover:scale-110 transition-transform`}>
                            <feature.icon className={`w-6 h-6 ${feature.color}`} />
                        </div>
                        <h3 className="text-lg font-bold text-white mb-3">{t(`features.${feature.key}.title`)}</h3>
                        <p className="text-sm text-slate-400 leading-relaxed">{t(`features.${feature.key}.desc`)}</p>
                    </div>
                ))}
            </div>
        </section>

        {/* 5. FAQ (Accordion Style - Simplified) */}
        <section id="faq" className="max-w-3xl mx-auto scroll-mt-24">
            <h2 className="text-3xl font-bold text-white mb-12 text-center">{t('faq.title')}</h2>
            <div className="space-y-4">
              {['q1', 'q2', 'q3'].map((qKey, i) => (
                <div key={qKey} className="bg-slate-900/30 border border-slate-800 rounded-xl p-6 hover:bg-slate-900/50 transition-colors">
                  <h4 className="font-bold text-slate-200 mb-2 flex items-start gap-3">
                    <span className="text-teal-500/50 text-sm mt-1">0{i+1}</span>
                    {t(`faq.${qKey}.q`)}
                  </h4>
                  <p className="text-slate-400 text-sm leading-relaxed pl-8">{t(`faq.${qKey}.a`)}</p>
                </div>
              ))}
            </div>
            <div className="mt-12 text-center">
                <Link href="/faq" className="inline-flex items-center text-sm font-medium text-teal-400 hover:text-teal-300 transition-colors">
                    View all FAQs <span aria-hidden="true" className="ml-1">→</span>
                </Link>
            </div>
        </section>

      </div>

      <Script
        id="ld-breadcrumbs-docs"
        type="application/ld+json"
        strategy="afterInteractive"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbsJsonLd) }}
      />
    </div>
  );
}
