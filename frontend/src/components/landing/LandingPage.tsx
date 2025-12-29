"use client";

import { HeroSection } from "./HeroSection";
import dynamic from "next/dynamic";
import { useTranslations } from 'next-intl';
import { useHomeView } from "../../context/HomeViewContext";
import { ElectricDivider } from "./ElectricDivider";

const PipelineInteractiveDiagram = dynamic(() => import("./PipelineInteractiveDiagram").then(mod => mod.PipelineInteractiveDiagram), {
  loading: () => <div className="h-96 bg-slate-900" />
});

const FeaturesSection = dynamic(() => import("./FeaturesSection").then(mod => mod.FeaturesSection), {
  loading: () => <div className="h-96 bg-slate-900" />
});
const LiveSoundAnalysis = dynamic(() => import("./LiveSoundAnalysis").then(mod => mod.LiveSoundAnalysis), {
  loading: () => <div className="h-96 bg-slate-950" />
});
const BenefitsSection = dynamic(() => import("./BenefitsSection").then(mod => mod.BenefitsSection), {
  loading: () => <div className="h-96 bg-slate-900" />
});
const TechSpecsSection = dynamic(() => import("./TechSpecsSection").then(mod => mod.TechSpecsSection), {
  loading: () => <div className="h-96 bg-slate-950" />
});

export function LandingPage() {
  // Alternating pattern: Dark (Hero) -> Light -> Dark -> Light -> Dark -> Light
  // "Light" in this dark theme context = bg-slate-900
  // "Dark" = bg-slate-950

  const t = useTranslations('LandingPage');
  const { handleTryIt } = useHomeView();

  return (
    <div className="flex-1 flex flex-col bg-slate-950">
      {/* 1. Hero: Dark (bg-slate-950) - Default */}
      <HeroSection onTryIt={handleTryIt} />

      <ElectricDivider />

      {/* 2. Pipeline: Light (bg-slate-900) */}
      <PipelineInteractiveDiagram className="bg-slate-900" />

      <ElectricDivider />

      {/* 3. Live Analysis: Dark (bg-slate-950) */}
      <LiveSoundAnalysis className="bg-slate-950" />

      <ElectricDivider />

      {/* 4. Features (DAW to World): Light (bg-slate-900) */}
      <FeaturesSection className="bg-slate-900" />

      <ElectricDivider />

      {/* 5. Tech Specs (Power & Precision): Dark (bg-slate-950) */}
      <TechSpecsSection className="bg-slate-950" />

      <ElectricDivider />

      {/* 6. Benefits (Hours in minutes): Light (bg-slate-900) */}
      <BenefitsSection className="bg-slate-900" />

      <ElectricDivider />

      {/* Bottom CTA */}
      <section className="py-10 md:py-14 lg:py-16 2xl:py-20 bg-gradient-to-t from-teal-900/20 to-slate-950 text-center px-4">
        <h2 className="text-xl sm:text-2xl lg:text-3xl 2xl:text-4xl font-bold text-white mb-5 font-['Orbitron']">
          {t('readyToElevate')}
        </h2>
        <button
          onClick={handleTryIt}
          className="bg-white text-slate-950 px-6 py-2.5 rounded-full text-sm sm:text-base font-bold hover:bg-teal-50 transition shadow-xl shadow-teal-500/10"
        >
          {t('startMixing')}
        </button>
      </section>

      {/* Footer removed from here, now in GlobalLayout */}
    </div>
  );
}
