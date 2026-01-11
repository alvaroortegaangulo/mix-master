"use client";

import { motion } from "framer-motion";

export function SonarBackground() {
  // Configuración "Dub": Menos anillos, más pesados y con más "aire" entre ellos.
  const ripples = [0, 1, 2];

  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none -z-10 flex items-center justify-center">

      {/* 1. FONDO ATMOSFÉRICO (El degradado Negro -> Ámbar -> Negro) */}
      <div className="absolute inset-0 bg-slate-950">
        <div className="absolute inset-0 bg-gradient-to-b from-slate-950 via-amber-900/20 to-slate-950 opacity-80" />
        {/* Añadimos un punto de luz radial extra en el centro para potenciar el efecto "foco" */}
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(217,119,6,0.15)_0%,transparent_50%)]" />
      </div>

      {/* 2. ONDAS DE SUBGRAVE (Ripples) */}
      {ripples.map((index) => (
        <motion.div
          key={index}
          className="absolute rounded-full border border-amber-500/30"
          initial={{
            width: "0px",
            height: "0px",
            opacity: 0,
            borderWidth: "4px" // Empieza grueso (el "golpe")
          }}
          animate={{
            width: ["0vw", "90vw"], // Se expande hasta casi llenar la pantalla
            height: ["0vw", "90vw"],
            opacity: [0.6, 0], // Se desvanece
            borderWidth: ["4px", "1px"], // Se afina mientras se expande
          }}
          transition={{
            duration: 8, // Lento y pesado (Dub feeling)
            repeat: Infinity,
            delay: index * 3, // Mucho espacio entre ondas para dar sensación de "bajos profundos"
            ease: [0.1, 0.5, 0.2, 1], // Curva Bezier personalizada: "Explosión" inicial rápida, expansión lenta
          }}
          style={{
             // Glow interior para que parezca energía pura
             boxShadow: "inset 0 0 40px rgba(245, 158, 11, 0.15), 0 0 20px rgba(245, 158, 11, 0.1)"
          }}
        />
      ))}

      {/* 3. NÚCLEO DEL SPEAKER (El centro que emite el sonido) */}
      {/* Un círculo estático difuso en el centro que da anclaje visual */}
      <div className="relative z-10 w-24 h-24 bg-amber-600/10 blur-2xl rounded-full animate-pulse" />

    </div>
  );
}
