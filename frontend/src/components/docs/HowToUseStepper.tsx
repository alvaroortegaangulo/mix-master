"use client";

import { useState } from "react";
import Image from "next/image";
import { useTranslations } from "next-intl";
import {
  CloudArrowUpIcon,
  AdjustmentsVerticalIcon,
  CpuChipIcon,
  SpeakerWaveIcon,
  SparklesIcon
} from "@heroicons/react/24/outline";

const STEPS = [
  { id: "step1", icon: CloudArrowUpIcon, image: "/docs/how-to-use/upload_dropzone.webp", width: 832, height: 514 },
  { id: "step2", icon: AdjustmentsVerticalIcon, image: "/docs/how-to-use/stems_profile.webp", width: 358, height: 514 },
  { id: "step3", icon: CpuChipIcon, image: "/docs/how-to-use/pipeline_steps.webp", width: 736, height: 445 },
  { id: "step4", icon: SpeakerWaveIcon, image: "/docs/how-to-use/space_depth.webp", width: 355, height: 480 },
  { id: "step5", icon: SparklesIcon, image: null, width: 0, height: 0 },
];

export default function HowToUseStepper() {
  const t = useTranslations("Docs.howToUse");
  const [activeStep, setActiveStep] = useState(0);

  const activeData = STEPS[activeStep];
  const ActiveIcon = activeData.icon;

  return (
    <div className="w-full">
      {/* Tabs */}
      <div className="flex flex-wrap gap-2 mb-8 border-b border-slate-800 pb-1">
        {STEPS.map((step, index) => {
          const isActive = index === activeStep;
          return (
            <button
              key={step.id}
              onClick={() => setActiveStep(index)}
              className={`relative px-4 py-3 text-sm font-medium transition-all rounded-t-lg flex items-center gap-2 ${
                isActive
                  ? "text-teal-400 bg-slate-900 border-b-2 border-teal-400"
                  : "text-slate-500 hover:text-slate-300 hover:bg-slate-900/50"
              }`}
            >
              <span className={`flex items-center justify-center w-5 h-5 rounded-full text-xs font-bold ${
                 isActive ? "bg-teal-500 text-slate-950" : "bg-slate-800 text-slate-400"
              }`}>
                {index + 1}
              </span>
              <span className="hidden sm:inline">{t(`${step.id}.title`).split(":")[1] || t(`${step.id}.title`)}</span>
            </button>
          );
        })}
      </div>

      {/* Content */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center min-h-[400px]">
        <div className="order-2 lg:order-1 space-y-6">
           <div className="w-12 h-12 rounded-xl bg-slate-800 flex items-center justify-center text-teal-400 mb-4">
             <ActiveIcon className="w-6 h-6" />
           </div>
           <h3 className="text-2xl font-bold text-white">
             {t(`${activeData.id}.title`)}
           </h3>
           <div className="prose prose-invert prose-p:text-slate-300 prose-p:leading-relaxed">
             <p dangerouslySetInnerHTML={{ __html: t.raw(`${activeData.id}.desc`) }} />
           </div>
        </div>

        <div className="order-1 lg:order-2 flex justify-center">
            {activeData.image ? (
                <div className="relative group rounded-xl overflow-hidden border border-slate-800 bg-slate-950/50 shadow-2xl">
                    <div className="absolute inset-0 bg-gradient-to-t from-slate-950 via-transparent to-transparent opacity-0 group-hover:opacity-40 transition-opacity z-10" />
                    <Image
                        src={activeData.image}
                        alt="Step Screenshot"
                        width={activeData.width}
                        height={activeData.height}
                        className="max-h-[400px] w-auto object-contain"
                    />
                </div>
            ) : (
                <div className="flex flex-col items-center justify-center h-64 w-full bg-slate-900/30 rounded-xl border border-dashed border-slate-800 text-slate-500">
                    <SparklesIcon className="w-12 h-12 mb-4 opacity-50" />
                    <span className="text-sm">Processing in progress...</span>
                </div>
            )}
        </div>
      </div>
    </div>
  );
}
