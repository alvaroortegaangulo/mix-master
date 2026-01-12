"use client";

import dynamic from "next/dynamic";
import { useTranslations } from "next-intl";
import { ScrollReveal } from "./ScrollReveal";
import { ViewportMount } from "./ViewportMount";
import { Link } from "../../i18n/routing";

// Componentes dinámicos
const PipelineInteractiveDiagram = dynamic(
  () => import("./PipelineInteractiveDiagram").then((mod) => mod.PipelineInteractiveDiagram),
  { loading: () => <div className="h-96 bg-slate-900 animate-pulse" /> }
);

const ListenDifferenceSection = dynamic(
  () => import("./ListenDifferenceSection").then((mod) => mod.ListenDifferenceSection),
  { loading: () => <div className="h-80 bg-slate-950 animate-pulse" /> }
);

const FeaturesSection = dynamic(
  () => import("./FeaturesSection").then((mod) => mod.FeaturesSection),
  { loading: () => <div className="h-96 bg-slate-900 animate-pulse" /> }
);

const LiveSoundAnalysis = dynamic(
  () => import("./LiveSoundAnalysis").then((mod) => mod.LiveSoundAnalysis),
  { loading: () => <div className="h-96 bg-slate-950 animate-pulse" /> }
);

const BenefitsSection = dynamic(
  () => import("./BenefitsSection").then((mod) => mod.BenefitsSection),
  { loading: () => <div className="h-96 bg-slate-900 animate-pulse" /> }
);

const TechSpecsSection = dynamic(
  () => import("./TechSpecsSection").then((mod) => mod.TechSpecsSection),
  { loading: () => <div className="h-96 bg-slate-950 animate-pulse" /> }
);

// Helper para precargar
const preloadSection = (section: any) => {
  if (section && typeof section.preload === "function") {
    section.preload();
  }
};

export function LandingSectionsClient() {
  const t = useTranslations("LandingPage");
  const readyToElevate = t("readyToElevate");
  
  const viewportDefaults = {
    rootMargin: "200px 0px",
    prefetchMargin: "500px 0px",
    animateOnMount: false,
  };

  return (
    <>
      {/* 2. Listen Difference: Fade Up */}
      <ViewportMount
        {...viewportDefaults}
        className="bg-slate-950 min-h-[700px]"
        preload={() => preloadSection(ListenDifferenceSection)}
      >
        <ScrollReveal direction="up" duration={0.8} className="w-full">
          <ListenDifferenceSection className="bg-slate-950" />
        </ScrollReveal>
      </ViewportMount>

      {/* 3. Pipeline: Fade Up con ligero delay */}
      <ViewportMount
        {...viewportDefaults}
        className="bg-slate-900 min-h-[400px] lg:min-h-screen"
        preload={() => preloadSection(PipelineInteractiveDiagram)}
      >
        <ScrollReveal direction="up" delay={0.1} className="w-full">
          <PipelineInteractiveDiagram className="bg-gradient-to-b from-black via-purple-900/40 to-black section-blend blend-next-slate-950" />
        </ScrollReveal>
      </ViewportMount>

      {/* 4. Live Analysis: Aparece desde la derecha (efecto sutil) */}
      <ViewportMount
        {...viewportDefaults}
        className="bg-slate-950 min-h-[500px] lg:min-h-screen"
        preload={() => preloadSection(LiveSoundAnalysis)}
      >
        <ScrollReveal direction="right" x={50} duration={0.9} className="w-full">
          <LiveSoundAnalysis className="bg-slate-950" />
        </ScrollReveal>
      </ViewportMount>

      {/* 5. Features: Fade Up clásico */}
      <ViewportMount
        {...viewportDefaults}
        className="bg-slate-900 min-h-screen"
        preload={() => preloadSection(FeaturesSection)}
      >
        <ScrollReveal direction="up" className="w-full">
          <FeaturesSection className="bg-slate-900" />
        </ScrollReveal>
      </ViewportMount>

      {/* 6. Tech Specs: Aparece desde la izquierda */}
      <ViewportMount
        {...viewportDefaults}
        className="bg-slate-950 min-h-[520px]"
        preload={() => preloadSection(TechSpecsSection)}
      >
        <ScrollReveal direction="left" x={50} className="w-full">
          <TechSpecsSection className="bg-slate-950" />
        </ScrollReveal>
      </ViewportMount>

      {/* 7. Benefits: Fade Up */}
      <ViewportMount
        {...viewportDefaults}
        className="bg-slate-900 min-h-[500px] lg:min-h-screen"
        preload={() => preloadSection(BenefitsSection)}
      >
        <ScrollReveal direction="up" className="w-full">
          <BenefitsSection className="bg-slate-900" />
        </ScrollReveal>
      </ViewportMount>

      {/* Bottom CTA: Elementos individuales (Ya estaba configurado, se mantiene optimizado) */}
      <ViewportMount {...viewportDefaults} className="bg-slate-950 min-h-[260px]">
        <section className="relative py-10 md:py-14 lg:py-16 2xl:py-20 bg-slate-950 text-center px-4 overflow-hidden">
          <div className="absolute top-0 left-0 h-full w-full overflow-hidden pointer-events-none z-0">
            <div className="absolute -top-[20%] -left-[10%] h-[50%] w-[50%] rounded-full bg-teal-500/10 blur-[120px]" />
            <div className="absolute top-[40%] -right-[10%] h-[60%] w-[60%] rounded-full bg-violet-600/10 blur-[120px]" />
          </div>
          
          <div className="relative z-10 flex flex-col items-center gap-6">
            <ScrollReveal direction="up" delay={0.1}>
              <h2
                className="text-xl sm:text-2xl lg:text-3xl 2xl:text-4xl font-bold text-white mb-2 font-['Orbitron'] metallic-sheen"
                data-text={readyToElevate}
              >
                {readyToElevate}
              </h2>
            </ScrollReveal>
            
            <ScrollReveal direction="up" delay={0.3}>
              <Link
                href="/mix"
                className="inline-flex items-center justify-center bg-white text-slate-950 px-8 py-3 rounded-full text-base sm:text-lg font-bold hover:bg-teal-50 hover:scale-105 transition-all duration-300 shadow-xl shadow-teal-500/20"
              >
                {t("startMixing")}
              </Link>
            </ScrollReveal>
          </div>
        </section>
      </ViewportMount>
    </>
  );
}