import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { GoogleAnalytics } from "@next/third-parties/google";
import Script from "next/script";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Audio Alchemy: Professional AI Audio Mixing & Mastering Online",
  description: "Transform your tracks with Audio Alchemy. Our AI-powered mixing and mastering service delivers professional studio-quality results from your multi-track stems in minutes.",
  keywords: ["AI mixing", "AI mastering", "online audio mixing", "automated mixing service", "stem mastering", "Audio Alchemy"],
  openGraph: {
    title: "Audio Alchemy: Professional AI Audio Mixing & Mastering Online",
    description: "Transform your tracks with Audio Alchemy. Our AI-powered mixing and mastering service delivers professional studio-quality results from your multi-track stems in minutes.",
    type: "website",
    locale: "en_US",
  },
  twitter: {
    card: "summary_large_image",
    title: "Audio Alchemy: Professional AI Audio Mixing & Mastering Online",
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
      </body>
    </html>
  );
}