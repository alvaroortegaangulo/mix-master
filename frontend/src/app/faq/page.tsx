import Link from "next/link";
import Script from "next/script";

export const metadata = {
  title: "FAQ - Piroola",
  description: "Frequently Asked Questions about Piroola's AI Mixing & Mastering service.",
};

const FAQ_ITEMS = [
  {
    question: "What is Piroola?",
    answer: "Piroola is an advanced online service that uses Artificial Intelligence to mix and master your multi-track audio files. It analyzes your stems and applies professional studio techniques to deliver radio-ready quality tracks in minutes."
  },
  {
    question: "How does the AI mixing work?",
    answer: "Our AI pipeline analyzes each stem for frequency content, dynamics, and tonal balance. It then applies corrective processing (EQ, compression), balances levels, places instruments in the stereo field, and adds effects like reverb to create a cohesive mix, tailored to your genre."
  },
  {
    question: "What file formats are supported?",
    answer: "We support most standard audio formats including WAV, AIFF, FLAC, and MP3. For the best results, we recommend uploading high-quality uncompressed WAV or AIFF files (24-bit / 44.1kHz or higher)."
  },
  {
    question: "Is my music secure?",
    answer: "Yes, your security is our priority. Your files are processed securely on our servers and are automatically deleted after a short period. We do not claim any rights to your music; you retain 100% ownership of your work."
  },
  {
    question: "How long does the process take?",
    answer: "Most mixes are completed within a few minutes, depending on the number of stems and the length of the track. You will see a progress bar indicating each step of the analysis and mixing process."
  },
  {
    question: "Can I upload stems?",
    answer: "Absolutely. In fact, our service is designed for stems! You can upload individual instrument tracks (like kick, snare, bass, vocals) to allow our AI to mix them together perfectly."
  },
  {
    question: "What is the difference between mixing and mastering?",
    answer: "Mixing involves balancing individual tracks (stems) to form a song, including adjusting levels, panning, and adding effects. Mastering is the final step that polishes the mixed song, ensuring it sounds consistent and loud enough for commercial release."
  },
  {
    question: "Do I own the rights to the mixed track?",
    answer: "Yes! You maintain full copyright and ownership of your original music and the final mix produced by Piroola. You can release your tracks on any streaming platform without paying us royalties."
  },
  {
    question: "What if I'm not satisfied with the result?",
    answer: "We provide a detailed report of the processing applied. If the result isn't what you expected, you can try adjusting the input stems (e.g., cleaning up noise) or ensuring your files are correctly labeled, and run the process again."
  },
  {
    question: "Is there a file size limit?",
    answer: "Currently, we support reasonable file sizes typical for music production stems. If you encounter issues with extremely large projects, consider exporting your stems at a standard sample rate (e.g., 44.1kHz or 48kHz)."
  },
  {
    question: "How do I download my results?",
    answer: "Once the processing is complete, a 'Download' button will appear. You can download the final mixed and mastered stereo file directly to your device."
  },
  {
    question: "Can I use Piroola on mobile?",
    answer: "Yes, our website is fully responsive and works on mobile devices. However, for managing multiple stem files, a desktop computer might offer a smoother workflow."
  }
];

export default function FAQPage() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
       <Script
        id="faq-schema"
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "FAQPage",
            mainEntity: FAQ_ITEMS.map((item) => ({
              "@type": "Question",
              name: item.question,
              acceptedAnswer: {
                "@type": "Answer",
                text: item.answer,
              },
            })),
          }),
        }}
      />

      <main className="flex-1 px-4 py-12">
        <div className="mx-auto max-w-3xl">
          <h1 className="mb-8 text-4xl font-bold tracking-tight text-teal-400 text-center">
            Frequently Asked Questions
          </h1>
          <p className="mb-12 text-center text-slate-400 text-lg">
            Everything you need to know about our AI mixing and mastering service.
          </p>

          <div className="space-y-6">
            {FAQ_ITEMS.map((item, index) => (
              <div
                key={index}
                className="rounded-2xl border border-slate-800/60 bg-slate-900/50 p-6 shadow-lg transition hover:border-teal-500/30"
              >
                <h3 className="mb-3 text-xl font-semibold text-slate-200">
                  {item.question}
                </h3>
                <p className="text-slate-400 leading-relaxed">
                  {item.answer}
                </p>
              </div>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}
