"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import {
  DocumentArrowUpIcon,
  WrenchScrewdriverIcon,
  ArrowsRightLeftIcon,
  AdjustmentsHorizontalIcon,
  FunnelIcon,
  SpeakerWaveIcon,
  CubeTransparentIcon,
  ChartBarIcon,
  PaintBrushIcon,
  TrophyIcon,
  ClipboardDocumentCheckIcon,
  DocumentChartBarIcon,
  ChevronRightIcon,
  FlagIcon,
  InformationCircleIcon
} from "@heroicons/react/24/outline";

const STAGES = [
  { id: "s0", icon: DocumentArrowUpIcon, color: "text-slate-400" },
  { id: "s1", icon: WrenchScrewdriverIcon, color: "text-cyan-400" },
  { id: "s2", icon: ArrowsRightLeftIcon, color: "text-indigo-400" },
  { id: "s3", icon: AdjustmentsHorizontalIcon, color: "text-blue-400" },
  { id: "s4", icon: FunnelIcon, color: "text-teal-400" },
  { id: "s5", icon: SpeakerWaveIcon, color: "text-orange-400" },
  { id: "s6", icon: CubeTransparentIcon, color: "text-purple-400" },
  { id: "s7", icon: ChartBarIcon, color: "text-pink-400" },
  { id: "s8", icon: PaintBrushIcon, color: "text-rose-400" },
  { id: "s9", icon: TrophyIcon, color: "text-amber-400" },
  { id: "s10", icon: ClipboardDocumentCheckIcon, color: "text-emerald-400" },
  { id: "s11", icon: DocumentChartBarIcon, color: "text-slate-300" },
];

export default function PipelineViewer() {
  const t = useTranslations("Docs.pipeline");
  const [activeStage, setActiveStage] = useState(0);

  const activeData = STAGES[activeStage];
  const ActiveIcon = activeData.icon;

  const renderPoints = (points: any) => {
    if (!points) return null;
    return (
      <ul className="list-disc pl-5 mt-2 space-y-1 text-slate-400 text-sm">
        {Object.values(points).map((point: any, i: number) => (
          <li key={i} dangerouslySetInnerHTML={{ __html: point }} />
        ))}
      </ul>
    );
  };

  return (
    <div className="w-full grid grid-cols-1 lg:grid-cols-12 gap-6">
      {/* List Column */}
      <div className="lg:col-span-5 space-y-2">
        {STAGES.map((stage, index) => {
          const isActive = index === activeStage;
          const StageIcon = stage.icon;
          return (
            <button
              key={stage.id}
              onClick={() => setActiveStage(index)}
              className={`w-full text-left group flex items-center gap-4 p-3 rounded-lg border transition-all duration-200 ${
                isActive
                  ? "bg-emerald-900/10 border-emerald-500/50 shadow-[0_0_15px_-3px_rgba(16,185,129,0.2)]"
                  : "bg-slate-900/50 border-slate-800 hover:bg-slate-800 hover:border-slate-700"
              }`}
            >
              <div
                className={`flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center border transition-colors ${
                  isActive
                    ? "bg-slate-900 border-emerald-500 text-emerald-400"
                    : "bg-slate-800 border-slate-700 text-slate-400 group-hover:border-emerald-500/50 group-hover:text-emerald-400"
                }`}
              >
                <StageIcon className="w-5 h-5" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex justify-between items-center">
                  <span
                    className={`font-bold text-sm truncate ${
                      isActive ? "text-white" : "text-slate-300 group-hover:text-white"
                    }`}
                  >
                    {t(`${stage.id}.title`)}
                  </span>
                  <ChevronRightIcon
                    className={`w-4 h-4 transition-all ${
                      isActive
                        ? "text-emerald-500 opacity-100"
                        : "text-slate-600 opacity-0 group-hover:opacity-100 -translate-x-2 group-hover:translate-x-0"
                    }`}
                  />
                </div>
                <div className="text-xs text-slate-500 truncate mt-0.5">
                  {t(`${stage.id}.goal`)}
                </div>
              </div>
            </button>
          );
        })}
      </div>

      {/* Detail Column */}
      <div className="lg:col-span-7">
        <div className="sticky top-24 bg-slate-900/80 backdrop-blur-md border border-slate-800 rounded-2xl p-6 lg:p-8 shadow-2xl animate-in fade-in slide-in-from-right-4 duration-300 key={activeStage}">
          {/* Header */}
          <div className="flex items-start gap-5 mb-8 border-b border-slate-800/60 pb-6">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center shadow-lg shadow-emerald-500/20 text-white shrink-0">
              <ActiveIcon className="w-8 h-8" />
            </div>
            <div>
              <div className="text-emerald-500 font-bold text-xs tracking-[0.2em] uppercase mb-2">
                Stage {activeStage}
              </div>
              <h3 className="text-2xl lg:text-3xl font-bold text-white leading-tight">
                {t(`${activeData.id}.title`)}
              </h3>
            </div>
          </div>

          <div className="space-y-8">
            {/* Goal Section */}
            <div>
              <h4 className="text-xs font-bold text-teal-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                <FlagIcon className="w-4 h-4" />
                Goal
              </h4>
              <p className="text-slate-200 text-lg leading-relaxed">
                {t(`${activeData.id}.goal`)}
              </p>
            </div>

            {/* Details Section */}
            <div className="bg-slate-950/50 rounded-xl p-6 border border-slate-800/50">
              <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-4 flex items-center gap-2">
                <InformationCircleIcon className="w-4 h-4" />
                Technical Details
              </h4>
              <div className="text-slate-400 text-sm leading-7 space-y-4">
                <p>{t(`${activeData.id}.desc`)}</p>
                {/* Render points if they exist */}
                {(() => {
                  try {
                    const points = t.raw(`${activeData.id}.points`);
                    if (Array.isArray(points) || typeof points === "object") {
                      return renderPoints(points);
                    }
                  } catch (e) {
                    // Ignore missing points
                  }
                  return null;
                })()}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
