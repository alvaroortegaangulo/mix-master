"use client";

import type { ReactNode } from "react";
import { useEffect, useRef, useState, memo } from "react";
import { motion, useReducedMotion } from "framer-motion";

type ViewportMountProps = {
  children: ReactNode;
  className?: string;
  id?: string;
  rootMargin?: string;
  prefetchMargin?: string;
  threshold?: number;
  unmountOnExit?: boolean;
  initiallyMounted?: boolean;
  animateOnMount?: boolean;
  preload?: () => void;
};

function ViewportMountComponent({
  children,
  className,
  id,
  rootMargin = "100px 0px", // Reducido de 200px para mejor rendimiento
  prefetchMargin = "400px 0px", // Reducido de 700px para cargar más cerca
  threshold = 0.01, // Reducido de 0.1 para activar antes
  unmountOnExit = false, // Cambiado a false para evitar unmount/remount costosos
  initiallyMounted = false,
  animateOnMount = false, // Deshabilitado por defecto, ScrollReveal se encarga
  preload,
}: ViewportMountProps) {
  const reduceMotion = useReducedMotion();
  const containerRef = useRef<HTMLDivElement | null>(null);
  const observerRef = useRef<IntersectionObserver | null>(null);
  const prefetchObserverRef = useRef<IntersectionObserver | null>(null);

  const [isInView, setIsInView] = useState(initiallyMounted);
  const [hasBeenInView, setHasBeenInView] = useState(initiallyMounted);
  const [hasPrefetched, setHasPrefetched] = useState(false);

  const shouldRender = unmountOnExit ? isInView : hasBeenInView;

  // Efecto combinado para IntersectionObserver (optimizado)
  useEffect(() => {
    const element = containerRef.current;
    if (!element || typeof IntersectionObserver === "undefined") {
      setIsInView(true);
      setHasBeenInView(true);
      return;
    }

    // Observer principal para visibilidad
    observerRef.current = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsInView(true);
          setHasBeenInView(true);
        } else {
          setIsInView(false);
        }
      },
      { threshold, rootMargin }
    );

    observerRef.current.observe(element);

    return () => {
      observerRef.current?.disconnect();
    };
  }, [rootMargin, threshold]);

  // Efecto para prefetch (optimizado)
  useEffect(() => {
    if (!preload || hasPrefetched) return;
    const element = containerRef.current;
    if (!element || typeof IntersectionObserver === "undefined") {
      preload();
      setHasPrefetched(true);
      return;
    }

    prefetchObserverRef.current = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          preload();
          setHasPrefetched(true);
          prefetchObserverRef.current?.disconnect();
        }
      },
      { threshold: 0, rootMargin: prefetchMargin }
    );

    prefetchObserverRef.current.observe(element);

    return () => {
      prefetchObserverRef.current?.disconnect();
    };
  }, [preload, hasPrefetched, prefetchMargin]);

  // Animación simplificada y optimizada
  const shouldAnimate = animateOnMount && !reduceMotion && !hasBeenInView;

  return (
    <div
      ref={containerRef}
      id={id}
      className={className}
    >
      {shouldRender ? (
        shouldAnimate ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.3, ease: "easeOut" }}
          >
            {children}
          </motion.div>
        ) : (
          <>{children}</>
        )
      ) : null}
    </div>
  );
}

// Memoizar componente para evitar re-renders innecesarios
export const ViewportMount = memo(ViewportMountComponent);
