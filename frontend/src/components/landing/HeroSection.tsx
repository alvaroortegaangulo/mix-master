import Image from "next/image";
import { PlayIcon, StarIcon } from "@heroicons/react/24/solid";

export function HeroSection({ onTryIt }: { onTryIt: () => void }) {
  return (
    <section className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-slate-950 px-4 text-center">
      {/* Background gradients/blobs */}
      <div className="absolute top-0 left-0 h-full w-full overflow-hidden pointer-events-none">
        <div className="absolute -top-[20%] -left-[10%] h-[50%] w-[50%] rounded-full bg-teal-500/10 blur-[120px]" />
        <div className="absolute top-[40%] -right-[10%] h-[60%] w-[60%] rounded-full bg-purple-600/10 blur-[120px]" />
      </div>

      <div className="relative z-10 max-w-4xl space-y-8 animate-in fade-in zoom-in duration-1000">
        <div className="mx-auto flex justify-center">
          <Image
            src="/logo.png"
            alt="Piroola logo"
            width={96}
            height={96}
            className="h-24 w-24"
            priority
          />
        </div>

        <h1 className="text-5xl font-extrabold tracking-tight text-white md:text-7xl lg:text-8xl flex flex-col gap-2">
          <span>Studio Sound.</span>
          <span className="bg-gradient-to-r from-purple-400 to-purple-600 bg-clip-text text-transparent">
            Perfected by AI.
          </span>
        </h1>

        <p className="mx-auto max-w-2xl text-lg font-light leading-relaxed text-slate-300 md:text-2xl">
          Transform your home recordings (stems) into professional, Spotify-ready mixes in minutes. Piroola handles the technical engineering so you can focus on the music.
        </p>

        <div className="flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
          <button
            onClick={onTryIt}
            className="group relative inline-flex items-center justify-center gap-2 overflow-hidden rounded-full bg-teal-500 px-8 py-4 text-lg font-bold text-slate-950 transition-all hover:bg-teal-400 hover:scale-105 focus:outline-none focus:ring-4 focus:ring-teal-500/30"
          >
            {/* Simple circle outline icon */}
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              className="w-5 h-5"
            >
              <circle cx="12" cy="12" r="9" />
            </svg>
            <span className="relative z-10">Mix my Track</span>
          </button>

          <button
             onClick={() => document.getElementById('benefits')?.scrollIntoView({ behavior: 'smooth' })}
             className="group inline-flex items-center justify-center gap-2 rounded-full bg-slate-800/80 px-8 py-4 text-lg font-semibold text-white transition-all hover:bg-slate-700 hover:scale-105 border border-slate-700/50"
          >
            <PlayIcon className="h-5 w-5 text-white" />
            <span>Listen to Demos</span>
          </button>
        </div>

        {/* Ratings */}
        <div className="flex items-center justify-center gap-2 text-sm text-slate-400">
           <StarIcon className="h-4 w-4 text-yellow-500" />
           <span className="font-medium">4.9/5 Rating</span>
           <span className="text-slate-600">•</span>
           <span>+10k Tracks Mastered</span>
        </div>
      </div>

      {/* Visual placeholder for waveform/animation */}
      <div className="absolute bottom-0 left-0 w-full opacity-20 pointer-events-none">
          {/* This would be an SVG wave or similar */}
          <svg className="w-full h-24 text-teal-500/30" viewBox="0 0 1440 320" preserveAspectRatio="none">
             <path fill="currentColor" fillOpacity="1" d="M0,160L48,170.7C96,181,192,203,288,197.3C384,192,480,160,576,149.3C672,139,768,149,864,170.7C960,192,1056,224,1152,229.3C1248,235,1344,213,1392,202.7L1440,192V320H1392C1344,320,1248,320,1152,320C1056,320,960,320,864,320C768,320,672,320,576,320C480,320,384,320,288,320C192,320,96,320,48,320H0Z"></path>
          </svg>
      </div>
    </section>
  );
}
