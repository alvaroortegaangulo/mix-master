import { Link } from "../../../i18n/routing";
import Script from "next/script";
import { useTranslations } from "next-intl";
import FAQItem from "../../../components/FAQItem";

export const metadata = {
  title: "FAQ - Piroola",
  description: "Frequently Asked Questions about Piroola's AI Mixing & Mastering service.",
  alternates: {
    canonical: "/faq",
  },
};

export default function FAQPage() {
  const t = useTranslations('FAQ');

  const FAQ_ITEMS = [
    {
      question: t('items.0.question'),
      answer: t('items.0.answer')
    },
    {
      question: t('items.1.question'),
      answer: t('items.1.answer')
    },
    {
      question: t('items.2.question'),
      answer: t('items.2.answer')
    },
    {
      question: t('items.3.question'),
      answer: t('items.3.answer')
    },
    {
      question: t('items.4.question'),
      answer: t('items.4.answer')
    },
    {
      question: t('items.5.question'),
      answer: t('items.5.answer')
    },
    {
      question: t('items.6.question'),
      answer: t('items.6.answer')
    },
    {
      question: t('items.7.question'),
      answer: t('items.7.answer')
    },
    {
      question: t('items.8.question'),
      answer: t('items.8.answer')
    },
    {
      question: t('items.9.question'),
      answer: t('items.9.answer')
    },
    {
      question: t('items.10.question'),
      answer: t('items.10.answer')
    },
    {
      question: t('items.11.question'),
      answer: t('items.11.answer')
    }
  ];

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: FAQ_ITEMS.map((item) => ({
      "@type": "Question",
      name: item.question,
      acceptedAnswer: {
        "@type": "Answer",
        text: item.answer,
      },
    })),
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
       <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify(jsonLd),
        }}
      />

      <main className="flex-1 px-4 py-12">
        <div className="mx-auto max-w-3xl">
          <h1 className="mb-8 text-4xl font-bold tracking-tight text-teal-400 text-center">
            {t('title')}
          </h1>
          <p className="mb-12 text-center text-slate-400 text-lg">
            {t('subtitle')}
          </p>

          <div className="space-y-6">
            {FAQ_ITEMS.map((item, index) => (
              <FAQItem
                key={index}
                question={item.question}
                answer={item.answer}
              />
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}
