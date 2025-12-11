"use client";

import { useState } from "react";
import Link from "next/link";
import { CheckIcon, XMarkIcon } from "@heroicons/react/20/solid";
import Script from "next/script";

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
      name: "Pricing",
      item: `${siteUrl}/pricing`,
    },
  ],
};

const TIERS = [
  {
    name: "Free",
    id: "tier-free",
    href: "/#upload",
    priceMonthly: "$0",
    priceYearly: "$0",
    description: "Perfect for hobbyists and trying out our AI mixing engine.",
    features: [
      "2 Songs per month",
      "MP3 Output (320kbps)",
      "Standard AI Mixing",
      "Basic Support",
    ],
    notIncluded: [
      "WAV Output",
      "Stems Download",
      "Priority Processing",
      "Advanced Mastering Options",
    ],
    cta: "Start for Free",
    mostPopular: false,
  },
  {
    name: "Plus",
    id: "tier-plus",
    href: "/register?plan=plus",
    priceMonthly: "$19",
    priceYearly: "$15",
    description: "For independent artists who release music regularly.",
    features: [
      "10 Songs per month",
      "High-Res WAV Output (24-bit)",
      "Advanced AI Mixing & Mastering",
      "Email Support",
      "Project History (30 days)",
    ],
    notIncluded: [
      "Stems Download",
      "Priority Processing",
    ],
    cta: "Get Plus",
    mostPopular: true,
  },
  {
    name: "Pro",
    id: "tier-pro",
    href: "/register?plan=pro",
    priceMonthly: "$49",
    priceYearly: "$39",
    description: "For professionals and studios demanding the highest quality.",
    features: [
      "Unlimited Songs",
      "High-Res WAV + Stems Download",
      "Priority Processing (Skip the queue)",
      "Premium Support",
      "Permanent Project History",
      "Commercial License",
    ],
    notIncluded: [],
    cta: "Get Pro",
    mostPopular: false,
  },
];

export default function PricingPage() {
  const [billingCycle, setBillingCycle] = useState<"monthly" | "yearly">("monthly");

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans selection:bg-teal-500/30">
      {/* Header / Nav */}
      <header className="border-b border-slate-800/80">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-2">
            <Link href="/" className="flex items-center gap-2 group">
              <div className="h-8 w-8 rounded-full bg-teal-400/90 flex items-center justify-center text-slate-950 text-lg font-bold transition group-hover:bg-teal-300" aria-hidden="true">
                A
              </div>
              <span className="text-xl font-bold tracking-tight text-slate-100 group-hover:text-teal-300 transition">
                Audio Alchemy
              </span>
            </Link>
          </div>
          <nav className="flex gap-4">
            <Link href="/" className="text-sm font-medium text-slate-300 hover:text-teal-300 transition">
              Home
            </Link>
            <Link href="/pricing" className="text-sm font-medium text-teal-400">
              Pricing
            </Link>
          </nav>
        </div>
      </header>

      <main className="py-24 sm:py-32">
        <div className="mx-auto max-w-7xl px-6 lg:px-8">
          <div className="mx-auto max-w-4xl text-center">
            <h1 className="text-base font-semibold leading-7 text-teal-400">Pricing</h1>
            <p className="mt-2 text-4xl font-bold tracking-tight text-white sm:text-5xl">
              Pricing plans for every stage of your journey
            </p>
            <p className="mt-6 text-lg leading-8 text-slate-300">
              Choose the perfect plan for your audio production needs. From demos to professional releases, we have you covered.
            </p>
          </div>

          {/* Billing Toggle */}
          <div className="mt-16 flex justify-center">
            <div className="relative flex rounded-full bg-slate-900 p-1 ring-1 ring-slate-800">
              <button
                type="button"
                className={`${
                  billingCycle === "monthly" ? "bg-slate-800 text-white shadow-sm" : "text-slate-400 hover:text-white"
                } relative rounded-full px-6 py-2 text-sm font-semibold transition-all duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-500`}
                onClick={() => setBillingCycle("monthly")}
              >
                Monthly billing
              </button>
              <button
                type="button"
                className={`${
                  billingCycle === "yearly" ? "bg-slate-800 text-white shadow-sm" : "text-slate-400 hover:text-white"
                } relative rounded-full px-6 py-2 text-sm font-semibold transition-all duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-500`}
                onClick={() => setBillingCycle("yearly")}
              >
                Yearly billing <span className="ml-1 text-teal-400 text-xs">(Save ~20%)</span>
              </button>
            </div>
          </div>

          {/* Pricing Cards */}
          <div className="isolate mx-auto mt-10 grid max-w-md grid-cols-1 gap-8 lg:mx-0 lg:max-w-none lg:grid-cols-3">
            {TIERS.map((tier) => (
              <div
                key={tier.id}
                className={`relative flex flex-col justify-between rounded-3xl p-8 ring-1 xl:p-10 transition hover:scale-105 duration-300 ${
                  tier.mostPopular
                    ? "bg-slate-900/50 ring-teal-500 shadow-xl shadow-teal-500/10 z-10"
                    : "bg-slate-900/20 ring-slate-800 hover:bg-slate-900/40"
                }`}
              >
                {tier.mostPopular && (
                  <div className="absolute -top-4 left-1/2 -translate-x-1/2 rounded-full bg-teal-500 px-4 py-1 text-sm font-semibold text-white shadow-sm">
                    Most Popular
                  </div>
                )}
                <div>
                  <div className="flex items-center justify-between gap-x-4">
                    <h3 id={tier.id} className="text-lg font-semibold leading-8 text-white">
                      {tier.name}
                    </h3>
                  </div>
                  <p className="mt-4 text-sm leading-6 text-slate-300">{tier.description}</p>
                  <p className="mt-6 flex items-baseline gap-x-1">
                    <span className="text-4xl font-bold tracking-tight text-white">
                      {billingCycle === "yearly" ? tier.priceYearly : tier.priceMonthly}
                    </span>
                    <span className="text-sm font-semibold leading-6 text-slate-400">/month</span>
                  </p>
                  {billingCycle === "yearly" && tier.priceYearly !== "$0" && (
                    <p className="mt-1 text-xs text-teal-400">
                      Billed yearly (${parseInt(tier.priceYearly.replace("$", "")) * 12}/year)
                    </p>
                  )}

                  <ul role="list" className="mt-8 space-y-3 text-sm leading-6 text-slate-300">
                    {tier.features.map((feature) => (
                      <li key={feature} className="flex gap-x-3">
                        <CheckIcon className="h-6 w-5 flex-none text-teal-400" aria-hidden="true" />
                        {feature}
                      </li>
                    ))}
                    {tier.notIncluded.map((feature) => (
                      <li key={feature} className="flex gap-x-3 text-slate-600">
                        <XMarkIcon className="h-6 w-5 flex-none text-slate-600" aria-hidden="true" />
                        {feature}
                      </li>
                    ))}
                  </ul>
                </div>
                <Link
                  href={tier.href}
                  aria-describedby={tier.id}
                  className={`mt-8 block rounded-full px-3 py-2 text-center text-sm font-semibold leading-6 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ${
                    tier.mostPopular
                      ? "bg-teal-500 text-white hover:bg-teal-400 focus-visible:outline-teal-500 shadow-lg shadow-teal-500/20"
                      : "bg-slate-800 text-white hover:bg-slate-700 focus-visible:outline-slate-700 hover:ring-1 hover:ring-slate-600"
                  }`}
                >
                  {tier.cta}
                </Link>
              </div>
            ))}
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800/80 py-8 text-center text-xs text-slate-400">
        <p>© 2025 Audio Alchemy. All Rights Reserved.</p>
        <div className="mt-4 flex justify-center gap-6">
          <Link href="/terms-of-service" className="hover:text-teal-400 transition">Terms of Service</Link>
          <Link href="/privacy-policy" className="hover:text-teal-400 transition">Privacy Policy</Link>
          <Link href="/cookie-policy" className="hover:text-teal-400 transition">Cookie Policy</Link>
        </div>
      </footer>
      <Script
        id="ld-breadcrumbs-pricing"
        type="application/ld+json"
        strategy="afterInteractive"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbsJsonLd) }}
      />
    </div>
  );
}
