import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Terms of Service",
  description:
    "Review the Terms of Service for Audio Alchemy's AI mixing and mastering platform, including user responsibilities and limitations.",
  alternates: { canonical: "/terms-of-service" },
  robots: { index: true, follow: true },
};

export default function TermsOfServicePage() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      <header className="border-b border-slate-800/80 sticky top-0 bg-slate-950/90 backdrop-blur z-10">
        <div className="mx-auto flex h-16 max-w-5xl items-center px-4 justify-between">
          <div className="flex items-center gap-2">
            <Link href="/" className="flex items-center gap-2 no-underline text-inherit hover:opacity-80 transition">
              <div className="h-7 w-7 rounded-full bg-teal-400/90 flex items-center justify-center text-slate-950 text-lg font-bold">
                A
              </div>
              <span className="text-lg font-semibold tracking-tight">Audio Alchemy</span>
            </Link>
          </div>
          <Link href="/" className="text-sm font-medium text-teal-400 hover:text-teal-300">
            ← Back to Home
          </Link>
        </div>
      </header>

      <main className="flex-1 px-4 py-12">
        <div className="mx-auto max-w-3xl prose prose-invert prose-slate">
          <h1 className="text-3xl font-bold mb-8 text-teal-400">Terms of Service</h1>

          <p className="text-slate-300 mb-6">Last updated: {new Date().toLocaleDateString()}</p>

          <section className="mb-8">
            <h2 className="text-xl font-semibold mb-4 text-slate-200">1. Acceptance of Terms</h2>
            <p className="text-slate-400 leading-relaxed">
              By accessing or using <strong>Audio Alchemy</strong>, you agree to be bound by these Terms of Service.
              If you do not agree to these terms, please do not use our services.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-xl font-semibold mb-4 text-slate-200">2. Service Description</h2>
            <p className="text-slate-400 leading-relaxed">
              Audio Alchemy provides AI-assisted audio mixing and mastering services. We allow users to upload audio files,
              process them through our automated pipeline, and download the results.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-xl font-semibold mb-4 text-slate-200">3. User Responsibilities</h2>
            <p className="text-slate-400 leading-relaxed mb-4">
              You are responsible for your use of the service and for any content you provide, including compliance with applicable laws.
              You must not upload any content that:
            </p>
            <ul className="list-disc pl-5 text-slate-400 space-y-2">
              <li>Violates any third-party intellectual property rights.</li>
              <li>Is illegal, harmful, threatening, or otherwise objectionable.</li>
              <li>Contains viruses or other malicious code.</li>
            </ul>
          </section>

          <section className="mb-8">
            <h2 className="text-xl font-semibold mb-4 text-slate-200">4. Intellectual Property</h2>
            <p className="text-slate-400 leading-relaxed">
              You retain all rights and ownership of your original content. By uploading content, you grant us a limited license
              to process, store, and modify your content solely for the purpose of providing the service to you.
              The processed output is owned by you.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-xl font-semibold mb-4 text-slate-200">5. Limitation of Liability</h2>
            <p className="text-slate-400 leading-relaxed">
              Audio Alchemy is provided "as is" without any warranties. We shall not be liable for any indirect, incidental,
              special, consequential or punitive damages, including without limitation, loss of profits, data, use, goodwill,
              or other intangible losses.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-xl font-semibold mb-4 text-slate-200">6. Changes to Terms</h2>
            <p className="text-slate-400 leading-relaxed">
              We reserve the right to modify these terms at any time. We will provide notice of any significant changes
              by posting the new terms on this page. Your continued use of the service after any such changes constitutes
              your acceptance of the new terms.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-xl font-semibold mb-4 text-slate-200">7. Contact Us</h2>
            <p className="text-slate-400 leading-relaxed">
              If you have any questions about these Terms, please contact us at: <br />
              <span className="text-teal-400">legal@audioalchemy.com</span>
            </p>
          </section>
        </div>
      </main>

      <footer className="border-t border-slate-800/80 py-6 text-center text-xs text-slate-400 bg-slate-950">
        <p>© {new Date().getFullYear()} Audio Alchemy. All Rights Reserved.</p>
      </footer>
    </div>
  );
}
