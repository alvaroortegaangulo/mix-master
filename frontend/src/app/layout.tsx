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
  title: "Audio Alchemy – AI Mix Master",
  description: "Upload your tracks and get an AI-assisted professional mix.",
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