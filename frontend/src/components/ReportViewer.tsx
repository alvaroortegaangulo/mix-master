
import React, { useState } from "react";

// --- Types ---
interface StageParameter {
  [key: string]: string | number | { [subKey: string]: string | number };
}

interface StageReport {
  contract_id: string;
  stage_id: string;
  name: string;
  status: string;
  parameters?: StageParameter;
  images?: {
    waveform?: string;
    spectrogram?: string;
  };
  key_metrics?: any;
}

interface FullReport {
  pipeline_version: string;
  generated_at_utc: string;
  style_preset: string;
  general_summary?: string;
  stages: StageReport[];
  final_metrics: any;
}

interface ReportViewerProps {
  report: FullReport;
  jobId: string;
}

// --- Components ---

const ReportStageCard = ({
  stage,
  jobId,
}: {
  stage: StageReport;
  jobId: string;
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const hasParameters = stage.parameters && Object.keys(stage.parameters).length > 0;
  const images = stage.images || {};
  const hasImages = Object.keys(images).length > 0;
  const hasKeyMetrics = stage.key_metrics && Object.keys(stage.key_metrics).length > 0;

  // Updated URL to point to the static file server path
  const getImageUrl = (imageName: string) => `/files/${jobId}/S11_REPORT_GENERATION/${imageName}`;
  const renderMetricValue = (value: unknown) => {
    if (value === null || value === undefined) return "N/A";
    if (typeof value === "object") {
      return (
        <pre className="text-[10px] opacity-70 whitespace-pre-wrap break-words">
          {JSON.stringify(value, null, 2)}
        </pre>
      );
    }
    return String(value);
  };

  return (
    <div className="mb-3 overflow-hidden rounded-lg border border-emerald-900/50 bg-slate-900/40 backdrop-blur-sm transition-all hover:bg-slate-900/60">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex w-full items-center justify-between px-5 py-3 text-left transition hover:bg-white/5"
      >
        <div className="flex flex-col">
          <span className="text-sm font-bold text-emerald-100/90">
            {stage.name || stage.stage_id}
          </span>
          <span className="text-[10px] uppercase tracking-wider text-emerald-500/60 font-mono">
            {stage.contract_id}
          </span>
        </div>
        <div className="flex items-center gap-3">
            <span className={`text-[10px] px-2 py-0.5 rounded-full uppercase tracking-wider font-bold ${stage.status === 'analyzed' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-slate-800 text-slate-500'}`}>
                {stage.status}
            </span>
          <span className={`text-emerald-500/50 text-xs transition-transform duration-300 ${isOpen ? "rotate-180" : ""}`}>▼</span>
        </div>
      </button>

      {isOpen && (
        <div className="border-t border-emerald-500/10 bg-black/20 p-5">

          {/* Parameters Table */}
          {hasParameters && (
            <div className="mb-6">
              <h4 className="mb-2 text-[10px] font-bold uppercase tracking-widest text-emerald-500/70">
                Modified Parameters
              </h4>
              <div className="overflow-hidden rounded-md border border-emerald-500/20">
                <table className="w-full text-left text-xs text-slate-300">
                  <thead className="bg-emerald-950/30 text-[10px] font-semibold uppercase text-emerald-400/80">
                    <tr>
                      <th className="px-3 py-2">Parameter</th>
                      <th className="px-3 py-2">Value</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-emerald-500/10 bg-emerald-900/10">
                    {Object.entries(stage.parameters || {}).map(([key, value]) => (
                      <tr key={key}>
                        <td className="px-3 py-1.5 font-medium text-slate-200">
                          {key}
                        </td>
                        <td className="px-3 py-1.5 text-emerald-100 font-mono">
                          {typeof value === 'object' ? (
                              <pre className="text-[10px] opacity-70">{JSON.stringify(value, null, 2)}</pre>
                          ) : (
                              String(value)
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Key Metrics */}
          {hasKeyMetrics && (
            <div className="mb-6">
              <h4 className="mb-2 text-[10px] font-bold uppercase tracking-widest text-emerald-500/70">
                Key Metrics
              </h4>
              <div className="overflow-hidden rounded-md border border-emerald-500/20">
                <table className="w-full text-left text-xs text-slate-300">
                  <thead className="bg-emerald-950/30 text-[10px] font-semibold uppercase text-emerald-400/80">
                    <tr>
                      <th className="px-3 py-2">Metric</th>
                      <th className="px-3 py-2">Value</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-emerald-500/10 bg-emerald-900/10">
                    {Object.entries(stage.key_metrics || {}).map(([key, value]) => (
                      <tr key={key}>
                        <td className="px-3 py-1.5 font-medium text-slate-200">
                          {key}
                        </td>
                        <td className="px-3 py-1.5 text-emerald-100 font-mono">
                          {renderMetricValue(value)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Images Grid */}
          {hasImages && (
            <div>
              <h4 className="mb-2 text-[10px] font-bold uppercase tracking-widest text-emerald-500/70">
                Signal Analysis (Before vs After)
              </h4>
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                  {images.waveform && (
                      <div className="space-y-1">
                          <p className="text-[10px] text-center text-slate-400 uppercase tracking-wide">Waveform Comparison</p>
                          <div className="rounded border border-emerald-500/20 bg-black/40 p-1">
                              <img src={getImageUrl(images.waveform)} alt="Waveform" className="w-full h-auto object-cover opacity-90 hover:opacity-100 transition-opacity" />
                          </div>
                      </div>
                  )}
                  {images.spectrogram && (
                       <div className="space-y-1">
                          <p className="text-[10px] text-center text-slate-400 uppercase tracking-wide">Spectrogram Comparison</p>
                          <div className="rounded border border-emerald-500/20 bg-black/40 p-1">
                              <img src={getImageUrl(images.spectrogram)} alt="Spectrogram" className="w-full h-auto object-contain opacity-90 hover:opacity-100 transition-opacity" />
                          </div>
                      </div>
                  )}
              </div>
            </div>
          )}

          {!hasParameters && !hasImages && !hasKeyMetrics && (
            <p className="text-xs text-slate-500">No data captured for this stage yet.</p>
          )}
        </div>
      )}
    </div>
  );
};

export const ReportViewer: React.FC<ReportViewerProps> = ({ report, jobId }) => {
  if (!report) return null;

  const processedStages = report.stages || [];

  return (
    <div className="w-full space-y-6 p-1">

      {/* Mix Summary Section */}
      <section className="rounded-xl border border-emerald-500/20 bg-gradient-to-br from-emerald-900/20 to-slate-900/40 p-5 shadow-lg">
        <h2 className="mb-4 text-lg font-bold text-emerald-100 tracking-tight">Mix Summary</h2>

        <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
            {/* Context Info */}
            <div className="md:col-span-1 space-y-3">
                 <div className="rounded-lg bg-black/20 border border-emerald-500/10 p-3">
                    <p className="text-[10px] text-emerald-400/70 uppercase tracking-widest font-bold mb-1">Style Preset</p>
                    <p className="text-base font-medium text-emerald-50">{report.style_preset}</p>
                 </div>
                 {/* Removed Generated At as requested */}
                 {report.general_summary && (
                    <p className="text-sm text-slate-300 italic px-1">
                        {report.general_summary}
                    </p>
                 )}
            </div>

            {/* Metrics Grid */}
             <div className="md:col-span-2 rounded-lg border border-emerald-500/10 bg-black/20 p-4">
                <h3 className="mb-3 text-[10px] font-bold uppercase tracking-widest text-emerald-400/70">Final Master Metrics</h3>
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
                    <div className="flex flex-col">
                        <span className="text-[10px] text-slate-400 uppercase">Integrated LUFS</span>
                        <span className="font-mono text-sm text-emerald-300 font-bold">{report.final_metrics?.lufs_integrated?.toFixed(2) ?? 'N/A'}</span>
                    </div>
                    <div className="flex flex-col">
                        <span className="text-[10px] text-slate-400 uppercase">True Peak</span>
                        <span className="font-mono text-sm text-emerald-300 font-bold">{report.final_metrics?.true_peak_dbtp?.toFixed(2) ?? 'N/A'} <span className="text-[10px] font-normal text-emerald-500/50">dBTP</span></span>
                    </div>
                    <div className="flex flex-col">
                        <span className="text-[10px] text-slate-400 uppercase">LRA</span>
                        <span className="font-mono text-sm text-slate-200">{report.final_metrics?.lra?.toFixed(2) ?? 'N/A'} <span className="text-[10px] font-normal text-slate-500">LU</span></span>
                    </div>
                     <div className="flex flex-col">
                        <span className="text-[10px] text-slate-400 uppercase">Crest Factor</span>
                        <span className="font-mono text-sm text-slate-200">{report.final_metrics?.crest_factor_db?.toFixed(2) ?? 'N/A'} <span className="text-[10px] font-normal text-slate-500">dB</span></span>
                    </div>
                    <div className="flex flex-col">
                        <span className="text-[10px] text-slate-400 uppercase">Correlation</span>
                        <span className="font-mono text-sm text-slate-200">{report.final_metrics?.correlation?.toFixed(3) ?? 'N/A'}</span>
                    </div>
                     <div className="flex flex-col">
                        <span className="text-[10px] text-slate-400 uppercase">Diff L/R</span>
                        <span className="font-mono text-sm text-slate-200">{report.final_metrics?.channel_loudness_diff_db?.toFixed(2) ?? 'N/A'} <span className="text-[10px] font-normal text-slate-500">dB</span></span>
                    </div>
                </div>
            </div>
        </div>
      </section>

      {/* Detailed Stage Report */}
      <section>
          <div className="mb-3 flex items-center justify-between px-1">
             <h2 className="text-sm font-bold uppercase tracking-widest text-emerald-500/80">Detailed Stage Report</h2>
             <span className="text-[10px] text-slate-500">{processedStages.length} stages processed</span>
          </div>

          <div className="space-y-2">
            {processedStages.map((stage) => (
                <ReportStageCard key={stage.contract_id} stage={stage} jobId={jobId} />
            ))}
            {processedStages.length === 0 && (
                <div className="rounded-lg border border-dashed border-slate-700 p-8 text-center">
                    <p className="text-slate-500">No detailed stage data available.</p>
                </div>
            )}
          </div>
      </section>

    </div>
  );
};
