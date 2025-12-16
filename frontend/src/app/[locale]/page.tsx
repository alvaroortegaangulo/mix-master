import type { Metadata } from "next";
import { getTranslations } from 'next-intl/server';
import { HomeClient } from "../../components/HomeClient";
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
    <HomeClient>
      <LandingPage />
    </HomeClient>
  );
}
