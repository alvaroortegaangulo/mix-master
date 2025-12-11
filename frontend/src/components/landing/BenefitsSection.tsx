export function BenefitsSection() {
    return (
      <section id="benefits" className="py-24 bg-slate-950 overflow-hidden">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">

          {/* Benefit 1: Speed */}
          <div className="flex flex-col lg:flex-row items-center gap-16 mb-24">
            <div className="flex-1 order-2 lg:order-1">
               {/* Image Placeholder */}
               <div className="w-full aspect-video rounded-2xl bg-gradient-to-br from-slate-800 to-slate-900 border border-slate-700 flex items-center justify-center relative shadow-2xl overflow-hidden group">
                  <video
                    src="/master_interface.mp4"
                    className="w-full h-full object-cover"
                    autoPlay
                    loop
                    muted
                    playsInline
                  />
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
               <div className="w-full aspect-video rounded-2xl bg-gradient-to-br from-purple-900/20 to-slate-900 border border-slate-700 flex items-center justify-center relative shadow-2xl overflow-hidden">
                  <video
                    src="/spectral_analysis.mp4"
                    className="w-full h-full object-cover"
                    autoPlay
                    loop
                    muted
                    playsInline
                  />
               </div>
            </div>
          </div>

        </div>
      </section>
    );
  }
