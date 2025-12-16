import { Link } from "../../../i18n/routing";
import type { Metadata } from "next";
import Image from "next/image";
import Script from "next/script";
import { useTranslations } from "next-intl";
import { getTranslations } from "next-intl/server";

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
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      <div className="flex flex-1 mx-auto max-w-7xl w-full">
        {/* Sidebar Navigation */}
        <aside className="hidden lg:block w-64 shrink-0 sticky top-16 h-[calc(100vh-4rem)] overflow-y-auto border-r border-slate-800/80 py-8 pr-4 custom-scrollbar">
          <nav className="flex flex-col gap-1 text-sm">
            <p className="px-2 mb-2 font-semibold text-teal-400 uppercase tracking-wider text-xs">{t('toc.gettingStarted')}</p>
            <Link href="#introduction" className="px-2 py-1.5 rounded hover:bg-slate-900 text-slate-400 hover:text-slate-100 transition">{t('toc.intro')}</Link>
            <Link href="#how-to-use" className="px-2 py-1.5 rounded hover:bg-slate-900 text-slate-400 hover:text-slate-100 transition">{t('toc.howToUse')}</Link>
            <Link href="#features" className="px-2 py-1.5 rounded hover:bg-slate-900 text-slate-400 hover:text-slate-100 transition">{t('toc.features')}</Link>

            <p className="px-2 mt-6 mb-2 font-semibold text-teal-400 uppercase tracking-wider text-xs">{t('toc.pipelineStages')}</p>
            <Link href="#pipeline-overview" className="px-2 py-1.5 rounded hover:bg-slate-900 text-slate-400 hover:text-slate-100 transition">{t('toc.overview')}</Link>
            <Link href="#s0-input" className="px-2 py-1.5 rounded hover:bg-slate-900 text-slate-400 hover:text-slate-100 transition">{t('toc.s0')}</Link>
            <Link href="#s1-tech-prep" className="px-2 py-1.5 rounded hover:bg-slate-900 text-slate-400 hover:text-slate-100 transition">{t('toc.s1')}</Link>
            <Link href="#s2-phase" className="px-2 py-1.5 rounded hover:bg-slate-900 text-slate-400 hover:text-slate-100 transition">{t('toc.s2')}</Link>
            <Link href="#s3-static-mix" className="px-2 py-1.5 rounded hover:bg-slate-900 text-slate-400 hover:text-slate-100 transition">{t('toc.s3')}</Link>
            <Link href="#s4-spectral" className="px-2 py-1.5 rounded hover:bg-slate-900 text-slate-400 hover:text-slate-100 transition">{t('toc.s4')}</Link>
            <Link href="#s5-dynamics" className="px-2 py-1.5 rounded hover:bg-slate-900 text-slate-400 hover:text-slate-100 transition">{t('toc.s5')}</Link>
            <Link href="#s6-space" className="px-2 py-1.5 rounded hover:bg-slate-900 text-slate-400 hover:text-slate-100 transition">{t('toc.s6')}</Link>
            <Link href="#s7-tonal" className="px-2 py-1.5 rounded hover:bg-slate-900 text-slate-400 hover:text-slate-100 transition">{t('toc.s7')}</Link>
            <Link href="#s8-color" className="px-2 py-1.5 rounded hover:bg-slate-900 text-slate-400 hover:text-slate-100 transition">{t('toc.s8')}</Link>
            <Link href="#s9-mastering" className="px-2 py-1.5 rounded hover:bg-slate-900 text-slate-400 hover:text-slate-100 transition">{t('toc.s9')}</Link>
            <Link href="#s10-qc" className="px-2 py-1.5 rounded hover:bg-slate-900 text-slate-400 hover:text-slate-100 transition">{t('toc.s10')}</Link>
            <Link href="#s11-reporting" className="px-2 py-1.5 rounded hover:bg-slate-900 text-slate-400 hover:text-slate-100 transition">{t('toc.s11')}</Link>

            <p className="px-2 mt-6 mb-2 font-semibold text-teal-400 uppercase tracking-wider text-xs">{t('toc.results')}</p>
            <Link href="#results" className="px-2 py-1.5 rounded hover:bg-slate-900 text-slate-400 hover:text-slate-100 transition">{t('toc.understandingResults')}</Link>
            <Link href="#faq" className="px-2 py-1.5 rounded hover:bg-slate-900 text-slate-400 hover:text-slate-100 transition">{t('toc.faq')}</Link>
          </nav>
        </aside>

        {/* Main Content */}
        <main className="flex-1 py-12 px-4 lg:px-12 prose prose-invert prose-slate max-w-none">
          <section id="introduction" className="scroll-mt-24 mb-16">
            <h1 className="text-4xl font-bold mb-6 text-teal-400">{t('intro.title')}</h1>
            <p className="text-xl text-slate-300 leading-relaxed" dangerouslySetInnerHTML={{ __html: t.raw('intro.p1') }} />
            <p className="text-slate-400" dangerouslySetInnerHTML={{ __html: t.raw('intro.p2') }} />
          </section>

          <section id="how-to-use" className="scroll-mt-24 mb-16 border-t border-slate-800/50 pt-8">
            <h2 className="text-3xl font-semibold mb-6 text-slate-100">{t('howToUse.title')}</h2>

            <h3 className="text-xl font-medium text-teal-300 mt-8 mb-4">{t('howToUse.step1.title')}</h3>
            <p className="text-slate-300">{t('howToUse.step1.desc')}</p>
            <div className="my-6 p-4 border border-dashed border-slate-700 rounded-lg bg-slate-900/50 flex items-center justify-center text-slate-500 h-120">
              <Image src="/upload_dropzone.webp" alt="Screenshot" width={832} height={514} className="max-h-full w-auto object-contain rounded-md" />
            </div>

            <h3 className="text-xl font-medium text-teal-300 mt-8 mb-4">{t('howToUse.step2.title')}</h3>
            <p className="text-slate-300" dangerouslySetInnerHTML={{ __html: t.raw('howToUse.step2.desc') }} />
            <div className="my-6 p-4 border border-dashed border-slate-700 rounded-lg bg-slate-900/50 flex items-center justify-center text-slate-500 h-120">
              <Image src="/stems_profile.webp" alt="Screenshot" width={358} height={514} className="max-h-full w-auto object-contain rounded-md" />
            </div>

            <h3 className="text-xl font-medium text-teal-300 mt-8 mb-4">{t('howToUse.step3.title')}</h3>
            <p className="text-slate-300" dangerouslySetInnerHTML={{ __html: t.raw('howToUse.step3.desc') }} />
            <div className="my-6 p-4 border border-dashed border-slate-700 rounded-lg bg-slate-900/50 flex items-center justify-center text-slate-500 h-120">
              <Image src="/pipeline_steps.webp" alt="Screenshot" width={736} height={445} className="max-h-full w-auto object-contain rounded-md" />
            </div>

            <h3 className="text-xl font-medium text-teal-300 mt-8 mb-4">{t('howToUse.step4.title')}</h3>
            <p className="text-slate-300" dangerouslySetInnerHTML={{ __html: t.raw('howToUse.step4.desc') }} />
            <div className="my-6 p-4 border border-dashed border-slate-700 rounded-lg bg-slate-900/50 flex items-center justify-center text-slate-500 h-120">
              <Image src="/space_depth.webp" alt="Screenshot" width={355} height={480} className="max-h-full w-auto object-contain rounded-md" />
            </div>

            <h3 className="text-xl font-medium text-teal-300 mt-8 mb-4">{t('howToUse.step5.title')}</h3>
            <p className="text-slate-300" dangerouslySetInnerHTML={{ __html: t.raw('howToUse.step5.desc') }} />
          </section>

          <section id="features" className="scroll-mt-24 mb-16 border-t border-slate-800/50 pt-8">
            <h2 className="text-3xl font-semibold mb-6 text-slate-100">{t('features.title')}</h2>
            <ul className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <li className="bg-slate-900 p-6 rounded-xl border border-slate-800">
                <h4 className="font-bold text-teal-400 mb-2">{t('features.smartAnalysis.title')}</h4>
                <p className="text-sm text-slate-400">{t('features.smartAnalysis.desc')}</p>
              </li>
              <li className="bg-slate-900 p-6 rounded-xl border border-slate-800">
                <h4 className="font-bold text-teal-400 mb-2">{t('features.autoMixing.title')}</h4>
                <p className="text-sm text-slate-400">{t('features.autoMixing.desc')}</p>
              </li>
              <li className="bg-slate-900 p-6 rounded-xl border border-slate-800">
                <h4 className="font-bold text-teal-400 mb-2">{t('features.aiMastering.title')}</h4>
                <p className="text-sm text-slate-400">{t('features.aiMastering.desc')}</p>
              </li>
              <li className="bg-slate-900 p-6 rounded-xl border border-slate-800">
                <h4 className="font-bold text-teal-400 mb-2">{t('features.detailedReports.title')}</h4>
                <p className="text-sm text-slate-400">{t('features.detailedReports.desc')}</p>
              </li>
            </ul>
          </section>

          <section id="pipeline-overview" className="scroll-mt-24 mb-16 border-t border-slate-800/50 pt-8">
            <h2 className="text-3xl font-semibold mb-6 text-slate-100">{t('pipeline.title')}</h2>
            <p className="text-slate-300 mb-8">{t('pipeline.desc')}</p>
            <div className="my-6 p-4 border border-dashed border-slate-700 rounded-lg bg-slate-900/50 flex items-center justify-center text-slate-500 h-120">
              <Image src="/processing.webp" alt="Screenshot" width={439} height={268} className="max-h-full w-auto object-contain rounded-md" />
            </div>

            {/* Stage S0 */}
            <div id="s0-input" className="scroll-mt-28 mb-12">
              <h3 className="text-2xl font-semibold text-amber-400 mb-3">{t('pipeline.s0.title')}</h3>
              <p className="text-slate-400 mb-4"><strong>Goal:</strong> {t('pipeline.s0.goal')}</p>
              <p className="text-slate-300">{t('pipeline.s0.desc')}</p>
              <ul className="list-disc pl-5 mt-2 text-slate-400 text-sm">
                {Object.values(t.raw('pipeline.s0.points') as Record<string, string>).map((point, i) => (
                  <li key={i} dangerouslySetInnerHTML={{ __html: point }} />
                ))}
              </ul>
            </div>

            {/* Stage S1 */}
            <div id="s1-tech-prep" className="scroll-mt-28 mb-12">
              <h3 className="text-2xl font-semibold text-amber-400 mb-3">{t('pipeline.s1.title')}</h3>
              <p className="text-slate-400 mb-4"><strong>Goal:</strong> {t('pipeline.s1.goal')}</p>
              <p className="text-slate-300">{t('pipeline.s1.desc')}</p>
              <ul className="list-disc pl-5 mt-2 text-slate-400 text-sm">
                {Object.values(t.raw('pipeline.s1.points') as Record<string, string>).map((point, i) => (
                  <li key={i} dangerouslySetInnerHTML={{ __html: point }} />
                ))}
              </ul>
            </div>

            {/* Stage S2 */}
            <div id="s2-phase" className="scroll-mt-28 mb-12">
              <h3 className="text-2xl font-semibold text-amber-400 mb-3">{t('pipeline.s2.title')}</h3>
              <p className="text-slate-400 mb-4"><strong>Goal:</strong> {t('pipeline.s2.goal')}</p>
              <p className="text-slate-300">{t('pipeline.s2.desc')}</p>
            </div>

            {/* Stage S3 */}
            <div id="s3-static-mix" className="scroll-mt-28 mb-12">
              <h3 className="text-2xl font-semibold text-amber-400 mb-3">{t('pipeline.s3.title')}</h3>
              <p className="text-slate-400 mb-4"><strong>Goal:</strong> {t('pipeline.s3.goal')}</p>
              <p className="text-slate-300">{t('pipeline.s3.desc')}</p>
            </div>

            {/* Stage S4 */}
            <div id="s4-spectral" className="scroll-mt-28 mb-12">
              <h3 className="text-2xl font-semibold text-amber-400 mb-3">{t('pipeline.s4.title')}</h3>
              <p className="text-slate-400 mb-4"><strong>Goal:</strong> {t('pipeline.s4.goal')}</p>
              <p className="text-slate-300">{t('pipeline.s4.desc')}</p>
              <ul className="list-disc pl-5 mt-2 text-slate-400 text-sm">
                {Object.values(t.raw('pipeline.s4.points') as Record<string, string>).map((point, i) => (
                  <li key={i} dangerouslySetInnerHTML={{ __html: point }} />
                ))}
              </ul>
            </div>

            {/* Stage S5 */}
            <div id="s5-dynamics" className="scroll-mt-28 mb-12">
              <h3 className="text-2xl font-semibold text-amber-400 mb-3">{t('pipeline.s5.title')}</h3>
              <p className="text-slate-400 mb-4"><strong>Goal:</strong> {t('pipeline.s5.goal')}</p>
              <p className="text-slate-300">{t('pipeline.s5.desc')}</p>
              <ul className="list-disc pl-5 mt-2 text-slate-400 text-sm">
                {Object.values(t.raw('pipeline.s5.points') as Record<string, string>).map((point, i) => (
                  <li key={i} dangerouslySetInnerHTML={{ __html: point }} />
                ))}
              </ul>
            </div>

            {/* Stage S6 */}
            <div id="s6-space" className="scroll-mt-28 mb-12">
              <h3 className="text-2xl font-semibold text-amber-400 mb-3">{t('pipeline.s6.title')}</h3>
              <p className="text-slate-400 mb-4"><strong>Goal:</strong> {t('pipeline.s6.goal')}</p>
              <p className="text-slate-300">{t('pipeline.s6.desc')}</p>
            </div>

            {/* Stage S7 */}
            <div id="s7-tonal" className="scroll-mt-28 mb-12">
              <h3 className="text-2xl font-semibold text-amber-400 mb-3">{t('pipeline.s7.title')}</h3>
              <p className="text-slate-400 mb-4"><strong>Goal:</strong> {t('pipeline.s7.goal')}</p>
              <p className="text-slate-300">{t('pipeline.s7.desc')}</p>
            </div>

            {/* Stage S8 */}
            <div id="s8-color" className="scroll-mt-28 mb-12">
              <h3 className="text-2xl font-semibold text-amber-400 mb-3">{t('pipeline.s8.title')}</h3>
              <p className="text-slate-400 mb-4"><strong>Goal:</strong> {t('pipeline.s8.goal')}</p>
              <p className="text-slate-300">{t('pipeline.s8.desc')}</p>
            </div>

            {/* Stage S9 */}
            <div id="s9-mastering" className="scroll-mt-28 mb-12">
              <h3 className="text-2xl font-semibold text-amber-400 mb-3">{t('pipeline.s9.title')}</h3>
              <p className="text-slate-400 mb-4"><strong>Goal:</strong> {t('pipeline.s9.goal')}</p>
              <p className="text-slate-300">{t('pipeline.s9.desc')}</p>
            </div>

            {/* Stage S10 */}
            <div id="s10-qc" className="scroll-mt-28 mb-12">
              <h3 className="text-2xl font-semibold text-amber-400 mb-3">{t('pipeline.s10.title')}</h3>
              <p className="text-slate-400 mb-4"><strong>Goal:</strong> {t('pipeline.s10.goal')}</p>
              <p className="text-slate-300">{t('pipeline.s10.desc')}</p>
            </div>

            {/* Stage S11 */}
            <div id="s11-reporting" className="scroll-mt-28 mb-12">
              <h3 className="text-2xl font-semibold text-amber-400 mb-3">{t('pipeline.s11.title')}</h3>
              <p className="text-slate-400 mb-4"><strong>Goal:</strong> {t('pipeline.s11.goal')}</p>
              <p className="text-slate-300">{t('pipeline.s11.desc')}</p>
            </div>
          </section>

          <section id="results" className="scroll-mt-24 mb-16 border-t border-slate-800/50 pt-8">
            <h2 className="text-3xl font-semibold mb-6 text-slate-100">{t('results.title')}</h2>
            <p className="text-slate-300 mb-6" dangerouslySetInnerHTML={{ __html: t.raw('results.p1') }} />

            <h3 className="text-xl font-medium text-teal-300 mt-6 mb-3">{t('results.audioFiles.title')}</h3>
            <p className="text-slate-300 mb-4" dangerouslySetInnerHTML={{ __html: t.raw('results.audioFiles.desc') }} />
            <div className="my-6 p-4 border border-dashed border-slate-700 rounded-lg bg-slate-900/50 flex items-center justify-center text-slate-500 h-120">
              <Image src="/result.webp" alt="Screenshot" width={802} height={616} className="max-h-full w-auto object-contain rounded-md" />
            </div>

            <h3 className="text-xl font-medium text-teal-300 mt-6 mb-3">{t('results.report.title')}</h3>
            <p className="text-slate-300 mb-4" dangerouslySetInnerHTML={{ __html: t.raw('results.report.desc') }} />
            <ul className="list-disc pl-5 text-slate-400 text-sm space-y-2">
              {Object.values(t.raw('results.report.points') as Record<string, string>).map((point, i) => (
                <li key={i} dangerouslySetInnerHTML={{ __html: point }} />
              ))}
            </ul>
            <div className="my-6 p-4 border border-dashed border-slate-700 rounded-lg bg-slate-900/50 flex items-center justify-center text-slate-500 h-120">
              <Image src="/report.webp" alt="Screenshot" width={918} height={949} className="max-h-full w-auto object-contain rounded-md" />
            </div>
          </section>

          <section id="faq" className="scroll-mt-24 mb-16 border-t border-slate-800/50 pt-8">
            <h2 className="text-3xl font-semibold mb-6 text-slate-100">{t('faq.title')}</h2>

            <div className="space-y-6">
              {['q1', 'q2', 'q3'].map((qKey) => (
                <div key={qKey}>
                  <h4 className="font-bold text-slate-200">{t(`faq.${qKey}.q`)}</h4>
                  <p className="text-sm text-slate-400 mt-1">{t(`faq.${qKey}.a`)}</p>
                </div>
              ))}
            </div>
          </section>
        </main>
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
