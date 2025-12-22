"use client";

import React, { useState, useEffect, useRef, useMemo } from "react";
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

// Simple Magma-like colormap (Black -> Purple -> Orange -> Yellow -> White)
const getMagmaColor = (t: number): string => {
  // t is 0..1
  if (t < 0) t = 0;
  if (t > 1) t = 1;

  // Keypoints:
  // 0.0: 0, 0, 0 (Black)
  // 0.25: 64, 15, 80 (Deep Purple)
  // 0.5: 180, 50, 60 (Reddish)
  // 0.75: 250, 150, 40 (Orange)
  // 1.0: 255, 255, 220 (White-ish Yellow)

  let r, g, b;

  if (t < 0.25) {
      // 0.0 -> 0.25
      const p = t / 0.25;
      r = 64 * p;
      g = 15 * p;
      b = 80 * p;
  } else if (t < 0.5) {
      // 0.25 -> 0.5
      const p = (t - 0.25) / 0.25;
      r = 64 + (180 - 64) * p;
      g = 15 + (50 - 15) * p;
      b = 80 + (60 - 80) * p;
  } else if (t < 0.75) {
      // 0.5 -> 0.75
      const p = (t - 0.5) / 0.25;
      r = 180 + (250 - 180) * p;
      g = 50 + (150 - 50) * p;
      b = 60 + (40 - 60) * p;
  } else {
      // 0.75 -> 1.0
      const p = (t - 0.75) / 0.25;
      r = 250 + (255 - 250) * p;
      g = 150 + (255 - 150) * p;
      b = 40 + (220 - 40) * p;
  }

  return `rgb(${Math.floor(r)}, ${Math.floor(g)}, ${Math.floor(b)})`;
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
  <div className="flex flex-col rounded-lg border border-slate-800 bg-[rgba(15,23,42,0.5)] p-4 shadow-sm transition-all hover:border-[rgba(16,185,129,0.3)]">
    <div className="mb-3 flex items-center justify-between">
      <h3 className="text-sm font-bold uppercase tracking-wide text-slate-300">
        {title}
      </h3>
    </div>
    <div className="h-40 w-full relative mb-2">{children}</div>
    <div className="flex justify-end">
      <button
        onClick={onExpand}
        className="text-[10px] uppercase font-bold text-emerald-500 hover:text-emerald-400"
      >
        Expand
      </button>
    </div>
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[rgba(0,0,0,0.8)] p-4 backdrop-blur-sm">
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

// 4. Spectrogram (Interactive)
const SpectrogramCanvas = ({
    data,
    duration,
    expanded
}: {
    data: SpectrogramData;
    duration: number;
    expanded?: boolean;
}) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const [hoverInfo, setHoverInfo] = useState<{ x: number, y: number, time: number, freq: number, db: number } | null>(null);

    // Draw the spectrogram
    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas || !data || !data.data.length) return;

        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        // Resize canvas to match container explicitly for crisp rendering
        // or rely on CSS. Let's use internal resolution.
        const width = expanded ? 800 : 300;
        const height = expanded ? 400 : 150;

        // Ensure canvas element dimensions match
        if (canvas.width !== width || canvas.height !== height) {
             canvas.width = width;
             canvas.height = height;
        }

        const numTimeSteps = data.data.length;
        const numFreqBins = data.data[0].length;
        const cellW = width / numTimeSteps;
        const cellH = height / numFreqBins;

        ctx.clearRect(0,0,width,height);

        // Find min/max for normalization approx
        // We assume approx -80dB to 0dB range for display normalization
        const minDb = -80;
        const maxDb = 0;

        for (let i = 0; i < numTimeSteps; i++) {
            for (let j = 0; j < numFreqBins; j++) {
                const val = data.data[i][j];
                const norm = Math.max(0, Math.min(1, (val - minDb) / (maxDb - minDb)));

                ctx.fillStyle = getMagmaColor(norm);

                // j=0 is lowest freq (bottom), j=max is highest.
                // In canvas 0,0 is top-left.
                // So lowest freq should be at h - cellH
                const y = height - (j + 1) * cellH;
                const x = i * cellW;

                // Draw slightly larger to avoid gaps
                ctx.fillRect(x, y, cellW + 0.5, cellH + 0.5);
            }
        }

    }, [data, expanded]);

    // Handle Interaction
    const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
        if (!containerRef.current || !data) return;
        const rect = containerRef.current.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        const width = rect.width;
        const height = rect.height;

        // Normalize
        const normX = Math.max(0, Math.min(1, x / width));
        const normY = Math.max(0, Math.min(1, 1 - (y / height))); // Flip Y for frequency

        // Find data indices
        const numTimeSteps = data.data.length;
        const numFreqBins = data.data[0].length;

        const timeIndex = Math.floor(normX * numTimeSteps);
        const freqIndex = Math.floor(normY * numFreqBins);

        if (timeIndex >= 0 && timeIndex < numTimeSteps && freqIndex >= 0 && freqIndex < numFreqBins) {
            const val = data.data[timeIndex][freqIndex];
            const time = normX * duration;
            // Map freq index to Hz (approx or use freqs array)
            const freq = data.freqs[freqIndex] || 0;

            setHoverInfo({ x, y, time, freq, db: val });
        }
    };

    const handleMouseLeave = () => {
        setHoverInfo(null);
    };

    return (
        <div
            ref={containerRef}
            className="relative w-full h-full cursor-crosshair group overflow-hidden"
            onMouseMove={handleMouseMove}
            onMouseLeave={handleMouseLeave}
        >
            <canvas
                ref={canvasRef}
                // Width/Height controlled by useEffect but set default here
                width={expanded ? 800 : 300}
                height={expanded ? 400 : 150}
                className="w-full h-full object-cover bg-black"
            />

            {/* Overlay Axes Labels (Minimal) */}
            <div className="absolute left-1 bottom-1 text-[10px] text-slate-400 bg-black/50 px-1 rounded pointer-events-none">
                 Time
            </div>
            <div className="absolute left-1 top-1 text-[10px] text-slate-400 bg-black/50 px-1 rounded pointer-events-none">
                 Freq
            </div>

            {/* Hover Tooltip & Crosshair */}
            {hoverInfo && (
                <>
                    {/* Crosshair Lines */}
                    <div className="absolute top-0 bottom-0 border-l border-white/50 pointer-events-none" style={{ left: hoverInfo.x }} />
                    <div className="absolute left-0 right-0 border-t border-white/50 pointer-events-none" style={{ top: hoverInfo.y }} />

                    {/* Tooltip */}
                    <div
                        className="absolute bg-slate-900/90 border border-slate-700 p-2 rounded shadow-lg text-xs text-white pointer-events-none z-10 whitespace-nowrap"
                        style={{
                            left: hoverInfo.x + 10 > containerRef.current!.offsetWidth - 100 ? hoverInfo.x - 110 : hoverInfo.x + 10,
                            top: hoverInfo.y + 10 > containerRef.current!.offsetHeight - 60 ? hoverInfo.y - 70 : hoverInfo.y + 10
                        }}
                    >
                        <div className="font-bold text-emerald-400">{formatTime(hoverInfo.time)}</div>
                        <div>{hoverInfo.freq >= 1000 ? (hoverInfo.freq/1000).toFixed(1) + ' kHz' : hoverInfo.freq.toFixed(0) + ' Hz'}</div>
                        <div className="text-slate-400">{hoverInfo.db.toFixed(1)} dB</div>
                    </div>
                </>
            )}
        </div>
    );
}

// 5. Vectorscope (Interactive Density Plot)
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
    const containerRef = useRef<HTMLDivElement>(null);
    const [mode, setMode] = useState<'result' | 'original'>('result');
    const [hoverInfo, setHoverInfo] = useState<{ x: number, y: number, L: number, R: number, density: number } | null>(null);

    const activeData = (mode === 'result' ? data : original) || data;

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas || !activeData) return;

        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        const size = activeData.length; // 64
        // Use higher res for drawing to look smooth
        const w = expanded ? 400 : 200;
        const h = expanded ? 400 : 200;

        if (canvas.width !== w || canvas.height !== h) {
            canvas.width = w;
            canvas.height = h;
        }

        ctx.clearRect(0, 0, w, h);

        // --- Draw Background Grid ---
        const cx = w/2;
        const cy = h/2;
        const maxR = w/2 - 2;

        ctx.strokeStyle = '#334155';
        ctx.lineWidth = 1;

        // Polar Circles
        [0.25, 0.5, 0.75, 1.0].forEach(r => {
            ctx.beginPath();
            ctx.arc(cx, cy, maxR * r, 0, Math.PI * 2);
            ctx.stroke();
        });

        // Diagonals (Mid/Side)
        ctx.beginPath();
        ctx.moveTo(0, h); ctx.lineTo(w, 0); // L=R (Mid)
        ctx.strokeStyle = '#475569'; // Slightly brighter
        ctx.stroke();

        ctx.beginPath();
        ctx.moveTo(0, 0); ctx.lineTo(w, h); // L=-R (Side)
        ctx.stroke();

        // Axes
        ctx.beginPath();
        ctx.moveTo(cx, 0); ctx.lineTo(cx, h); // Vertical
        ctx.moveTo(0, cy); ctx.lineTo(w, cy); // Horizontal
        ctx.strokeStyle = '#1e293b';
        ctx.stroke();

        // --- Draw Density Map ---
        const cellW = w / size;
        const cellH = h / size;

        for (let y = 0; y < size; y++) {
            for (let x = 0; x < size; x++) {
                const val = activeData[y][x]; // Normalized 0-1
                if (val < 0.001) continue;

                // Use Magma Color Map
                // Boost low values for visibility
                const boost = Math.pow(val, 0.5);
                ctx.fillStyle = getMagmaColor(boost);

                // y index 0 is R=-1 (bottom), y=63 is R=1 (top)
                // canvas 0 is top.
                const drawY = h - (y + 1) * cellH;
                const drawX = x * cellW;

                // Slightly overlap to avoid grid lines
                ctx.fillRect(drawX, drawY, cellW + 0.5, cellH + 0.5);
            }
        }

        // Clip circle overlay (make corners black/transparent to simulate circular scope)
        // optional, but looks pro. Let's just draw a border.
        ctx.strokeStyle = '#64748b';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(cx, cy, maxR, 0, Math.PI * 2);
        ctx.stroke();

    }, [activeData, expanded, mode]);

    const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
        if (!containerRef.current) return;
        const rect = containerRef.current.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;

        // Coordinates -1 to 1
        // x=0 -> L=-1, x=w -> L=1
        // y=0 -> R=1, y=h -> R=-1 (Note: Y is inverted in canvas vs plot)

        const w = rect.width;
        const h = rect.height;

        const L = (mouseX / w) * 2 - 1;
        const R = ((h - mouseY) / h) * 2 - 1;

        // Lookup density
        // Map L,R back to 0..63 indices
        const size = activeData.length;
        // L = (idx / size)*2 - 1  => idx = (L+1)/2 * size
        const idxX = Math.floor((L + 1) / 2 * size);
        const idxY = Math.floor((R + 1) / 2 * size);

        let density = 0;
        if (idxX >= 0 && idxX < size && idxY >= 0 && idxY < size) {
             density = activeData[idxY][idxX];
        }

        setHoverInfo({ x: mouseX, y: mouseY, L, R, density });
    };

    return (
        <div className="w-full h-full flex flex-col items-center justify-center relative">
            <div
                ref={containerRef}
                className="relative cursor-crosshair group rounded-full overflow-hidden shadow-2xl bg-black border border-slate-800"
                style={{ width: expanded ? 400 : 200, height: expanded ? 400 : 200 }}
                onMouseMove={handleMouseMove}
                onMouseLeave={() => setHoverInfo(null)}
            >
                <canvas
                    ref={canvasRef}
                    className="w-full h-full"
                />

                {/* Crosshair */}
                {hoverInfo && (
                    <>
                         <div className="absolute top-0 bottom-0 border-l border-white/30 pointer-events-none" style={{ left: hoverInfo.x }} />
                         <div className="absolute left-0 right-0 border-t border-white/30 pointer-events-none" style={{ top: hoverInfo.y }} />

                         {/* Tooltip (Fixed position or floating) */}
                         <div className="absolute top-2 left-2 bg-black/80 text-[10px] text-white p-1 rounded border border-slate-700 pointer-events-none">
                            <div>L: {hoverInfo.L.toFixed(2)}</div>
                            <div>R: {hoverInfo.R.toFixed(2)}</div>
                            {/* Calculate M/S roughly */}
                            <div className="text-slate-400 mt-1">
                                M: {((hoverInfo.L + hoverInfo.R)/2).toFixed(2)}
                            </div>
                            <div className="text-slate-400">
                                S: {((hoverInfo.L - hoverInfo.R)/2).toFixed(2)}
                            </div>
                         </div>
                    </>
                )}
            </div>

            {expanded && original && (
                <div className="absolute top-4 right-4 flex space-x-2 z-10">
                     <button
                        onClick={() => setMode('result')}
                        className={`px-2 py-1 text-xs rounded border border-transparent ${mode==='result' ? 'bg-emerald-600 text-white shadow' : 'bg-slate-800 text-slate-400 hover:border-slate-600'}`}
                     >
                        Result
                     </button>
                     <button
                        onClick={() => setMode('original')}
                        className={`px-2 py-1 text-xs rounded border border-transparent ${mode==='original' ? 'bg-slate-600 text-white shadow' : 'bg-slate-800 text-slate-400 hover:border-slate-600'}`}
                     >
                        Original
                     </button>
                </div>
            )}

            <div className="absolute bottom-1 w-full flex justify-between px-8 text-[10px] text-slate-500 font-mono pointer-events-none">
                <span>-S</span>
                <span>M</span>
                <span>+S</span>
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

  // Determine total duration for Spectrogram X-Axis mapping
  // Use Loudness time axis as reference
  const duration = result.loudness?.time?.length
    ? result.loudness.time[result.loudness.time.length - 1]
    : 100; // default fallback

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
        component: <SpectrogramCanvas data={result.spectrogram!} duration={duration} />,
        expandedComponent: <SpectrogramCanvas data={result.spectrogram!} duration={duration} expanded />,
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
        <div className="w-full h-full p-4 bg-slate-900 flex items-center justify-center">
           {activeModal?.expandedComponent}
        </div>
      </Modal>
    </div>
  );
};
