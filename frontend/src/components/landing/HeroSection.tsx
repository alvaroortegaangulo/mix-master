import Image from "next/image";
import { PlayCircleIcon } from "@heroicons/react/24/solid";
import { getTranslations } from "next-intl/server";
import { Link } from '../../i18n/routing';
import { HeroWaveformCanvas } from "./HeroWaveformCanvas";

export async function HeroSection() {
  const t = await getTranslations('HeroSection');
  const perfectedByAI = t('perfectedByAI');

  return (
    <section className="relative flex min-h-[100svh] sm:min-h-[70vh] lg:min-h-screen flex-col items-center justify-center overflow-hidden bg-slate-950 px-4 text-center pt-3 pb-4 sm:py-6 md:py-10 lg:py-16 2xl:py-32">
      {/* Background gradients/blobs */}
      <div className="absolute top-0 left-0 h-full w-full overflow-hidden pointer-events-none z-0">
        <div className="absolute -top-[20%] -left-[10%] h-[50%] w-[50%] rounded-full bg-teal-500/10 blur-[120px]" />
        <div className="absolute top-[40%] -right-[10%] h-[60%] w-[60%] rounded-full bg-violet-600/10 blur-[120px]" />
      </div>

      <div className="relative z-10 max-w-5xl 2xl:max-w-7xl space-y-2 sm:space-y-3 lg:space-y-4 2xl:space-y-8 flex flex-col items-center">
        {/* Logo */}
        <div className="mx-auto flex justify-center mb-1 2xl:mb-4">
          <Image
            src="/brand/logo.webp"
            alt="Piroola logo"
            width={96}
            height={96}
            sizes="96px"
            className="h-14 w-14 sm:h-16 sm:w-16 2xl:h-24 2xl:w-24"
            priority
          />
        </div>

        {/* Main Heading - LCP Element (No entrance animation to minimize render delay) */}
        <h1 className="flex flex-col text-4xl font-extrabold tracking-[-0.02em] sm:text-5xl lg:text-6xl 2xl:text-8xl gap-1 2xl:gap-3 font-['Orbitron'] glow-teal">
          <span className="text-white leading-[0.95] shine-box py-4 -my-4 px-2 -mx-2">
            {t('studioSound')}
          </span>
          <span
            className="text-cyan-400 leading-[0.95] shine-box shine-delayed py-4 -my-4 px-2 -mx-2"
          >
            {perfectedByAI}
          </span>
        </h1>

        <p className="mx-auto max-w-3xl 2xl:max-w-4xl text-xs font-light leading-[1.5] text-slate-300 sm:text-sm lg:text-base 2xl:text-xl">
          {t('description')}
        </p>

        <div className="beta-badge flex items-center gap-2 px-3 py-1.5 2xl:px-5 2xl:py-2.5 text-[9px] font-semibold uppercase tracking-[0.18em] text-violet-100 backdrop-blur-sm leading-none sm:text-[10px] 2xl:text-sm">
          <span className="beta-dot" aria-hidden="true" />
          <span>{t('alertConstruction')}</span>
        </div>

        <div className="flex flex-col items-center gap-3 sm:gap-4 2xl:gap-6 sm:flex-row sm:justify-center mt-2 sm:mt-3 2xl:mt-8 mb-4 sm:mb-0">
          {/* Button 1: Mezclar mi Track */}
          <Link
            href="/mix"
            className="group relative inline-flex items-center justify-center gap-2 overflow-hidden rounded-full bg-teal-400 px-4 py-2 text-xs font-bold text-slate-950 transition-all hover:bg-teal-300 hover:scale-105 focus:outline-none focus:ring-4 focus:ring-teal-500/30 sm:px-5 sm:py-2.5 sm:text-sm 2xl:px-8 2xl:py-4 2xl:text-lg glow-pulse"
          >
            {/* Simple Circle Icon */}
            <svg
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
              className="stroke-current stroke-2 2xl:w-6 2xl:h-6"
              aria-hidden="true"
              focusable="false"
            >
              <circle cx="12" cy="12" r="9" />
            </svg>
            <span>{t('mixMyTracks')}</span>
          </Link>

          {/* Button 2: Escuchar Demos */}
          <Link
            href="/examples"
            className="group relative inline-flex items-center justify-center gap-2 overflow-hidden rounded-full bg-slate-800/80 px-4 py-2 text-xs font-semibold text-white transition-all hover:bg-slate-700 hover:scale-105 focus:outline-none focus:ring-4 focus:ring-violet-500/30 border border-slate-700 sm:px-5 sm:py-2.5 sm:text-sm 2xl:px-8 2xl:py-4 2xl:text-lg"
          >
            <PlayCircleIcon className="h-3.5 w-3.5 sm:h-4 sm:w-4 2xl:h-6 2xl:w-6 text-white" aria-hidden="true" />
            <span>{t('listenToDemos')}</span>
          </Link>
        </div>

        <style jsx>{`
          .hero-faq-pop {
            animation: hero-faq-pop 0.75s cubic-bezier(0.22, 1.2, 0.32, 1) 0.2s both;
          }

          .hero-faq-float {
            animation: hero-faq-float 4.2s ease-in-out 1.2s infinite;
            will-change: transform;
          }

          .shine-delayed::before {
            animation-delay: 0.6s !important;
          }

          @keyframes hero-faq-pop {
            0% {
              transform: scale(0);
              opacity: 0;
            }
            65% {
              transform: scale(1.06);
              opacity: 1;
            }
            85% {
              transform: scale(0.98);
            }
          100% {
            transform: scale(1);
          }
        }

        @keyframes hero-faq-float {
          0%,
          100% {
            transform: translateY(0);
          }
          50% {
            transform: translateY(-6px);
          }
        }
      `}</style>

      </div>

      <div className="absolute inset-0 opacity-[0.55] pointer-events-none mix-blend-screen z-[1]">
        <HeroWaveformCanvas />
      </div>

      <div className="relative z-30 mt-6 flex justify-center sm:absolute sm:bottom-10 sm:right-6 2xl:bottom-32 sm:mt-0 sm:justify-start">
        <div className="hero-faq-pop group w-[min(90vw,340px)] 2xl:w-[420px] origin-bottom sm:origin-bottom-right">
          <div className="hero-faq-float relative rounded-2xl border border-slate-800 bg-slate-950/90 p-3 sm:p-4 2xl:p-6 text-left shadow-2xl shadow-black/40 backdrop-blur">
            <div className="flex items-start gap-2">
              <span className="mt-0.5 inline-flex h-5 w-5 2xl:h-6 2xl:w-6 items-center justify-center rounded-full border border-amber-400/70 bg-amber-500/15 text-[11px] 2xl:text-sm font-bold text-amber-200">
                i
              </span>
              <p className="text-[12px] sm:text-sm 2xl:text-base font-semibold text-white">
                ¿Cuál es la diferencia entre Mezcla y Masterización?
              </p>
            </div>
            <div className="overflow-hidden opacity-0 max-h-0 mt-0 transition-all duration-300 group-hover:opacity-100 group-hover:max-h-64 group-hover:mt-3">
              <p className="text-[11px] text-slate-300 leading-relaxed 2xl:text-sm">
                La mezcla implica equilibrar pistas individuales (stems) para formar una canción, incluyendo ajustar niveles, paneo y añadir efectos. La masterización es el paso final que pule la canción mezclada, asegurando que suene consistente y lo suficientemente fuerte para el lanzamiento comercial.
              </p>
              <Link
                href="/faq"
                className="mt-3 inline-flex items-center justify-center rounded-full border border-amber-400/40 bg-amber-500/10 px-3 py-1.5 2xl:px-4 2xl:py-2 text-[11px] 2xl:text-sm font-semibold text-amber-200 transition hover:bg-amber-500/20"
              >
                Ir a FAQ
              </Link>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
