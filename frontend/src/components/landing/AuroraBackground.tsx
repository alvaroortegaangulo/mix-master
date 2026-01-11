"use client";

import { motion } from "framer-motion";

export function AuroraBackground({ className }: { className?: string }) {
  return (
    <div className={`absolute inset-0 overflow-hidden pointer-events-none z-0 ${className || ""}`}>

      {/* Fondo base oscuro */}
      <div className="absolute inset-0 bg-slate-950" />

      <div className="absolute inset-0 opacity-40">
        {/* Orbe 1: Violeta (Tu color primario) */}
        <motion.div
          animate={{
            scale: [1, 1.2, 1],
            x: [0, 100, 0],
            y: [0, 50, 0],
          }}
          transition={{
            duration: 20,
            repeat: Infinity,
            repeatType: "reverse",
            ease: "easeInOut",
          }}
          className="absolute top-[-10%] left-[-10%] w-[70vw] h-[70vw] bg-violet-600/30 rounded-full mix-blend-screen filter blur-[100px] opacity-50"
        />

        {/* Orbe 2: Teal (Tu color secundario) */}
        <motion.div
          animate={{
            scale: [1, 1.1, 1],
            x: [0, -100, 0],
            y: [0, 100, 0],
          }}
          transition={{
            duration: 25,
            repeat: Infinity,
            repeatType: "reverse",
            ease: "easeInOut",
            delay: 2,
          }}
          className="absolute top-[20%] right-[-20%] w-[60vw] h-[60vw] bg-teal-500/20 rounded-full mix-blend-screen filter blur-[100px] opacity-50"
        />

        {/* Orbe 3: Ámbar/Naranja (Acento sutil para calidez) */}
        <motion.div
          animate={{
            scale: [1, 1.3, 1],
            x: [0, 50, 0],
            y: [0, -50, 0],
          }}
          transition={{
            duration: 30,
            repeat: Infinity,
            repeatType: "reverse",
            ease: "easeInOut",
            delay: 5,
          }}
          className="absolute bottom-[-20%] left-[20%] w-[50vw] h-[50vw] bg-amber-600/10 rounded-full mix-blend-screen filter blur-[120px] opacity-40"
        />
      </div>

      {/* TEXTURA DE RUIDO (El toque secreto "Pro") */}
      <div
        className="absolute inset-0 opacity-[0.03] mix-blend-overlay pointer-events-none"
        style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E")`,
        }}
      />

      {/* Viñeta para integrar con el contenido */}
      <div className="absolute inset-0 bg-gradient-to-b from-slate-950/80 via-transparent to-slate-950/80" />
    </div>
  );
}
