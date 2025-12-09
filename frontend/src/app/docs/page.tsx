import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Documentation & Guide",
  description: "Comprehensive guide to using Audio Alchemy, including detailed explanations of the mixing and mastering pipeline, stages, and results.",
  alternates: { canonical: "/docs" },
};

export default function DocsPage() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Header */}
      <header className="border-b border-slate-800/80 sticky top-0 bg-slate-950/90 backdrop-blur z-20">
        <div className="mx-auto flex h-16 max-w-7xl items-center px-4 justify-between">
          <div className="flex items-center gap-2">
            <Link href="/" className="flex items-center gap-2 no-underline text-inherit hover:opacity-80 transition">
              <div className="h-7 w-7 rounded-full bg-teal-400/90 flex items-center justify-center text-slate-950 text-lg font-bold">
                A
              </div>
              <span className="text-lg font-semibold tracking-tight">Audio Alchemy</span>
            </Link>
          </div>
          <div className="flex items-center gap-4">
            <Link href="/" className="text-sm font-medium text-teal-400 hover:text-teal-300">
              ← Back to App
            </Link>
          </div>
        </div>
      </header>

      <div className="flex flex-1 mx-auto max-w-7xl w-full">
        {/* Sidebar Navigation */}
        <aside className="hidden lg:block w-64 shrink-0 sticky top-16 h-[calc(100vh-4rem)] overflow-y-auto border-r border-slate-800/80 py-8 pr-4 custom-scrollbar">
          <nav className="flex flex-col gap-1 text-sm">
            <p className="px-2 mb-2 font-semibold text-teal-400 uppercase tracking-wider text-xs">Getting Started</p>
            <Link href="#introduction" className="px-2 py-1.5 rounded hover:bg-slate-900 text-slate-400 hover:text-slate-100 transition">Introduction</Link>
            <Link href="#how-to-use" className="px-2 py-1.5 rounded hover:bg-slate-900 text-slate-400 hover:text-slate-100 transition">How to Use</Link>
            <Link href="#features" className="px-2 py-1.5 rounded hover:bg-slate-900 text-slate-400 hover:text-slate-100 transition">Key Features</Link>

            <p className="px-2 mt-6 mb-2 font-semibold text-teal-400 uppercase tracking-wider text-xs">Pipeline Stages</p>
            <Link href="#pipeline-overview" className="px-2 py-1.5 rounded hover:bg-slate-900 text-slate-400 hover:text-slate-100 transition">Overview</Link>
            <Link href="#s0-input" className="px-2 py-1.5 rounded hover:bg-slate-900 text-slate-400 hover:text-slate-100 transition">S0: Input & Metadata</Link>
            <Link href="#s1-tech-prep" className="px-2 py-1.5 rounded hover:bg-slate-900 text-slate-400 hover:text-slate-100 transition">S1: Technical Prep</Link>
            <Link href="#s2-phase" className="px-2 py-1.5 rounded hover:bg-slate-900 text-slate-400 hover:text-slate-100 transition">S2: Phase Alignment</Link>
            <Link href="#s3-static-mix" className="px-2 py-1.5 rounded hover:bg-slate-900 text-slate-400 hover:text-slate-100 transition">S3: Static Mix</Link>
            <Link href="#s4-spectral" className="px-2 py-1.5 rounded hover:bg-slate-900 text-slate-400 hover:text-slate-100 transition">S4: Spectral Cleanup</Link>
            <Link href="#s5-dynamics" className="px-2 py-1.5 rounded hover:bg-slate-900 text-slate-400 hover:text-slate-100 transition">S5: Dynamics</Link>
            <Link href="#s6-space" className="px-2 py-1.5 rounded hover:bg-slate-900 text-slate-400 hover:text-slate-100 transition">S6: Space & Depth</Link>
            <Link href="#s7-tonal" className="px-2 py-1.5 rounded hover:bg-slate-900 text-slate-400 hover:text-slate-100 transition">S7: Tonal Balance</Link>
            <Link href="#s8-color" className="px-2 py-1.5 rounded hover:bg-slate-900 text-slate-400 hover:text-slate-100 transition">S8: Mix Bus Color</Link>
            <Link href="#s9-mastering" className="px-2 py-1.5 rounded hover:bg-slate-900 text-slate-400 hover:text-slate-100 transition">S9: Mastering</Link>
            <Link href="#s10-qc" className="px-2 py-1.5 rounded hover:bg-slate-900 text-slate-400 hover:text-slate-100 transition">S10: Quality Control</Link>
            <Link href="#s11-reporting" className="px-2 py-1.5 rounded hover:bg-slate-900 text-slate-400 hover:text-slate-100 transition">S11: Reporting</Link>

            <p className="px-2 mt-6 mb-2 font-semibold text-teal-400 uppercase tracking-wider text-xs">Results & Support</p>
            <Link href="#results" className="px-2 py-1.5 rounded hover:bg-slate-900 text-slate-400 hover:text-slate-100 transition">Understanding Results</Link>
            <Link href="#faq" className="px-2 py-1.5 rounded hover:bg-slate-900 text-slate-400 hover:text-slate-100 transition">FAQ & Troubleshooting</Link>
          </nav>
        </aside>

        {/* Main Content */}
        <main className="flex-1 py-12 px-4 lg:px-12 prose prose-invert prose-slate max-w-none">
          <section id="introduction" className="scroll-mt-24 mb-16">
            <h1 className="text-4xl font-bold mb-6 text-teal-400">Audio Alchemy Documentation</h1>
            <p className="text-xl text-slate-300 leading-relaxed">
              Welcome to the official guide for <strong>Audio Alchemy</strong>. This platform leverages advanced AI to provide professional mixing and mastering services directly in your browser. Whether you are a musician, producer, or audio engineer, Audio Alchemy streamlines the complex process of audio engineering into a few simple steps.
            </p>
            <p className="text-slate-400">
              Our pipeline analyzes your audio stems, corrects technical issues, balances levels, applies creative processing, and delivers a release-ready master. This guide covers everything from uploading your first track to understanding the detailed engineering report.
            </p>
          </section>

          <section id="how-to-use" className="scroll-mt-24 mb-16 border-t border-slate-800/50 pt-8">
            <h2 className="text-3xl font-semibold mb-6 text-slate-100">How to Use the Application</h2>

            <h3 className="text-xl font-medium text-teal-300 mt-8 mb-4">1. Uploading Stems</h3>
            <p className="text-slate-300">
              Start by dragging and dropping your audio files into the upload zone on the home page. We accept common audio formats like WAV, AIFF, and MP3. For best results, use high-quality WAV files (24-bit, 44.1kHz or higher).
            </p>
            <div className="my-6 p-4 border border-dashed border-slate-700 rounded-lg bg-slate-900/50 flex items-center justify-center text-slate-500 h-48">
              {/* Screenshot Placeholder */}
              <span className="italic">[Screenshot: Upload Dropzone with files]</span>
            </div>

            <h3 className="text-xl font-medium text-teal-300 mt-8 mb-4">2. Configuring Stem Profiles</h3>
            <p className="text-slate-300">
              Once uploaded, the system will attempt to automatically identify the instrument in each stem (e.g., "Kick", "Bass", "Vocals"). Review the <strong>Stem Profiles</strong> panel on the right. Correct any misidentified stems to ensure the AI applies the correct processing profile.
            </p>
            <div className="my-6 p-4 border border-dashed border-slate-700 rounded-lg bg-slate-900/50 flex items-center justify-center text-slate-500 h-48">
               {/* Screenshot Placeholder */}
               <span className="italic">[Screenshot: Stem Profiles Panel]</span>
            </div>

            <h3 className="text-xl font-medium text-teal-300 mt-8 mb-4">3. Selecting Pipeline Stages</h3>
            <p className="text-slate-300">
              The <strong>Pipeline Steps</strong> panel allows you to enable or disable specific parts of the processing chain. By default, all stages are enabled for a complete mix and master. You can customize this if you only need specific corrections (e.g., only "Technical Prep" or "Mastering").
            </p>

            <h3 className="text-xl font-medium text-teal-300 mt-8 mb-4">4. Space & Depth Settings</h3>
            <p className="text-slate-300">
              Use the <strong>Space & Depth</strong> panel on the left to define the reverb style for different instrument groups (e.g., "Room" for Drums, "Plate" for Vocals). If left on "Auto", the AI will choose appropriate spaces based on the genre and instrumentation.
            </p>

            <h3 className="text-xl font-medium text-teal-300 mt-8 mb-4">5. Generate Mix</h3>
            <p className="text-slate-300">
              Click the <strong>Generate AI Mix</strong> button. The system will queue your job and process it through the selected stages. You can monitor progress in real-time.
            </p>
          </section>

          <section id="features" className="scroll-mt-24 mb-16 border-t border-slate-800/50 pt-8">
            <h2 className="text-3xl font-semibold mb-6 text-slate-100">Key Features</h2>
            <ul className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <li className="bg-slate-900 p-6 rounded-xl border border-slate-800">
                <h4 className="font-bold text-teal-400 mb-2">Smart Analysis</h4>
                <p className="text-sm text-slate-400">Detects key, tempo, instrument types, and technical flaws like DC offset or phase issues automatically.</p>
              </li>
              <li className="bg-slate-900 p-6 rounded-xl border border-slate-800">
                <h4 className="font-bold text-teal-400 mb-2">Auto-Mixing</h4>
                <p className="text-sm text-slate-400">Balances levels, applies EQ, compression, and spatial effects to create a cohesive mix.</p>
              </li>
              <li className="bg-slate-900 p-6 rounded-xl border border-slate-800">
                <h4 className="font-bold text-teal-400 mb-2">AI Mastering</h4>
                <p className="text-sm text-slate-400">Delivers a loud, competitive master that meets commercial loudness standards (LUFS) and True Peak limits.</p>
              </li>
              <li className="bg-slate-900 p-6 rounded-xl border border-slate-800">
                <h4 className="font-bold text-teal-400 mb-2">Detailed Reports</h4>
                <p className="text-sm text-slate-400">Provides a comprehensive engineering report detailing every decision made by the AI, from EQ curves to compressor settings.</p>
              </li>
            </ul>
          </section>

          <section id="pipeline-overview" className="scroll-mt-24 mb-16 border-t border-slate-800/50 pt-8">
            <h2 className="text-3xl font-semibold mb-6 text-slate-100">Pipeline Stages (Deep Dive)</h2>
            <p className="text-slate-300 mb-8">
              The Audio Alchemy pipeline consists of 12 sequential stages (S0-S11). Each stage addresses a specific aspect of audio engineering.
            </p>

            <div id="s0-input" className="scroll-mt-28 mb-12">
              <h3 className="text-2xl font-semibold text-amber-400 mb-3">S0: Input & Metadata</h3>
              <p className="text-slate-400 mb-4">
                <strong>Goal:</strong> Standardization and Preparation.
              </p>
              <p className="text-slate-300">
                This stage handles the ingestion of your audio files. It normalizes the sample rate (48kHz) and bit depth (32-bit float) to ensure high-fidelity processing throughout the pipeline. It also validates metadata and sets up the internal routing for the session.
              </p>
              <ul className="list-disc pl-5 mt-2 text-slate-400 text-sm">
                <li><strong>S0_SEPARATE_STEMS:</strong> Ensures files are treated as individual stems.</li>
                <li><strong>S0_SESSION_FORMAT:</strong> Converts all audio to the project standard.</li>
              </ul>
            </div>

            <div id="s1-tech-prep" className="scroll-mt-28 mb-12">
              <h3 className="text-2xl font-semibold text-amber-400 mb-3">S1: Technical Preparation</h3>
              <p className="text-slate-400 mb-4">
                <strong>Goal:</strong> Cleaning and Correction.
              </p>
              <p className="text-slate-300">
                Before mixing begins, technical issues must be resolved. This stage detects global properties like Key and Scale, and fixes individual stem issues.
              </p>
              <ul className="list-disc pl-5 mt-2 text-slate-400 text-sm">
                <li><strong>DC Offset Removal:</strong> Removes inaudible low-frequency energy that eats up headroom.</li>
                <li><strong>Key Detection:</strong> Analyzes the song's musical key.</li>
                <li><strong>Vocal Tuning:</strong> Gently pitch-corrects vocals to the detected key if needed (can be disabled).</li>
                <li><strong>Gain Staging:</strong> Sets a healthy working loudness for each stem.</li>
              </ul>
            </div>

            <div id="s2-phase" className="scroll-mt-28 mb-12">
              <h3 className="text-2xl font-semibold text-amber-400 mb-3">S2: Phase & Polarity Alignment</h3>
              <p className="text-slate-400 mb-4">
                <strong>Goal:</strong> Cohesion and Punch.
              </p>
              <p className="text-slate-300">
                Phase issues, especially in multi-mic recordings like drums, can cause tracks to sound thin or hollow. This stage analyzes the correlation between related tracks (e.g., Kick In, Kick Out, Overheads) and applies time alignment or polarity flips to ensure they sum constructively.
              </p>
            </div>

            <div id="s3-static-mix" className="scroll-mt-28 mb-12">
              <h3 className="text-2xl font-semibold text-amber-400 mb-3">S3: Static Mix & Routing</h3>
              <p className="text-slate-400 mb-4">
                <strong>Goal:</strong> Balance and Headroom.
              </p>
              <p className="text-slate-300">
                Establishes the initial volume balance. It ensures the lead vocal is audible and sits correctly against the backing tracks. It also sets the global mixbus headroom (typically -6dB to -12dB peak) to provide space for subsequent processing stages.
              </p>
            </div>

            <div id="s4-spectral" className="scroll-mt-28 mb-12">
              <h3 className="text-2xl font-semibold text-amber-400 mb-3">S4: Spectral Cleanup</h3>
              <p className="text-slate-400 mb-4">
                <strong>Goal:</strong> Clarity and Separation.
              </p>
              <p className="text-slate-300">
                This stage cleans up the frequency spectrum of each stem.
              </p>
              <ul className="list-disc pl-5 mt-2 text-slate-400 text-sm">
                <li><strong>HPF/LPF:</strong> Applies High-Pass and Low-Pass filters based on the instrument type (e.g., removing sub-bass rumble from a Hi-Hat).</li>
                <li><strong>Resonance Control:</strong> Identifies and cuts harsh, ringing resonant frequencies that can cause ear fatigue.</li>
              </ul>
            </div>

            <div id="s5-dynamics" className="scroll-mt-28 mb-12">
              <h3 className="text-2xl font-semibold text-amber-400 mb-3">S5: Dynamics & Level Automation</h3>
              <p className="text-slate-400 mb-4">
                <strong>Goal:</strong> Control and Consistency.
              </p>
              <p className="text-slate-300">
                Applies compression and gating to control the dynamic range. It ensures quiet parts are audible and loud transients are controlled.
              </p>
              <ul className="list-disc pl-5 mt-2 text-slate-400 text-sm">
                <li><strong>Stem Dynamics:</strong> Generic compression for instruments.</li>
                <li><strong>Vocal Dynamics:</strong> Specialized processing for vocals to keep them upfront and steady.</li>
                <li><strong>Bus Compression:</strong> Glue compression for groups like Drums.</li>
              </ul>
            </div>

            <div id="s6-space" className="scroll-mt-28 mb-12">
              <h3 className="text-2xl font-semibold text-amber-400 mb-3">S6: Space & Depth</h3>
              <p className="text-slate-400 mb-4">
                <strong>Goal:</strong> Dimension and Atmosphere.
              </p>
              <p className="text-slate-300">
                Creates a sense of space using reverb and delay. Different "styles" (e.g., Hall, Plate, Room) are applied to different bus groups to create depth without washing out the mix. You can customize these styles in the "Space & Depth" panel.
              </p>
            </div>

            <div id="s7-tonal" className="scroll-mt-28 mb-12">
              <h3 className="text-2xl font-semibold text-amber-400 mb-3">S7: Multiband EQ / Tonal Balance</h3>
              <p className="text-slate-400 mb-4">
                <strong>Goal:</strong> Professional Frequency Balance.
              </p>
              <p className="text-slate-300">
                Analyzes the overall frequency spectrum of the mixbus and compares it to a target curve typical of professional releases. It applies broad, musical EQ moves to correct imbalances (e.g., too muddy, too bright).
              </p>
            </div>

            <div id="s8-color" className="scroll-mt-28 mb-12">
              <h3 className="text-2xl font-semibold text-amber-400 mb-3">S8: Mix Bus Color</h3>
              <p className="text-slate-400 mb-4">
                <strong>Goal:</strong> Glue and Warmth.
              </p>
              <p className="text-slate-300">
                Adds subtle harmonic saturation to the entire mix. This "glues" the elements together and adds analog-style warmth and character.
              </p>
            </div>

            <div id="s9-mastering" className="scroll-mt-28 mb-12">
              <h3 className="text-2xl font-semibold text-amber-400 mb-3">S9: Mastering</h3>
              <p className="text-slate-400 mb-4">
                <strong>Goal:</strong> Commercial Loudness and Polish.
              </p>
              <p className="text-slate-300">
                The final creative stage. It brings the track up to commercial volume using limiting and maximizing. It also adjusts the stereo width to ensure an immersive experience that is still mono-compatible.
              </p>
            </div>

            <div id="s10-qc" className="scroll-mt-28 mb-12">
              <h3 className="text-2xl font-semibold text-amber-400 mb-3">S10: Master Stereo QC</h3>
              <p className="text-slate-400 mb-4">
                <strong>Goal:</strong> Technical Compliance.
              </p>
              <p className="text-slate-300">
                A final Quality Control pass. It verifies that the master meets technical standards for True Peak (preventing digital clipping), LUFS (loudness), and channel balance. It makes micro-adjustments if any limits are exceeded.
              </p>
            </div>

             <div id="s11-reporting" className="scroll-mt-28 mb-12">
              <h3 className="text-2xl font-semibold text-amber-400 mb-3">S11: Reporting</h3>
              <p className="text-slate-400 mb-4">
                <strong>Goal:</strong> Transparency and Insight.
              </p>
              <p className="text-slate-300">
                Collects data from all previous stages to generate the final JSON report and render the visual feedback provided to the user.
              </p>
            </div>
          </section>

          <section id="results" className="scroll-mt-24 mb-16 border-t border-slate-800/50 pt-8">
            <h2 className="text-3xl font-semibold mb-6 text-slate-100">Understanding Results</h2>
            <p className="text-slate-300 mb-6">
              When processing is complete, you will be presented with the <strong>Mix Result Panel</strong>.
            </p>

            <h3 className="text-xl font-medium text-teal-300 mt-6 mb-3">The Audio Files</h3>
            <p className="text-slate-300 mb-4">
              You can download the final <strong>Mastered Audio</strong> (WAV). This is the production-ready file. You may also have access to the unmastered Mixbus file if needed for external mastering.
            </p>

            <h3 className="text-xl font-medium text-teal-300 mt-6 mb-3">The Engineering Report</h3>
            <p className="text-slate-300 mb-4">
              Click "View Report" to open the detailed modal. This report contains:
            </p>
            <ul className="list-disc pl-5 text-slate-400 text-sm space-y-2">
              <li><strong>Stage Summaries:</strong> Pass/Fail status for each processing step.</li>
              <li><strong>Detailed Metrics:</strong> Numeric data showing exactly what changed (e.g., "Gain reduced by 2.5dB", "EQ cut at 300Hz").</li>
              <li><strong>Before/After Comparisons:</strong> (Where available) Visual representations of the audio signal before and after processing.</li>
            </ul>
             <div className="my-6 p-4 border border-dashed border-slate-700 rounded-lg bg-slate-900/50 flex items-center justify-center text-slate-500 h-48">
               {/* Screenshot Placeholder */}
               <span className="italic">[Screenshot: Report Viewer Modal]</span>
            </div>
          </section>

          <section id="faq" className="scroll-mt-24 mb-16 border-t border-slate-800/50 pt-8">
            <h2 className="text-3xl font-semibold mb-6 text-slate-100">FAQ & Troubleshooting</h2>

            <div className="space-y-6">
              <div>
                <h4 className="font-bold text-slate-200">My mix sounds distorted. What happened?</h4>
                <p className="text-sm text-slate-400 mt-1">Check your input files. If the stems are already clipped (distorted) before upload, the AI cannot fix them. Also, ensure you haven't assigned a "Drum" profile to a vocal track, as this can cause aggressive compression.</p>
              </div>
              <div>
                <h4 className="font-bold text-slate-200">The process failed at Stage S1.</h4>
                <p className="text-sm text-slate-400 mt-1">This usually means the input files were corrupted or in an unsupported format. Try re-exporting your stems as standard WAV files.</p>
              </div>
              <div>
                <h4 className="font-bold text-slate-200">Can I use the mastered file for streaming?</h4>
                <p className="text-sm text-slate-400 mt-1">Yes! Our S9 and S10 stages are calibrated to standard streaming loudness targets (approx -14 LUFS integrated, -1dB True Peak).</p>
              </div>
            </div>
          </section>
        </main>
      </div>

      <footer className="border-t border-slate-800/80 py-6 text-center text-xs text-slate-400 bg-slate-950">
        <p>© 2025 Audio Alchemy. All Rights Reserved.</p>
      </footer>
    </div>
  );
}
