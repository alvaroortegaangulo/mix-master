import { HeroSection } from "./HeroSection";
import dynamic from "next/dynamic";
import { BottomTryItButton } from "./LandingButtons";

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

  return (
    <div className="flex-1 flex flex-col bg-slate-950">
      {/* 1. Hero: Dark (bg-slate-950) - Default */}
      <HeroSection />

      {/* 2. Features: Light (bg-slate-900) */}
      <FeaturesSection className="bg-slate-900" />

      {/* 3. Live Analysis: Dark (bg-slate-950) */}
      <LiveSoundAnalysis className="bg-slate-950" />

      {/* 4. Benefits: Light (bg-slate-900) */}
      <BenefitsSection className="bg-slate-900" />

      {/* 5. Tech Specs (Power & Precision): Dark (bg-slate-950) */}
      <TechSpecsSection className="bg-slate-950" />

      {/* 6. Pipeline: Light (bg-slate-900) */}
      <PipelineInteractiveDiagram className="bg-slate-900" />

      {/* Bottom CTA */}
      <section className="py-24 bg-gradient-to-t from-teal-900/20 to-slate-950 text-center px-4">
        <h2 className="text-3xl md:text-5xl font-bold text-white mb-8">
          Ready to elevate your sound?
        </h2>
        <BottomTryItButton />
      </section>

      {/* Footer removed from here, now in GlobalLayout */}
    </div>
  );
}
