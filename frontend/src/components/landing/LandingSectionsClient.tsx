"use client";

import dynamic from "next/dynamic";
import { useTranslations } from "next-intl";
import { ScrollReveal } from "./ScrollReveal";
import { ViewportMount } from "./ViewportMount";
import { Link } from "../../i18n/routing";

const PipelineInteractiveDiagram = dynamic(
  () => import("./PipelineInteractiveDiagram").then((mod) => mod.PipelineInteractiveDiagram),
  { loading: () => <div className="h-96 bg-slate-900" /> }
);

const ListenDifferenceSection = dynamic(
  () => import("./ListenDifferenceSection").then((mod) => mod.ListenDifferenceSection),
  { loading: () => <div className="h-80 bg-slate-950" /> }
);

const FeaturesSection = dynamic(
  () => import("./FeaturesSection").then((mod) => mod.FeaturesSection),
  { loading: () => <div className="h-96 bg-slate-900" /> }
);

const LiveSoundAnalysis = dynamic(
  () => import("./LiveSoundAnalysis").then((mod) => mod.LiveSoundAnalysis),
  { loading: () => <div className="h-96 bg-slate-950" /> }
);

const BenefitsSection = dynamic(
  () => import("./BenefitsSection").then((mod) => mod.BenefitsSection),
  { loading: () => <div className="h-96 bg-slate-900" /> }
);

const TechSpecsSection = dynamic(
  () => import("./TechSpecsSection").then((mod) => mod.TechSpecsSection),
  { loading: () => <div className="h-96 bg-slate-950" /> }
);

const preloadSection = (section: unknown) => {
  (section as { preload?: () => void })?.preload?.();
};

export function LandingSectionsClient() {
  const t = useTranslations("LandingPage");
  const readyToElevate = t("readyToElevate");

  return (
    <>
      {/* 2. Listen Difference: Highlight (bg-slate-950) */}
      <ViewportMount
        className="bg-slate-950 min-h-[700px]"
        preload={() => preloadSection(ListenDifferenceSection)}
      >
        <ListenDifferenceSection className="bg-slate-950" />
      </ViewportMount>

      {/* 3. Pipeline: Light (bg-slate-900) */}
      <ViewportMount
        className="bg-slate-900 min-h-[400px] lg:min-h-screen"
        preload={() => preloadSection(PipelineInteractiveDiagram)}
      >
        <PipelineInteractiveDiagram className="bg-gradient-to-b from-black via-purple-900/40 to-black section-blend blend-next-slate-950" />
      </ViewportMount>

      {/* 4. Live Analysis: Dark (bg-slate-950) */}
      <ViewportMount
        className="bg-slate-950 min-h-[500px] lg:min-h-screen"
        preload={() => preloadSection(LiveSoundAnalysis)}
      >
        <LiveSoundAnalysis className="bg-slate-950" />
      </ViewportMount>

      {/* 5. Features (DAW to World): Match Pipeline background */}
      <ViewportMount
        className="bg-slate-900 min-h-screen"
        preload={() => preloadSection(FeaturesSection)}
      >
        <FeaturesSection className="bg-slate-900" />
      </ViewportMount>

      {/* 6. Tech Specs (Power & Precision): Dark (bg-slate-950) */}
      <ViewportMount
        className="bg-slate-950 min-h-[520px]"
        preload={() => preloadSection(TechSpecsSection)}
      >
        <TechSpecsSection className="bg-slate-950" />
      </ViewportMount>

      {/* 7. Benefits (Hours in minutes): Light (bg-slate-900) */}
      <ViewportMount
        className="bg-slate-900 min-h-[500px] lg:min-h-screen"
        preload={() => preloadSection(BenefitsSection)}
      >
        <BenefitsSection className="bg-slate-900" />
      </ViewportMount>

      {/* Bottom CTA */}
      <ViewportMount className="bg-slate-950 min-h-[260px]">
        <section className="relative py-10 md:py-14 lg:py-16 2xl:py-20 bg-slate-950 text-center px-4 overflow-hidden">
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
            <Link
              href="/mix"
              className="inline-flex items-center justify-center bg-white text-slate-950 px-6 py-2.5 rounded-full text-sm sm:text-base font-bold hover:bg-teal-50 transition shadow-xl shadow-teal-500/10"
            >
              {t("startMixing")}
            </Link>
          </ScrollReveal>
        </section>
      </ViewportMount>
    </>
  );
}
