import {
  AdjustmentsVerticalIcon,
  ArrowsRightLeftIcon,
  ChevronDownIcon,
  SparklesIcon
} from "@heroicons/react/24/outline";
import { PlayCircleIcon } from "@heroicons/react/24/solid";
import { Link } from "../../i18n/routing";
import { HeroDiagram } from "./HeroDiagram";
import { HeroWaveformCanvas } from "./HeroWaveformCanvas";

export function HeroSection() {
  return (
    <section className="relative flex min-h-[100svh] flex-col justify-center overflow-hidden bg-slate-950 px-4 pb-16 pt-10 sm:pt-14 lg:pt-12 2xl:pt-16">
      <div className="absolute left-0 top-0 z-0 h-full w-full overflow-hidden pointer-events-none">
        <div className="absolute -top-[20%] -left-[10%] h-[50%] w-[50%] rounded-full bg-teal-500/10 blur-[120px]" />
        <div className="absolute top-[40%] -right-[10%] h-[60%] w-[60%] rounded-full bg-violet-600/10 blur-[120px]" />
      </div>

      <div className="relative z-10 mx-auto w-full max-w-6xl 2xl:max-w-7xl">
        <div className="grid items-start gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,420px)] 2xl:grid-cols-[minmax(0,1fr)_minmax(0,540px)]">
          <div className="flex flex-col gap-8 lg:gap-6 2xl:gap-8">
            <div
              className="floating motion-reduce:animate-none text-left space-y-6 max-w-xl"
              style={{ animationDuration: "10s" }}
            >
              <div className="inline-flex items-center gap-2 rounded-full border border-cyan-400/30 bg-cyan-500/10 px-3 py-1 text-[9px] lg:text-[8.5px] 2xl:text-[10px] font-semibold uppercase tracking-[0.22em] text-cyan-200 shadow-[0_0_12px_rgba(34,211,238,0.2)]">
                <span className="h-2 w-2 rounded-full bg-cyan-300 shadow-[0_0_10px_rgba(34,211,238,0.6)]" />
                Beta v2.0 disponible
              </div>

              <h1 className="text-4xl font-extrabold leading-[1.05] tracking-tight text-white sm:text-5xl lg:text-5xl 2xl:text-7xl font-['Orbitron']">
                <span className="block">Tu musica,</span>
                <span className="block text-transparent bg-clip-text bg-gradient-to-r from-cyan-300 to-blue-500 drop-shadow-[0_0_16px_rgba(34,211,238,0.5)]">
                  Sonido Pro.
                </span>
                <span className="block">Sin lios.</span>
              </h1>

              <p className="text-sm text-slate-300 leading-relaxed sm:text-base lg:text-[13px] xl:text-base 2xl:text-lg">
                No necesitas ser ingeniero de sonido para sonar genial en Spotify. Sube tu grabacion casera y nuestra IA
                se encarga de pulirla, limpiarla y darle volumen en segundos.
              </p>

              <div className="flex flex-col gap-4 sm:flex-row">
                <Link
                  href="/mix"
                  className="group inline-flex items-center justify-center gap-2 rounded-xl bg-cyan-400 px-6 py-3 text-sm font-bold text-slate-950 transition-all hover:bg-cyan-300 hover:shadow-[0_0_28px_rgba(34,211,238,0.45)]"
                >
                  <svg
                    width="20"
                    height="20"
                    viewBox="0 0 24 24"
                    fill="none"
                    xmlns="http://www.w3.org/2000/svg"
                    className="stroke-current stroke-2"
                    aria-hidden="true"
                    focusable="false"
                  >
                    <circle cx="12" cy="12" r="9" />
                  </svg>
                  Mejorar mi Cancion
                </Link>
                <Link
                  href="/examples"
                  className="group inline-flex items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/5 px-6 py-3 text-sm font-semibold text-white backdrop-blur transition-all hover:bg-white/10"
                >
                  <PlayCircleIcon className="h-4 w-4 text-white" aria-hidden="true" />
                  Escuchar Demo
                </Link>
              </div>
            </div>

            <div className="space-y-4 lg:hidden">
              <div className="rounded-xl border border-cyan-400/20 bg-slate-950/70 p-4 shadow-xl backdrop-blur">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-cyan-500/15 text-cyan-200">
                    <AdjustmentsVerticalIcon className="h-5 w-5" aria-hidden="true" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-white">Mezcla unica</h3>
                    <p className="text-xs text-slate-400">Mezcla pistas individuales automaticamente.</p>
                  </div>
                </div>
              </div>

              <div className="rounded-xl border border-violet-400/20 bg-slate-950/70 p-4 shadow-xl backdrop-blur">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-violet-500/15 text-violet-200">
                    <SparklesIcon className="h-5 w-5" aria-hidden="true" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-white">Potenciado por IA</h3>
                    <p className="text-xs text-slate-400">Limpieza y pulido inteligente.</p>
                  </div>
                </div>
              </div>

              <div className="rounded-xl border border-cyan-400/20 bg-slate-950/70 p-4 shadow-xl backdrop-blur">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-cyan-500/15 text-cyan-200">
                    <ArrowsRightLeftIcon className="h-5 w-5" aria-hidden="true" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-white">Control Total</h3>
                    <p className="text-xs text-slate-400">Edicion manual en Studio implementado.</p>
                  </div>
                </div>
              </div>

              <div className="text-center">
                <a
                  href="#listen-difference"
                  className="inline-flex items-center gap-2 text-sm text-slate-400 transition-colors hover:text-white"
                >
                  Escuchar la diferencia
                  <ChevronDownIcon className="h-4 w-4" aria-hidden="true" />
                </a>
              </div>
            </div>
          </div>

          <HeroDiagram />
        </div>
      </div>

      <div className="absolute inset-0 z-[1] opacity-[0.55] pointer-events-none mix-blend-screen">
        <HeroWaveformCanvas />
      </div>
    </section>
  );
}
