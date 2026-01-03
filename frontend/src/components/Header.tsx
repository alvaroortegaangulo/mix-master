"use client";

import { Link, useRouter } from "../i18n/routing";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { useAuth } from "../context/AuthContext";
import { useModal } from "../context/ModalContext";
import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { ArrowRightIcon } from "@heroicons/react/20/solid";

export function Header() {
  const pathname = usePathname();
  const { user, loading: authLoading } = useAuth();
  const { openAuthModal } = useModal();
  const [scrolled, setScrolled] = useState(false);
  const router = useRouter();
  const tNav = useTranslations('Navigation');

  const NAV_LINKS = [
    { label: tNav('examples'), href: "/examples" },
    { label: tNav('pricing'), href: "/pricing" },
    { label: tNav('faq'), href: "/faq" },
    { label: tNav('howItWorks'), href: "/docs" },
    { label: tNav('blog'), href: "/blog" },
    { label: tNav('support'), href: "/support" },
  ];

  // Detect scroll to adjust background
  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 10);
    };
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const isMixTool = pathname.endsWith("/mix");
  const isLanding = /^\/([a-z]{2})?$/.test(pathname);

  const headerClass = (isLanding && !scrolled)
    ? "border-transparent bg-slate-950/80 backdrop-blur-md"
    : "border-slate-800 bg-slate-950/80 backdrop-blur-md";

  const handleLogoClick = (e: React.MouseEvent) => {
      e.preventDefault();
      router.push("/");
  };

  const handleGoToApp = () => {
      router.push("/mix");
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
                       {!isMixTool && (
                           <div className="relative group">
                             <div className="absolute -inset-0.5 bg-gradient-to-r from-cyan-500 to-purple-600 rounded-full blur opacity-60 group-hover:opacity-100 transition duration-200"></div>
                             <button
                                onClick={handleGoToApp}
                                className="relative flex items-center gap-2 px-4 py-2 bg-slate-950 text-white text-sm font-semibold rounded-full leading-none hover:bg-slate-900 transition-colors duration-200"
                             >
                                 {tNav('goToApp')}
                                 <ArrowRightIcon className="w-4 h-4 text-white" />
                             </button>
                           </div>
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
                          {tNav('logIn')}
                      </button>
                      <div className="relative group">
                        <div className="absolute -inset-0.5 bg-gradient-to-r from-cyan-500 to-purple-600 rounded-full blur opacity-60 group-hover:opacity-100 transition duration-200"></div>
                        <button
                            onClick={handleGoToApp}
                            className="relative flex items-center gap-2 px-4 py-2 bg-slate-950 text-white text-sm font-semibold rounded-full leading-none hover:bg-slate-900 transition-colors duration-200"
                        >
                            {tNav('tryForFree')}
                            <ArrowRightIcon className="w-4 h-4 text-white" />
                        </button>
                      </div>
                   </div>
               )
           )}
        </div>
      </div>
    </header>
  );
}
