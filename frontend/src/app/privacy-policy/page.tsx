import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description:
    "Read how Audio Alchemy collects, uses, and protects your data when using our AI audio mixing and mastering service.",
  alternates: { canonical: "/privacy-policy" },
  robots: { index: true, follow: true },
};

export default function PrivacyPolicyPage() {
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
          <h1 className="text-3xl font-bold mb-8 text-teal-400">Privacy Policy</h1>

          <p className="text-slate-300 mb-6">Last updated: {new Date().toLocaleDateString()}</p>

          <section className="mb-8">
            <h2 className="text-xl font-semibold mb-4 text-slate-200">1. Introduction</h2>
            <p className="text-slate-400 leading-relaxed">
              Welcome to <strong>Audio Alchemy</strong>. We respect your privacy and are committed to protecting your personal data.
              This privacy policy will inform you as to how we look after your personal data when you visit our website
              and tell you about your privacy rights and how the law protects you.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-xl font-semibold mb-4 text-slate-200">2. Data Controller</h2>
            <p className="text-slate-400 leading-relaxed">
              Audio Alchemy is the controller and responsible for your personal data.
              If you have any questions about this privacy policy, please contact us.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-xl font-semibold mb-4 text-slate-200">3. The Data We Collect</h2>
            <p className="text-slate-400 leading-relaxed mb-4">
              We may collect, use, store and transfer different kinds of personal data about you which we have grouped together follows:
            </p>
            <ul className="list-disc pl-5 text-slate-400 space-y-2">
              <li><strong>Identity Data:</strong> includes first name, last name, username or similar identifier (if applicable).</li>
              <li><strong>Contact Data:</strong> includes email address (if provided).</li>
              <li><strong>Technical Data:</strong> includes internet protocol (IP) address, your login data, browser type and version, time zone setting and location, browser plug-in types and versions, operating system and platform and other technology on the devices you use to access this website.</li>
              <li><strong>Usage Data:</strong> includes information about how you use our website, products and services.</li>
              <li><strong>Content Data:</strong> includes the audio files you upload for processing. These are processed solely for the purpose of providing the service and are not used for other purposes without your consent.</li>
            </ul>
          </section>

          <section className="mb-8">
            <h2 className="text-xl font-semibold mb-4 text-slate-200">4. How We Use Your Personal Data</h2>
            <p className="text-slate-400 leading-relaxed mb-4">
              We will only use your personal data when the law allows us to. Most commonly, we will use your personal data in the following circumstances:
            </p>
            <ul className="list-disc pl-5 text-slate-400 space-y-2">
              <li>Where we need to perform the contract we are about to enter into or have entered into with you (e.g., processing your mix).</li>
              <li>Where it is necessary for our legitimate interests (or those of a third party) and your interests and fundamental rights do not override those interests.</li>
              <li>Where we need to comply with a legal or regulatory obligation.</li>
            </ul>
          </section>

          <section className="mb-8">
            <h2 className="text-xl font-semibold mb-4 text-slate-200">5. Data Retention</h2>
            <p className="text-slate-400 leading-relaxed">
              We will only retain your personal data for as long as necessary to fulfill the purposes we collected it for, including for the purposes of satisfying any legal, accounting, or reporting requirements.
              Audio files uploaded are retained only for the duration of the processing job and a reasonable period thereafter to allow you to download results, after which they are deleted.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-xl font-semibold mb-4 text-slate-200">6. Data Security</h2>
            <p className="text-slate-400 leading-relaxed">
              We have put in place appropriate security measures to prevent your personal data from being accidentally lost, used or accessed in an unauthorized way, altered or disclosed.
              In addition, we limit access to your personal data to those employees, agents, contractors and other third parties who have a business need to know.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-xl font-semibold mb-4 text-slate-200">7. Your Legal Rights</h2>
            <p className="text-slate-400 leading-relaxed mb-4">
              Under certain circumstances, you have rights under data protection laws in relation to your personal data, including the right to:
            </p>
            <ul className="list-disc pl-5 text-slate-400 space-y-2">
              <li>Request access to your personal data.</li>
              <li>Request correction of your personal data.</li>
              <li>Request erasure of your personal data.</li>
              <li>Object to processing of your personal data.</li>
              <li>Request restriction of processing your personal data.</li>
              <li>Request transfer of your personal data.</li>
              <li>Right to withdraw consent.</li>
            </ul>
            <p className="text-slate-400 leading-relaxed mt-4">
              If you wish to exercise any of the rights set out above, please contact us.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-xl font-semibold mb-4 text-slate-200">8. Cookies</h2>
            <p className="text-slate-400 leading-relaxed">
              We use cookies to distinguish you from other users of our website. This helps us to provide you with a good experience when you browse our website and also allows us to improve our site.
              We use Google Analytics to analyze the use of our website.
            </p>
          </section>

          <section className="mb-8">
            <h2 className="text-xl font-semibold mb-4 text-slate-200">9. Contact Details</h2>
            <p className="text-slate-400 leading-relaxed">
              If you have any questions about this privacy policy or our privacy practices, please contact us at: <br />
              <span className="text-teal-400">privacy@audioalchemy.com</span>
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
