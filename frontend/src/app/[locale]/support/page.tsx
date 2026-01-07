"use client";

import { Link } from "../../../i18n/routing";
import { useState, type FormEvent } from "react";
import Script from "next/script";
import { useTranslations } from "next-intl";
import {
  MagnifyingGlassIcon,
  VideoCameraIcon,
  BookOpenIcon,
  QuestionMarkCircleIcon,
  ServerIcon,
  CheckCircleIcon,
  PaperClipIcon,
  PaperAirplaneIcon,
  ArrowRightIcon,
  ExclamationCircleIcon,
  ChatBubbleLeftRightIcon
} from "@heroicons/react/24/outline";

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
  const tFaq = useTranslations('FAQ.items');
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    subject: "",
    message: "",
  });
  const [status, setStatus] = useState<"idle" | "submitting" | "success" | "error">("idle");
  const [activeTab, setActiveTab] = useState<"support" | "billing">("support");
  const [searchQuery, setSearchQuery] = useState("");
  const [openFaq, setOpenFaq] = useState<number | null>(null);

  const helpArticles = [
    { title: t('articles.formats'), link: "/faq" },
    { title: t('articles.export'), link: "/docs" },
    { title: t('articles.levels'), link: "/docs" },
    { title: t('articles.payment'), link: "#" },
    { title: t('articles.refunds'), link: "#" },
    { title: t('articles.mastering'), link: "/docs" }
  ];

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

  const toggleFaq = (index: number) => {
    setOpenFaq(openFaq === index ? null : index);
  };

  const filteredArticles = helpArticles.filter(article =>
    article.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Hero Section */}
      <section className="relative py-20 overflow-hidden">
        {/* Background Visual */}
        <div className="absolute inset-0 pointer-events-none">
            <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-7xl h-full opacity-30">
                 <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-teal-500/20 rounded-full blur-[100px] animate-pulse"></div>
                 <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-violet-600/20 rounded-full blur-[100px] animate-pulse delay-1000"></div>
            </div>
             <div className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm"></div>
        </div>

        <div className="relative z-10 max-w-7xl mx-auto px-4 text-center">
            <span className="inline-block py-1 px-3 rounded-full bg-slate-800/50 border border-slate-700 text-teal-400 text-xs font-bold tracking-wider mb-6 backdrop-blur-md">
                {t('title')}
            </span>
            <h1 className="text-4xl md:text-5xl font-bold text-white mb-6 font-display">
                <span className="text-transparent bg-clip-text bg-gradient-to-r from-teal-400 to-violet-500">
                  {t('heroSearchPlaceholder')}
                </span>
            </h1>
            
            {/* Search Bar */}
            <div className="relative max-w-xl mx-auto group">
                <div className="absolute -inset-1 bg-gradient-to-r from-teal-500 to-violet-600 rounded-lg blur opacity-25 group-focus-within:opacity-50 transition duration-200"></div>
                <div className="relative bg-slate-900 rounded-lg shadow-xl flex items-center p-2 border border-slate-700/50">
                    <MagnifyingGlassIcon className="w-6 h-6 text-slate-400 ml-3" />
                    <input
                        type="text"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        placeholder={t('heroSearchPlaceholder')}
                        className="w-full bg-transparent border-none text-white placeholder-slate-500 focus:ring-0 px-4 py-2 text-lg"
                    />
                </div>

                 {/* Search Results Dropdown */}
                 {searchQuery.length > 1 && (
                    <div className="absolute top-full left-0 right-0 mt-2 bg-slate-900 border border-slate-700 rounded-lg shadow-2xl overflow-hidden z-50">
                        {filteredArticles.length > 0 ? (
                            filteredArticles.map((article, index) => (
                                <Link key={index} href={article.link} className="block px-4 py-3 border-b border-slate-800 hover:bg-slate-800/50 transition-colors flex items-center justify-between group">
                                    <span className="text-sm text-slate-200 group-hover:text-white">{article.title}</span>
                                    <ArrowRightIcon className="w-4 h-4 text-slate-500 group-hover:text-teal-400" />
                                </Link>
                            ))
                        ) : (
                            <div className="px-4 py-3 text-sm text-slate-500">{t('searchNoResults')} "{searchQuery}"</div>
                        )}
                    </div>
                 )}
            </div>
        </div>
      </section>

      <main className="flex-1 max-w-7xl mx-auto px-4 pb-20 w-full">
        {/* Quick Access Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 -mt-10 relative z-20 mb-16">
            <Link href="/docs" className="bg-slate-900/80 backdrop-blur border border-slate-800 p-6 rounded-xl hover:bg-slate-800/80 transition-all hover:-translate-y-1 hover:border-teal-500/30 group shadow-lg">
                <div className="w-12 h-12 rounded-lg bg-teal-500/10 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                    <BookOpenIcon className="w-6 h-6 text-teal-400" />
                </div>
                <h3 className="text-lg font-semibold text-white mb-2">{t('quickAccess.quickStart')}</h3>
                <p className="text-sm text-slate-400">{t('quickResourcesDesc')}</p>
            </Link>

            <Link href="#" className="bg-slate-900/80 backdrop-blur border border-slate-800 p-6 rounded-xl hover:bg-slate-800/80 transition-all hover:-translate-y-1 hover:border-violet-500/30 group shadow-lg">
                 <div className="w-12 h-12 rounded-lg bg-violet-500/10 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                    <VideoCameraIcon className="w-6 h-6 text-violet-400" />
                </div>
                <h3 className="text-lg font-semibold text-white mb-2">{t('quickAccess.videoTutorials')}</h3>
                <p className="text-sm text-slate-400">{t('quickAccess.videoTutorialsDesc')}</p>
            </Link>

            <button onClick={() => document.getElementById('faq-section')?.scrollIntoView({ behavior: 'smooth' })} className="bg-slate-900/80 backdrop-blur border border-slate-800 p-6 rounded-xl hover:bg-slate-800/80 transition-all hover:-translate-y-1 hover:border-amber-500/30 group shadow-lg text-left">
                 <div className="w-12 h-12 rounded-lg bg-amber-500/10 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                    <QuestionMarkCircleIcon className="w-6 h-6 text-amber-400" />
                </div>
                <h3 className="text-lg font-semibold text-white mb-2">{t('quickAccess.faq')}</h3>
                <p className="text-sm text-slate-400">{t('faqLink')}</p>
            </button>

            <div className="bg-slate-900/80 backdrop-blur border border-slate-800 p-6 rounded-xl hover:bg-slate-800/80 transition-all hover:-translate-y-1 hover:border-emerald-500/30 group shadow-lg">
                 <div className="w-12 h-12 rounded-lg bg-emerald-500/10 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                    <ServerIcon className="w-6 h-6 text-emerald-400" />
                </div>
                <h3 className="text-lg font-semibold text-white mb-2">{t('quickAccess.systemStatus')}</h3>
                <div className="flex items-center gap-2">
                    <span className="relative flex h-2 w-2">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                    </span>
                    <span className="text-xs text-emerald-400 font-medium">{t('systemStatus.allSystemsOperational')}</span>
                </div>
            </div>
        </div>

        {/* FAQ Section */}
        <div id="faq-section" className="mb-20 scroll-mt-24">
            <h2 className="text-2xl font-bold text-white mb-8 text-center">{t('faqLink')}</h2>
            <div className="max-w-3xl mx-auto space-y-4">
                {[0, 1, 2, 3, 4, 10].map((idx) => (
                    <div key={idx} className="border border-slate-800 rounded-lg overflow-hidden bg-slate-900/50">
                        <button
                            onClick={() => toggleFaq(idx)}
                            className={`w-full flex items-center justify-between p-4 text-left transition-colors ${openFaq === idx ? 'bg-slate-800' : 'bg-slate-800/50 hover:bg-slate-800'}`}
                        >
                            <span className="font-medium text-slate-200">{tFaq(`${idx}.question`)}</span>
                            <ArrowRightIcon className={`w-5 h-5 text-slate-500 transition-transform duration-300 ${openFaq === idx ? 'rotate-90' : ''}`} />
                        </button>
                        {openFaq === idx && (
                            <div className="p-4 text-slate-400 text-sm leading-relaxed border-t border-slate-800 animate-fade-in">
                                {tFaq(`${idx}.answer`)}
                            </div>
                        )}
                    </div>
                ))}
            </div>
        </div>

        {/* Contact Section Split */}
        <div className="grid lg:grid-cols-5 gap-8 lg:gap-12">
            {/* Left Info */}
            <div className="lg:col-span-2 space-y-8">
                <div>
                    <h2 className="text-2xl font-bold text-white mb-4">{t('directContact')}</h2>
                    <p className="text-slate-400 leading-relaxed mb-6">
                        {t('directContactDesc')}
                    </p>
                    <div className="flex items-center gap-4 text-slate-300 mb-4 p-4 bg-slate-900 rounded-lg border border-slate-800">
                        <div className="w-10 h-10 rounded-full bg-teal-500/10 flex items-center justify-center shrink-0">
                             <ChatBubbleLeftRightIcon className="w-5 h-5 text-teal-400" />
                        </div>
                        <div>
                            <div className="text-xs text-slate-500 uppercase font-bold tracking-wider mb-1">Email Support</div>
                            <a href="mailto:support@piroola.com" className="text-white hover:text-teal-400 transition font-medium">support@piroola.com</a>
                        </div>
                    </div>

                    <div className="p-6 bg-gradient-to-br from-slate-900 to-slate-800 rounded-2xl border border-slate-700/50 relative overflow-hidden group">
                        <div className="absolute top-0 right-0 w-32 h-32 bg-teal-500/5 rounded-full blur-3xl group-hover:bg-teal-500/10 transition-colors"></div>
                        <h3 className="text-lg font-semibold text-white mb-2 relative z-10">{t('quickAccess.systemStatus')}</h3>
                        <p className="text-sm text-slate-400 mb-4 relative z-10">{t('quickAccess.checkStatusDesc')}</p>
                        <div className="flex items-center gap-2 relative z-10">
                            <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                            <span className="text-emerald-400 text-sm font-medium">{t('quickAccess.apiOperational')}</span>
                        </div>
                         <div className="flex items-center gap-2 mt-2 relative z-10">
                            <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                            <span className="text-emerald-400 text-sm font-medium">{t('quickAccess.workerNodesOperational')}</span>
                        </div>
                    </div>
                </div>
            </div>

            {/* Right Form */}
            <div className="lg:col-span-3">
                <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 md:p-8 shadow-2xl relative">
                    <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-teal-500 to-violet-500"></div>

                    {/* Tabs */}
                    <div className="flex bg-slate-950 p-1 rounded-lg mb-8">
                        <button
                            onClick={() => setActiveTab('support')}
                            className={`flex-1 py-2 text-sm font-medium rounded-md transition-all ${activeTab === 'support' ? 'bg-slate-800 text-white shadow-sm' : 'text-slate-400 hover:text-white'}`}
                        >
                            {t('contactTabs.technical')}
                        </button>
                        <button
                            onClick={() => setActiveTab('billing')}
                            className={`flex-1 py-2 text-sm font-medium rounded-md transition-all ${activeTab === 'billing' ? 'bg-slate-800 text-white shadow-sm' : 'text-slate-400 hover:text-white'}`}
                        >
                            {t('contactTabs.billing')}
                        </button>
                    </div>

                    <div className="mb-6">
                        <h3 className="text-xl font-bold text-white mb-2">
                            {activeTab === 'support' ? t('formTitle') : t('contactTabs.billing')}
                        </h3>
                        <p className="text-slate-400 text-sm">
                            {activeTab === 'support' ? t('contactTabs.technicalDesc') : t('contactTabs.billingDesc')}
                        </p>
                    </div>

                    {status === "success" ? (
                      <div className="text-center py-12 bg-slate-950/50 rounded-xl border border-dashed border-slate-800">
                        <div className="w-16 h-16 bg-emerald-500/10 text-emerald-500 rounded-full flex items-center justify-center mx-auto mb-4">
                             <CheckCircleIcon className="w-8 h-8" />
                        </div>
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
                      <form onSubmit={handleSubmit} className="space-y-5">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                          <div className="space-y-1.5">
                            <label htmlFor="name" className="text-xs font-medium text-slate-400 uppercase tracking-wider">{t('labels.name')}</label>
                            <input
                              type="text"
                              id="name"
                              name="name"
                              required
                              value={formData.name}
                              onChange={handleChange}
                              className="w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-slate-100 placeholder-slate-600 focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500 transition"
                              placeholder={t('placeholders.name')}
                            />
                          </div>
                          <div className="space-y-1.5">
                            <label htmlFor="email" className="text-xs font-medium text-slate-400 uppercase tracking-wider">{t('labels.email')}</label>
                            <input
                              type="email"
                              id="email"
                              name="email"
                              required
                              value={formData.email}
                              onChange={handleChange}
                              className="w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-slate-100 placeholder-slate-600 focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500 transition"
                              placeholder={t('placeholders.email')}
                            />
                          </div>
                        </div>

                        <div className="space-y-1.5">
                          <label htmlFor="subject" className="text-xs font-medium text-slate-400 uppercase tracking-wider">{t('labels.subject')}</label>
                          <div className="relative">
                            <select
                                id="subject"
                                name="subject"
                                required
                                value={formData.subject}
                                onChange={handleChange}
                                className="w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-slate-100 placeholder-slate-600 focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500 transition appearance-none"
                            >
                                <option value="" disabled>{t('options.default')}</option>
                                {activeTab === 'support' ? (
                                    <>
                                        <option value="upload">{t('technicalOptions.uploadError')}</option>
                                        <option value="download">{t('technicalOptions.downloadError')}</option>
                                        <option value="quality">{t('technicalOptions.audioQuality')}</option>
                                        <option value="other">{t('technicalOptions.other')}</option>
                                    </>
                                ) : (
                                    <>
                                        <option value="invoice">{t('billingOptions.invoice')}</option>
                                        <option value="cancel">{t('billingOptions.cancel')}</option>
                                        <option value="plan">{t('billingOptions.changePlan')}</option>
                                        <option value="payment">{t('billingOptions.paymentMethod')}</option>
                                    </>
                                )}
                            </select>
                             <div className="absolute inset-y-0 right-0 flex items-center px-4 pointer-events-none">
                                <ArrowRightIcon className="w-4 h-4 text-slate-500 rotate-90" />
                            </div>
                          </div>
                        </div>

                        <div className="space-y-1.5">
                          <label htmlFor="message" className="text-xs font-medium text-slate-400 uppercase tracking-wider">{t('labels.message')}</label>
                          <textarea
                            id="message"
                            name="message"
                            required
                            rows={4}
                            value={formData.message}
                            onChange={handleChange}
                            className="w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-slate-100 placeholder-slate-600 focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500 transition resize-none"
                            placeholder={t('placeholders.message')}
                          />
                        </div>

                        {/* Optional Attachment (Visual Only) */}
                        <div className="flex items-center gap-2 p-3 rounded-lg border border-dashed border-slate-700/50 hover:bg-slate-800/30 transition-colors cursor-pointer group">
                             <PaperClipIcon className="w-5 h-5 text-slate-500 group-hover:text-teal-400 transition-colors" />
                             <span className="text-sm text-slate-500 group-hover:text-slate-300 transition-colors">{t('attachFile')}</span>
                        </div>

                        <button
                            type="submit"
                            disabled={status === "submitting"}
                            className="w-full bg-teal-500 hover:bg-teal-400 text-slate-950 font-bold py-3.5 rounded-lg shadow-lg shadow-teal-500/20 transition-all transform active:scale-95 flex items-center justify-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed disabled:transform-none"
                        >
                            {status === "submitting" ? (
                                <>
                                    <div className="w-5 h-5 border-2 border-slate-950/30 border-t-slate-950 rounded-full animate-spin"></div>
                                    <span>{t('labels.sending')}</span>
                                </>
                            ) : (
                                <>
                                    <span>{t('labels.submit')}</span>
                                    <PaperAirplaneIcon className="w-5 h-5" />
                                </>
                            )}
                        </button>
                      </form>
                    )}
                </div>

                 {/* Direct Contact Info Small */}
                <div className="mt-6 flex items-center justify-between text-xs text-slate-500 px-2">
                    <span>Email: <a href="mailto:support@piroola.com" className="text-teal-400 hover:underline">support@piroola.com</a></span>
                    <span className="flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span> Online Support</span>
                </div>
            </div>
        </div>
      </main>

      {/* System Status Banner Footer */}
      <div className="bg-slate-900 border-t border-slate-800 py-4">
        <div className="max-w-7xl mx-auto px-4 flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-3">
                <span className="relative flex h-2.5 w-2.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
                </span>
                <span className="text-sm text-slate-300 font-medium">{t('systemStatus.allSystemsOperational')}</span>
                <span className="hidden sm:inline text-xs text-slate-500 border-l border-slate-700 pl-3 ml-1">v2.4.1 (Latest)</span>
            </div>
            <div className="flex gap-6">
                <Link href="#" className="text-slate-500 hover:text-white text-xs transition-colors">{t('systemStatus.serviceStatus')}</Link>
                <Link href="/privacy-policy" className="text-slate-500 hover:text-white text-xs transition-colors">{t('systemStatus.privacyPolicy')}</Link>
                <Link href="/terms-of-service" className="text-slate-500 hover:text-white text-xs transition-colors">{t('systemStatus.terms')}</Link>
            </div>
        </div>
      </div>

      <Script
        id="ld-breadcrumbs-support"
        type="application/ld+json"
        strategy="afterInteractive"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbsJsonLd) }}
      />
    </div>
  );
}
