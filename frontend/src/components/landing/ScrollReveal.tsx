"use client";

import type { ReactNode } from "react";
import { useEffect, useMemo, useRef } from "react";
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

export function ScrollReveal({
  children,
  className,
  delay = 0,
  duration = 0.8,
  y = 30,
  once = true,
  amount = 0.15,
}: ScrollRevealProps) {
  const reduceMotion = useReducedMotion();
  const elementRef = useRef<HTMLDivElement | null>(null);
  const activationTimeoutRef = useRef<number | null>(null);

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
    const element = elementRef.current;
    if (!element) return;

    // Immediately show if reduced motion is enabled
    if (reduceMotion) {
      element.classList.add("active");
      return;
    }

    if (typeof IntersectionObserver === "undefined") {
      element.classList.add("active");
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          if (activationTimeoutRef.current) {
            window.clearTimeout(activationTimeoutRef.current);
          }

          activationTimeoutRef.current = window.setTimeout(() => {
            entry.target.classList.add("active");
          }, 0);

          if (once) observer.unobserve(entry.target);
        } else if (!once) {
          if (activationTimeoutRef.current) {
            window.clearTimeout(activationTimeoutRef.current);
            activationTimeoutRef.current = null;
          }

          entry.target.classList.remove("active");
        }
      },
      { threshold: Math.min(Math.max(amount, 0), 1) }
    );

    observer.observe(element);
    return () => {
      observer.disconnect();
      if (activationTimeoutRef.current) {
        window.clearTimeout(activationTimeoutRef.current);
        activationTimeoutRef.current = null;
      }
    };
  }, [reduceMotion, once, amount]);

  // Determine base class if not provided in className
  const hasDirectionalClass =
    className?.includes("reveal-left") || className?.includes("reveal-right");
  const baseClass = hasDirectionalClass ? "" : "reveal";

  const combinedClass = [baseClass, className].filter(Boolean).join(" ");

  return (
    <div ref={elementRef} className={combinedClass} style={revealStyle}>
      {children}
    </div>
  );
}
