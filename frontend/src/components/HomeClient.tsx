"use client";

import { Suspense, useState, useEffect } from "react";
import dynamic from "next/dynamic";
import { useSearchParams } from "next/navigation";
import { useAuth } from "../context/AuthContext";
import { useModal } from "../context/ModalContext";
import { HomeViewContext } from "../context/HomeViewContext";

const MixTool = dynamic(
  () => import("./MixTool").then((mod) => mod.MixTool),
  {
    ssr: false,
    loading: () => (
      <div className="flex min-h-[60vh] items-center justify-center text-slate-300">
        Loading studio...
      </div>
    ),
  }
);

interface HomeClientProps {
  children?: React.ReactNode;
}

function PageContent({ children }: HomeClientProps) {
  // view state: 'landing' or 'tool'
  const searchParams = useSearchParams();
  const jobIdParam = searchParams.get("jobId");
  const startInTool = searchParams.get("view") === "tool" || !!jobIdParam;
  const [view, setView] = useState<'landing' | 'tool'>(startInTool ? 'tool' : 'landing');

  // Use global modal context
  const { openAuthModal } = useModal();
  const { user } = useAuth();

  const handleTryIt = () => {
    if (user) {
      setView('tool');
    } else {
      openAuthModal();
    }
  };

  useEffect(() => {
    if (startInTool) {
      setView('tool');
    }
  }, [startInTool]);

  return (
    <HomeViewContext.Provider value={{ handleTryIt }}>
      <div className="min-h-screen bg-slate-950 text-slate-100 font-sans selection:bg-teal-500/30">
        <div className="flex flex-col">
          {view === 'landing' ? (
              children
          ) : (
              <MixTool resumeJobId={jobIdParam || undefined} />
          )}
        </div>
      </div>
    </HomeViewContext.Provider>
  );
}

export function HomeClient({ children }: HomeClientProps) {
  return (
    <Suspense fallback={<div className="min-h-screen bg-slate-950" />}>
      <PageContent>{children}</PageContent>
    </Suspense>
  );
}
