"use client";

import { Suspense, useState, useEffect } from "react";
import dynamic from "next/dynamic";
import { useSearchParams } from "next/navigation";
import { LandingPage } from "../components/landing/LandingPage";
import { useAuth } from "../context/AuthContext";
import { useModal } from "../context/ModalContext";

// We no longer need local AuthModal import as it is handled by GlobalLayoutClient -> ModalProvider

const MixTool = dynamic(
  () => import("../components/MixTool").then((mod) => mod.MixTool),
  {
    ssr: false,
    loading: () => (
      <div className="flex min-h-[60vh] items-center justify-center text-slate-300">
        Loading studio...
      </div>
    ),
  }
);

function PageContent() {
  // view state: 'landing' or 'tool'
  const searchParams = useSearchParams();
  const jobIdParam = searchParams.get("jobId");
  const startInTool = searchParams.get("view") === "tool" || !!jobIdParam;
  const [view, setView] = useState<'landing' | 'tool'>(startInTool ? 'tool' : 'landing');

  // Use global modal context
  const { openAuthModal, isAuthModalOpen } = useModal();
  const { user } = useAuth();

  const handleTryIt = () => {
    if (user) {
      setView('tool');
    } else {
      openAuthModal();
    }
  };

  // If user successfully logs in via modal, we switch to tool.
  // We check if modal was open and now we have user.
  // We need to track previous user state or just rely on open/close?
  // Actually, if we just opened the modal, and then user became logged in, we want to redirect.
  // However, isAuthModalOpen is global now.
  // We can just say: if user is logged in, and we are on landing, maybe we don't force switch unless clicked?
  // But usually if I click "Log In" in header, I stay on page.
  // If I click "Try it" and log in, I want to go to tool.
  // Let's keep it simple: If user logs in, we don't auto-switch unless they were trying to access tool.
  // BUT, the previous logic was: if user exists and modal was open -> switch.
  // Let's replicate that somewhat?
  // Actually, if I login via Header, I might want to stay on Landing.
  // If I login via "Try it", I want Tool.
  // "Try it" opens modal.
  // Let's assume for now default behavior is fine. The user can click "Go to App" in header if logged in.

  // Wait, if I am logged in, the "Try it" button in Hero becomes "Go to App"?
  // LandingPage's HeroSection calls `onTryIt`.
  // If user is logged in, `handleTryIt` sets view to 'tool'. Correct.

  useEffect(() => {
    if (startInTool) {
      setView('tool');
    }
  }, [startInTool]);

  // We don't render Header here anymore.

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans selection:bg-teal-500/30">
      <div className="flex flex-col">
         {view === 'landing' ? (
             <LandingPage onTryIt={handleTryIt} />
         ) : (
             <MixTool resumeJobId={jobIdParam || undefined} />
         )}
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-slate-950" />}>
      <PageContent />
    </Suspense>
  );
}
