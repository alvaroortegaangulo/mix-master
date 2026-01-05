"use client";

import { useState } from "react";
import { Link } from "../../../i18n/routing";
import { CheckIcon, XMarkIcon, BoltIcon, MusicalNoteIcon, CloudArrowDownIcon } from "@heroicons/react/20/solid";
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
      credits: 1,
    },
    {
      name: t('Tiers.artist.name'),
      id: "tier-artist",
      href: "/register?plan=artist",
      priceMonthly: "$9",
      priceYearly: "$7",
      description: t('Tiers.artist.description'),
      features: getFeatures('artist', 'features'),
      notIncluded: getFeatures('artist', 'notIncluded'),
      cta: t('Tiers.artist.cta'),
      mostPopular: false,
      credits: 10,
    },
    {
      name: t('Tiers.producer.name'),
      id: "tier-producer",
      href: "/register?plan=producer",
      priceMonthly: "$29",
      priceYearly: "$24",
      description: t('Tiers.producer.description'),
      features: getFeatures('producer', 'features'),
      notIncluded: getFeatures('producer', 'notIncluded'),
      cta: t('Tiers.producer.cta'),
      mostPopular: true,
      credits: 50,
    },
    {
      name: t('Tiers.studio.name'),
      id: "tier-studio",
      href: "/register?plan=studio",
      priceMonthly: "$69",
      priceYearly: "$55",
      description: t('Tiers.studio.description'),
      features: getFeatures('studio', 'features'),
      notIncluded: getFeatures('studio', 'notIncluded'),
      cta: t('Tiers.studio.cta'),
      mostPopular: false,
      credits: 150,
    },
  ];

  const PACKS = [
    {
      name: t('payAsYouGo.smallPack.name'),
      price: t('payAsYouGo.smallPack.price'),
      credits: t('payAsYouGo.smallPack.credits'),
      desc: t('payAsYouGo.smallPack.desc'),
    },
    {
      name: t('payAsYouGo.largePack.name'),
      price: t('payAsYouGo.largePack.price'),
      credits: t('payAsYouGo.largePack.credits'),
      desc: t('payAsYouGo.largePack.desc'),
    },
  ];

  const COMPARISON_ROWS = [
    { key: 'monthlyCredits', label: t('Comparison.rows.monthlyCredits'), values: ['1', '10', '50', '150'] },
    { key: 'previews', label: t('Comparison.rows.previews'), values: [t('Comparison.values.unlimited'), t('Comparison.values.unlimited'), t('Comparison.values.unlimited'), t('Comparison.values.unlimited')] },
    { key: 'maxStems', label: t('Comparison.rows.maxStems'), values: [t('Comparison.values.limited4'), t('Comparison.values.limited4'), t('Comparison.values.unlimitedStems'), t('Comparison.values.unlimitedStems')] },
    { key: 'quality', label: t('Comparison.rows.quality'), values: [t('Comparison.values.mp3low'), t('Comparison.values.mp3high'), t('Comparison.values.wav'), t('Comparison.values.wav')] },
    { key: 'storage', label: t('Comparison.rows.storage'), values: [t('Comparison.values.days7'), t('Comparison.values.days7'), t('Comparison.values.days30'), t('Comparison.values.permanent')] },
    { key: 'stemDownload', label: t('Comparison.rows.stemDownload'), values: [t('Comparison.values.no'), t('Comparison.values.no'), t('Comparison.values.no'), t('Comparison.values.yes')] },
    { key: 'support', label: t('Comparison.rows.support'), values: [t('Comparison.values.standard'), t('Comparison.values.standard'), t('Comparison.values.priority'), t('Comparison.values.priority')] },
  ];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans selection:bg-teal-500/30">
      <main className="py-24 sm:py-32">
        <div className="mx-auto max-w-7xl px-6 lg:px-8">

          {/* Header */}
          <div className="mx-auto max-w-4xl text-center">
            <h1 className="text-base font-semibold leading-7 text-teal-400 uppercase tracking-widest font-display">{t('title')}</h1>
            <p className="mt-2 text-4xl font-bold tracking-tight text-white sm:text-5xl font-display">
              {t('subtitle')}
            </p>
            <p className="mt-6 text-lg leading-8 text-slate-300">
              {t('description')}
            </p>
          </div>

          {/* Credit System Explanation */}
          <div className="mx-auto mt-16 max-w-5xl">
            <h2 className="text-2xl font-bold text-center text-white mb-8">{t('creditSystem.title')}</h2>
            <p className="text-center text-slate-400 mb-10 max-w-2xl mx-auto">{t('creditSystem.description')}</p>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              {/* Mastering */}
              <div className="bg-slate-900/40 rounded-2xl p-6 border border-slate-800 flex flex-col items-center text-center hover:bg-slate-900/60 transition">
                <div className="h-12 w-12 rounded-full bg-teal-500/10 flex items-center justify-center mb-4 text-teal-400">
                  <MusicalNoteIcon className="h-6 w-6" />
                </div>
                <h3 className="text-lg font-semibold text-white">{t('creditSystem.mastering.title')}</h3>
                <p className="text-3xl font-bold text-teal-400 mt-2">{t('creditSystem.mastering.cost')}</p>
                <p className="text-sm text-slate-400 mt-2">{t('creditSystem.mastering.desc')}</p>
              </div>

              {/* Mixing */}
              <div className="bg-slate-900/40 rounded-2xl p-6 border border-slate-800 flex flex-col items-center text-center hover:bg-slate-900/60 transition">
                <div className="h-12 w-12 rounded-full bg-purple-500/10 flex items-center justify-center mb-4 text-purple-400">
                  <BoltIcon className="h-6 w-6" />
                </div>
                <h3 className="text-lg font-semibold text-white">{t('creditSystem.mixing.title')}</h3>
                <p className="text-3xl font-bold text-purple-400 mt-2">{t('creditSystem.mixing.cost')}</p>
                <p className="text-sm text-slate-400 mt-2">{t('creditSystem.mixing.desc')}</p>
              </div>

              {/* Downloads */}
              <div className="bg-slate-900/40 rounded-2xl p-6 border border-slate-800 flex flex-col items-center text-center hover:bg-slate-900/60 transition">
                <div className="h-12 w-12 rounded-full bg-amber-500/10 flex items-center justify-center mb-4 text-amber-400">
                  <CloudArrowDownIcon className="h-6 w-6" />
                </div>
                <h3 className="text-lg font-semibold text-white">{t('creditSystem.download.title')}</h3>
                <p className="text-3xl font-bold text-amber-400 mt-2">{t('creditSystem.download.cost')}</p>
                <p className="text-sm text-slate-400 mt-2">{t('creditSystem.download.desc')}</p>
              </div>
            </div>
          </div>

          {/* Billing Toggle */}
          <div className="mt-20 flex justify-center">
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
          <div className="isolate mx-auto mt-10 grid max-w-md grid-cols-1 gap-8 lg:mx-0 lg:max-w-none lg:grid-cols-4">
            {TIERS.map((tier) => (
              <div
                key={tier.id}
                className={`relative flex flex-col justify-between rounded-3xl p-6 xl:p-8 ring-1 transition hover:scale-[1.02] duration-300 ${
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
                  <p className="mt-4 text-sm leading-6 text-slate-300 min-h-[48px]">{tier.description}</p>

                  <div className="mt-6 flex items-baseline gap-x-1">
                    <span className="text-4xl font-bold tracking-tight text-white">
                      {billingCycle === "yearly" ? tier.priceYearly : tier.priceMonthly}
                    </span>
                    <span className="text-sm font-semibold leading-6 text-slate-400">/{t('month')}</span>
                  </div>

                  {/* Credit Highlight */}
                  <div className="mt-4 inline-flex items-center rounded-md bg-teal-400/10 px-2 py-1 text-sm font-medium text-teal-400 ring-1 ring-inset ring-teal-400/20">
                    {tier.credits} {t('credits')} / {t('month')}
                  </div>

                  {billingCycle === "yearly" && tier.priceYearly !== "$0" && (
                    <p className="mt-2 text-xs text-slate-500">
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

          {/* Pay As You Go Section */}
          <div className="mx-auto mt-24 max-w-4xl">
             <div className="text-center mb-10">
                <h2 className="text-2xl font-bold text-white">{t('payAsYouGo.title')}</h2>
                <p className="mt-2 text-slate-400">{t('payAsYouGo.subtitle')}</p>
             </div>

             <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                {PACKS.map((pack) => (
                  <div key={pack.name} className="flex flex-col md:flex-row items-center justify-between rounded-3xl bg-slate-900/30 border border-slate-800 p-8 hover:bg-slate-900/50 transition">
                    <div className="text-center md:text-left mb-6 md:mb-0">
                      <h3 className="text-xl font-semibold text-white">{pack.name}</h3>
                      <p className="text-sm text-slate-400 mt-1">{pack.desc}</p>
                      <div className="mt-3 flex items-center justify-center md:justify-start gap-3">
                        <span className="text-3xl font-bold text-teal-400">{pack.price}</span>
                        <span className="inline-flex items-center rounded-md bg-teal-400/10 px-2 py-1 text-sm font-medium text-teal-400 ring-1 ring-inset ring-teal-400/20">
                          {pack.credits}
                        </span>
                      </div>
                    </div>
                    <Link
                      href="/register?mode=pack"
                      className="rounded-full bg-slate-800 px-6 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-slate-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
                    >
                      {t('payAsYouGo.cta')}
                    </Link>
                  </div>
                ))}
             </div>
          </div>

          {/* Comparison Table */}
          <div className="mx-auto mt-24 max-w-7xl">
            <h2 className="text-2xl font-bold text-white text-center mb-10">{t('Comparison.title')}</h2>
            <div className="overflow-x-auto rounded-3xl border border-slate-800">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-slate-900/50 border-b border-slate-800">
                    <th className="p-4 text-sm font-semibold text-slate-200 min-w-[200px]">{t('Comparison.headers.features')}</th>
                    <th className="p-4 text-sm font-semibold text-center text-white min-w-[140px]">{t('Comparison.headers.free')}</th>
                    <th className="p-4 text-sm font-semibold text-center text-teal-400 min-w-[140px]">{t('Comparison.headers.artist')}</th>
                    <th className="p-4 text-sm font-semibold text-center text-purple-400 min-w-[140px]">{t('Comparison.headers.producer')}</th>
                    <th className="p-4 text-sm font-semibold text-center text-amber-400 min-w-[140px]">{t('Comparison.headers.studio')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800 bg-slate-900/20">
                  {COMPARISON_ROWS.map((row) => (
                    <tr key={row.key} className="hover:bg-slate-900/40 transition">
                      <td className="p-4 text-sm font-medium text-slate-300">{row.label}</td>
                      {row.values.map((val, idx) => (
                        <td key={idx} className={`p-4 text-sm text-center ${idx === 0 ? 'text-slate-400' : 'text-slate-300'}`}>
                          {val === t('Comparison.values.yes') ? (
                            <CheckIcon className="h-5 w-5 text-teal-400 mx-auto" />
                          ) : val === t('Comparison.values.no') ? (
                            <span className="text-slate-600">-</span>
                          ) : (
                            val
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
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
