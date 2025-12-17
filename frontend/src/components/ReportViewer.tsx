"use client";
import React, { useEffect, useState, useRef } from "react";
import { appendApiKeyParam, getBackendBaseUrl } from "../lib/mixApi";
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { useTranslations } from "next-intl";
import html2canvas from "html2canvas";
import jsPDF from "jspdf";

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

interface InteractiveChartsData {
  dynamics?: {
    time_step: number;
    rms_db: number[];
    peak_db: number[];
    duration_sec: number;
  };
  spectrum?: {
    frequencies: number[];
    magnitudes_db: number[];
  };
}

interface FullReport {
  pipeline_version: string;
  generated_at_utc: string;
  style_preset: string;
  general_summary?: string;
  stages: StageReport[];
  final_metrics: any;
  interactive_charts?: InteractiveChartsData;
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
  const t = useTranslations("Report.stages");
  const [waveformUrl, setWaveformUrl] = useState("");
  const [spectrogramUrl, setSpectrogramUrl] = useState("");
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
    setSpectrogramUrl(buildUrl(images.spectrogram));
  }, [jobId, images.waveform, images.spectrogram]);

  // Combine parameters and metrics for translation variables
  const params = {
    ...stage.parameters,
    ...stage.key_metrics,
  };

  // Safe translation helper
  const stageTitle = t(`${stage.stage_id}.title`, { default: stage.name || stage.stage_id });
  const stageDescription = t(`${stage.stage_id}.description`, {
    ...params,
    default: "Processing complete.",
  });

  return (
    <div className="mb-4 overflow-hidden rounded-lg border border-emerald-900/50 bg-slate-900/40 backdrop-blur-sm p-6">
      <div className="mb-4">
        <h3 className="text-base font-bold text-emerald-100">{stageTitle}</h3>
        <p className="mt-2 text-sm text-slate-300 leading-relaxed">
          {stageDescription}
        </p>
      </div>

      {/* Images Grid - Larger now */}
      {hasImages && (
        <div className="mt-6 space-y-6">
          {images.waveform && (
            <div className="space-y-2">
              <p className="text-xs font-bold text-slate-400 uppercase tracking-wide">
                Waveform Comparison
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
          )}
          {images.spectrogram && (
            <div className="space-y-2">
              <p className="text-xs font-bold text-slate-400 uppercase tracking-wide">
                Spectrogram Comparison
              </p>
              <div className="rounded border border-emerald-500/20 bg-black/40 p-1">
                <img
                  src={spectrogramUrl}
                  alt="Spectrogram"
                  className="w-full h-auto object-contain opacity-90"
                  crossOrigin="anonymous"
                />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// --- Chart Components ---

const DynamicsChart = ({
  data,
}: {
  data: NonNullable<InteractiveChartsData["dynamics"]>;
}) => {
  // Transform data for Recharts
  const chartData = data.rms_db.map((rms, i) => ({
    time: (i * data.time_step).toFixed(1),
    rms: rms,
    peak: data.peak_db[i] || -90,
  }));

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart
          data={chartData}
          margin={{ top: 5, right: 0, left: -20, bottom: 0 }}
        >
          <defs>
            <linearGradient id="colorRms" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="#334155"
            vertical={false}
          />
          <XAxis
            dataKey="time"
            stroke="#64748b"
            tick={{ fill: "#64748b", fontSize: 10 }}
            minTickGap={30}
            interval="preserveStartEnd"
          />
          <YAxis
            stroke="#64748b"
            tick={{ fill: "#64748b", fontSize: 10 }}
            domain={[-60, 0]}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#0f172a",
              borderColor: "#334155",
              color: "#f8fafc",
              fontSize: "12px",
            }}
            itemStyle={{ color: "#10b981" }}
            labelFormatter={(label: any) => `Time: ${label}s`}
            formatter={(value: any) => [`${Number(value).toFixed(1)} dB`, ""]}
          />
          <Area
            type="monotone"
            dataKey="rms"
            stroke="#10b981"
            fillOpacity={1}
            fill="url(#colorRms)"
            name="RMS"
            strokeWidth={1.5}
          />
          <Line
            type="monotone"
            dataKey="peak"
            stroke="#f59e0b"
            dot={false}
            strokeWidth={1}
            strokeOpacity={0.6}
            name="Peak"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
};

const SpectrumChart = ({
  data,
}: {
  data: NonNullable<InteractiveChartsData["spectrum"]>;
}) => {
  const chartData = data.frequencies.map((freq, i) => ({
    freq: freq,
    mag: data.magnitudes_db[i],
  }));

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={chartData}
          margin={{ top: 5, right: 0, left: -20, bottom: 0 }}
        >
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="#334155"
            vertical={false}
          />
          <XAxis
            dataKey="freq"
            stroke="#64748b"
            tick={{ fill: "#64748b", fontSize: 10 }}
            scale="log"
            domain={[20, 20000]}
            type="number"
            tickFormatter={(val) =>
              val >= 1000 ? `${(val / 1000).toFixed(0)}k` : val
            }
            ticks={[50, 100, 200, 500, 1000, 2000, 5000, 10000]}
          />
          <YAxis
            stroke="#64748b"
            tick={{ fill: "#64748b", fontSize: 10 }}
            domain={[-60, 0]}
          />
          <Tooltip
            cursor={{ fill: "#334155", opacity: 0.2 }}
            contentStyle={{
              backgroundColor: "#0f172a",
              borderColor: "#334155",
              color: "#f8fafc",
              fontSize: "12px",
            }}
            labelFormatter={(label: any) =>
              `Freq: ${Number(label).toFixed(0)} Hz`
            }
            formatter={(value: any) => [
              `${Number(value).toFixed(1)} dB`,
              "Magnitude",
            ]}
          />
          <Bar dataKey="mag" fill="#3b82f6" radius={[2, 2, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
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

  // Filter only processed stages as requested
  // Assuming 'processed' usually implies a successful execution or present data.
  // The 'status' field in report stages usually is 'analyzed', 'processed', or 'skipped'.
  // We'll filter out skipped ones if status indicates it.
  const processedStages = (report.stages || []).filter(
    (s) => s.status !== "skipped" && s.status !== "pending"
  );

  const charts = report.interactive_charts;

  const handleDownloadPdf = async () => {
    if (!reportRef.current) return;
    setIsDownloading(true);

    try {
      // Small delay to ensure rendering
      await new Promise((resolve) => setTimeout(resolve, 100));

      const canvas = await html2canvas(reportRef.current, {
        scale: 2,
        useCORS: true,
        logging: false,
        backgroundColor: "#0f172a", // Match bg-slate-950
      });

      const imgData = canvas.toDataURL("image/png");
      const pdf = new jsPDF("p", "mm", "a4");
      const pdfWidth = pdf.internal.pageSize.getWidth();
      const pdfHeight = pdf.internal.pageSize.getHeight();

      const imgWidth = canvas.width;
      const imgHeight = canvas.height;

      const ratio = pdfWidth / imgWidth;
      const pdfImgHeight = imgHeight * ratio;

      let heightLeft = pdfImgHeight;
      let position = 0;

      // Add first page
      pdf.addImage(imgData, "PNG", 0, position, pdfWidth, pdfImgHeight);
      heightLeft -= pdfHeight;

      // Add subsequent pages
      while (heightLeft > 0) {
        position = heightLeft - pdfImgHeight; // relative to bottom
        // Actually, multipage logic with image slicing is tricky.
        // Simplified approach: Add new page and offset image.
        pdf.addPage();
        // position needs to be negative to show the next part
        // For page 2, we want to show from -pdfHeight
        position = - (pdfImgHeight - heightLeft); // This logic is often buggy for naive slicing

        // Correct logic for simple naive slicing (might cut text in half):
        // Page 1: y=0.
        // Page 2: y=-pdfHeight.

        const pageIndex = Math.ceil((pdfImgHeight - heightLeft) / pdfHeight);
        pdf.addImage(imgData, "PNG", 0, -(pageIndex * pdfHeight), pdfWidth, pdfImgHeight);

        heightLeft -= pdfHeight;
      }

      pdf.save(`piroola_report_${jobId}.pdf`);
    } catch (error) {
      console.error("PDF generation failed:", error);
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

        {/* Report Content Container for PDF */}
        <div ref={reportRef} id="report-content" className="space-y-6 p-4 bg-slate-950 text-slate-200">
            {/* Mix Summary Section */}
            <section className="rounded-xl border border-emerald-500/20 bg-gradient-to-br from-emerald-900/20 to-slate-900/40 p-5 shadow-lg">
                <h2 className="mb-4 text-lg font-bold text-emerald-100 tracking-tight">
                {t("mixSummary")}
                </h2>

                <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
                {/* Context Info */}
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

                {/* Metrics Grid */}
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

            {/* Interactive Charts Section */}
            {charts && (
                <section className="rounded-xl border border-emerald-500/20 bg-slate-900/40 p-5">
                <h2 className="mb-4 text-sm font-bold uppercase tracking-widest text-emerald-500/80">
                    {t("interactiveAnalysis")}
                </h2>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    {charts.dynamics && (
                    <div className="space-y-2">
                        <h3 className="text-xs font-bold text-slate-400 uppercase">
                        Dynamic Range (RMS & Peak)
                        </h3>
                        <div className="rounded-lg border border-slate-800 bg-black/20 p-2">
                        <DynamicsChart data={charts.dynamics} />
                        </div>
                    </div>
                    )}
                    {charts.spectrum && (
                    <div className="space-y-2">
                        <h3 className="text-xs font-bold text-slate-400 uppercase">
                        Average Frequency Spectrum
                        </h3>
                        <div className="rounded-lg border border-slate-800 bg-black/20 p-2">
                        <SpectrumChart data={charts.spectrum} />
                        </div>
                    </div>
                    )}
                </div>
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
                {processedStages.length === 0 && (
                    <div className="rounded-lg border border-dashed border-slate-700 p-8 text-center">
                    <p className="text-slate-500">
                        No detailed stage data available.
                    </p>
                    </div>
                )}
                </div>
            </section>
        </div>
    </div>
  );
};
