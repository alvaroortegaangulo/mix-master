"use client";

import { Suspense, useState, useEffect } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { LandingPage } from "../components/landing/LandingPage";
import { MixTool } from "../components/MixTool";
import { AuthModal } from "../components/AuthModal";
import { useAuth } from "../context/AuthContext";

const NAV_LINKS = [
  { label: "Examples", href: "/examples" },
  { label: "Pricing", href: "/pricing" },
  { label: "FAQ", href: "/faq" },
  { label: "Docs", href: "/docs" },
  { label: "Support", href: "/support" },
];

function PageContent() {
  // view state: 'landing' or 'tool'
  const searchParams = useSearchParams();
  const jobIdParam = searchParams.get("jobId");
  const startInTool = searchParams.get("view") === "tool" || !!jobIdParam;
  const [view, setView] = useState<'landing' | 'tool'>(startInTool ? 'tool' : 'landing');
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const { user, loading: authLoading } = useAuth();

  // If user is already logged in, we MIGHT want to show the tool?
  // The user requirement says: "Try it for free" guides to the tool...
  // It implies the landing page is the default.
  // We keep it as landing page default.

  const handleTryIt = () => {
    if (user) {
      setView('tool');
    } else {
      setIsAuthModalOpen(true);
    }
  };

  // If user successfully logs in via modal, we want to switch to tool.
  // We can watch `user` state.
  // But wait, what if I am on landing page, not clicking Try It, but I reload and I am logged in?
  // Should I see tool or landing?
  // Standard SaaS: Authenticated users usually go to Dashboard/Tool. Unauthenticated go to Landing.
  // However, since we are merging both in one route `/`, let's see.
  // The user says: "I want the main screen... to follow the idea...".
  // This implies even for logged in users, they might land on the landing page first?
  // But usually "Try it" guides to tool.
  // Let's implement: Default Landing.
  // If user clicks "Try it" -> Check Auth.

  // Also, if `AuthModal` succeeds (login or register), `user` will become non-null.
  // We can use an effect to switch if the modal was open.
  useEffect(() => {
    if (user && isAuthModalOpen) {
       // If modal was open and now we have user -> User just logged in.
       setIsAuthModalOpen(false);
       setView('tool');
    }
  }, [user, isAuthModalOpen]);

  useEffect(() => {
    if (startInTool) {
      setView('tool');
    }
  }, [startInTool]);

  const handleReset = () => {
      setView('landing');
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans selection:bg-teal-500/30">

      {/* Global Header (sticky or fixed?) */}
      {/* We can have a header that adapts based on view, or a common header */}
      <header className={`fixed top-0 left-0 right-0 z-50 border-b transition-all duration-300 ${view === 'landing' ? 'border-transparent bg-slate-950/80 backdrop-blur-md' : 'border-slate-800 bg-slate-950'}`}>
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-2 shrink-0 cursor-pointer" onClick={handleReset}>
            <img src="/logo.png" alt="Piroola Logo" className="h-8 w-8" />
            <span className="text-xl font-bold tracking-tight text-white hidden sm:block">Piroola</span>
          </div>

          <nav className="hidden md:flex items-center gap-8">
            {NAV_LINKS.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="text-sm font-medium text-slate-300 hover:text-white transition-colors"
              >
                {item.label}
              </Link>
            ))}
          </nav>

          <div className="flex items-center gap-4">
             {!authLoading && (
                 user ? (
                     <div className="flex items-center gap-4">
                         {view === 'landing' && (
                             <button
                                onClick={() => setView('tool')}
                                className="text-sm font-semibold text-white hover:text-teal-400 transition"
                             >
                                 Go to App
                             </button>
                         )}
                         <Link href="/profile" className="flex h-9 w-9 items-center justify-center rounded-full bg-purple-600 font-bold text-white shadow-md ring-2 ring-slate-800/50 hover:ring-teal-500/50 transition">
                            {user.full_name ? user.full_name.charAt(0).toUpperCase() : user.email.charAt(0).toUpperCase()}
                         </Link>
                     </div>
                 ) : (
                     <div className="flex items-center gap-4">
                        <button
                            onClick={() => setIsAuthModalOpen(true)}
                            className="text-sm font-semibold text-slate-300 hover:text-white transition"
                        >
                            Log In
                        </button>
                        <button
                            onClick={handleTryIt}
                            className="rounded-full bg-teal-500 text-slate-950 px-5 py-2 text-sm font-bold shadow-lg shadow-teal-500/20 hover:bg-teal-400 hover:shadow-teal-500/40 transition transform hover:-translate-y-0.5"
                        >
                            Try for free
                        </button>
                     </div>
                 )
             )}
          </div>
        </div>
      </header>

      <div className="pt-16 min-h-screen flex flex-col">
         {view === 'landing' ? (
             <LandingPage onTryIt={handleTryIt} />
         ) : (
             <MixTool resumeJobId={jobIdParam || undefined} />
         )}
      </div>

      <AuthModal
        isOpen={isAuthModalOpen}
        onClose={() => setIsAuthModalOpen(false)}
      />
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
