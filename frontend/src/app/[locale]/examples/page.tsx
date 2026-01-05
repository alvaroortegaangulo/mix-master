import type { Metadata } from "next";
import { Link } from "../../../i18n/routing";
import Script from "next/script";
import { useTranslations } from "next-intl";
import { getTranslations } from "next-intl/server";
import { ExamplesGrid } from "../../../components/examples/ExamplesGrid";

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
  const t = await getTranslations({ locale, namespace: 'Examples' });

  return {
    title: `${t('subtitle')} | Piroola`,
    description: t('description'),
    alternates: {
      canonical: "/examples",
    },
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
      name: "Examples",
      item: `${siteUrl}/examples`,
    },
  ],
};

export default function ExamplesPage() {
  const t = useTranslations('Examples');
  const exampleKeys = ['pop', 'rock', 'indie', 'trap'];

  const EXAMPLES = exampleKeys.map(key => ({
    id: key,
    title: t(`items.${key}.title`),
    genre: t(`items.${key}.genre`),
    summary: t(`items.${key}.summary`),
    highlights: Object.values(t.raw(`items.${key}.highlights`) as Record<string, string>),
    metrics: Object.values(t.raw(`items.${key}.metrics`) as Record<string, string>),
    originalSrc: `/examples/${key}_original.wav`,
    masterSrc: `/examples/${key}_mixdown.wav`,
  }));

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      <main className="flex-1 px-4 py-12">
        <div className="mx-auto max-w-5xl">
          <div className="flex flex-col gap-4 mb-10 text-center">
            <p className="text-xs uppercase tracking-[0.2em] text-teal-300/80">{t('subtitle')}</p>
            <h1 className="text-4xl font-bold tracking-tight text-slate-50">{t('title')}</h1>
            <p className="text-lg text-slate-400 max-w-3xl mx-auto">
              {t('description')}
            </p>
            <div className="flex flex-wrap gap-3 justify-center">
              <Link href="/pricing" className="rounded-full bg-teal-400 text-slate-950 px-4 py-2 text-sm font-semibold shadow-md shadow-teal-500/30 hover:bg-teal-300 transition">
                {t('viewPricing')}
              </Link>
              <Link href="/docs" className="rounded-full border border-slate-800 px-4 py-2 text-sm font-semibold text-slate-100 hover:border-teal-400 hover:text-teal-300 transition">
                {t('howItWorks')}
              </Link>
            </div>
          </div>

          <ExamplesGrid
            examples={EXAMPLES}
            toggleLabels={{ original: t("toggleOriginal"), master: t("toggleMaster") }}
            notableChangesLabel={t("notableChanges")}
          />

          <div className="mt-12 rounded-2xl border border-teal-500/40 bg-teal-500/10 p-8 text-center shadow-lg shadow-teal-500/20">
            <h3 className="text-2xl font-semibold text-teal-200 mb-3">{t('ctaTitle')}</h3>
            <p className="text-slate-200 mb-6">{t('ctaDescription')}</p>
            <div className="flex justify-center gap-3">
              <Link href="/" className="rounded-full bg-teal-400 text-slate-950 px-4 py-2 text-sm font-semibold shadow-md shadow-teal-500/30 hover:bg-teal-300 transition">
                {t('startMixing')}
              </Link>
              <Link href="/support" className="rounded-full border border-teal-500/70 px-4 py-2 text-sm font-semibold text-teal-100 hover:bg-teal-500/10 transition">
                {t('talkToSupport')}
              </Link>
            </div>
          </div>
        </div>
      </main>

      <Script
        id="ld-breadcrumbs-examples"
        type="application/ld+json"
        strategy="afterInteractive"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbsJsonLd) }}
      />
    </div>
  );
}
