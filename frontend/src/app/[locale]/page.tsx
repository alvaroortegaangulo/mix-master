import type { Metadata } from "next";
import { getTranslations } from 'next-intl/server';
import { LandingPage } from "../../components/landing/LandingPage";

export async function generateMetadata({params}: {params: Promise<{locale: string}>}): Promise<Metadata> {
  const {locale} = await params;
  const t = await getTranslations({locale, namespace: 'Metadata'});

  return {
    description: t('description'),
    alternates: {
      canonical: "/",
    },
  };
}

export default function Page() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans selection:bg-teal-500/30">
      <div className="flex flex-col">
        <LandingPage />
      </div>
    </div>
  );
}
