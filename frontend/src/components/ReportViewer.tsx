
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

  // Construct image URLs.
  // Assuming images are served from a static endpoint or API that serves temp files.
  // We need an endpoint in Next.js to serve files from temp.
  // For now, let's assume we have a route `/api/job/[jobId]/image/[imageName]`.

  const getImageUrl = (imageName: string) => `/api/job/${jobId}/image/${imageName}`;

  return (
    <div className="mb-4 rounded-xl border border-slate-700 bg-slate-900 overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex w-full items-center justify-between px-6 py-4 text-left transition hover:bg-slate-800"
      >
        <div>
          <h3 className="text-lg font-semibold text-teal-400">
            {stage.name || stage.stage_id}
          </h3>
          <p className="text-xs text-slate-400 font-mono">{stage.contract_id}</p>
        </div>
        <div className="flex items-center gap-4">
            <span className={`text-xs px-2 py-1 rounded-full uppercase tracking-wider font-bold ${stage.status === 'analyzed' ? 'bg-green-900/50 text-green-400' : 'bg-slate-800 text-slate-500'}`}>
                {stage.status}
            </span>
          <span className="text-slate-400 text-xl">{isOpen ? "▲" : "▼"}</span>
        </div>
      </button>

      {isOpen && (
        <div className="border-t border-slate-700 p-6 bg-slate-950/50">

          {/* Description - Assuming static text map or from backend if available */}
           <p className="mb-6 text-sm text-slate-300 italic">
               Stage processing results.
           </p>

          {/* Parameters Table */}
          {stage.parameters && Object.keys(stage.parameters).length > 0 && (
            <div className="mb-8">
              <h4 className="mb-3 text-sm font-bold uppercase tracking-wider text-slate-500">
                Modified Parameters
              </h4>
              <div className="overflow-x-auto rounded-lg border border-slate-800">
                <table className="w-full text-left text-sm text-slate-300">
                  <thead className="bg-slate-900 text-xs font-semibold uppercase text-slate-400">
                    <tr>
                      <th className="px-4 py-2">Parameter</th>
                      <th className="px-4 py-2">Value</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800 bg-slate-900/50">
                    {Object.entries(stage.parameters).map(([key, value]) => (
                      <tr key={key}>
                        <td className="px-4 py-2 font-medium text-slate-200">
                          {key}
                        </td>
                        <td className="px-4 py-2 text-slate-400 font-mono">
                          {typeof value === 'object' ? (
                              <pre className="text-xs">{JSON.stringify(value, null, 2)}</pre>
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

          {/* Images Grid */}
          {stage.images && (Object.keys(stage.images).length > 0) && (
            <div>
              <h4 className="mb-3 text-sm font-bold uppercase tracking-wider text-slate-500">
                Signal Analysis (Before vs After)
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {stage.images.waveform && (
                      <div className="space-y-2">
                          <p className="text-xs text-center text-slate-400">Waveform Comparison</p>
                          <div className="rounded-lg border border-slate-800 bg-black overflow-hidden relative aspect-[10/4]">
                              <img src={getImageUrl(stage.images.waveform)} alt="Waveform" className="object-cover w-full h-full" />
                          </div>
                      </div>
                  )}
                  {stage.images.spectrogram && (
                       <div className="space-y-2">
                          <p className="text-xs text-center text-slate-400">Spectrogram Comparison</p>
                          <div className="rounded-lg border border-slate-800 bg-black overflow-hidden relative aspect-[12/6]">
                              <img src={getImageUrl(stage.images.spectrogram)} alt="Spectrogram" className="object-contain w-full h-full" />
                          </div>
                      </div>
                  )}
              </div>
            </div>
          )}

          {(!stage.parameters && !stage.images) && (
              <p className="text-sm text-slate-500 text-center py-4">No detailed reporting data available for this stage.</p>
          )}

        </div>
      )}
    </div>
  );
};


export const ReportViewer: React.FC<ReportViewerProps> = ({ report, jobId }) => {
  if (!report) return null;

  return (
    <div className="w-full space-y-8">

      {/* General Summary Section */}
      <section className="rounded-2xl border border-teal-500/30 bg-teal-900/10 p-6 shadow-lg">
        <h2 className="mb-4 text-2xl font-bold text-teal-100">Mix Summary</h2>
        <div className="flex flex-col md:flex-row gap-8">
            <div className="flex-1 space-y-4">
                <p className="text-slate-300 leading-relaxed">
                    {report.general_summary || "The mixing pipeline has successfully processed your tracks."}
                </p>
                <div className="grid grid-cols-2 gap-4 mt-4">
                     <div className="bg-slate-900/50 p-3 rounded-lg border border-slate-800">
                        <p className="text-xs text-slate-500 uppercase">Style Preset</p>
                        <p className="text-lg font-semibold text-teal-300">{report.style_preset}</p>
                     </div>
                     <div className="bg-slate-900/50 p-3 rounded-lg border border-slate-800">
                        <p className="text-xs text-slate-500 uppercase">Generated At</p>
                        <p className="text-sm text-slate-300">{new Date(report.generated_at_utc).toLocaleString()}</p>
                     </div>
                </div>
            </div>

            {/* Final Metrics Compact View */}
             <div className="flex-1 bg-slate-950/50 rounded-xl p-4 border border-slate-800">
                <h3 className="text-sm font-bold uppercase text-slate-500 mb-3">Final Master Metrics</h3>
                <ul className="space-y-2 text-sm">
                    <li className="flex justify-between">
                        <span className="text-slate-400">Integrated LUFS</span>
                        <span className="font-mono text-teal-400">{report.final_metrics?.lufs_integrated?.toFixed(2) ?? 'N/A'}</span>
                    </li>
                    <li className="flex justify-between">
                        <span className="text-slate-400">True Peak</span>
                        <span className="font-mono text-teal-400">{report.final_metrics?.true_peak_dbtp?.toFixed(2) ?? 'N/A'} dBTP</span>
                    </li>
                     <li className="flex justify-between">
                        <span className="text-slate-400">LRA</span>
                        <span className="font-mono text-slate-200">{report.final_metrics?.lra?.toFixed(2) ?? 'N/A'} LU</span>
                    </li>
                    <li className="flex justify-between">
                        <span className="text-slate-400">Crest Factor</span>
                        <span className="font-mono text-slate-200">{report.final_metrics?.crest_factor_db?.toFixed(2) ?? 'N/A'} dB</span>
                    </li>
                </ul>
            </div>
        </div>
      </section>

      {/* Stages Accordion List */}
      <section>
          <h2 className="mb-6 text-xl font-bold text-slate-200 px-2">Detailed Stage Report</h2>
          <div className="space-y-2">
            {report.stages.map((stage) => (
                <ReportStageCard key={stage.contract_id} stage={stage} jobId={jobId} />
            ))}
          </div>
      </section>

    </div>
  );
};
