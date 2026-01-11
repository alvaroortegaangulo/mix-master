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
  }, [reduceMotion, once, amount]);

  const hasDirectionalClass =
    className?.includes("reveal-left") || className?.includes("reveal-right");
  const baseClass = hasDirectionalClass ? "" : "reveal";
  const combinedClass = [baseClass, className, isVisible ? "active" : ""]
    .filter(Boolean)
    .join(" ");

  return (
    <div ref={elementRef} className={combinedClass} style={revealStyle}>
      {children}
    </div>
  );
}
