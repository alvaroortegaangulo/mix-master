import { Link } from "../i18n/routing";
import Image from "next/image";
import { useTranslations } from "next-intl";

export function Footer() {
  const t = useTranslations('Footer');

  return (
    <footer className="bg-slate-950 border-t border-slate-800 py-12 px-4 z-10 relative">
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-center gap-8 text-slate-400 text-sm">
        <div className="flex items-center gap-2">
           <Image src="/logo.webp" alt="Piroola Logo" width={24} height={24} className="h-6 w-6" />
           <span className="font-semibold text-slate-200">Piroola</span>
        </div>
        <div className="flex gap-6">
          <Link href="/terms-of-service" className="hover:text-white transition">{t('terms')}</Link>
          <Link href="/privacy-policy" className="hover:text-white transition">{t('privacy')}</Link>
          <Link href="/cookie-policy" className="hover:text-white transition">{t('cookies')}</Link>
          <Link href="/support" className="hover:text-white transition">{t('contact')}</Link>
          <Link href="/rss.xml" className="hover:text-white transition">{t('rss')}</Link>
        </div>
        <div>
            {t('copyright')}
        </div>
      </div>
    </footer>
  );
}
