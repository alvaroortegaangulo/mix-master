"use client";

declare global {
  interface Window {
    gtag?: (...args: any[]) => void;
  }
}

export function gaEvent(name: string, params: Record<string, any> = {}) {
  if (typeof window === "undefined") return;
  if (!window.gtag) return;
  // No mandes PII (email, nombre, etc.). Usa ids internos/UUID.
  window.gtag("event", name, params);
}
