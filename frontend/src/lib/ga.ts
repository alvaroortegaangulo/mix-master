"use client";

import { sendGAEvent } from "@next/third-parties/google";

export function gaEvent(name: string, params: Record<string, any> = {}) {
  // No mandes PII (email, nombre, etc.). Usa ids internos/UUID.
  sendGAEvent("event", name, params);
}
