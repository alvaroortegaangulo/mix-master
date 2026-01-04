"use client";
import React, { useEffect, useState, useRef } from "react";
import { appendApiKeyParam, getBackendBaseUrl, signFileUrl } from "../lib/mixApi";
import { useTranslations } from "next-intl";
import html2canvas from "html2canvas";
import { jsPDF } from "jspdf";
import { AdvancedInteractiveCharts, AnalysisData } from "./report/AdvancedInteractiveCharts";
import { useAuth } from "../context/AuthContext";
import { useModal } from "../context/ModalContext";

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
  pipeline_durations?: {
    total_duration_sec?: number | null;
    stages?: Array<{
      contract_id?: string | null;
      duration_sec?: number | null;
    }>;
    generated_at_utc?: string | null;
  };
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
  authRedirectPath?: string;
}

// --- Components ---

const ReportStageCard = ({
  stage,
  jobId,
  durationSec,
}: {
  stage: StageReport;
  jobId: string;
  durationSec?: number | null;
}) => {
  const tStages = useTranslations("Report.stages"); // Access stage descriptions
  const durationLabel = formatDuration(durationSec);

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

  // Build params
  const rawParams = {
    ...stage.parameters,
    ...stage.key_metrics,
  };

  // Process changes to add them to params
  const changesParams: Record<string, any> = {};
  if (stage.changes) {
    stage.changes.forEach((c) => {
      // Use the key from the change (e.g. 'gain_db')
      // Pass the raw value. The translation string template should contain the unit if desired.
      // e.g. "Gain was <green>{gain_db}</green>dB"
      changesParams[c.key] = c.value;
    });
  }

  const combinedParams = { ...rawParams, ...changesParams };

  const stageKey = stage.contract_id || stage.stage_id || "stage";
  const fallbackTitle = stage.name || stage.stage_id || stage.contract_id;
  const fallbackDescription =
    stage.status === "missing_analysis"
      ? "No analysis data available for this stage."
      : stage.name || "Processing complete.";

  // Use rich translation
  // We pass a 'green' tag function to style the variables
  const stageTitle = tStages.has(`${stageKey}.title` as any)
    ? tStages(`${stageKey}.title` as any, combinedParams)
    : fallbackTitle;

  // Check if key exists to avoid error
  const hasDescription = tStages.has(`${stageKey}.description` as any);

  return (
    <div className="mb-4 overflow-hidden rounded-lg border border-[rgba(19,78,74,0.5)] bg-[rgba(15,23,42,0.4)] backdrop-blur-sm p-6">
      <div className="mb-4">
        <h3 className="text-base font-bold text-teal-100 mb-3">
          {stageTitle}
          {durationLabel && (
            <span className="ml-2 text-[10px] font-semibold text-slate-400">
              ({durationLabel})
            </span>
          )}
        </h3>
        <p className="text-sm text-slate-300 leading-relaxed text-justify">
          {hasDescription ? tStages.rich(`${stageKey}.description` as any, {
              ...combinedParams,
              green: (chunks) => (
                <span className="font-mono font-bold text-amber-400 bg-[rgba(251,191,36,0.1)] px-1 rounded mx-0.5">
                  {chunks}
                </span>
              )
          }) : fallbackDescription}
        </p>
      </div>

      {hasImages && images.waveform && !stage.interactive_comparison && (
        <div className="mt-6 space-y-6">
          <div className="space-y-2">
            <p className="text-xs font-bold text-slate-400 uppercase tracking-wide">
              Waveform Comparison (Image)
            </p>
            <div className="rounded border border-[rgba(20,184,166,0.2)] bg-[rgba(0,0,0,0.4)] p-1">
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
  authRedirectPath,
}) => {
  const t = useTranslations("Report");
  const [isDownloading, setIsDownloading] = useState(false);
  const [showLogs, setShowLogs] = useState(false);
  const [logsContent, setLogsContent] = useState("");
  const [logsLoading, setLogsLoading] = useState(false);
  const [logsError, setLogsError] = useState<string | null>(null);
  const reportRef = useRef<HTMLDivElement>(null);
  const { user } = useAuth();
  const { openAuthModal } = useModal();

  if (!report) return null;

  const processedStages = (report.stages || []).filter(
    (s) => s.status !== "skipped" && s.status !== "pending"
  );
  const durationByStage = buildDurationMap(report.pipeline_durations?.stages);
  const totalDurationLabel =
    formatDuration(report.pipeline_durations?.total_duration_sec) || "N/A";

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
    if (!user) {
      openAuthModal(authRedirectPath);
      return;
    }
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

  const fetchLogsText = async () => {
    const url = await signFileUrl(jobId, "pipeline.log");
    const response = await fetch(url);
    if (!response.ok) throw new Error("Failed to fetch logs");
    return response.text();
  };

  const handleToggleLogs = async () => {
    if (showLogs) {
      setShowLogs(false);
      return;
    }
    if (!user) {
      openAuthModal(authRedirectPath);
      return;
    }
    setShowLogs(true);
    if (logsContent || logsLoading) return;
    setLogsLoading(true);
    setLogsError(null);
    try {
      const text = await fetchLogsText();
      setLogsContent(text);
    } catch (err) {
      console.error("Failed to load logs:", err);
      setLogsError("No se pudieron cargar los logs.");
    } finally {
      setLogsLoading(false);
    }
  };

  const handleDownloadLogs = async () => {
    if (!user) {
      openAuthModal(authRedirectPath);
      return;
    }
    try {
      // 1. Fetch the log file (via signed URL)
      // Since we don't have a direct "get log text" method in mixApi usually,
      // we'll use the file signing mechanism to get a URL, then fetch the text.
      const text = await fetchLogsText();

      // 2. Generate PDF with jsPDF
      const doc = new jsPDF();

      // Set background to black
      doc.setFillColor(0, 0, 0);
      doc.rect(0, 0, doc.internal.pageSize.width, doc.internal.pageSize.height, "F");

      // Set font to monospace (Courier)
      doc.setFont("Courier", "normal");
      doc.setFontSize(10);

      let cursorY = 10;
      const margin = 10;
      const lineHeight = 5;
      const pageHeight = doc.internal.pageSize.height;

      // Split lines
      const lines = text.split("\n");

      // Regex for ANSI codes: \033[...m
      // We handle basic colors: 30-37 (foreground), 1 (bold - ignore or map to bold font?)
      // Simplification: we map specific known codes from logger.py to RGB.
      const ansiRegex = /\u001b\[(\d+(?:;\d+)*)m/g;

      // Color map based on logger.py
      const colorMap: Record<string, [number, number, number]> = {
        "0": [255, 255, 255], // Reset -> White
        "30": [0, 0, 0],       // Black
        "31": [255, 85, 85],   // Red
        "32": [80, 250, 123],  // Green
        "33": [241, 250, 140], // Yellow
        "34": [189, 147, 249], // Blue
        "35": [255, 121, 198], // Magenta
        "36": [139, 233, 253], // Cyan
        "37": [255, 255, 255], // White
        "1": [255, 255, 255],  // Bold -> White (ignore bold weight for simplicity or just keep current color)
      };

      let currentColor: [number, number, number] = [255, 255, 255]; // Start white

      for (const line of lines) {
        // Reset X
        let cursorX = margin;

        // We need to parse the line into segments of (text, color)
        let lastIndex = 0;
        let match;

        // Create a temporary "clean" line for wrapping calculation?
        // Wrapping with mixed colors is complex. We'll assume logs generally fit or simple wrap.
        // For accurate wrapping with colors, we'd need to measure segments.
        // For now, let's assume no wrapping needed for typical log lines, or truncate.
        // Actually, logs can be long. Let's do simple char-based processing or naive segmenting.

        const segments: { text: string; color: [number, number, number] }[] = [];

        while ((match = ansiRegex.exec(line)) !== null) {
          const textSegment = line.substring(lastIndex, match.index);
          if (textSegment) {
            segments.push({ text: textSegment, color: [...currentColor] });
          }

          const codes = match[1].split(";");
          for (const code of codes) {
            if (code === "0") {
              currentColor = [255, 255, 255];
            } else if (colorMap[code]) {
              currentColor = colorMap[code];
            }
          }
          lastIndex = ansiRegex.lastIndex;
        }
        // Remaining text
        if (lastIndex < line.length) {
          segments.push({ text: line.substring(lastIndex), color: [...currentColor] });
        }

        // Print segments
        for (const seg of segments) {
           doc.setTextColor(seg.color[0], seg.color[1], seg.color[2]);
           doc.text(seg.text, cursorX, cursorY);
           // Advance X - this is tricky without measuring. Courier is monospaced!
           // 10pt Courier approx width?
           // doc.getTextWidth(seg.text) works.
           cursorX += doc.getTextWidth(seg.text);
        }

        cursorY += lineHeight;
        if (cursorY > pageHeight - margin) {
          doc.addPage();
          doc.setFillColor(0, 0, 0);
          doc.rect(0, 0, doc.internal.pageSize.width, doc.internal.pageSize.height, "F");
          cursorY = margin;
        }
      }

      doc.save(`Piroola_Logs_${jobId}.pdf`);

    } catch (err) {
      console.error("Failed to download logs:", err);
      // Optional: show toast error
    }
  };

  return (
    <div className="w-full space-y-6">
        <div className="flex justify-between items-center px-1">
             <h1 className="text-xl font-bold text-teal-400">{t("title")}</h1>
             <div className="flex gap-2">
               <button
                  onClick={handleDownloadLogs}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-sm font-bold rounded shadow transition-colors"
               >
                  {t("downloadLogs")}
               </button>
               <button
                  onClick={handleDownloadPdf}
                  disabled={isDownloading}
                  className="px-4 py-2 bg-teal-600 hover:bg-teal-500 text-white text-sm font-bold rounded shadow transition-colors disabled:opacity-50"
               >
                  {isDownloading ? t("generatingPdf") : t("downloadPdf")}
               </button>
             </div>
        </div>

        <div ref={reportRef} id="report-content" className="space-y-6 p-4 bg-slate-950 text-slate-200">
            {/* Mix Summary Section */}
            <section
              className="rounded-xl border border-[rgba(20,184,166,0.2)] p-5 shadow-lg"
              style={{
                // Use explicit rgba gradient to avoid html2canvas "lab" parsing errors.
                backgroundImage:
                  "linear-gradient(to bottom right, rgba(19, 78, 74, 0.2), rgba(15, 23, 42, 0.4))",
              }}
            >
                <button
                  type="button"
                  onClick={handleToggleLogs}
                  className="mb-3 inline-flex items-center justify-center rounded-lg border border-amber-400/50 bg-amber-500 px-3 py-1.5 text-[11px] font-bold text-slate-950 transition hover:bg-amber-400"
                >
                  {showLogs ? t("viewReport") : t("viewProcessing")}
                </button>
                <h2 className="mb-4 text-lg font-bold text-teal-100 tracking-tight">
                {t("mixSummary")}
                </h2>

                <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
                <div className="md:col-span-1 space-y-3">
                    <div className="rounded-lg bg-[rgba(0,0,0,0.2)] border border-[rgba(20,184,166,0.1)] p-3">
                    <p className="text-[10px] text-[rgba(45,212,191,0.7)] uppercase tracking-widest font-bold mb-1">
                        Style Preset
                    </p>
                    <p className="text-base font-medium text-teal-50">
                        {report.style_preset}
                    </p>
                    </div>
                    <div className="rounded-lg bg-[rgba(0,0,0,0.2)] border border-[rgba(20,184,166,0.1)] p-3">
                    <p className="text-[10px] text-[rgba(45,212,191,0.7)] uppercase tracking-widest font-bold mb-1">
                        Tiempo total del pipeline
                    </p>
                    <p className="text-base font-medium text-teal-50">
                        {totalDurationLabel}
                    </p>
                    </div>
                    {report.general_summary && (
                    <p className="text-sm text-slate-300 italic px-1">
                        {report.general_summary}
                    </p>
                    )}
                </div>

                <div className="md:col-span-2 rounded-lg border border-[rgba(20,184,166,0.1)] bg-[rgba(0,0,0,0.2)] p-4">
                    <h3 className="mb-3 text-[10px] font-bold uppercase tracking-widest text-[rgba(45,212,191,0.7)]">
                    Final Master Metrics
                    </h3>
                    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
                    <div className="flex flex-col">
                        <span className="text-[10px] text-slate-400 uppercase">
                        Integrated LUFS
                        </span>
                        <span className="font-mono text-sm text-teal-300 font-bold">
                        {report.final_metrics?.lufs_integrated?.toFixed(2) ?? "N/A"}
                        </span>
                    </div>
                    <div className="flex flex-col">
                        <span className="text-[10px] text-slate-400 uppercase">
                        True Peak
                        </span>
                        <span className="font-mono text-sm text-teal-300 font-bold">
                        {report.final_metrics?.true_peak_dbtp?.toFixed(2) ?? "N/A"}{" "}
                        <span className="text-[10px] font-normal text-[rgba(20,184,166,0.5)]">
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

            {showLogs && (
              <section className="rounded-xl border border-amber-500/20 bg-[rgba(15,23,42,0.35)] p-5">
                <h2 className="mb-4 text-sm font-bold uppercase tracking-widest text-amber-200/80">
                  {t("processingLogs")}
                </h2>
                {logsLoading && (
                  <div className="text-xs text-slate-400">Cargando logs...</div>
                )}
                {!logsLoading && logsError && (
                  <div className="text-xs text-amber-200">{logsError}</div>
                )}
                {!logsLoading && !logsError && (
                  <pre className="max-h-[60vh] overflow-y-auto whitespace-pre-wrap break-words rounded-lg border border-slate-800 bg-slate-950/80 p-4 text-[11px] text-slate-200">
                    {logsContent || "Sin logs disponibles."}
                  </pre>
                )}
              </section>
            )}

            {!showLogs && (
              <>
                {/* Advanced Interactive Charts Section */}
                {displayResult && (
                    <section className="rounded-xl border border-[rgba(20,184,166,0.2)] bg-[rgba(15,23,42,0.4)] p-5">
                    <h2 className="mb-4 text-sm font-bold uppercase tracking-widest text-[rgba(20,184,166,0.8)]">
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
                    <h2 className="text-sm font-bold uppercase tracking-widest text-[rgba(20,184,166,0.8)]">
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
                        durationSec={durationByStage[stage.contract_id] ?? null}
                        />
                    ))}
                    </div>
                </section>
              </>
            )}
        </div>
    </div>
  );
};

function formatDuration(totalSeconds?: number | null): string | null {
  if (typeof totalSeconds !== "number" || !Number.isFinite(totalSeconds)) {
    return null;
  }
  const safeSeconds = Math.max(0, Math.round(totalSeconds));
  const hours = Math.floor(safeSeconds / 3600);
  const minutes = Math.floor((safeSeconds % 3600) / 60);
  const seconds = safeSeconds % 60;

  if (hours > 0) {
    return `${hours}h ${minutes}m ${seconds}s`;
  }
  if (minutes > 0) {
    return `${minutes}m ${seconds}s`;
  }
  return `${seconds}s`;
}

function buildDurationMap(
  stages: Array<{ contract_id?: string | null; duration_sec?: number | null }> | undefined,
): Record<string, number> {
  const map: Record<string, number> = {};
  if (!Array.isArray(stages)) {
    return map;
  }
  stages.forEach((stage) => {
    if (!stage?.contract_id) {
      return;
    }
    if (typeof stage.duration_sec !== "number" || !Number.isFinite(stage.duration_sec)) {
      return;
    }
    map[stage.contract_id] = stage.duration_sec;
  });
  return map;
}
