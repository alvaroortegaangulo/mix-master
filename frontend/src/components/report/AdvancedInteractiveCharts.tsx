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
  Legend,
  ReferenceArea
} from "recharts";

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
  width_low?: number[];
  width_mid?: number[];
  width_high?: number[];
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
  vectorscope?: number[][]; // 64x64 density matrix
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

// 3. Stereo (Correlation & Width)
const StereoChart = ({
    data,
    original,
    expanded,
  }: {
    data: StereoData;
    original?: StereoData;
    expanded?: boolean;
  }) => {
    // Toggles for multiband
    const [showBands, setShowBands] = useState(false);

    const chartData = data.time.map((t, i) => ({
      time: t,
      timeLabel: formatTime(t),
      corr_res: data.correlation[i] ?? 0,
      corr_orig: original?.correlation[i] ?? 0,
      width_res: data.width?.[i] ?? 0,
      width_orig: original?.width?.[i] ?? 0,
      width_low: data.width_low?.[i] ?? 0,
      width_mid: data.width_mid?.[i] ?? 0,
      width_high: data.width_high?.[i] ?? 0,
    }));

    // Gradient for correlation: Blue above 0, Red below 0
    // Domain [-1, 1], so 0 is at 50%
    const gradientOffset = 0.5;

    return (
      <div className="w-full h-full relative">
          {expanded && (
             <div className="absolute top-0 right-0 z-10 p-2">
                 <label className="flex items-center space-x-2 text-xs text-slate-300 bg-slate-800 p-1 rounded cursor-pointer">
                     <input type="checkbox" checked={showBands} onChange={(e) => setShowBands(e.target.checked)} />
                     <span>Show Width Bands (L/M/H)</span>
                 </label>
             </div>
          )}
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData}>
            <defs>
                <linearGradient id="corrGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#3b82f6" />
                    <stop offset="50%" stopColor="#3b82f6" />
                    <stop offset="50%" stopColor="#ef4444" />
                    <stop offset="100%" stopColor="#ef4444" />
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
                domain={[-1, 1]}
            />
            <Tooltip
                contentStyle={{ backgroundColor: "#0f172a", borderColor: "#334155", color: "#f8fafc" }}
                formatter={(val?: number, name?: string) => {
                    const label = name ?? "";
                    if (typeof val !== "number" || Number.isNaN(val)) return ["N/A", label];
                    return [val.toFixed(2), label];
                }}
            />
            {expanded && <Legend />}

            <ReferenceLine y={0} stroke="#475569" strokeDasharray="3 3" />

            {/* Highlight negative correlation areas - tricky with LineChart, better use gradient line color */}

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
                stroke="url(#corrGradient)"
                strokeWidth={2}
                dot={false}
                name="Correlation (Res)"
            />

            {/* Global Width */}
            <Line
                type="monotone"
                dataKey="width_res"
                stroke="#d946ef" // Fuchsia
                strokeWidth={2}
                strokeDasharray="2 2"
                dot={false}
                name="Width (Global)"
                hide={!expanded}
            />

            {/* Multiband Width */}
            {expanded && showBands && (
                <>
                    <Line type="monotone" dataKey="width_low" stroke="#f87171" strokeWidth={1} dot={false} name="Width (Low)" />
                    <Line type="monotone" dataKey="width_mid" stroke="#4ade80" strokeWidth={1} dot={false} name="Width (Mid)" />
                    <Line type="monotone" dataKey="width_high" stroke="#60a5fa" strokeWidth={1} dot={false} name="Width (High)" />
                </>
            )}

            </LineChart>
        </ResponsiveContainer>
      </div>
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

        // Find min/max for normalization (approx)
        let minDb = -80;
        let maxDb = 0;

        for (let i = 0; i < numTimeSteps; i++) {
            for (let j = 0; j < numFreqBins; j++) {
                const val = data.data[i][j];
                const norm = Math.max(0, Math.min(1, (val - minDb) / (maxDb - minDb)));
                const hue = (1 - norm) * 240; // Blue to Red
                ctx.fillStyle = `hsl(${hue}, 100%, 50%)`;
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

// 5. Vectorscope (Density Plot)
const VectorscopeChart = ({
    data,
    original,
    expanded
}: {
    data: number[][]; // 64x64
    original?: number[][];
    expanded?: boolean;
}) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const [mode, setMode] = useState<'result' | 'original'>('result');

    const activeData = (mode === 'result' ? data : original) || data;

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas || !activeData) return;

        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        const size = activeData.length; // 64
        const w = canvas.width;
        const h = canvas.height;

        ctx.clearRect(0, 0, w, h);

        // Draw grid/background
        ctx.strokeStyle = '#334155';
        ctx.lineWidth = 1;

        // M/S Diagonals
        ctx.beginPath();
        ctx.moveTo(0, h); ctx.lineTo(w, 0); // L=R (Mid)
        ctx.moveTo(0, 0); ctx.lineTo(w, h); // L=-R (Side)
        ctx.stroke();

        // Draw density
        // activeData[y][x] where y is row (0..63), x is col (0..63)
        // y=0 corresponds to R=-1 (bottom), y=63 to R=1 (top)
        // x=0 corresponds to L=-1 (left), x=63 to L=1 (right)

        const cellW = w / size;
        const cellH = h / size;

        for (let y = 0; y < size; y++) {
            for (let x = 0; x < size; x++) {
                const val = activeData[y][x]; // Normalized 0-1
                if (val < 0.01) continue;

                // Heatmap color: Green-ish for result
                // Opacity based on density
                const alpha = Math.min(1, val * 2); // Boost visibility
                const intensity = Math.floor(val * 255);

                // Use Emerald for result, Slate/White for generic
                // Or standard Green scope
                ctx.fillStyle = `rgba(16, 185, 129, ${alpha})`;

                // Draw rect. Y needs flip if canvas 0 is top
                // y index 0 is bottom (-1).
                // So canvas y = h - (y+1)*cellH
                const cy = h - (y + 1) * cellH;
                const cx = x * cellW;

                // Slightly larger to fill gaps
                ctx.fillRect(cx, cy, cellW + 0.5, cellH + 0.5);
            }
        }

    }, [activeData, expanded, mode]);

    return (
        <div className="w-full h-full flex flex-col items-center justify-center relative">
            <canvas
                ref={canvasRef}
                width={expanded ? 400 : 200}
                height={expanded ? 400 : 200}
                className="bg-slate-950 rounded-full border border-slate-800"
                style={{ aspectRatio: '1/1' }}
            />
            {expanded && original && (
                <div className="absolute top-4 right-4 flex space-x-2">
                     <button
                        onClick={() => setMode('result')}
                        className={`px-2 py-1 text-xs rounded ${mode==='result' ? 'bg-emerald-600 text-white' : 'bg-slate-800 text-slate-400'}`}
                     >
                        Result
                     </button>
                     <button
                        onClick={() => setMode('original')}
                        className={`px-2 py-1 text-xs rounded ${mode==='original' ? 'bg-slate-600 text-white' : 'bg-slate-800 text-slate-400'}`}
                     >
                        Original
                     </button>
                </div>
            )}
            <div className="absolute bottom-2 text-[10px] text-slate-500 font-mono">
                L &lt;-- Stereo Image --&gt; R
            </div>
        </div>
    );
}

// 6. Tonal Balance (Spectrum)
const SpectrumChart = ({
    data,
    original,
    expanded,
  }: {
    data: TonalData;
    original?: TonalData;
    expanded?: boolean;
  }) => {
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
        title: "Stereo Correlation & Width",
        component: <StereoChart data={result.stereo!} original={original?.stereo} />,
        expandedComponent: <StereoChart data={result.stereo!} original={original?.stereo} expanded />,
        hasData: !!result.stereo
    },
    {
        id: "vectorscope",
        title: "Vectorscope (L/R Density)",
        component: <VectorscopeChart data={result.vectorscope!} original={original?.vectorscope} />,
        expandedComponent: <VectorscopeChart data={result.vectorscope!} original={original?.vectorscope} expanded />,
        hasData: !!result.vectorscope // New field
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
