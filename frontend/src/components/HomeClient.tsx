"use client";

import { Suspense } from "react";
import { useRouter } from "../i18n/routing";
import { HomeViewContext } from "../context/HomeViewContext";

interface HomeClientProps {
  children?: React.ReactNode;
}

function PageContent({ children }: HomeClientProps) {
  const router = useRouter();

  const handleTryIt = () => {
    router.push("/mix");
  };

  return (
    <HomeViewContext.Provider value={{ handleTryIt }}>
      <div className="min-h-screen bg-slate-950 text-slate-100 font-sans selection:bg-teal-500/30">
        <div className="flex flex-col">
           {children}
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
