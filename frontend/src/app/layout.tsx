import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { GoogleAnalytics } from "@next/third-parties/google";
import Script from "next/script";
import { AuthProvider } from "../context/AuthContext";

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

const siteName = "Audio Alchemy";

const organizationJsonLd = {
  "@context": "https://schema.org",
  "@type": "Organization",
  name: siteName,
  url: siteUrl,
  logo: `${siteUrl}/favicon.ico`,
  contactPoint: [
    {
      "@type": "ContactPoint",
      contactType: "legal",
      email: "legal@audioalchemy.com",
    },
    {
      "@type": "ContactPoint",
      contactType: "privacy",
      email: "privacy@audioalchemy.com",
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

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: `${siteName}: Professional AI Audio Mixing & Mastering Online`,
    template: `%s | ${siteName}`,
  },
  description:
    "Transform your tracks with Audio Alchemy. Our AI-powered mixing and mastering service delivers professional studio-quality results from your multi-track stems in minutes.",
  keywords: ["AI mixing", "AI mastering", "online audio mixing", "automated mixing service", "stem mastering", "Audio Alchemy"],
  alternates: {
    canonical: "/",
  },
  robots: {
    index: true,
    follow: true,
  },
  openGraph: {
    title: `${siteName}: Professional AI Audio Mixing & Mastering Online`,
    description: "Transform your tracks with Audio Alchemy. Our AI-powered mixing and mastering service delivers professional studio-quality results from your multi-track stems in minutes.",
    url: siteUrl,
    siteName,
    type: "website",
    locale: "en_US",
  },
  twitter: {
    card: "summary_large_image",
    title: `${siteName}: Professional AI Audio Mixing & Mastering Online`,
    description: "Transform your tracks with Audio Alchemy. Our AI-powered mixing and mastering service delivers professional studio-quality results from your multi-track stems in minutes.",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const gaId = process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID;

  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        <AuthProvider>
        <Script
          id="ld-organization"
          type="application/ld+json"
          strategy="beforeInteractive"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(organizationJsonLd) }}
        />
        <Script
          id="ld-website"
          type="application/ld+json"
          strategy="beforeInteractive"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(websiteJsonLd) }}
        />

        {children}

        {/* Google Analytics: solo si hay ID */}
        {gaId && <GoogleAnalytics gaId={gaId} />}

        {/* CookieScript / Cookie CMP */}
        <Script
          id="cookie-script"
          src="https://cdn.cookie-script.com/s/ae74c6bd8d098a84d8017855c6fba2af.js"
          strategy="beforeInteractive"
          charSet="UTF-8"
        />
        </AuthProvider>
      </body>
    </html>
  );
}
