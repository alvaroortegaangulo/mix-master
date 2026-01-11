"use client";

import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";

type ViewportMountProps = {
  children: ReactNode;
  className?: string;
  id?: string;
  rootMargin?: string;
  threshold?: number;
  unmountOnExit?: boolean;
  initiallyMounted?: boolean;
};

export function ViewportMount({
  children,
  className,
  id,
  rootMargin = "200px 0px",
  threshold = 0.1,
  unmountOnExit = true,
  initiallyMounted = false,
}: ViewportMountProps) {
  const reduceMotion = useReducedMotion();
  const containerRef = useRef<HTMLDivElement | null>(null);
  const contentRef = useRef<HTMLDivElement | null>(null);

  const [isInView, setIsInView] = useState(initiallyMounted);
  const [hasBeenInView, setHasBeenInView] = useState(initiallyMounted);
  const [reservedHeight, setReservedHeight] = useState<number | null>(null);

  const shouldRender = unmountOnExit ? isInView : hasBeenInView;

  useEffect(() => {
    if (isInView) {
      setHasBeenInView(true);
    }
  }, [isInView]);

  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;

    if (typeof IntersectionObserver === "undefined") {
      setIsInView(true);
      setHasBeenInView(true);
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        setIsInView(entry.isIntersecting);
      },
      { threshold, rootMargin }
    );

    observer.observe(element);
    return () => observer.disconnect();
  }, [rootMargin, threshold]);

  useEffect(() => {
    const element = contentRef.current;
    if (!element) return;

    const updateHeight = () => {
      const nextHeight = Math.ceil(element.getBoundingClientRect().height);
      if (nextHeight > 0) setReservedHeight(nextHeight);
    };

    updateHeight();

    if (typeof ResizeObserver === "undefined") return;

    const observer = new ResizeObserver(updateHeight);
    observer.observe(element);
    return () => observer.disconnect();
  }, [shouldRender]);

  const transition = reduceMotion
    ? { duration: 0 }
    : ({ duration: 0.65, ease: [0.22, 1, 0.36, 1] } as any);

  return (
    <div
      ref={containerRef}
      id={id}
      className={className}
      style={reservedHeight ? { minHeight: `${reservedHeight}px` } : undefined}
    >
      {shouldRender ? (
        <motion.div
          ref={contentRef}
          initial={
            reduceMotion
              ? false
              : { opacity: 0, y: 22, filter: "blur(14px)" }
          }
          animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
          transition={transition}
        >
          {children}
        </motion.div>
      ) : null}
    </div>
  );
}

