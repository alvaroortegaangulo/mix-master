"use client";

import { useState } from "react";
import { Link } from "../../../i18n/routing";
import { CheckIcon, XMarkIcon } from "@heroicons/react/20/solid";
import Script from "next/script";
import { gaEvent } from "../../../lib/ga";
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

export default function PricingPage() {
  const [billingCycle, setBillingCycle] = useState<"monthly" | "yearly">("monthly");
  const t = useTranslations('Pricing');

  // Helper to get array from translations object
  const getFeatures = (tier: string, type: 'features' | 'notIncluded'): string[] => {
    try {
      const data = t.raw(`Tiers.${tier}.${type}`);
      return data ? Object.values(data) : [];
    } catch (e) {
      return [];
    }
  };

  const TIERS = [
    {
      name: t('Tiers.free.name'),
      id: "tier-free",
      href: "/#upload",
      priceMonthly: "$0",
      priceYearly: "$0",
      description: t('Tiers.free.description'),
      features: getFeatures('free', 'features'),
      notIncluded: getFeatures('free', 'notIncluded'),
      cta: t('Tiers.free.cta'),
      mostPopular: false,
    },
    {
      name: t('Tiers.plus.name'),
      id: "tier-plus",
      href: "/register?plan=plus",
      priceMonthly: "$19",
      priceYearly: "$15",
      description: t('Tiers.plus.description'),
      features: getFeatures('plus', 'features'),
      notIncluded: getFeatures('plus', 'notIncluded'),
      cta: t('Tiers.plus.cta'),
      mostPopular: true,
    },
    {
      name: t('Tiers.pro.name'),
      id: "tier-pro",
      href: "/register?plan=pro",
      priceMonthly: "$49",
      priceYearly: "$39",
      description: t('Tiers.pro.description'),
      features: getFeatures('pro', 'features'),
      notIncluded: getFeatures('pro', 'notIncluded'),
      cta: t('Tiers.pro.cta'),
      mostPopular: false,
    },
  ];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans selection:bg-teal-500/30">
      <main className="py-24 sm:py-32">
        <div className="mx-auto max-w-7xl px-6 lg:px-8">
          <div className="mx-auto max-w-4xl text-center">
            <h1 className="text-base font-semibold leading-7 text-teal-400">{t('title')}</h1>
            <p className="mt-2 text-4xl font-bold tracking-tight text-white sm:text-5xl">
              {t('subtitle')}
            </p>
            <p className="mt-6 text-lg leading-8 text-slate-300">
              {t('description')}
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
                {t('monthlyBilling')}
              </button>
              <button
                type="button"
                className={`${
                  billingCycle === "yearly" ? "bg-slate-800 text-white shadow-sm" : "text-slate-400 hover:text-white"
                } relative rounded-full px-6 py-2 text-sm font-semibold transition-all duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-500`}
                onClick={() => setBillingCycle("yearly")}
              >
                {t('yearlyBilling')} <span className="ml-1 text-teal-400 text-xs">({t('save20')})</span>
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
                    {t('mostPopular')}
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
                    <span className="text-sm font-semibold leading-6 text-slate-400">/{t('month')}</span>
                  </p>
                  {billingCycle === "yearly" && tier.priceYearly !== "$0" && (
                    <p className="mt-1 text-xs text-teal-400">
                      {t('billedYearly')} (${parseInt(tier.priceYearly.replace("$", "")) * 12}/year)
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
                  onClick={() => gaEvent("select_plan", { plan: tier.id, billing: billingCycle })}
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
      <Script
        id="ld-breadcrumbs-pricing"
        type="application/ld+json"
        strategy="afterInteractive"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbsJsonLd) }}
      />
    </div>
  );
}
