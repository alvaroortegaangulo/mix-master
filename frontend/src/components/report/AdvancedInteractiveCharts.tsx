"use client";

import React, { useState, useEffect, useRef } from "react";
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
  ReferenceLine,
  Legend
} from "recharts";
import { useTranslations } from "next-intl";

// --- Types (matching backend) ---

export interface TimeSeriesData {
  time: number[];
  values: number[];
}

export interface LoudnessData {
  momentary: number[];
  short_term: number[];
  integrated: number;
  lra: number;
  time: number[];
}

export interface DynamicsData {
  crest: number[];
  time: number[];
}

export interface StereoData {
  correlation: number[];
  width?: number[];
  time: number[];
}

export interface SpectrogramData {
  data: number[][]; // [time][freq_bin]
  freqs: number[];
}

export interface TonalData {
    spectrum: number[];
    freqs: number[];
}

export interface AnalysisData {
  loudness?: LoudnessData;
  dynamics?: DynamicsData;
  stereo?: StereoData;
  spectrogram?: SpectrogramData;
  tonal?: TonalData;
}

export interface AdvancedChartsProps {
  result: AnalysisData;
  original?: AnalysisData;
}

// --- Utils ---

const formatTime = (seconds: number) => {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
};

// --- Sub-Components ---

const ChartCard = ({
  title,
  children,
  onExpand,
}: {
  title: string;
  children: React.ReactNode;
  onExpand: () => void;
}) => (
  <div className="flex flex-col rounded-lg border border-slate-800 bg-slate-900/50 p-4 shadow-sm transition-all hover:border-emerald-500/30">
    <div className="mb-3 flex items-center justify-between">
      <h3 className="text-sm font-bold uppercase tracking-wide text-slate-300">
        {title}
      </h3>
      <button
        onClick={onExpand}
        className="text-[10px] uppercase font-bold text-emerald-500 hover:text-emerald-400"
      >
        Expand
      </button>
    </div>
    <div className="h-40 w-full relative">{children}</div>
  </div>
);

const Modal = ({
  isOpen,
  onClose,
  title,
  children,
}: {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
}) => {
  if (!isOpen) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm">
      <div className="flex h-[90vh] w-full max-w-6xl flex-col rounded-xl border border-slate-700 bg-slate-900 shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-800 p-4">
          <h2 className="text-xl font-bold text-emerald-400">{title}</h2>
          <button
            onClick={onClose}
            className="rounded p-2 text-slate-400 hover:bg-slate-800 hover:text-white"
          >
            ✕
          </button>
        </div>
        <div className="flex-1 overflow-hidden p-4 relative">{children}</div>
      </div>
    </div>
  );
};

// --- Chart Implementations ---

// 1. Loudness Chart
const LoudnessChart = ({
  data,
  original,
  expanded,
}: {
  data: LoudnessData;
  original?: LoudnessData;
  expanded?: boolean;
}) => {
  // Combine data
  // Assuming same time axis for simplicity, or we prioritize 'data' time
  const chartData = data.time.map((t, i) => ({
    time: t,
    timeLabel: formatTime(t),
    m_res: data.momentary[i] ?? -90,
    s_res: data.short_term[i] ?? -90,
    m_orig: original?.momentary[i] ?? -90,
    s_orig: original?.short_term[i] ?? -90,
  }));

  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={chartData}>
        <defs>
            <linearGradient id="gradResult" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
                <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
            </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
        <XAxis
          dataKey="timeLabel"
          stroke="#64748b"
          tick={{ fill: "#64748b", fontSize: 10 }}
          minTickGap={30}
        />
        <YAxis
          stroke="#64748b"
          tick={{ fill: "#64748b", fontSize: 10 }}
          domain={[-60, 0]}
        />
        <Tooltip
            contentStyle={{ backgroundColor: "#0f172a", borderColor: "#334155", color: "#f8fafc" }}
            labelFormatter={(l) => `Time: ${l}`}
            formatter={(val?: number) => {
              if (typeof val !== "number" || Number.isNaN(val)) {
                return ["N/A", ""];
              }
              return [`${val.toFixed(1)} LUFS`, ""];
            }}
        />
        {expanded && <Legend />}

        {/* Original */}
        {original && (
             <Area
             type="monotone"
             dataKey="s_orig"
             stroke="#64748b"
             fill="transparent"
             strokeDasharray="4 4"
             strokeWidth={1}
             name="Short-term (Original)"
           />
        )}

        {/* Result */}
        <Area
          type="monotone"
          dataKey="s_res"
          stroke="#10b981"
          fill="url(#gradResult)"
          strokeWidth={2}
          name="Short-term (Result)"
        />

        <ReferenceLine y={data.integrated} stroke="#34d399" strokeDasharray="3 3" label={{ position: 'right', value: 'I', fill: '#34d399', fontSize: 10 }} />

      </AreaChart>
    </ResponsiveContainer>
  );
};

// 2. Dynamics (Crest)
const DynamicsChart = ({
    data,
    original,
    expanded,
  }: {
    data: DynamicsData;
    original?: DynamicsData;
    expanded?: boolean;
  }) => {
    const chartData = data.time.map((t, i) => ({
      time: t,
      timeLabel: formatTime(t),
      crest_res: data.crest[i] ?? 0,
      crest_orig: original?.crest[i] ?? 0,
    }));

    return (
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
          <XAxis
            dataKey="timeLabel"
            stroke="#64748b"
            tick={{ fill: "#64748b", fontSize: 10 }}
            minTickGap={30}
          />
          <YAxis
            stroke="#64748b"
            tick={{ fill: "#64748b", fontSize: 10 }}
            domain={[0, 20]}
          />
          <Tooltip
              contentStyle={{ backgroundColor: "#0f172a", borderColor: "#334155", color: "#f8fafc" }}
              formatter={(val?: number) => {
                if (typeof val !== "number" || Number.isNaN(val)) {
                  return ["N/A", ""];
                }
                return [`${val.toFixed(1)} dB`, ""];
              }}
          />
          {expanded && <Legend />}

          {original && (
            <Line
              type="monotone"
              dataKey="crest_orig"
              stroke="#64748b"
              strokeWidth={1}
              strokeDasharray="4 4"
              dot={false}
              name="Crest Factor (Original)"
            />
          )}

          <Line
            type="monotone"
            dataKey="crest_res"
            stroke="#f59e0b"
            strokeWidth={2}
            dot={false}
            name="Crest Factor (Result)"
          />
        </LineChart>
      </ResponsiveContainer>
    );
  };

// 3. Stereo (Correlation)
const StereoChart = ({
    data,
    original,
    expanded,
  }: {
    data: StereoData;
    original?: StereoData;
    expanded?: boolean;
  }) => {
    const chartData = data.time.map((t, i) => ({
      time: t,
      timeLabel: formatTime(t),
      corr_res: data.correlation[i] ?? 0,
      corr_orig: original?.correlation[i] ?? 0,
      width_res: data.width?.[i] ?? 0,
      width_orig: original?.width?.[i] ?? 0,
    }));

    return (
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
          <XAxis
            dataKey="timeLabel"
            stroke="#64748b"
            tick={{ fill: "#64748b", fontSize: 10 }}
            minTickGap={30}
          />
          <YAxis
            stroke="#64748b"
            tick={{ fill: "#64748b", fontSize: 10 }}
            domain={[-1, 1]}
          />
          <Tooltip
              contentStyle={{ backgroundColor: "#0f172a", borderColor: "#334155", color: "#f8fafc" }}
              formatter={(val?: number, name?: string) => {
                const label = name ?? "";
                if (typeof val !== "number" || Number.isNaN(val)) {
                  return ["N/A", label];
                }
                return [val.toFixed(2), label];
              }}
          />
          {expanded && <Legend />}

          <ReferenceLine y={0} stroke="#ef4444" strokeOpacity={0.5} />

          {original && (
            <Line
              type="monotone"
              dataKey="corr_orig"
              stroke="#64748b"
              strokeWidth={1}
              strokeDasharray="4 4"
              dot={false}
              name="Correlation (Orig)"
            />
          )}

          <Line
            type="monotone"
            dataKey="corr_res"
            stroke="#3b82f6"
            strokeWidth={2}
            dot={false}
            name="Correlation (Res)"
          />
           {/* Width lines - only if present */}
           {expanded && (
             <>
               {original && (
                   <Line
                   type="monotone"
                   dataKey="width_orig"
                   stroke="#94a3b8"
                   strokeWidth={1}
                   strokeDasharray="2 2"
                   dot={false}
                   name="Width (Orig)"
                   />
               )}
                <Line
                   type="monotone"
                   dataKey="width_res"
                   stroke="#ec4899"
                   strokeWidth={2}
                   strokeDasharray="2 2"
                   dot={false}
                   name="Width (Res)"
                />
             </>
           )}
        </LineChart>
      </ResponsiveContainer>
    );
  };

// 4. Spectrogram (Canvas)
const SpectrogramCanvas = ({
    data,
    expanded
}: {
    data: SpectrogramData;
    expanded?: boolean;
}) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas || !data || !data.data.length) return;

        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        const numTimeSteps = data.data.length;
        const numFreqBins = data.data[0].length;

        const w = canvas.width;
        const h = canvas.height;

        const cellW = w / numTimeSteps;
        const cellH = h / numFreqBins;

        ctx.clearRect(0,0,w,h);

        // Find min/max for normalization
        let minDb = -80;
        let maxDb = 0;

        for (let i = 0; i < numTimeSteps; i++) {
            for (let j = 0; j < numFreqBins; j++) {
                const val = data.data[i][j];
                // Map val (db) to color
                // -80 (black) to 0 (yellow/white)
                const norm = Math.max(0, Math.min(1, (val - minDb) / (maxDb - minDb)));

                // Heatmap color: Blue -> Cyan -> Green -> Yellow -> Red
                const hue = (1 - norm) * 240;
                ctx.fillStyle = `hsl(${hue}, 100%, 50%)`;

                // Draw rect
                // Freq 0 is low freq (bottom), but index 0 in list is usually low freq?
                // data.freqs is typically sorted low to high.
                // So j=0 is bottom.
                // Canvas y=0 is top. So we flip y.
                const y = h - (j + 1) * cellH;

                ctx.fillRect(i * cellW, y, cellW + 1, cellH + 1);
            }
        }

    }, [data, expanded]);

    return (
        <canvas
            ref={canvasRef}
            width={expanded ? 800 : 300}
            height={expanded ? 400 : 150}
            className="w-full h-full object-cover rounded bg-black"
        />
    );
}

// 5. Tonal Balance (Spectrum)
const SpectrumChart = ({
    data,
    original,
    expanded,
  }: {
    data: TonalData;
    original?: TonalData;
    expanded?: boolean;
  }) => {
    // data.spectrum is array of db values.
    // data.freqs is array of freq values.
    const chartData = data.spectrum.map((val, i) => ({
      freq: data.freqs[i],
      val_res: val,
      val_orig: original?.spectrum[i] ?? -80
    }));

    return (
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData}>
            <defs>
                <linearGradient id="gradSpec" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.4}/>
                    <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0}/>
                </linearGradient>
            </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
          <XAxis
            dataKey="freq"
            type="number"
            scale="log"
            domain={['auto', 'auto']}
            stroke="#64748b"
            tick={{ fill: "#64748b", fontSize: 10 }}
            tickFormatter={(val) => val >= 1000 ? `${(val/1000).toFixed(1)}k` : `${val}`}
            allowDataOverflow
          />
          <YAxis
            stroke="#64748b"
            tick={{ fill: "#64748b", fontSize: 10 }}
            domain={[-80, 0]}
            allowDataOverflow={false}
          />
          <Tooltip
              contentStyle={{ backgroundColor: "#0f172a", borderColor: "#334155", color: "#f8fafc" }}
              labelFormatter={(label) => `${Number(label).toFixed(0)} Hz`}
              formatter={(val?: number) => {
                if (typeof val !== "number" || Number.isNaN(val)) {
                  return ["N/A", "dB"];
                }
                return [`${val.toFixed(1)} dB`, ""];
              }}
          />
          {expanded && <Legend />}

          {original && (
             <Area
             type="monotone"
             dataKey="val_orig"
             stroke="#64748b"
             fill="transparent"
             strokeDasharray="4 4"
             strokeWidth={1}
             name="Original"
           />
          )}

          <Area
            type="monotone"
            dataKey="val_res"
            stroke="#8b5cf6"
            fill="url(#gradSpec)"
            strokeWidth={2}
            name="Result"
          />
        </AreaChart>
      </ResponsiveContainer>
    );
  };


// --- Main Component ---

export const AdvancedInteractiveCharts: React.FC<AdvancedChartsProps> = ({
  result,
  original,
}) => {
  const [modalChart, setModalChart] = useState<string | null>(null);

  if (!result) return null;

  const charts = [
    {
      id: "loudness",
      title: "Loudness (EBU R128)",
      component: <LoudnessChart data={result.loudness!} original={original?.loudness} />,
      expandedComponent: <LoudnessChart data={result.loudness!} original={original?.loudness} expanded />,
      hasData: !!result.loudness
    },
    {
        id: "dynamics",
        title: "Dynamics & Crest Factor",
        component: <DynamicsChart data={result.dynamics!} original={original?.dynamics} />,
        expandedComponent: <DynamicsChart data={result.dynamics!} original={original?.dynamics} expanded />,
        hasData: !!result.dynamics
    },
    {
        id: "stereo",
        title: "Stereo Correlation",
        component: <StereoChart data={result.stereo!} original={original?.stereo} />,
        expandedComponent: <StereoChart data={result.stereo!} original={original?.stereo} expanded />,
        hasData: !!result.stereo
    },
    {
        id: "spectrogram",
        title: "Spectrogram",
        component: <SpectrogramCanvas data={result.spectrogram!} />,
        expandedComponent: <SpectrogramCanvas data={result.spectrogram!} expanded />,
        hasData: !!result.spectrogram
    },
    {
        id: "tonal",
        title: "Tonal Balance (Avg Spectrum)",
        component: <SpectrumChart data={result.tonal!} original={original?.tonal} />,
        expandedComponent: <SpectrumChart data={result.tonal!} original={original?.tonal} expanded />,
        hasData: !!result.tonal
    }
  ];

  const activeModal = charts.find(c => c.id === modalChart);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {charts.filter(c => c.hasData).map((chart) => (
          <ChartCard
            key={chart.id}
            title={chart.title}
            onExpand={() => setModalChart(chart.id)}
          >
            {chart.component}
          </ChartCard>
        ))}
      </div>

      <Modal
        isOpen={!!modalChart}
        onClose={() => setModalChart(null)}
        title={activeModal?.title || ""}
      >
        <div className="w-full h-full p-4 bg-slate-900">
           {activeModal?.expandedComponent}
        </div>
      </Modal>
    </div>
  );
};
