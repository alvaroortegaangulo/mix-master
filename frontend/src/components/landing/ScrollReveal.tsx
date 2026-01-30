"use client";

import type { ReactNode } from "react";
import { memo } from "react";
import { motion, useReducedMotion, type Variants } from "framer-motion";

type RevealDirection = "up" | "down" | "left" | "right";

type ScrollRevealProps = {
  children: ReactNode;
  className?: string;
  /** Delay en segundos */
  delay?: number;
  /** Duración en segundos */
  duration?: number;
  /** Distancia de desplazamiento vertical en px */
  y?: number;
  /** Distancia de desplazamiento horizontal en px */
  x?: number;
  /** Si true, la animación ocurre solo la primera vez */
  once?: boolean;
  /** Margen del viewport (ej: "-20%" para que active antes de llegar al final) */
  viewportMargin?: string;
  /** Cantidad de elemento visible para activar (0 a 1) */
  amount?: number | "some" | "all";
  /** Dirección de la animación */
  direction?: RevealDirection;
  /** Blur opcional para efecto moderno */
  blur?: boolean;
  /** Disable animation completely for performance */
  disabled?: boolean;
};

function ScrollRevealComponent({
  children,
  className = "",
  delay = 0,
  duration = 0.4, // Reducido de 0.6 a 0.4 para más fluidez
  y = 20, // Reducido de 30 a 20 para animación más sutil
  x = 20, // Reducido de 30 a 20
  once = true,
  amount = 0.05, // Reducido de 0.12 a 0.05 para activar antes
  direction = "up",
  viewportMargin = "0px 0px 200px 0px", // Aumentado para activar más temprano
  blur = false,
  disabled = false,
}: ScrollRevealProps) {
  // Respetar preferencias de accesibilidad del usuario
  const shouldReduceMotion = useReducedMotion();

  // Si está deshabilitado o reduce motion, no animar
  if (disabled || shouldReduceMotion) {
    return <div className={className}>{children}</div>;
  }

  const speedFactor = 0.7; // Aumentado de 0.6 a 0.7 para animaciones más rápidas
  const effectiveDelay = delay * speedFactor;
  const effectiveDuration = duration * speedFactor;

  // Configuración de las direcciones (optimizado con switch directo)
  const getInitialCoords = (): { y: number; x: number } => {
    switch (direction) {
      case "up":
        return { y, x: 0 };
      case "down":
        return { y: -y, x: 0 };
      case "left":
        return { x, y: 0 };
      case "right":
        return { x: -x, y: 0 };
      default:
        return { y, x: 0 };
    }
  };

  const coords = getInitialCoords();

  // Variants optimizados sin blur por defecto (mejor rendimiento)
  const variants: Variants = {
    hidden: {
      opacity: 0,
      y: coords.y,
      x: coords.x,
      ...(blur && { filter: "blur(4px)" }),
    },
    visible: {
      opacity: 1,
      y: 0,
      x: 0,
      ...(blur && { filter: "blur(0px)" }),
      transition: {
        duration: effectiveDuration,
        delay: effectiveDelay,
        ease: [0.25, 0.1, 0.25, 1], // ease-out optimizado
      },
    },
  };

  return (
    <motion.div
      variants={variants}
      initial="hidden"
      whileInView="visible"
      viewport={{
        once,
        amount,
        margin: viewportMargin,
      }}
      className={className}
      style={{
        willChange: "opacity, transform",
      }}
    >
      {children}
    </motion.div>
  );
}

// Memoizar para evitar re-renders innecesarios
export const ScrollReveal = memo(ScrollRevealComponent);
