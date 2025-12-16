"use client";

import { Link } from "../../../i18n/routing";
import { useState, type FormEvent } from "react";
import Script from "next/script";
import { useTranslations } from "next-intl";
import { getTranslations } from "next-intl/server";

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
      name: "Support",
      item: `${siteUrl}/support`,
    },
  ],
};

export default function SupportPage() {
  const t = useTranslations('Support');
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    subject: "",
    message: "",
  });
  const [status, setStatus] = useState<"idle" | "submitting" | "success" | "error">("idle");

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setStatus("submitting");

    // Simulate API call
    try {
      await new Promise((resolve) => setTimeout(resolve, 1500));
      setStatus("success");
      setFormData({ name: "", email: "", subject: "", message: "" });
    } catch (error) {
      console.error(error);
      setStatus("error");
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      <main className="flex-1 px-4 py-12">
        <div className="mx-auto max-w-3xl">
          <h1 className="mb-4 text-4xl font-bold tracking-tight text-teal-400 text-center">
            {t('title')}
          </h1>
          <p className="mb-12 text-center text-slate-400 text-lg">
            {t('subtitle')}
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-12">
            <div className="rounded-2xl border border-slate-800/60 bg-slate-900/50 p-6 shadow-lg">
              <h2 className="text-xl font-semibold text-slate-200 mb-4">{t('quickResources')}</h2>
              <p className="text-slate-400 mb-6">
                {t('quickResourcesDesc')}
              </p>
              <div className="flex flex-col gap-3">
                <Link 
                  href="/faq" 
                  className="inline-flex items-center justify-between px-4 py-3 rounded-lg bg-slate-800/50 hover:bg-slate-800 hover:text-teal-400 transition border border-slate-700/50"
                >
                  <span>{t('faqLink')}</span>
                  <span>→</span>
                </Link>
                <Link 
                  href="/docs" 
                  className="inline-flex items-center justify-between px-4 py-3 rounded-lg bg-slate-800/50 hover:bg-slate-800 hover:text-teal-400 transition border border-slate-700/50"
                >
                  <span>{t('docsLink')}</span>
                  <span>→</span>
                </Link>
              </div>
            </div>

             <div className="rounded-2xl border border-slate-800/60 bg-slate-900/50 p-6 shadow-lg">
              <h2 className="text-xl font-semibold text-slate-200 mb-4">{t('directContact')}</h2>
              <p className="text-slate-400 mb-6">
                {t('directContactDesc')}
              </p>
              <div className="flex items-center gap-3 text-slate-300 mb-2">
                <a href="mailto:support@audioalchemy.com" className="hover:text-teal-400 transition">support@audioalchemy.com</a>
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-800/60 bg-slate-900/50 p-8 shadow-xl">
            <h2 className="text-2xl font-semibold text-slate-200 mb-6 text-center">{t('formTitle')}</h2>
            
            {status === "success" ? (
              <div className="text-center py-12">
                <h3 className="text-xl font-medium text-slate-100 mb-2">{t('successTitle')}</h3>
                <p className="text-slate-400">{t('successDesc')}</p>
                <button 
                  onClick={() => setStatus("idle")}
                  className="mt-6 text-teal-400 hover:text-teal-300 font-medium text-sm hover:underline"
                >
                  {t('sendAnother')}
                </button>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-2">
                    <label htmlFor="name" className="text-sm font-medium text-slate-300">{t('labels.name')}</label>
                    <input
                      type="text"
                      id="name"
                      name="name"
                      required
                      value={formData.name}
                      onChange={handleChange}
                      className="w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-2.5 text-slate-100 placeholder-slate-500 focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500 transition"
                      placeholder={t('placeholders.name')}
                    />
                  </div>
                  <div className="space-y-2">
                    <label htmlFor="email" className="text-sm font-medium text-slate-300">{t('labels.email')}</label>
                    <input
                      type="email"
                      id="email"
                      name="email"
                      required
                      value={formData.email}
                      onChange={handleChange}
                      className="w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-2.5 text-slate-100 placeholder-slate-500 focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500 transition"
                      placeholder={t('placeholders.email')}
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <label htmlFor="subject" className="text-sm font-medium text-slate-300">{t('labels.subject')}</label>
                  <select
                    id="subject"
                    name="subject"
                    required
                    value={formData.subject}
                    onChange={handleChange}
                    className="w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-2.5 text-slate-100 placeholder-slate-500 focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500 transition appearance-none"
                  >
                    <option value="" disabled>{t('options.default')}</option>
                    <option value="technical">{t('options.technical')}</option>
                    <option value="billing">{t('options.billing')}</option>
                    <option value="feedback">{t('options.feedback')}</option>
                    <option value="other">{t('options.other')}</option>
                  </select>
                </div>

                <div className="space-y-2">
                  <label htmlFor="message" className="text-sm font-medium text-slate-300">{t('labels.message')}</label>
                  <textarea
                    id="message"
                    name="message"
                    required
                    rows={5}
                    value={formData.message}
                    onChange={handleChange}
                    className="w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-2.5 text-slate-100 placeholder-slate-500 focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500 transition resize-none"
                    placeholder={t('placeholders.message')}
                  />
                </div>

                <div className="pt-2">
                  <button
                    type="submit"
                    disabled={status === "submitting"}
                    className="w-full rounded-full bg-teal-500 py-3 text-sm font-bold text-slate-950 shadow-md shadow-teal-500/20 hover:bg-teal-400 hover:shadow-teal-500/30 transition disabled:opacity-60 disabled:cursor-not-allowed"
                  >
                    {status === "submitting" ? t('labels.sending') : t('labels.submit')}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      </main>
      <Script
        id="ld-breadcrumbs-support"
        type="application/ld+json"
        strategy="afterInteractive"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbsJsonLd) }}
      />
    </div>
  );
}
