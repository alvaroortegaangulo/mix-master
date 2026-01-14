"use client";

import { memo } from "react";
import { motion } from "framer-motion";

export const AuroraBackground = memo(function AuroraBackground({ className }: { className?: string }) {
  return (
    <div className={`absolute inset-0 overflow-hidden pointer-events-none -z-10 bg-[#020408] ${className || ""}`}>

      {/* 1. FONDO BASE: El degradado "Negro - Ámbar - Negro" estático
          Esto garantiza que siempre haya color en el centro, incluso si la animación es sutil.
      */}
      <div
        className="absolute inset-0 opacity-80"
        style={{
          background: `linear-gradient(
            to bottom,
            #020408 0%,
            rgba(69, 10, 10, 0) 15%,
            rgba(180, 83, 9, 0.15) 40%,
            rgba(245, 158, 11, 0.25) 50%,
            rgba(180, 83, 9, 0.15) 60%,
            rgba(69, 10, 10, 0) 85%,
            #020408 100%
          )`
        }}
      />

      {/* 2. AURORA VIVA (Luces en movimiento)
          Usamos mix-blend-screen para que los colores brillen intensamente sobre el fondo oscuro.
      */}
      <div className="absolute inset-0 mix-blend-screen">

        {/* Orbe 1: El Núcleo Ámbar (Lento y Grande) */}
        <motion.div
          animate={{
            scale: [1, 1.2, 1],
            opacity: [0.3, 0.5, 0.3],
            x: ["-5%", "5%", "-5%"],
          }}
          transition={{
            duration: 15,
            repeat: Infinity,
            ease: "easeInOut",
          }}
          className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[60vw] h-[40vw] bg-amber-600 rounded-full blur-[120px]"
        />

        {/* Orbe 2: Acento Naranja (Movimiento lateral) */}
        <motion.div
          animate={{
            x: ["-20%", "20%", "-20%"],
            y: ["-10%", "10%", "-10%"],
            scale: [1, 1.1, 1],
          }}
          transition={{
            duration: 20,
            repeat: Infinity,
            ease: "easeInOut",
          }}
          className="absolute top-[30%] left-[20%] w-[50vw] h-[50vw] bg-orange-700/60 rounded-full blur-[100px] opacity-60"
        />

        {/* Orbe 3: Brillo Dorado (Pequeño y más rápido) */}
        <motion.div
          animate={{
            scale: [1, 1.3, 1],
            opacity: [0.2, 0.6, 0.2],
          }}
          transition={{
            duration: 8,
            repeat: Infinity,
            ease: "easeInOut",
          }}
          className="absolute bottom-[30%] right-[20%] w-[40vw] h-[40vw] bg-amber-400/40 rounded-full blur-[90px]"
        />
      </div>

      {/* 3. TEXTURA DE RUIDO (Noise)
          Crucial para que los degradados se vean profesionales y no tengan "banding" (rayas).
      */}
      <div
        className="absolute inset-0 opacity-[0.07] mix-blend-overlay"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E")`
        }}
      />

      {/* 4. VIÑETA FINAL (El corte limpio)
          Asegura que el texto que pongas encima se lea perfectamente y
          que la transición a la siguiente sección sea invisible.
      */}
      <div className="absolute inset-0 bg-gradient-to-b from-[#020408] via-transparent to-[#020408]" />

    </div>
  );
});
