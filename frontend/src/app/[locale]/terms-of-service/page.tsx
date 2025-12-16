import type { Metadata } from "next";
import { Link } from "../../../i18n/routing";
import { getTranslations } from "next-intl/server";
import { useTranslations } from "next-intl";

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
const canonicalUrl = `${siteUrl}/terms-of-service`;

const breadcrumbJsonLd = {
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  itemListElement: [
    {
      "@type": "ListItem",
      position: 1,
      name: "Home",
      item: siteUrl,
    },
    {
      "@type": "ListItem",
      position: 2,
      name: "Terms of Service",
      item: canonicalUrl,
    },
  ],
};

const webPageJsonLd = {
  "@context": "https://schema.org",
  "@type": "WebPage",
  name: "Terms of Service",
  url: canonicalUrl,
  isPartOf: {
    "@type": "WebSite",
    url: siteUrl,
    name: "Piroola",
  },
  inLanguage: "en",
};

type Props = {
  params: Promise<{ locale: string }>;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: 'Terms' });
  return {
    title: t('title'),
    description: "Review the Terms of Service for Piroola's AI mixing and mastering platform.",
    alternates: { canonical: "/terms-of-service" },
    robots: { index: true, follow: true },
  };
}

export default function TermsOfServicePage() {
  const t = useTranslations('Terms');

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbJsonLd) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(webPageJsonLd) }}
      />
      <main className="flex-1 px-4 py-12">
        <div className="mx-auto max-w-3xl prose prose-invert prose-slate">
          <h1 className="text-3xl font-bold mb-8 text-teal-400">{t('title')}</h1>

          <p className="text-slate-300 mb-6">{t('lastUpdated', { date: new Date().toLocaleDateString() })}</p>

          <section className="mb-8">
            <h2 className="text-xl font-semibold mb-4 text-slate-200">{t('sections.0.title')}</h2>
            <p className="text-slate-400 leading-relaxed" dangerouslySetInnerHTML={{ __html: t.raw('sections.0.content') }} />
          </section>

          <section className="mb-8">
            <h2 className="text-xl font-semibold mb-4 text-slate-200">{t('sections.1.title')}</h2>
            <p className="text-slate-400 leading-relaxed">{t('sections.1.content')}</p>
          </section>

          <section className="mb-8">
            <h2 className="text-xl font-semibold mb-4 text-slate-200">{t('sections.2.title')}</h2>
            <p className="text-slate-400 leading-relaxed mb-4">{t('sections.2.content')}</p>
            <ul className="list-disc pl-5 text-slate-400 space-y-2">
              {Object.values(t.raw('sections.2.list') as Record<string, string>).map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          </section>

          <section className="mb-8">
            <h2 className="text-xl font-semibold mb-4 text-slate-200">{t('sections.3.title')}</h2>
            <p className="text-slate-400 leading-relaxed">{t('sections.3.content')}</p>
          </section>

          <section className="mb-8">
            <h2 className="text-xl font-semibold mb-4 text-slate-200">{t('sections.4.title')}</h2>
            <p className="text-slate-400 leading-relaxed">{t('sections.4.content')}</p>
          </section>

          <section className="mb-8">
            <h2 className="text-xl font-semibold mb-4 text-slate-200">{t('sections.5.title')}</h2>
            <p className="text-slate-400 leading-relaxed">{t('sections.5.content')}</p>
          </section>

          <section className="mb-8">
            <h2 className="text-xl font-semibold mb-4 text-slate-200">{t('sections.6.title')}</h2>
            <p className="text-slate-400 leading-relaxed" dangerouslySetInnerHTML={{ __html: t.raw('sections.6.content') }} />
          </section>
        </div>
      </main>
    </div>
  );
}
