import type { Metadata } from "next";
import { Suspense } from "react";
import { Geist_Mono, Space_Grotesk, Orbitron, Inter } from "next/font/google";
import "../globals.css";
import Script from "next/script";
import { GARouteTracker } from "../../components/analytics/GARouteTracker";
import { AuthProvider } from "../../context/AuthContext";
import { GlobalLayoutClient } from "../../components/GlobalLayoutClient";
import { NextIntlClientProvider } from 'next-intl';
import { getMessages, getTranslations, setRequestLocale } from 'next-intl/server';
import { notFound } from 'next/navigation';
import { routing } from '../../i18n/routing';

export function generateStaticParams() {
  return routing.locales.map((locale) => ({locale}));
}

const spaceGrotesk = Space_Grotesk({
  variable: "--font-space-grotesk",
  subsets: ["latin"],
  display: "swap",
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const orbitron = Orbitron({
  variable: "--font-orbitron",
  subsets: ["latin"],
  display: "swap",
  weight: ["500", "700", "900"],
});

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

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

const siteName = "Piroola";

const organizationJsonLd = {
  "@context": "https://schema.org",
  "@type": "Organization",
  name: siteName,
  url: siteUrl,
  logo: `${siteUrl}/brand/logo.webp`,
  contactPoint: [
    {
      "@type": "ContactPoint",
      contactType: "legal",
      email: "legal@piroola.com",
    },
    {
      "@type": "ContactPoint",
      contactType: "privacy",
      email: "privacy@piroola.com",
    },
    ],
  };

const softwareApplicationJsonLd = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: "Piroola",
  applicationCategory: "MultimediaApplication",
  operatingSystem: "Web",
  offers: [
    {
      "@type": "Offer",
      price: "0",
      priceCurrency: "USD",
      name: "Free",
    },
    {
      "@type": "Offer",
      price: "19",
      priceCurrency: "USD",
      name: "Plus Monthly",
    },
    {
      "@type": "Offer",
      price: "49",
      priceCurrency: "USD",
      name: "Pro Monthly",
    },
  ],
};

export async function generateMetadata({params}: {params: Promise<{locale: string}>}): Promise<Metadata> {
  const {locale} = await params;
  const t = await getTranslations({locale, namespace: 'Metadata'});
  const tNav = await getTranslations({locale, namespace: 'Navigation'});

  const navLinks = [
    { name: tNav('examples'), url: `${siteUrl}/${locale}/examples` },
    { name: tNav('pricing'), url: `${siteUrl}/${locale}/pricing` },
    { name: tNav('faq'), url: `${siteUrl}/${locale}/faq` },
    { name: tNav('howItWorks'), url: `${siteUrl}/${locale}/docs` },
    { name: tNav('blog'), url: `${siteUrl}/${locale}/blog` },
    { name: tNav('rss'), url: `${siteUrl}/${locale}/rss.xml` },
    { name: tNav('support'), url: `${siteUrl}/${locale}/support` },
  ];

  return {
    metadataBase: new URL(siteUrl),
    title: {
      default: t('title'),
      template: `%s | ${siteName}`,
    },
    description: t('description'),
    keywords: [
      "AI mixing",
      "AI mastering",
      "online audio mixing",
      "automated mixing service",
      "stem mastering",
      "Piroola",
      "online vocal tuner",
      "free stem mastering",
      "audio post-production AI",
      "best ai mixing service for logic pro users",
      "automatic mixing",
      "music mastering online",
      "vocal mixing",
    ],
    icons: {
      icon: "/brand/logo.webp",
      shortcut: "/brand/logo.webp",
      apple: "/brand/logo.webp",
    },
    robots: {
      index: true,
      follow: true,
    },
    openGraph: {
      title: t('title'),
      description: t('description'),
      url: `${siteUrl}/${locale}`,
      siteName,
      images: [
        {
          url: "/brand/logo.webp",
          width: 512,
          height: 512,
          alt: "Piroola Logo",
        },
      ],
      type: "website",
      locale: locale === 'en' ? 'en_US' : locale,
    },
    twitter: {
      card: "summary_large_image",
      title: t('title'),
      description: t('description'),
      images: ["/brand/logo.webp"],
    },
  };
}

export default async function LocaleLayout({
  children,
  params
}: {
  children: React.ReactNode;
  params: Promise<{locale: string}>;
}) {
  const { locale } = await params;

  // Enable static rendering
  if (routing.locales.includes(locale as any)) {
    setRequestLocale(locale);
  } else {
    notFound();
  }

  const messages = await getMessages();
  const tNav = await getTranslations({locale, namespace: 'Navigation'});

  const navLinks = [
    { name: tNav('examples'), url: `${siteUrl}/${locale}/examples` },
    { name: tNav('pricing'), url: `${siteUrl}/${locale}/pricing` },
    { name: tNav('faq'), url: `${siteUrl}/${locale}/faq` },
    { name: tNav('howItWorks'), url: `${siteUrl}/${locale}/docs` },
    { name: tNav('blog'), url: `${siteUrl}/${locale}/blog` },
    { name: tNav('rss'), url: `${siteUrl}/${locale}/rss.xml` },
    { name: tNav('support'), url: `${siteUrl}/${locale}/support` },
  ];

  const websiteJsonLd = {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: siteName,
    url: `${siteUrl}/${locale}`,
    inLanguage: locale,
  };

  const siteNavigationJsonLd = {
    "@context": "https://schema.org",
    "@type": "ItemList",
    itemListElement: navLinks.map((item, index) => ({
      "@type": "SiteNavigationElement",
      position: index + 1,
      name: item.name,
      url: item.url,
    })),
  };

  const gaId = process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID;

  return (
    <html lang={locale}>
      <head>
      </head>
      <body className={`${spaceGrotesk.variable} ${geistMono.variable} ${orbitron.variable} ${inter.variable} antialiased`}>
        <NextIntlClientProvider messages={messages}>
          <AuthProvider>
            <script
              id="ld-organization"
              type="application/ld+json"
              dangerouslySetInnerHTML={{ __html: JSON.stringify(organizationJsonLd) }}
            />
            <script
              id="ld-software-app"
              type="application/ld+json"
              dangerouslySetInnerHTML={{ __html: JSON.stringify(softwareApplicationJsonLd) }}
            />
            <script
              id="ld-website"
              type="application/ld+json"
              dangerouslySetInnerHTML={{ __html: JSON.stringify(websiteJsonLd) }}
            />
            <script
              id="ld-site-navigation"
              type="application/ld+json"
              dangerouslySetInnerHTML={{ __html: JSON.stringify(siteNavigationJsonLd) }}
            />

            <GlobalLayoutClient>
              {children}
            </GlobalLayoutClient>

            {/* Google Analytics: solo si hay ID */}
            {gaId && (
              <>
                <Script
                  src={`https://www.googletagmanager.com/gtag/js?id=${gaId}`}
                  strategy="lazyOnload"
                />
                <Script
                  id="ga-init"
                  strategy="lazyOnload"
                  dangerouslySetInnerHTML={{
                    __html: `
                      window.dataLayer = window.dataLayer || [];
                      function gtag(){dataLayer.push(arguments);}
                      gtag('js', new Date());
                      gtag('config', '${gaId}', { anonymize_ip: true });
                    `,
                  }}
                />
                <Suspense fallback={null}>
                  <GARouteTracker gaId={gaId} />
                </Suspense>
              </>
            )}

            {/* CookieScript / Cookie CMP */}
            <Script
              id="cookie-script"
              src="https://cdn.cookie-script.com/s/ae74c6bd8d098a84d8017855c6fba2af.js"
              strategy="afterInteractive"
              charSet="UTF-8"
            />
          </AuthProvider>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
