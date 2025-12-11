import { HeroSection } from "./HeroSection";
import { FeaturesSection } from "./FeaturesSection";
import { BenefitsSection } from "./BenefitsSection";
import { TechSpecsSection } from "./TechSpecsSection";
import Link from "next/link";

export function LandingPage({ onTryIt }: { onTryIt: () => void }) {
  return (
    <div className="flex-1 flex flex-col bg-slate-950">
      <HeroSection onTryIt={onTryIt} />
      <FeaturesSection />
      <BenefitsSection />
      <TechSpecsSection />

      {/* Bottom CTA */}
      <section className="py-24 bg-gradient-to-t from-teal-900/20 to-slate-950 text-center px-4">
        <h2 className="text-3xl md:text-5xl font-bold text-white mb-8">
          Ready to elevate your sound?
        </h2>
        <button
          onClick={onTryIt}
          className="bg-white text-slate-950 px-10 py-4 rounded-full text-lg font-bold hover:bg-teal-50 transition shadow-xl shadow-teal-500/10"
        >
          Start Mixing for Free
        </button>
      </section>

      {/* Footer */}
      <footer className="bg-slate-950 border-t border-slate-800 py-12 px-4">
          <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-center gap-8 text-slate-400 text-sm">
              <div className="flex items-center gap-2">
                 <img src="/logo.png" alt="Piroola Logo" className="h-6 w-6" />
                 <span className="font-semibold text-slate-200">Piroola</span>
              </div>
              <div className="flex gap-6">
                <Link href="/terms-of-service" className="hover:text-white transition">Terms</Link>
                <Link href="/privacy-policy" className="hover:text-white transition">Privacy</Link>
                <Link href="/cookie-policy" className="hover:text-white transition">Cookies</Link>
                <Link href="/contact" className="hover:text-white transition">Contact</Link>
              </div>
              <div>
                  © 2025 Piroola.
              </div>
          </div>
      </footer>
    </div>
  );
}
