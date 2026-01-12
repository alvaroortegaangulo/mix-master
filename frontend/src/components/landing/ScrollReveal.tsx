"use client";

import type { ReactNode, CSSProperties } from "react";
import { useEffect, useMemo, useRef } from "react";
import { useReducedMotion } from "framer-motion";

type RevealDirection = "up" | "down" | "left" | "right";

type ScrollRevealProps = {
  children: ReactNode;
  className?: string;

  /** Delay (segundos) antes de iniciar la transición al entrar en viewport */
  delay?: number;

  /** Duración (segundos) de la transición */
  duration?: number;

  /**
   * Desplazamiento vertical (px) para "up" (por defecto) y "down".
   * - up: empieza más abajo (y>0) y sube hasta su sitio
   * - down: empieza más arriba (y>0) y baja hasta su sitio
   */
  y?: number;

  /** Desplazamiento horizontal (px) para "left" y "right" */
  x?: number;

  /** Si true, revela una sola vez; si false, alterna al entrar/salir */
  once?: boolean;

  /** Threshold de IO entre 0 y 1 (valores bajos disparan antes) */
  amount?: number;

  /**
   * rootMargin para emular el "offset" de AOS.
   * Ejemplo: "0px 0px -20% 0px" => dispara antes (cuando aún queda 20% de viewport)
   */
  rootMargin?: string;

  /**
   * Dirección opcional. Si ya pasas "reveal-left" / "reveal-right" en className,
   * eso tiene prioridad para mantener compatibilidad con tu uso actual.
   */
  direction?: RevealDirection;
};

type CachedObserver = {
  observer: IntersectionObserver;
  handlers: Map<Element, (entry: IntersectionObserverEntry) => void>;
};

const observerCache = new Map<string, CachedObserver>();

function clamp01(value: number) {
  if (Number.isNaN(value)) return 0;
  return Math.min(1, Math.max(0, value));
}

function getObserverKey(rootMargin: string, threshold: number) {
  return `${rootMargin}__${threshold}`;
}

function getCachedObserver(rootMargin: string, threshold: number): CachedObserver {
  const key = getObserverKey(rootMargin, threshold);
  const cached = observerCache.get(key);
  if (cached) return cached;

  const handlers = new Map<Element, (entry: IntersectionObserverEntry) => void>();

  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        const handler = handlers.get(entry.target);
        if (handler) handler(entry);
      }
    },
    { root: null, rootMargin, threshold }
  );

  const created: CachedObserver = { observer, handlers };
  observerCache.set(key, created);
  return created;
}

function releaseObserverIfEmpty(rootMargin: string, threshold: number) {
  const key = getObserverKey(rootMargin, threshold);
  const cached = observerCache.get(key);
  if (!cached) return;

  if (cached.handlers.size === 0) {
    cached.observer.disconnect();
    observerCache.delete(key);
  }
}

export function ScrollReveal({
  children,
  className,
  delay = 0,
  duration = 0.8,
  y = 30,
  x = 50,
  once = true,
  amount = 0.15,
  rootMargin = "0px 0px",
  direction = "up",
}: ScrollRevealProps) {
  const reduceMotion = useReducedMotion();
  const elementRef = useRef<HTMLDivElement | null>(null);
  const rafRef = useRef<number | null>(null);

  const { baseClass, effectiveDirection } = useMemo(() => {
    const hasLeft = className?.includes("reveal-left");
    const hasRight = className?.includes("reveal-right");

    // Compatibilidad: si ya pasas reveal-left/right en className, respétalo.
    if (hasLeft) return { baseClass: "", effectiveDirection: "left" as const };
    if (hasRight) return { baseClass: "", effectiveDirection: "right" as const };

    // Si direction pide left/right y el usuario no añadió clase, la añadimos.
    if (direction === "left") return { baseClass: "reveal-left", effectiveDirection: "left" as const };
    if (direction === "right") return { baseClass: "reveal-right", effectiveDirection: "right" as const };

    // Por defecto: vertical con `.reveal`
    return { baseClass: "reveal", effectiveDirection: direction === "down" ? ("down" as const) : ("up" as const) };
  }, [className, direction]);

  const revealStyle = useMemo(() => {
    const translateY = effectiveDirection === "down" ? -Math.abs(y) : Math.abs(y);

    return {
      "--reveal-delay": `${delay}s`,
      "--reveal-duration": `${duration}s`,
      "--reveal-translate": `${translateY}px`,
      "--reveal-distance-x": `${Math.abs(x)}px`,
    } as CSSProperties;
  }, [delay, duration, y, x, effectiveDirection]);

  useEffect(() => {
    const element = elementRef.current;
    if (!element) return;

    const addActive = () => {
      // Evita tocar nodos desconectados (transiciones de ruta, scroll rápido, etc.)
      if (!element.isConnected) return;
      // Mantengo "active" (tu CSS actual) y añado alias "is-revealed" por si quieres migrar luego.
      element.classList.add("active", "is-revealed");
    };

    const removeActive = () => {
      if (!element.isConnected) return;
      element.classList.remove("active", "is-revealed");
    };

    // Reduced motion: mostrar inmediatamente
    if (reduceMotion) {
      addActive();
      return;
    }

    // Fallback (entornos sin IO)
    if (typeof IntersectionObserver === "undefined") {
      addActive();
      return;
    }

    const threshold = clamp01(amount);
    const cached = getCachedObserver(rootMargin, threshold);

    const handler = (entry: IntersectionObserverEntry) => {
      if (entry.isIntersecting) {
        if (rafRef.current) cancelAnimationFrame(rafRef.current);

        // rAF: asegura que el estilo inicial (opacity/transform) pinte antes de activar la transición
        rafRef.current = requestAnimationFrame(() => {
          addActive();
          rafRef.current = null;

          if (once) {
            cached.observer.unobserve(entry.target);
            cached.handlers.delete(entry.target);
            releaseObserverIfEmpty(rootMargin, threshold);
          }
        });
      } else if (!once) {
        if (rafRef.current) {
          cancelAnimationFrame(rafRef.current);
          rafRef.current = null;
        }
        removeActive();
      }
    };

    cached.handlers.set(element, handler);
    cached.observer.observe(element);

    return () => {
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }

      cached.observer.unobserve(element);
      cached.handlers.delete(element);
      releaseObserverIfEmpty(rootMargin, threshold);
    };
  }, [reduceMotion, once, amount, rootMargin]);

  const combinedClass = [baseClass, className].filter(Boolean).join(" ");

  return (
    <div ref={elementRef} className={combinedClass} style={revealStyle}>
      {children}
    </div>
  );
}
