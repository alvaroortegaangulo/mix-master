"use client";

import { motion } from "framer-motion";

export function PipelineBackground() {
  // Configuración de las "tuberías"
  const paths = [
    "M0 100 C 200 100, 300 300, 600 300", // Tubería 1
    "M0 200 C 250 200, 350 400, 700 400", // Tubería 2
    "M0 400 C 300 400, 400 150, 800 150", // Tubería 3
    "M0 600 C 400 600, 500 350, 900 350", // Tubería 4
  ];

  return (
    <div className="absolute inset-0 size-full overflow-hidden pointer-events-none">

      {/* EL TRUCO "PRO": La Máscara de Opacidad
        Esto crea el efecto "difuminado" en los bordes y centro,
        haciendo que las tuberías desaparezcan suavemente donde va el texto.
      */}
      <div
        className="absolute inset-0 z-10 bg-slate-950"
        style={{
          maskImage: 'radial-gradient(circle at center, transparent 30%, black 100%)',
          WebkitMaskImage: 'radial-gradient(circle at center, transparent 30%, black 100%)'
        }}
      />

      <svg
        className="absolute inset-0 size-full opacity-30" // Opacidad baja general
        viewBox="0 0 900 600"
        fill="none"
        preserveAspectRatio="none"
      >
        {paths.map((path, i) => (
          <g key={i}>
            {/* Tubería Base (oscura/sutil) */}
            <path
              d={path}
              stroke="rgba(148, 163, 184, 0.1)" // Slate-400 muy transparente
              strokeWidth="2"
              fill="none"
            />

            {/* Flujo de energía dentro de la tubería */}
            <motion.path
              d={path}
              stroke={`url(#gradient-${i})`} // Gradiente para cada tubo
              strokeWidth="2"
              fill="none"
              initial={{ pathLength: 0, opacity: 0 }}
              animate={{
                pathLength: [0, 1, 1], // Crece -> Se llena -> Desaparece
                pathOffset: [0, 0, 1], // Efecto de flujo
                opacity: [0, 1, 0]
              }}
              transition={{
                duration: 6 + ((i * 13) % 4), // Duración determinista (6-9s) para evitar hidratación mismatch
                repeat: Infinity,
                ease: "linear",
                delay: i * 2, // Retraso escalonado
              }}
            />

            <defs>
              <linearGradient id={`gradient-${i}`} x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="transparent" />
                <stop offset="50%" stopColor="#2dd4bf" /> {/* Teal-400 */}
                <stop offset="100%" stopColor="transparent" />
              </linearGradient>
            </defs>
          </g>
        ))}
      </svg>

      {/* Capa extra de desenfoque CSS para suavizar las líneas vectorial (opcional) */}
      <div className="absolute inset-0 backdrop-blur-[1px]" />
    </div>
  );
}
