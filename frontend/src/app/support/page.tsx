"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";

export default function SupportPage() {
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    subject: "",
    message: "",
  });
  const [status, setStatus] = useState<"idle" | "submitting" | "success" | "error">("idle");

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setStatus("submitting");

    // Simulate API call
    try {
      await new Promise((resolve) => setTimeout(resolve, 1500));
      setStatus("success");
      setFormData({ name: "", email: "", subject: "", message: "" });
    } catch (error) {
      console.error(error);
      setStatus("error");
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      <header className="border-b border-slate-800/80">
        <div className="mx-auto flex h-16 max-w-5xl items-center justify-between px-4">
          <div className="flex items-center gap-2">
            <div className="h-7 w-7 rounded-full bg-teal-400/90 flex items-center justify-center text-slate-950 text-lg font-bold" aria-hidden="true">
              A
            </div>
            <Link href="/" className="text-lg font-semibold tracking-tight text-slate-100 hover:text-teal-400 transition">
              Audio Alchemy
            </Link>
          </div>
          <nav className="hidden md:flex gap-6 text-sm">
            <Link href="/" className="hover:text-teal-400 transition">Home</Link>
            <Link href="/faq" className="hover:text-teal-400 transition">FAQ</Link>
            <Link href="/docs" className="hover:text-teal-400 transition">Docs</Link>
          </nav>
        </div>
      </header>

      <main className="flex-1 px-4 py-12">
        <div className="mx-auto max-w-3xl">
          <h1 className="mb-4 text-4xl font-bold tracking-tight text-teal-400 text-center">
            Support Center
          </h1>
          <p className="mb-12 text-center text-slate-400 text-lg">
            Need help? We've got you covered.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-12">
            <div className="rounded-2xl border border-slate-800/60 bg-slate-900/50 p-6 shadow-lg">
              <h2 className="text-xl font-semibold text-slate-200 mb-4">Quick Resources</h2>
              <p className="text-slate-400 mb-6">
                Before reaching out, check our documentation and FAQs.
              </p>
              <div className="flex flex-col gap-3">
                <Link 
                  href="/faq" 
                  className="inline-flex items-center justify-between px-4 py-3 rounded-lg bg-slate-800/50 hover:bg-slate-800 hover:text-teal-400 transition border border-slate-700/50"
                >
                  <span>Frequently Asked Questions</span>
                  <span>→</span>
                </Link>
                <Link 
                  href="/docs" 
                  className="inline-flex items-center justify-between px-4 py-3 rounded-lg bg-slate-800/50 hover:bg-slate-800 hover:text-teal-400 transition border border-slate-700/50"
                >
                  <span>Documentation & Guide</span>
                  <span>→</span>
                </Link>
              </div>
            </div>

             <div className="rounded-2xl border border-slate-800/60 bg-slate-900/50 p-6 shadow-lg">
              <h2 className="text-xl font-semibold text-slate-200 mb-4">Direct Contact</h2>
              <p className="text-slate-400 mb-6">
                Prefer email? You can reach our support team directly.
              </p>
              <div className="flex items-center gap-3 text-slate-300 mb-2">
                <a href="mailto:support@audioalchemy.com" className="hover:text-teal-400 transition">support@audioalchemy.com</a>
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-800/60 bg-slate-900/50 p-8 shadow-xl">
            <h2 className="text-2xl font-semibold text-slate-200 mb-6 text-center">Send us a message</h2>
            
            {status === "success" ? (
              <div className="text-center py-12">
                <h3 className="text-xl font-medium text-slate-100 mb-2">Message Sent!</h3>
                <p className="text-slate-400">Thank you for contacting us.</p>
                <button 
                  onClick={() => setStatus("idle")}
                  className="mt-6 text-teal-400 hover:text-teal-300 font-medium text-sm hover:underline"
                >
                  Send another message
                </button>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-2">
                    <label htmlFor="name" className="text-sm font-medium text-slate-300">Name</label>
                    <input
                      type="text"
                      id="name"
                      name="name"
                      required
                      value={formData.name}
                      onChange={handleChange}
                      className="w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-2.5 text-slate-100 placeholder-slate-500 focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500 transition"
                      placeholder="Your name"
                    />
                  </div>
                  <div className="space-y-2">
                    <label htmlFor="email" className="text-sm font-medium text-slate-300">Email</label>
                    <input
                      type="email"
                      id="email"
                      name="email"
                      required
                      value={formData.email}
                      onChange={handleChange}
                      className="w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-2.5 text-slate-100 placeholder-slate-500 focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500 transition"
                      placeholder="you@example.com"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <label htmlFor="subject" className="text-sm font-medium text-slate-300">Subject</label>
                  <select
                    id="subject"
                    name="subject"
                    required
                    value={formData.subject}
                    onChange={handleChange}
                    className="w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-2.5 text-slate-100 placeholder-slate-500 focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500 transition appearance-none"
                  >
                    <option value="" disabled>Select a topic</option>
                    <option value="technical">Technical Support</option>
                    <option value="billing">Billing & Pricing</option>
                    <option value="feedback">Feedback & Suggestions</option>
                    <option value="other">Other</option>
                  </select>
                </div>

                <div className="space-y-2">
                  <label htmlFor="message" className="text-sm font-medium text-slate-300">Message</label>
                  <textarea
                    id="message"
                    name="message"
                    required
                    rows={5}
                    value={formData.message}
                    onChange={handleChange}
                    className="w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-2.5 text-slate-100 placeholder-slate-500 focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500 transition resize-none"
                    placeholder="How can we help you?"
                  />
                </div>

                <div className="pt-2">
                  <button
                    type="submit"
                    disabled={status === "submitting"}
                    className="w-full rounded-full bg-teal-500 py-3 text-sm font-bold text-slate-950 shadow-md shadow-teal-500/20 hover:bg-teal-400 hover:shadow-teal-500/30 transition disabled:opacity-60 disabled:cursor-not-allowed"
                  >
                    {status === "submitting" ? "Sending..." : "Send Message"}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      </main>

      <footer className="border-t border-slate-800/80 py-4 text-center text-xs text-slate-400 flex flex-col gap-2 items-center justify-center">
        <p>© 2025 Audio Alchemy. All Rights Reserved.</p>
        <div className="flex gap-4">
          <Link href="/terms-of-service" className="hover:text-teal-400 hover:underline">Terms of Service</Link>
          <Link href="/privacy-policy" className="hover:text-teal-400 hover:underline">Privacy Policy</Link>
          <Link href="/cookie-policy" className="hover:text-teal-400 hover:underline">Cookie Policy</Link>
        </div>
      </footer>
    </div>
  );
}
