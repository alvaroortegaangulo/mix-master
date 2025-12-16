"use client";

import { usePathname } from "next/navigation";
import { ModalProvider } from "../context/ModalContext";
import { Header } from "./Header";
import { Footer } from "./Footer";
import { Suspense } from "react";

export function GlobalLayoutClient({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  // Exclude studio pages from the global marketing header/footer
  const isStudio = pathname?.startsWith("/studio/");

  return (
    <ModalProvider>
      {!isStudio && (
        <Suspense fallback={<div className="h-16 bg-slate-950" />}>
          <Header />
        </Suspense>
      )}
      <main className={!isStudio ? "pt-16 min-h-screen flex flex-col" : "min-h-screen flex flex-col"}>
         {children}
      </main>
      {!isStudio && <Footer />}
    </ModalProvider>
  );
}
