export function HeroSection({ onTryIt }: { onTryIt: () => void }) {
  return (
    <section className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-slate-950 px-4 text-center">
      {/* Background gradients/blobs */}
      <div className="absolute top-0 left-0 h-full w-full overflow-hidden pointer-events-none">
        <div className="absolute -top-[20%] -left-[10%] h-[50%] w-[50%] rounded-full bg-teal-500/10 blur-[120px]" />
        <div className="absolute top-[40%] -right-[10%] h-[60%] w-[60%] rounded-full bg-purple-600/10 blur-[120px]" />
      </div>

      <div className="relative z-10 max-w-4xl space-y-8 animate-in fade-in zoom-in duration-1000">
        <h1 className="text-5xl font-extrabold tracking-tight text-white md:text-7xl lg:text-8xl">
          <span className="bg-gradient-to-r from-teal-400 to-purple-500 bg-clip-text text-transparent">
            Piroola
          </span>
        </h1>

        <p className="mx-auto max-w-2xl text-lg font-light leading-relaxed text-slate-300 md:text-2xl">
          Transform your raw stems into professional, studio-quality mixes in minutes.
          Powered by advanced AI that understands your music.
        </p>

        <div className="flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
          <button
            onClick={onTryIt}
            className="group relative inline-flex items-center justify-center overflow-hidden rounded-full bg-teal-500 px-8 py-4 text-lg font-bold text-slate-950 transition-all hover:bg-teal-400 hover:scale-105 focus:outline-none focus:ring-4 focus:ring-teal-500/30"
          >
            <span className="relative z-10">Try it for free</span>
            <div className="absolute inset-0 -z-10 bg-gradient-to-r from-teal-600 to-teal-400 opacity-0 transition-opacity group-hover:opacity-100" />
          </button>

          <button
             onClick={() => document.getElementById('how-it-works')?.scrollIntoView({ behavior: 'smooth' })}
             className="text-sm font-semibold text-slate-400 hover:text-white transition-colors"
          >
            Learn more ↓
          </button>
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
