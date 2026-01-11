"use client";

import { HeroSection } from "./HeroSection";
import dynamic from "next/dynamic";
import { useTranslations } from 'next-intl';
import { useHomeView } from "../../context/HomeViewContext";
import { ScrollReveal } from "./ScrollReveal";

const PipelineInteractiveDiagram = dynamic(() => import("./PipelineInteractiveDiagram").then(mod => mod.PipelineInteractiveDiagram), {
  loading: () => <div className="h-96 bg-slate-900" />
});

const ListenDifferenceSection = dynamic(() => import("./ListenDifferenceSection").then(mod => mod.ListenDifferenceSection), {
  loading: () => <div className="h-80 bg-slate-950" />
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
  // Alternating pattern: Dark (Hero) -> Highlight -> Light -> Dark -> Light -> Dark -> Light
  // "Light" in this dark theme context = bg-slate-900
  // "Dark" = bg-slate-950

  const t = useTranslations('LandingPage');
  const { handleTryIt } = useHomeView();
  const readyToElevate = t('readyToElevate');

  return (
    <div className="flex-1 flex flex-col bg-slate-950">
      {/* 1. Hero: Dark (bg-slate-950) - Default */}
      <HeroSection onTryIt={handleTryIt} />

      {/* 2. Listen Difference: Highlight (bg-slate-950) */}
      <ListenDifferenceSection className="bg-slate-950 section-blend blend-next-slate-900" />

      {/* 3. Pipeline: Light (bg-slate-900) */}
      <PipelineInteractiveDiagram className="bg-slate-900 section-blend blend-next-slate-950" />

      {/* 4. Live Analysis: Dark (bg-slate-950) */}
      <LiveSoundAnalysis className="bg-slate-950 section-blend blend-next-slate-900" />

      {/* 5. Features (DAW to World): Match Pipeline background */}
      <FeaturesSection className="bg-slate-900 section-blend blend-next-slate-950" />

      {/* 6. Tech Specs (Power & Precision): Dark (bg-slate-950) */}
      <TechSpecsSection className="bg-slate-950 section-blend blend-next-slate-900" />

      {/* 7. Benefits (Hours in minutes): Light (bg-slate-900) */}
      <BenefitsSection className="bg-slate-900 section-blend blend-next-slate-950" />

      {/* Bottom CTA */}
      <section className="relative py-10 md:py-14 lg:py-16 2xl:py-20 bg-slate-950 text-center px-4 overflow-hidden section-blend blend-next-slate-950">
        <div className="absolute top-0 left-0 h-full w-full overflow-hidden pointer-events-none z-0">
          <div className="absolute -top-[20%] -left-[10%] h-[50%] w-[50%] rounded-full bg-teal-500/10 blur-[120px]" />
          <div className="absolute top-[40%] -right-[10%] h-[60%] w-[60%] rounded-full bg-violet-600/10 blur-[120px]" />
        </div>
        <ScrollReveal className="relative z-10" delay={0.05}>
          <h2
            className="text-xl sm:text-2xl lg:text-3xl 2xl:text-4xl font-bold text-white mb-5 font-['Orbitron'] metallic-sheen"
            data-text={readyToElevate}
          >
            {readyToElevate}
          </h2>
          <button
            onClick={handleTryIt}
            className="bg-white text-slate-950 px-6 py-2.5 rounded-full text-sm sm:text-base font-bold hover:bg-teal-50 transition shadow-xl shadow-teal-500/10"
          >
            {t('startMixing')}
          </button>
        </ScrollReveal>
      </section>

      {/* Footer removed from here, now in GlobalLayout */}
    </div>
  );
}
