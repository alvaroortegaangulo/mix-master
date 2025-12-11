import PipelineInteractiveDiagram from './PipelineInteractiveDiagram';

export function TechSpecsSection() {
    return (
      <section className="py-24 bg-slate-900 overflow-hidden">
        <div className="max-w-6xl mx-auto px-4 text-center">
          <h2 className="text-3xl font-bold text-white mb-12">Power & Precision</h2>

          <div className="max-w-4xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-8 mb-20">
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

          <PipelineInteractiveDiagram />
        </div>
      </section>
    );
  }
