import { HeroSection } from "./HeroSection";
import { LandingSectionsClient } from "./LandingSectionsClient";

export function LandingPage() {
  return (
    <div className="flex-1 flex flex-col bg-slate-950">
      <HeroSection />
      <LandingSectionsClient />
    </div>
  );
}
