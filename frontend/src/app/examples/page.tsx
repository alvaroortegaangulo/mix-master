import type { Metadata } from "next";
import Link from "next/link";
import Script from "next/script";

const fallbackSiteUrl = "https://music-mix-master.com";
const siteUrl = (() => {
  const envUrl = process.env.NEXT_PUBLIC_SITE_URL?.trim();
  if (!envUrl) return fallbackSiteUrl;
  try {
    return new URL(envUrl).origin;
  } catch {
    return fallbackSiteUrl;
  }
})();

export const metadata: Metadata = {
  title: "Examples | Piroola",
  description: "Listen to sample outcomes from Piroola: vocal polish, wide pop mixes, punchy hip-hop, and clean acoustic masters.",
  alternates: {
    canonical: "/examples",
  },
};

const EXAMPLES = [
  {
    title: "Modern Pop Vocal",
    genre: "Pop / Top 40",
    summary: "Bright, upfront vocals with de-essing, airy reverb, and tight low-end control for chart-ready polish.",
    highlights: ["Lead vocal leveling", "De-essing and air EQ", "Stereo widener on choruses"],
    metrics: ["LUFS: -8.9 → -8.0", "True Peak: -2.0 dB → -1.0 dB", "Vocal sibilance reduced ~2 dB"],
  },
  {
    title: "Punchy Hip-Hop",
    genre: "Hip-Hop / Trap",
    summary: "Low-end glued with parallel compression while keeping 808s clean and transients snappy on the snare.",
    highlights: ["808 clarity and sub control", "Transient shaping on snare/clap", "Bus saturation for glue"],
    metrics: ["LUFS: -10.5 → -9.2", "Stereo width: +12%", "Noise floor cleaned 3 dB"],
  },
  {
    title: "Indie Band",
    genre: "Indie / Rock",
    summary: "Phase-aligned drums, guitars separated with mid/side EQ, and a cohesive master with analog-style color.",
    highlights: ["Drum phase alignment", "Mid/side guitar EQ", "Tape-like saturation on mixbus"],
    metrics: ["LUFS: -12.0 → -10.8", "Crest Factor: 11 dB → 9 dB", "Stereo image balanced L/R <0.5 dB"],
  },
  {
    title: "Cinematic Ambient",
    genre: "Score / Ambient",
    summary: "Wide, enveloping space with controlled low-mid build-up, keeping pads lush without mud.",
    highlights: ["Low-mid resonance control", "Layered reverbs with pre-delay", "Gentle multiband glue"],
    metrics: ["LUFS: -16.0 → -14.5", "Reverb RT60 tamed 12%", "Sub rumble cut below 30 Hz"],
  },
];

const breadcrumbsJsonLd = {
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  itemListElement: [
    {
      "@type": "ListItem",
      position: 1,
      name: "Home",
      item: `${siteUrl}/`,
    },
    {
      "@type": "ListItem",
      position: 2,
      name: "Examples",
      item: `${siteUrl}/examples`,
    },
  ],
};

export default function ExamplesPage() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      <header className="border-b border-slate-800/80 sticky top-0 bg-slate-950/90 backdrop-blur z-20">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4">
          <div className="flex items-center gap-2">
            <div className="h-7 w-7 rounded-full bg-teal-400/90 flex items-center justify-center text-slate-950 text-lg font-bold" aria-hidden="true">
              A
            </div>
            <Link href="/" className="text-lg font-semibold tracking-tight text-slate-100 hover:text-teal-300 transition">
              Piroola
            </Link>
          </div>
          <nav className="hidden md:flex items-center gap-5 text-sm">
            <Link href="/pricing" className="hover:text-teal-300 transition">Pricing</Link>
            <Link href="/docs" className="hover:text-teal-300 transition">How it works</Link>
            <Link href="/support" className="hover:text-teal-300 transition">Support</Link>
          </nav>
        </div>
      </header>

      <main className="flex-1 px-4 py-12">
        <div className="mx-auto max-w-5xl">
          <div className="flex flex-col gap-4 mb-10 text-center">
            <p className="text-xs uppercase tracking-[0.2em] text-teal-300/80">Examples</p>
            <h1 className="text-4xl font-bold tracking-tight text-slate-50">Hear what Piroola delivers</h1>
            <p className="text-lg text-slate-400 max-w-3xl mx-auto">
              Representative mixes and masters that show how our AI pipeline cleans, balances, and enhances different genres.
              Each example highlights the processing moves you can expect on your own tracks.
            </p>
            <div className="flex flex-wrap gap-3 justify-center">
              <Link href="/pricing" className="rounded-full bg-teal-400 text-slate-950 px-4 py-2 text-sm font-semibold shadow-md shadow-teal-500/30 hover:bg-teal-300 transition">
                View pricing
              </Link>
              <Link href="/docs" className="rounded-full border border-slate-800 px-4 py-2 text-sm font-semibold text-slate-100 hover:border-teal-400 hover:text-teal-300 transition">
                How it works
              </Link>
            </div>
          </div>

          <div className="grid gap-6 sm:grid-cols-2">
            {EXAMPLES.map((example) => (
              <article key={example.title} className="rounded-2xl border border-slate-800/70 bg-slate-900/40 p-6 shadow-lg shadow-slate-900/60">
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <p className="text-xs uppercase tracking-wide text-teal-300/80">{example.genre}</p>
                    <h2 className="text-xl font-semibold text-slate-100">{example.title}</h2>
                  </div>
                  <span aria-hidden="true" className="text-slate-500 text-lg">↗</span>
                </div>
                <p className="text-sm text-slate-400 mb-4">{example.summary}</p>
                <div className="flex flex-wrap gap-2 mb-4">
                  {example.highlights.map((item) => (
                    <span key={item} className="rounded-full border border-slate-800 bg-slate-900/70 px-3 py-1 text-xs text-slate-200">
                      {item}
                    </span>
                  ))}
                </div>
                <div className="rounded-xl border border-slate-800/70 bg-slate-950/50 p-4">
                  <p className="text-xs uppercase tracking-[0.12em] text-slate-400 mb-2">Notable changes</p>
                  <ul className="space-y-2 text-sm text-slate-300 list-disc list-inside">
                    {example.metrics.map((metric) => (
                      <li key={metric}>{metric}</li>
                    ))}
                  </ul>
                </div>
              </article>
            ))}
          </div>

          <div className="mt-12 rounded-2xl border border-teal-500/40 bg-teal-500/10 p-8 text-center shadow-lg shadow-teal-500/20">
            <h3 className="text-2xl font-semibold text-teal-200 mb-3">Ready to hear your own track at this quality?</h3>
            <p className="text-slate-200 mb-6">Upload stems, pick a space, and let the AI mix and master in minutes.</p>
            <div className="flex justify-center gap-3">
              <Link href="/" className="rounded-full bg-teal-400 text-slate-950 px-4 py-2 text-sm font-semibold shadow-md shadow-teal-500/30 hover:bg-teal-300 transition">
                Start mixing
              </Link>
              <Link href="/support" className="rounded-full border border-teal-500/70 px-4 py-2 text-sm font-semibold text-teal-100 hover:bg-teal-500/10 transition">
                Talk to support
              </Link>
            </div>
          </div>
        </div>
      </main>

      <footer className="border-t border-slate-800/80 py-6 text-center text-xs text-slate-500 bg-slate-950">
        <p>© 2025 Piroola. All rights reserved.</p>
      </footer>

      <Script
        id="ld-breadcrumbs-examples"
        type="application/ld+json"
        strategy="afterInteractive"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbsJsonLd) }}
      />
    </div>
  );
}
