export function BenefitsSection() {
    return (
      <section className="py-24 bg-slate-950 overflow-hidden">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">

          {/* Benefit 1: Speed */}
          <div className="flex flex-col lg:flex-row items-center gap-16 mb-24">
            <div className="flex-1 order-2 lg:order-1">
               {/* Image Placeholder */}
               <div className="w-full aspect-video rounded-2xl bg-gradient-to-br from-slate-800 to-slate-900 border border-slate-700 flex items-center justify-center relative shadow-2xl overflow-hidden group">
                  <div className="absolute inset-0 bg-teal-500/5 group-hover:bg-teal-500/10 transition duration-500"></div>
                  <div className="text-slate-500 font-mono text-sm">[ Animation: Fast Processing ]</div>
                  {/* Decorative elements */}
                  <div className="absolute left-10 top-10 w-20 h-1 bg-slate-700 rounded-full animate-pulse"></div>
                  <div className="absolute left-10 top-14 w-32 h-1 bg-slate-700 rounded-full animate-pulse delay-75"></div>
                  <div className="absolute right-10 bottom-10 h-16 w-16 rounded-full border-4 border-teal-500/20"></div>
               </div>
            </div>
            <div className="flex-1 order-1 lg:order-2">
              <h3 className="text-3xl font-bold text-white mb-6">
                Hours of work, done in minutes.
              </h3>
              <p className="text-lg text-slate-400 mb-6 leading-relaxed">
                Forget about tedious gain staging, phase alignment, and resonance cleanup.
                Piroola handles the technical heavy lifting so you can focus on the creative vibe.
              </p>
              <ul className="space-y-3 text-slate-300">
                <li className="flex items-center gap-3">
                  <span className="h-2 w-2 rounded-full bg-teal-500" />
                  Instant session setup and routing
                </li>
                <li className="flex items-center gap-3">
                  <span className="h-2 w-2 rounded-full bg-teal-500" />
                  Automated corrective EQ
                </li>
                <li className="flex items-center gap-3">
                  <span className="h-2 w-2 rounded-full bg-teal-500" />
                  Real-time loudness compliance check
                </li>
              </ul>
            </div>
          </div>

          {/* Benefit 2: Quality */}
          <div className="flex flex-col lg:flex-row items-center gap-16">
            <div className="flex-1">
              <h3 className="text-3xl font-bold text-white mb-6">
                Studio Quality, accessible to everyone.
              </h3>
              <p className="text-lg text-slate-400 mb-6 leading-relaxed">
                You don't need a million-dollar studio or decades of experience to get a professional sound.
                Our algorithms are trained on hit records to deliver commercially competitive results.
              </p>
              <div className="flex gap-4">
                 <div className="px-4 py-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 text-sm font-medium">
                    Spotify Ready
                 </div>
                 <div className="px-4 py-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 text-sm font-medium">
                    Apple Music Ready
                 </div>
              </div>
            </div>
            <div className="flex-1">
               {/* Image Placeholder */}
               <div className="w-full aspect-video rounded-2xl bg-gradient-to-br from-purple-900/20 to-slate-900 border border-slate-700 flex items-center justify-center relative shadow-2xl">
                  <div className="text-slate-500 font-mono text-sm">[ Animation: Spectral Balance ]</div>
                   {/* Decorative elements representing EQ curve */}
                   <svg className="absolute bottom-0 left-0 w-full h-1/2 text-purple-500/20" viewBox="0 0 100 20" preserveAspectRatio="none">
                      <path d="M0 20 Q 25 5 50 15 T 100 10 V 20 Z" fill="currentColor" />
                   </svg>
               </div>
            </div>
          </div>

        </div>
      </section>
    );
  }
