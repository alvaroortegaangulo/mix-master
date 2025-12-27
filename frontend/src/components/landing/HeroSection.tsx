import Image from "next/image";
import { PlayCircleIcon, StarIcon } from "@heroicons/react/24/solid";
import { useTranslations } from 'next-intl';
import { Link } from '../../i18n/routing';

export function HeroSection({ onTryIt }: { onTryIt: () => void }) {
  const t = useTranslations('HeroSection');

  return (
    <section className="relative flex min-h-[70vh] lg:min-h-[75vh] 2xl:min-h-[85vh] flex-col items-center justify-center overflow-hidden bg-slate-950 px-4 text-center py-8 md:py-10 2xl:py-14">
      {/* Background Image */}
      <div className="absolute inset-0 z-0 pointer-events-none">
        <Image
          src="/background_hero.webp"
          alt=""
          fill
          sizes="100vw"
          className="object-cover opacity-20"
          quality={60}
          loading="lazy"
          aria-hidden="true"
        />
      </div>

      {/* Background gradients/blobs */}
      <div className="absolute top-0 left-0 h-full w-full overflow-hidden pointer-events-none z-0">
        <div className="absolute -top-[20%] -left-[10%] h-[50%] w-[50%] rounded-full bg-teal-500/10 blur-[120px]" />
        <div className="absolute top-[40%] -right-[10%] h-[60%] w-[60%] rounded-full bg-violet-600/10 blur-[120px]" />
      </div>

      <div className="relative z-10 max-w-5xl space-y-2 sm:space-y-3 lg:space-y-4 flex flex-col items-center">
        {/* Logo */}
        <div className="mx-auto flex justify-center mb-1 animate-in fade-in zoom-in duration-1000">
          <Image
            src="/logo.webp"
            alt="Piroola logo"
            width={96}
            height={96}
            sizes="96px"
            className="h-14 w-14 sm:h-16 sm:w-16"
            priority
          />
        </div>

        {/* Main Heading - LCP Element (No entrance animation to minimize render delay) */}
        <h1 className="flex flex-col text-4xl font-extrabold tracking-[-0.02em] sm:text-5xl lg:text-6xl 2xl:text-7xl gap-1">
          <span className="text-white leading-[0.95]">
            {t('studioSound')}
          </span>
          <span className="bg-gradient-to-r from-teal-400 to-violet-500 bg-clip-text text-transparent leading-[0.95]">
            {t('perfectedByAI')}
          </span>
        </h1>

        <p className="mx-auto max-w-3xl text-xs font-light leading-[1.5] text-slate-300 sm:text-sm lg:text-base animate-in fade-in slide-in-from-bottom-4 duration-1000 delay-100 fill-mode-backwards">
          {t('description')}
        </p>

        <div className="beta-badge flex items-center gap-2 px-3 py-1.5 text-[9px] font-semibold uppercase tracking-[0.18em] text-violet-100 backdrop-blur-sm leading-none sm:text-[10px]">
          <span className="beta-dot" aria-hidden="true" />
          <span>{t('alertConstruction')}</span>
        </div>

        <div className="flex flex-col items-center gap-2 sm:flex-row sm:justify-center mt-2 sm:mt-3 animate-in fade-in slide-in-from-bottom-6 duration-1000 delay-200 fill-mode-backwards">
          {/* Button 1: Mezclar mi Track */}
          <button
            onClick={onTryIt}
            className="group relative inline-flex items-center justify-center gap-2 overflow-hidden rounded-full bg-teal-400 px-4 py-2 text-xs font-bold text-slate-950 transition-all hover:bg-teal-300 hover:scale-105 focus:outline-none focus:ring-4 focus:ring-teal-500/30 sm:px-5 sm:py-2.5 sm:text-sm"
          >
            {/* Simple Circle Icon */}
            <svg
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
              className="stroke-current stroke-2"
              aria-hidden="true"
              focusable="false"
            >
              <circle cx="12" cy="12" r="9" />
            </svg>
            <span>{t('mixMyTracks')}</span>
          </button>

          {/* Button 2: Escuchar Demos */}
          <Link
            href="/examples"
            className="group relative inline-flex items-center justify-center gap-2 overflow-hidden rounded-full bg-slate-800/80 px-4 py-2 text-xs font-semibold text-white transition-all hover:bg-slate-700 hover:scale-105 focus:outline-none focus:ring-4 focus:ring-violet-500/30 border border-slate-700 sm:px-5 sm:py-2.5 sm:text-sm"
          >
            <PlayCircleIcon className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-white" aria-hidden="true" />
            <span>{t('listenToDemos')}</span>
          </Link>
        </div>

        {/* Rating Section */}
        <div className="flex items-center gap-2 text-[11px] font-medium text-slate-300 mt-1 sm:mt-2 sm:text-xs animate-in fade-in slide-in-from-bottom-8 duration-1000 delay-300 fill-mode-backwards">
          <div className="flex items-center gap-1 text-amber-300">
            <StarIcon className="h-3.5 w-3.5 sm:h-4 sm:w-4" aria-hidden="true" />
            <span>{t('rating')}</span>
          </div>
          <span className="text-slate-400">&bull;</span>
          <span>{t('tracksMastered')}</span>
        </div>
      </div>

      {/* Visual placeholder for waveform/animation */}
      <div className="absolute bottom-0 left-0 w-full opacity-20 pointer-events-none">
          <svg
            className="w-full h-24 text-teal-500/30"
            viewBox="0 0 1440 320"
            preserveAspectRatio="none"
            aria-hidden="true"
            focusable="false"
          >
             <path fill="currentColor" fillOpacity="1" d="M0,160L48,170.7C96,181,192,203,288,197.3C384,192,480,160,576,149.3C672,139,768,149,864,170.7C960,192,1056,224,1152,229.3C1248,235,1344,213,1392,202.7L1440,192V320H1392C1344,320,1248,320,1152,320C1056,320,960,320,864,320C768,320,672,320,576,320C480,320,384,320,288,320C192,320,96,320,48,320H0Z"></path>
          </svg>
      </div>
    </section>
  );
}
