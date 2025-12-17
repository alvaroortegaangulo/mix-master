"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { WaveformPlayer } from "../../../../components/WaveformPlayer";
import { getSharedJob } from "../../../../lib/mixApi";
import { useTranslations } from "next-intl";

export default function SharePage() {
  const { token } = useParams();
  const [jobData, setJobData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const t = useTranslations('MixTool.share');

  useEffect(() => {
    async function loadSharedJob() {
      if (!token) return;
      try {
        const data = await getSharedJob(token as string);
        setJobData(data);
      } catch (err) {
        setError(t('invalidLink'));
      } finally {
        setLoading(false);
      }
    }
    void loadSharedJob();
  }, [token, t]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 text-emerald-500">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-current border-t-transparent" />
      </div>
    );
  }

  if (error || !jobData) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 text-center">
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-8">
          <p className="text-xl text-red-200">{error || t('notFound')}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-slate-950 p-4">
      <div className="w-full max-w-2xl space-y-8 rounded-3xl border border-emerald-500/20 bg-slate-900/50 p-8 shadow-2xl backdrop-blur-sm">
        <div className="text-center">
          <h1 className="text-3xl font-bold text-emerald-100">{t('sharedMixTitle')}</h1>
          <p className="mt-2 text-emerald-200/60">{t('sharedMixDesc')}</p>
        </div>

        <div className="space-y-4">
          <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/5 p-6">
             <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-emerald-400">
               {t('aiMix')}
             </h2>
             <WaveformPlayer
                src={jobData.audio_url}
                downloadFileName={`mix_${jobData.jobId}.wav`}
                accentColor="#10b981" // emerald-500
             />
          </div>

          {jobData.original_url && (
            <div className="rounded-2xl border border-slate-700/50 bg-slate-800/30 p-6 opacity-80 transition hover:opacity-100">
               <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-400">
                 {t('originalMix')}
               </h2>
               <WaveformPlayer
                  src={jobData.original_url}
                  downloadFileName={`original_${jobData.jobId}.wav`}
                  accentColor="#94a3b8" // slate-400
               />
            </div>
          )}
        </div>

        <div className="text-center">
           <a
             href="/"
             className="inline-flex items-center gap-2 rounded-full bg-emerald-600 px-6 py-2 text-sm font-bold text-white transition hover:bg-emerald-500"
           >
             <span>{t('createYourOwn')}</span>
             <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5">
               <path fillRule="evenodd" d="M3 10a.75.75 0 01.75-.75h10.638L10.23 5.29a.75.75 0 111.04-1.08l5.5 5.25a.75.75 0 010 1.08l-5.5 5.25a.75.75 0 11-1.04-1.08l4.158-3.96H3.75A.75.75 0 013 10z" clipRule="evenodd" />
             </svg>
           </a>
        </div>
      </div>
    </div>
  );
}
