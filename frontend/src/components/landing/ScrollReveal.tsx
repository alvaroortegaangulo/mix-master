"use client";

import type { ReactNode } from "react";
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
};

export function ScrollReveal({
  children,
  className = "",
  delay = 0,
  duration = 0.6,
  y = 30,
  x = 30,
  once = true,
  amount = 0.2, // Equivale a tu threshold antiguo
  direction = "up",
  blur = false, // Nuevo: añade un fade con blur si quieres
}: ScrollRevealProps) {
  // Respetar preferencias de accesibilidad del usuario
  const shouldReduceMotion = useReducedMotion();
  const speedFactor = 0.75;
  const effectiveDelay = delay * speedFactor;
  const effectiveDuration = duration * speedFactor;

  // Configuración de las direcciones para imitar AOS
  const getInitialCoords = () => {
    switch (direction) {
      case "up":
        return { y: y, x: 0 }; // Empieza abajo, sube a 0
      case "down":
        return { y: -y, x: 0 }; // Empieza arriba, baja a 0
      case "left":
        return { x: x, y: 0 }; // Empieza a la derecha, va a izq (0)
      case "right":
        return { x: -x, y: 0 }; // Empieza a la izquierda, va a der (0)
      default:
        return { y: y, x: 0 };
    }
  };

  const coords = getInitialCoords();

  const variants: Variants = {
    hidden: {
      opacity: 0,
      y: shouldReduceMotion ? 0 : coords.y,
      x: shouldReduceMotion ? 0 : coords.x,
      filter: blur ? "blur(4px)" : "blur(0px)",
    },
    visible: {
      opacity: 1,
      y: 0,
      x: 0,
      filter: "blur(0px)",
      transition: {
        duration: effectiveDuration,
        delay: effectiveDelay,
        ease: "easeOut", // Curva suave similar a AOS
      },
    },
  };

  return (
    <motion.div
      variants={variants}
      initial="hidden"
      whileInView="visible"
      viewport={{
        once: once,
        amount: amount,
        margin: "0px 0px -100px 0px", // Ajuste fino para que no active justo al borde
      }}
      className={className}
    >
      {children}
    </motion.div>
  );
}
