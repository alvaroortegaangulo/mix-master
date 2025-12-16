"use client";

import { Link } from "../i18n/routing";
import Image from "next/image";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "../context/AuthContext";
import { useModal } from "../context/ModalContext";
import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";

export function Header() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { user, loading: authLoading } = useAuth();
  const { openAuthModal } = useModal();
  const [scrolled, setScrolled] = useState(false);
  const router = useRouter();
  const t = useTranslations('Navigation');

  const NAV_LINKS = [
    { label: t('examples'), href: "/examples" },
    { label: t('pricing'), href: "/pricing" },
    { label: t('faq'), href: "/faq" },
    { label: t('howItWorks'), href: "/docs" },
    { label: t('support'), href: "/support" },
  ];

  // Detect scroll to adjust background
  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 10);
    };
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const isLanding = pathname === "/" && (!searchParams.get("view") || searchParams.get("view") === "landing");
  const isTool = pathname === "/" && searchParams.get("view") === "tool";

  // If on tool view, we might want a solid header or keep it consistent?
  // The original page.tsx had: view === 'landing' ? transparent : slate-950
  // We will replicate this logic based on path and params.

  // Note: /studio/... has its own layout so this Header won't be rendered there (handled in GlobalLayoutClient).

  const headerClass = (isLanding && !scrolled)
    ? "border-transparent bg-slate-950/80 backdrop-blur-md"
    : "border-slate-800 bg-slate-950/80 backdrop-blur-md";

  const handleLogoClick = (e: React.MouseEvent) => {
      e.preventDefault();
      // If on landing/root, verify we reset view?
      // Actually Link href="/" does a soft nav.
      // If we are on /?view=tool, clicking logo should probably go to /?view=landing or just /
      router.push("/");
  };

  const handleGoToApp = () => {
      router.push("/?view=tool");
  };

  return (
    <header className={`fixed top-0 left-0 right-0 z-50 border-b transition-all duration-300 ${headerClass}`}>
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <Link href="/" onClick={handleLogoClick} className="flex items-center gap-2 shrink-0 cursor-pointer">
          <Image src="/logo.webp" alt="Piroola Logo" width={32} height={32} className="h-8 w-8" />
          <span className="text-xl font-bold tracking-tight text-white hidden sm:block">Piroola</span>
        </Link>

        <nav className="hidden md:flex items-center gap-8">
          {NAV_LINKS.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={`text-sm font-medium transition-colors ${pathname === item.href ? "text-white" : "text-slate-300 hover:text-white"}`}
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="flex items-center gap-4">
           {!authLoading && (
               user ? (
                   <div className="flex items-center gap-4">
                       {/* If we are NOT in the tool view, show Go to App */}
                       {!isTool && (
                           <button
                              onClick={handleGoToApp}
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
                          onClick={openAuthModal}
                          className="text-sm font-semibold text-slate-300 hover:text-white transition"
                      >
                          Log In
                      </button>
                      <button
                          onClick={openAuthModal} // Or go to app? Usually Try for free = Sign up
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
  );
}
