"use client";
import React, { useEffect, useState, useRef } from "react";
import { appendApiKeyParam, getBackendBaseUrl } from "../lib/mixApi";
import { useTranslations } from "next-intl";
import html2canvas from "html2canvas";
import { jsPDF } from "jspdf";
import { AdvancedInteractiveCharts, AnalysisData } from "./report/AdvancedInteractiveCharts";

// --- Types ---
interface StageParameter {
  [key: string]: string | number | { [subKey: string]: string | number };
}

interface ReportChange {
  key: string;
  value: string;
  unit: string;
  raw_key: string;
}

interface StageReport {
  contract_id: string;
  stage_id?: string | null;
  name: string;
  status: string;
  parameters?: StageParameter;
  changes?: ReportChange[];
  images?: {
    waveform?: string;
    spectrogram?: string;
  };
  key_metrics?: any;
  interactive_comparison?: {
    pre: any; // Legacy
    post: any; // Legacy
  };
}

interface FullReport {
  pipeline_version: string;
  generated_at_utc: string;
  style_preset: string;
  general_summary?: string;
  stages: StageReport[];
  final_metrics: any;
  interactive_charts?: {
    result?: AnalysisData;
    original?: AnalysisData;
    // Legacy fallback
    dynamics?: any;
    spectrum?: any;
  };
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
  const t = useTranslations("Report"); // Access common report translations (metrics etc)
  const tStages = useTranslations("Report.stages"); // Access stage descriptions

  const [waveformUrl, setWaveformUrl] = useState("");
  const images = stage.images || {};
  const hasImages = Object.keys(images).length > 0;

  // Prepara URLs firmadas (o con api_key) para las imágenes del reporte
  useEffect(() => {
    const base = getBackendBaseUrl();
    const buildUrl = (name?: string) =>
      name
        ? appendApiKeyParam(
            `${base}/files/${jobId}/S11_REPORT_GENERATION/${name}`
          )
        : "";
    setWaveformUrl(buildUrl(images.waveform));
  }, [jobId, images.waveform]);

  // Combine parameters and metrics for translation variables
  const params = {
    ...stage.parameters,
    ...stage.key_metrics,
  };

  const stageKey = stage.contract_id || stage.stage_id || "stage";
  const fallbackTitle = stage.name || stage.stage_id || stage.contract_id;
  const fallbackDescription =
    stage.status === "missing_analysis"
      ? "No analysis data available for this stage."
      : stage.name || "Processing complete.";

  const resolveStageTranslation = (key: string, fallback: string) =>
    tStages.has(key as any) ? tStages(key as any, params) : fallback;

  const stageTitle = resolveStageTranslation(`${stageKey}.title`, fallbackTitle);
  const stageDescription = resolveStageTranslation(
    `${stageKey}.description`,
    fallbackDescription
  );

  const changes = stage.changes || [];

  const renderChangeLine = (c: ReportChange, index: number) => {
    const metricNameKey = `metrics.${c.key}`;
    const metricName = t.has(metricNameKey as any) ? t(metricNameKey as any) : c.key;

    return (
      <li key={index} className="text-sm text-slate-300">
        <span className="font-semibold text-emerald-400">{metricName}</span>: <span className="font-mono text-emerald-200">{c.value} {c.unit}</span>
      </li>
    );
  };

  return (
    <div className="mb-4 overflow-hidden rounded-lg border border-emerald-900/50 bg-slate-900/40 backdrop-blur-sm p-6">
      <div className="mb-4">
        <h3 className="text-base font-bold text-emerald-100">{stageTitle}</h3>
        <p className="mt-2 text-sm text-slate-400 italic mb-4">
          {stageDescription}
        </p>

        <div className="rounded bg-black/30 p-4 border border-emerald-500/10">
           <h4 className="text-xs font-bold text-emerald-500 uppercase tracking-widest mb-2">
             {t("stageChangesTitle")}
           </h4>
           {changes.length > 0 ? (
             <ul className="space-y-1 list-disc list-inside">
               {changes.map((c, i) => renderChangeLine(c, i))}
             </ul>
           ) : (
             <p className="text-sm text-slate-500">
               {t("noChangesDetected")}
             </p>
           )}
        </div>
      </div>

      {hasImages && images.waveform && !stage.interactive_comparison && (
        <div className="mt-6 space-y-6">
          <div className="space-y-2">
            <p className="text-xs font-bold text-slate-400 uppercase tracking-wide">
              Waveform Comparison (Image)
            </p>
            <div className="rounded border border-emerald-500/20 bg-black/40 p-1">
              <img
                src={waveformUrl}
                alt="Waveform"
                className="w-full h-auto object-cover opacity-90"
                crossOrigin="anonymous"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export const ReportViewer: React.FC<ReportViewerProps> = ({
  report,
  jobId,
}) => {
  const t = useTranslations("Report");
  const [isDownloading, setIsDownloading] = useState(false);
  const reportRef = useRef<HTMLDivElement>(null);

  if (!report) return null;

  const processedStages = (report.stages || []).filter(
    (s) => s.status !== "skipped" && s.status !== "pending"
  );

  // Normalize charts data
  const charts = report.interactive_charts || {};
  const hasAdvancedCharts = !!charts.result;

  // Legacy support for old reports (if any)
  const legacyResult = (!hasAdvancedCharts && charts.dynamics) ? {
      loudness: undefined,
      dynamics: charts.dynamics,
      spectrum: charts.spectrum
  } as AnalysisData : undefined;

  const displayResult = charts.result || legacyResult;
  const displayOriginal = charts.original;

  const handleDownloadPdf = async () => {
    if (!reportRef.current) return;
    setIsDownloading(true);

    try {
      const scrollY = window.scrollY;
      window.scrollTo(0, 0);

      await new Promise((resolve) => setTimeout(resolve, 500));

      const canvas = await html2canvas(reportRef.current, {
        scale: 2,
        useCORS: true,
        logging: false,
        backgroundColor: "#0f172a",
        allowTaint: false,
      });

      window.scrollTo(0, scrollY);

      const imgData = canvas.toDataURL("image/png");
      const pdf = new jsPDF("p", "mm", "a4");
      const pdfWidth = pdf.internal.pageSize.getWidth();
      const pdfHeight = pdf.internal.pageSize.getHeight();
      const imgWidth = canvas.width;
      const imgHeight = canvas.height;
      const ratio = pdfWidth / imgWidth;
      const pdfImgHeight = imgHeight * ratio;
      let heightLeft = pdfImgHeight;

      pdf.addImage(imgData, "PNG", 0, 0, pdfWidth, pdfImgHeight);
      heightLeft -= pdfHeight;

      while (heightLeft > 0) {
        pdf.addPage();
        const pageIndex = Math.ceil((pdfImgHeight - heightLeft) / pdfHeight);
        pdf.addImage(imgData, "PNG", 0, -(pageIndex * pdfHeight), pdfWidth, pdfImgHeight);
        heightLeft -= pdfHeight;
      }

      pdf.save(`piroola_report_${jobId}.pdf`);
    } catch (error) {
      console.error("PDF generation failed:", error);
      alert("Failed to generate PDF.");
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <div className="w-full space-y-6">
        <div className="flex justify-between items-center px-1">
             <h1 className="text-xl font-bold text-emerald-400">{t("title")}</h1>
             <button
                onClick={handleDownloadPdf}
                disabled={isDownloading}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-bold rounded shadow transition-colors disabled:opacity-50"
             >
                {isDownloading ? t("generatingPdf") : t("downloadPdf")}
             </button>
        </div>

        <div ref={reportRef} id="report-content" className="space-y-6 p-4 bg-slate-950 text-slate-200">
            {/* Mix Summary Section */}
            <section className="rounded-xl border border-emerald-500/20 bg-gradient-to-br from-emerald-900/20 to-slate-900/40 p-5 shadow-lg">
                <h2 className="mb-4 text-lg font-bold text-emerald-100 tracking-tight">
                {t("mixSummary")}
                </h2>

                <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
                <div className="md:col-span-1 space-y-3">
                    <div className="rounded-lg bg-black/20 border border-emerald-500/10 p-3">
                    <p className="text-[10px] text-emerald-400/70 uppercase tracking-widest font-bold mb-1">
                        Style Preset
                    </p>
                    <p className="text-base font-medium text-emerald-50">
                        {report.style_preset}
                    </p>
                    </div>
                    {report.general_summary && (
                    <p className="text-sm text-slate-300 italic px-1">
                        {report.general_summary}
                    </p>
                    )}
                </div>

                <div className="md:col-span-2 rounded-lg border border-emerald-500/10 bg-black/20 p-4">
                    <h3 className="mb-3 text-[10px] font-bold uppercase tracking-widest text-emerald-400/70">
                    Final Master Metrics
                    </h3>
                    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
                    <div className="flex flex-col">
                        <span className="text-[10px] text-slate-400 uppercase">
                        Integrated LUFS
                        </span>
                        <span className="font-mono text-sm text-emerald-300 font-bold">
                        {report.final_metrics?.lufs_integrated?.toFixed(2) ?? "N/A"}
                        </span>
                    </div>
                    <div className="flex flex-col">
                        <span className="text-[10px] text-slate-400 uppercase">
                        True Peak
                        </span>
                        <span className="font-mono text-sm text-emerald-300 font-bold">
                        {report.final_metrics?.true_peak_dbtp?.toFixed(2) ?? "N/A"}{" "}
                        <span className="text-[10px] font-normal text-emerald-500/50">
                            dBTP
                        </span>
                        </span>
                    </div>
                    <div className="flex flex-col">
                        <span className="text-[10px] text-slate-400 uppercase">LRA</span>
                        <span className="font-mono text-sm text-slate-200">
                        {report.final_metrics?.lra?.toFixed(2) ?? "N/A"}{" "}
                        <span className="text-[10px] font-normal text-slate-500">
                            LU
                        </span>
                        </span>
                    </div>
                    <div className="flex flex-col">
                        <span className="text-[10px] text-slate-400 uppercase">
                        Crest Factor
                        </span>
                        <span className="font-mono text-sm text-slate-200">
                        {report.final_metrics?.crest_factor_db?.toFixed(2) ?? "N/A"}{" "}
                        <span className="text-[10px] font-normal text-slate-500">
                            dB
                        </span>
                        </span>
                    </div>
                    <div className="flex flex-col">
                        <span className="text-[10px] text-slate-400 uppercase">
                        Correlation
                        </span>
                        <span className="font-mono text-sm text-slate-200">
                        {report.final_metrics?.correlation?.toFixed(3) ?? "N/A"}
                        </span>
                    </div>
                    <div className="flex flex-col">
                        <span className="text-[10px] text-slate-400 uppercase">
                        Diff L/R
                        </span>
                        <span className="font-mono text-sm text-slate-200">
                        {report.final_metrics?.channel_loudness_diff_db?.toFixed(2) ??
                            "N/A"}{" "}
                        <span className="text-[10px] font-normal text-slate-500">
                            dB
                        </span>
                        </span>
                    </div>
                    </div>
                </div>
                </div>
            </section>

            {/* Advanced Interactive Charts Section */}
            {displayResult && (
                <section className="rounded-xl border border-emerald-500/20 bg-slate-900/40 p-5">
                <h2 className="mb-4 text-sm font-bold uppercase tracking-widest text-emerald-500/80">
                    {t("interactiveAnalysis")}
                </h2>

                <AdvancedInteractiveCharts
                    result={displayResult}
                    original={displayOriginal}
                />

                </section>
            )}

            {/* Detailed Stage Report */}
            <section>
                <div className="mb-3 flex items-center justify-between px-1">
                <h2 className="text-sm font-bold uppercase tracking-widest text-emerald-500/80">
                    {t("detailedStageReport")}
                </h2>
                <span className="text-[10px] text-slate-500">
                    {processedStages.length} stages processed
                </span>
                </div>

                <div className="space-y-4">
                {processedStages.map((stage) => (
                    <ReportStageCard
                    key={stage.contract_id}
                    stage={stage}
                    jobId={jobId}
                    />
                ))}
                </div>
            </section>
        </div>
    </div>
  );
};
