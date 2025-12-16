import type { Metadata } from "next";
import { Suspense } from "react";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { GoogleAnalytics } from "@next/third-parties/google";
import Script from "next/script";
import { GARouteTracker } from "../components/analytics/GARouteTracker";
import { AuthProvider } from "../context/AuthContext";
import { GoogleOAuthProvider } from "@react-oauth/google";
import { GlobalLayoutClient } from "../components/GlobalLayoutClient";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
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
const navLinks = [
  { name: "Examples", url: `${siteUrl}/examples` },
  { name: "Pricing", url: `${siteUrl}/pricing` },
  { name: "FAQ", url: `${siteUrl}/faq` },
  { name: "How it works", url: `${siteUrl}/docs` },
  { name: "Support", url: `${siteUrl}/support` },
];

const organizationJsonLd = {
  "@context": "https://schema.org",
  "@type": "Organization",
  name: siteName,
  url: siteUrl,
  logo: `${siteUrl}/logo.webp`,
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

const websiteJsonLd = {
  "@context": "https://schema.org",
  "@type": "WebSite",
  name: siteName,
  url: siteUrl,
  inLanguage: "en",
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

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: `${siteName}: Professional AI Audio Mixing & Mastering Online`,
    template: `%s | ${siteName}`,
  },
  description:
    "Transform your tracks with Piroola. Our AI-powered mixing and mastering service delivers professional studio-quality results from your multi-track stems in minutes.",
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
    icon: "/logo.webp",
    shortcut: "/logo.webp",
    apple: "/logo.webp",
  },
  robots: {
    index: true,
    follow: true,
  },
  openGraph: {
    title: `${siteName}: Professional AI Audio Mixing & Mastering Online`,
    description: "Transform your tracks with Piroola. Our AI-powered mixing and mastering service delivers professional studio-quality results from your multi-track stems in minutes.",
    url: siteUrl,
    siteName,
    images: [
      {
        url: "/logo.webp",
        width: 512,
        height: 512,
        alt: "Piroola Logo",
      },
    ],
    type: "website",
    locale: "en_US",
  },
  twitter: {
    card: "summary_large_image",
    title: `${siteName}: Professional AI Audio Mixing & Mastering Online`,
    description: "Transform your tracks with Piroola. Our AI-powered mixing and mastering service delivers professional studio-quality results from your multi-track stems in minutes.",
    images: ["/logo.webp"],
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const gaId = process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID;
  const googleClientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || "YOUR_GOOGLE_CLIENT_ID_HERE";

  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        <GoogleOAuthProvider clientId={googleClientId}>
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
            <GoogleAnalytics gaId={gaId} />
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
        </GoogleOAuthProvider>
      </body>
    </html>
  );
}
