export function TechSpecsSection() {
    return (
      <section className="py-24 bg-slate-900">
        <div className="max-w-4xl mx-auto px-4 text-center">
          <h2 className="text-3xl font-bold text-white mb-12">Power & Precision</h2>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
             <div className="p-6">
                <div className="text-4xl font-bold text-teal-400 mb-2">96k</div>
                <div className="text-sm font-medium text-slate-400 uppercase tracking-wide">Internal Processing</div>
             </div>
             <div className="p-6">
                <div className="text-4xl font-bold text-purple-400 mb-2">32-bit</div>
                <div className="text-sm font-medium text-slate-400 uppercase tracking-wide">Float Depth</div>
             </div>
             <div className="p-6">
                <div className="text-4xl font-bold text-amber-400 mb-2">10+</div>
                <div className="text-sm font-medium text-slate-400 uppercase tracking-wide">Processing Stages</div>
             </div>
             <div className="p-6">
                <div className="text-4xl font-bold text-rose-400 mb-2">0s</div>
                <div className="text-sm font-medium text-slate-400 uppercase tracking-wide">Latency (Cloud)</div>
             </div>
          </div>

          <div className="mt-16 p-8 rounded-2xl bg-slate-950/50 border border-slate-800 text-left">
              <h3 className="text-xl font-semibold text-white mb-4">Pipeline Architecture</h3>
              <div className="flex flex-col md:flex-row gap-4 justify-between items-center text-slate-400 text-sm font-mono">
                  <div className="bg-slate-900 px-4 py-2 rounded border border-slate-800 w-full text-center">Analysis</div>
                  <div className="text-slate-600">→</div>
                  <div className="bg-slate-900 px-4 py-2 rounded border border-slate-800 w-full text-center">Correction</div>
                  <div className="text-slate-600">→</div>
                  <div className="bg-slate-900 px-4 py-2 rounded border border-slate-800 w-full text-center">Dynamics</div>
                  <div className="text-slate-600">→</div>
                  <div className="bg-slate-900 px-4 py-2 rounded border border-slate-800 w-full text-center">Spatial</div>
                  <div className="text-slate-600">→</div>
                  <div className="bg-slate-900 px-4 py-2 rounded border border-slate-800 w-full text-center">Mastering</div>
              </div>
          </div>
        </div>
      </section>
    );
  }
