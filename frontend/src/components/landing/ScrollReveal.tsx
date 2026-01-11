"use client";

import type { ReactNode } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useReducedMotion } from "framer-motion";

type ScrollRevealProps = {
  children: ReactNode;
  className?: string;
  delay?: number;
  duration?: number;
  y?: number;
  once?: boolean;
  amount?: number;
};

type ScrollRevealInstance = ReturnType<typeof import("scrollreveal").default>;

let sharedInstance: ScrollRevealInstance | null = null;
let sharedPromise: Promise<ScrollRevealInstance> | null = null;

const getScrollReveal = () => {
  if (sharedInstance) {
    return Promise.resolve(sharedInstance);
  }
  if (!sharedPromise) {
    sharedPromise = import("scrollreveal").then((mod) => {
      const factory = (mod as { default?: () => ScrollRevealInstance }).default ?? mod;
      sharedInstance = factory();
      return sharedInstance;
    });
  }
  return sharedPromise;
};

export function ScrollReveal({
  children,
  className,
  delay = 0,
  duration = 0.6,
  y = 18,
  once = true,
  amount = 0.25,
}: ScrollRevealProps) {
  const reduceMotion = useReducedMotion();
  const elementRef = useRef<HTMLDivElement | null>(null);
  const cleanupTargetRef = useRef<Element | null>(null);
  const instanceRef = useRef<ScrollRevealInstance | null>(null);
  const [useFallback, setUseFallback] = useState(false);
  const [isVisible, setIsVisible] = useState(reduceMotion);

  const revealStyle = useMemo(
    () =>
      ({
        "--reveal-delay": `${delay}s`,
        "--reveal-duration": `${duration}s`,
        "--reveal-translate": `${y}px`,
      }) as React.CSSProperties,
    [delay, duration, y]
  );

  useEffect(() => {
    if (reduceMotion) {
      setIsVisible(true);
      return;
    }

    let active = true;
    const target = elementRef.current;
    if (!target) return;
    let fallbackTimer: number | null = null;

    const distanceValue = `${Math.abs(y)}px`;
    const originValue = y < 0 ? "top" : "bottom";
    const enableFallback = () => {
      if (!active) return;
      if (elementRef.current) {
        const rect = elementRef.current.getBoundingClientRect();
        const inView = rect.top < window.innerHeight && rect.bottom > 0;
        setIsVisible(inView);
      }
      setUseFallback(true);
    };

    getScrollReveal()
      .then((sr) => {
        if (!active || !elementRef.current) return;

        instanceRef.current = sr;
        cleanupTargetRef.current = elementRef.current;

        sr.reveal(elementRef.current, {
          delay: Math.round(delay * 1000),
          duration: Math.round(duration * 1000),
          distance: distanceValue,
          origin: originValue,
          opacity: 0,
          easing: "cubic-bezier(0.22, 1, 0.36, 1)",
          viewFactor: amount,
          reset: !once,
        });

        sr.sync();

        fallbackTimer = window.setTimeout(() => {
          const hasBinding = Boolean(
            elementRef.current?.getAttribute("data-sr-id")
          );
          if (!hasBinding) {
            enableFallback();
          }
        }, 200);
      })
      .catch(() => {
        enableFallback();
      });

    return () => {
      active = false;
      if (fallbackTimer) {
        window.clearTimeout(fallbackTimer);
      }
      if (cleanupTargetRef.current && instanceRef.current) {
        instanceRef.current.clean(cleanupTargetRef.current);
      }
    };
  }, [reduceMotion, delay, duration, y, once, amount]);

  useEffect(() => {
    if (!useFallback || reduceMotion) return;

    const target = elementRef.current;
    if (!target || typeof IntersectionObserver === "undefined") {
      setIsVisible(true);
      return;
    }

    const threshold = Math.min(Math.max(amount, 0), 1);
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
          if (once) observer.unobserve(entry.target);
        } else if (!once) {
          setIsVisible(false);
        }
      },
      { threshold }
    );

    observer.observe(target);
    return () => observer.disconnect();
  }, [useFallback, reduceMotion, once, amount]);

  return (
    <div
      ref={elementRef}
      className={className}
      data-reveal-fallback={useFallback ? "true" : undefined}
      data-reveal-visible={useFallback && isVisible ? "true" : undefined}
      style={useFallback ? revealStyle : undefined}
    >
      {children}
    </div>
  );
}
