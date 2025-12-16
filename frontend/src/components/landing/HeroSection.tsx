import Image from "next/image";
import { PlayCircleIcon, StarIcon, ExclamationTriangleIcon } from "@heroicons/react/24/solid";
import { useTranslations } from 'next-intl';

export function HeroSection({ onTryIt }: { onTryIt: () => void }) {
  const t = useTranslations('HeroSection');

  return (
    <section className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-slate-950 px-4 text-center">
      {/* Background gradients/blobs */}
      <div className="absolute top-0 left-0 h-full w-full overflow-hidden pointer-events-none">
        <div className="absolute -top-[20%] -left-[10%] h-[50%] w-[50%] rounded-full bg-teal-500/10 blur-[120px]" />
        <div className="absolute top-[40%] -right-[10%] h-[60%] w-[60%] rounded-full bg-purple-600/10 blur-[120px]" />
      </div>

      <div className="relative z-10 max-w-5xl space-y-8 flex flex-col items-center">
        {/* Alert: Website under construction */}
        <div className="flex items-center gap-2 rounded-full bg-red-900/20 border border-red-500/50 px-5 py-2 text-red-400 animate-in fade-in zoom-in duration-1000">
          <ExclamationTriangleIcon className="h-5 w-5" />
          <span className="font-bold text-sm tracking-wide uppercase">{t('alertConstruction')}</span>
        </div>

        {/* Logo */}
        <div className="mx-auto flex justify-center mb-4 animate-in fade-in zoom-in duration-1000">
          <Image
            src="/logo.webp"
            alt="Piroola logo"
            width={96}
            height={96}
            className="h-24 w-24"
            priority
          />
        </div>

        {/* Main Heading - LCP Element (No entrance animation to minimize render delay) */}
        <h1 className="flex flex-col text-5xl font-extrabold tracking-tight md:text-7xl lg:text-8xl gap-2">
          <span className="text-white">
            {t('studioSound')}
          </span>
          <span className="bg-gradient-to-r from-teal-400 to-purple-500 bg-clip-text text-transparent">
            {t('perfectedByAI')}
          </span>
        </h1>

        <p className="mx-auto max-w-3xl text-lg font-light leading-relaxed text-slate-300 md:text-xl animate-in fade-in slide-in-from-bottom-4 duration-1000 delay-100 fill-mode-backwards">
          {t('description')}
        </p>

        <div className="flex flex-col items-center gap-4 sm:flex-row sm:justify-center mt-4 animate-in fade-in slide-in-from-bottom-6 duration-1000 delay-200 fill-mode-backwards">
          {/* Button 1: Mezclar mi Track */}
          <button
            onClick={onTryIt}
            className="group relative inline-flex items-center justify-center gap-2 overflow-hidden rounded-full bg-teal-400 px-8 py-4 text-lg font-bold text-slate-950 transition-all hover:bg-teal-300 hover:scale-105 focus:outline-none focus:ring-4 focus:ring-teal-500/30"
          >
            {/* Simple Circle Icon */}
            <svg
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
              className="stroke-current stroke-2"
            >
              <circle cx="12" cy="12" r="9" />
            </svg>
            <span>{t('mixMyTracks')}</span>
          </button>

          {/* Button 2: Escuchar Demos */}
          <button
             onClick={() => document.getElementById('benefits')?.scrollIntoView({ behavior: 'smooth' })}
             className="group relative inline-flex items-center justify-center gap-2 overflow-hidden rounded-full bg-slate-800/80 px-8 py-4 text-lg font-semibold text-white transition-all hover:bg-slate-700 hover:scale-105 focus:outline-none focus:ring-4 focus:ring-purple-500/30 border border-slate-700"
          >
            <PlayCircleIcon className="h-6 w-6 text-white" />
            <span>{t('listenToDemos')}</span>
          </button>
        </div>

        {/* Rating Section */}
        <div className="flex items-center gap-2 text-sm font-medium text-slate-400 mt-2 animate-in fade-in slide-in-from-bottom-8 duration-1000 delay-300 fill-mode-backwards">
            <div className="flex items-center gap-1 text-yellow-400">
                <StarIcon className="h-5 w-5" />
                <span>{t('rating')}</span>
            </div>
            <span>•</span>
            <span>{t('tracksMastered')}</span>
        </div>
      </div>

      {/* Visual placeholder for waveform/animation */}
      <div className="absolute bottom-0 left-0 w-full opacity-20 pointer-events-none">
          <svg className="w-full h-24 text-teal-500/30" viewBox="0 0 1440 320" preserveAspectRatio="none">
             <path fill="currentColor" fillOpacity="1" d="M0,160L48,170.7C96,181,192,203,288,197.3C384,192,480,160,576,149.3C672,139,768,149,864,170.7C960,192,1056,224,1152,229.3C1248,235,1344,213,1392,202.7L1440,192V320H1392C1344,320,1248,320,1152,320C1056,320,960,320,864,320C768,320,672,320,576,320C480,320,384,320,288,320C192,320,96,320,48,320H0Z"></path>
          </svg>
      </div>
    </section>
  );
}
