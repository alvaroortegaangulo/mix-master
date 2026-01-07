"use client";

import type { ReactNode } from "react";
import { motion, useReducedMotion } from "framer-motion";

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
  const offset = reduceMotion ? 0 : y;
  const transition = reduceMotion
    ? { duration: 0 }
    : { duration, delay, ease: [0.22, 1, 0.36, 1] as any };

  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: offset }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once, amount }}
      transition={transition}
    >
      {children}
    </motion.div>
  );
}
