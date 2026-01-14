"use client";

import { memo, useEffect, useState } from "react";
import { motion } from "framer-motion";

export const ComplexPipelineBackground = memo(function ComplexPipelineBackground() {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Configuración de las "tuberías" (Paths SVG complejos)
  // Usamos Curvas de Bézier cúbicas (C) para suavidad extrema.
  // M = Move to, C = Cubic Bezier (ControlPoint1, ControlPoint2, EndPoint)
  const pipes = [
    // Capa Fondo (Oscuras, Gruesas, Lentas)
    { d: "M-100 600 C 200 600, 400 200, 800 200 S 1200 600, 1600 600", width: 4, opacity: 0.1, speed: 25, delay: 0 },
    { d: "M-100 300 C 300 300, 500 800, 900 800 S 1400 200, 1800 200", width: 5, opacity: 0.08, speed: 30, delay: 2 },
    { d: "M-100 800 C 400 800, 600 100, 1000 100 S 1500 900, 1900 900", width: 6, opacity: 0.07, speed: 35, delay: 4 },

    // Capa Media (Color base, Grosor medio)
    { d: "M0 400 C 100 400, 300 500, 600 500 S 1000 300, 1400 300", width: 2, opacity: 0.3, speed: 12, delay: 0 },
    { d: "M0 200 C 200 200, 400 600, 800 600 S 1200 200, 1600 200", width: 2, opacity: 0.25, speed: 15, delay: 1.5 },
    { d: "M0 700 C 300 700, 500 400, 900 400 S 1300 600, 1700 600", width: 2.5, opacity: 0.2, speed: 18, delay: 3 },
    { d: "M-50 100 C 250 100, 450 450, 850 450 S 1350 150, 1750 150", width: 2, opacity: 0.3, speed: 14, delay: 5 },

    // Capa Frontal (Brillantes, Finas, Rápidas - "Data streams")
    { d: "M0 450 C 150 450, 350 550, 650 550 S 1050 350, 1450 350", width: 1, opacity: 0.6, speed: 6, delay: 1 },
    { d: "M0 250 C 250 250, 450 650, 850 650 S 1250 250, 1650 250", width: 1, opacity: 0.5, speed: 8, delay: 2 },
    { d: "M-100 500 C 200 500, 400 300, 800 300 S 1200 500, 1600 500", width: 1.5, opacity: 0.4, speed: 7, delay: 0.5 },
  ];

  if (!mounted) return <div className="absolute inset-0 bg-slate-950" />;

  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none -z-10 bg-[#020408]">

      {/* 1. ATMÓSFERA VOLUMÉTRICA (Negro -> Burdeos -> Negro)
          Este es el fondo base que pediste.
      */}
      <div
        className="absolute inset-0 opacity-90"
        style={{
          background: `linear-gradient(
            to bottom,
            #020408 0%,
            rgba(120, 20, 35, 0.1) 20%,
            rgba(120, 20, 35, 0.35) 50%,
            rgba(120, 20, 35, 0.1) 80%,
            #020408 100%
          )`
        }}
      />

      {/* 2. TEXTURA DE RUIDO (Noise)
          Para dar ese toque "analógico" y profesional, rompiendo el banding del degradado.
      */}
      <div
        className="absolute inset-0 opacity-[0.15] mix-blend-overlay"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E")`
        }}
      />

      {/* 3. SISTEMA DE TUBERÍAS (SVG) */}
      <svg
        className="absolute inset-0 w-full h-full"
        viewBox="0 0 1600 900"
        preserveAspectRatio="xMidYMid slice"
        fill="none"
      >
        <defs>
          {/* Gradiente lineal para los tubos estáticos (Burdeos sutil) */}
          <linearGradient id="pipe-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="rgba(120, 20, 35, 0)" />
            <stop offset="50%" stopColor="rgba(160, 35, 55, 0.5)" />
            <stop offset="100%" stopColor="rgba(120, 20, 35, 0)" />
          </linearGradient>

          {/* Gradiente para el FLUJO de energía (Rosa/Blanco brillante) */}
          <linearGradient id="flow-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="transparent" />
            <stop offset="50%" stopColor="#fda4af" /> {/* Rose-300 */}
            <stop offset="100%" stopColor="transparent" />
          </linearGradient>

          {/* Máscara de desvanecimiento para ocultar bordes duros */}
          <mask id="fade-mask">
            <rect x="0" y="0" width="1600" height="900" fill="url(#mask-gradient)" />
          </mask>
          <linearGradient id="mask-gradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="black" />
            <stop offset="0.2" stopColor="white" />
            <stop offset="0.8" stopColor="white" />
            <stop offset="1" stopColor="black" />
          </linearGradient>
        </defs>

        <g mask="url(#fade-mask)">
          {pipes.map((pipe, i) => (
            <g key={i}>
              {/* Tubería Base (Estructura física) */}
              <path
                d={pipe.d}
                stroke="url(#pipe-gradient)"
                strokeWidth={pipe.width}
                strokeOpacity={pipe.opacity}
                fill="none"
              />

              {/* Energía Fluyendo (Animación) */}
              <motion.path
                d={pipe.d}
                stroke="url(#flow-gradient)"
                strokeWidth={pipe.width} // Un poco más fino para que parezca interior
                strokeLinecap="round"
                fill="none"
                initial={{ pathLength: 0, pathOffset: 0, opacity: 0 }}
                animate={{
                  pathLength: [0, 0.3, 0],   // Crece, viaja, desaparece
                  pathOffset: [0, 1, 1],     // Se mueve a lo largo del path
                  opacity: [0, 1, 0]         // Fade in/out
                }}
                transition={{
                  duration: pipe.speed,
                  repeat: Infinity,
                  ease: "linear",
                  delay: pipe.delay,
                  repeatDelay: Math.random() * 2 // Aleatoriedad para naturalidad
                }}
                style={{ filter: "blur(2px)" }} // Glow suave
              />
            </g>
          ))}
        </g>
      </svg>

      {/* 4. VIÑETA SUTIL (Integración final) */}
      <div className="absolute inset-0 bg-gradient-to-t from-[#020408] via-transparent to-[#020408] opacity-80" />
    </div>
  );
});
