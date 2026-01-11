"use client";

import type { ReactNode } from "react";
import { useEffect, useRef } from "react";
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
      sharedInstance = mod.default();
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

  useEffect(() => {
    if (reduceMotion) return;

    let active = true;
    const target = elementRef.current;
    if (!target) return;

    const distanceValue = `${Math.abs(y)}px`;
    const originValue = y < 0 ? "top" : "bottom";

    getScrollReveal().then((sr) => {
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
    });

    return () => {
      active = false;
      if (cleanupTargetRef.current && instanceRef.current) {
        instanceRef.current.clean(cleanupTargetRef.current);
      }
    };
  }, [reduceMotion, delay, duration, y, once, amount]);

  return (
    <div ref={elementRef} className={className}>
      {children}
    </div>
  );
}
