"use client";

import { useEffect } from "react";
import { usePathname, useSearchParams } from "next/navigation";

declare global {
  interface Window {
    gtag?: (...args: any[]) => void;
  }
}

export function GARouteTracker({ gaId }: { gaId: string }) {
  const pathname = usePathname();
  const searchParams = useSearchParams();

  useEffect(() => {
    if (!gaId) return;
    if (!window.gtag) return;

    const qs = searchParams?.toString();
    const page_path = qs ? `${pathname}?${qs}` : pathname;

    // Llamar "config" en cada navegación suele generar el page_view correspondiente
    window.gtag("config", gaId, {
      page_path,
      page_location: window.location.href,
    });
  }, [gaId, pathname, searchParams]);

  return null;
}
