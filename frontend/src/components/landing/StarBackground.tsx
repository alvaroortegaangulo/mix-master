"use client";

import { useEffect, useState } from "react";
import Particles, { initParticlesEngine } from "@tsparticles/react";
import { loadSlim } from "@tsparticles/slim";

export function StarBackground() {
  const [init, setInit] = useState(false);

  useEffect(() => {
    initParticlesEngine(async (engine) => {
      await loadSlim(engine);
    }).then(() => {
      setInit(true);
    });
  }, []);

  if (!init) return <div className="absolute inset-0 bg-[#020408] -z-10" />;

  const options = {
    background: {
      color: {
        value: "transparent", // Dejamos transparente para ver el degradado CSS detrás
      },
    },
    fpsLimit: 120,
    particles: {
      color: {
        value: "#ffffff",
      },
      links: {
        enable: false,
      },
      move: {
        direction: "none",
        enable: true,
        outModes: {
          default: "out",
        },
        random: true,
        speed: 0.4, // Un poco más rápido que antes para que se note la "vida"
        straight: false,
      },
      number: {
        density: {
          enable: true,
          // area: 800 es el estándar, lo bajamos un poco para tener más densidad sin saturar
          width: 1920,
          height: 1080,
        },
        value: 150, // Aumentado de 100 a 150 para más estrellas
      },
      opacity: {
        // Aumentamos la opacidad mínima para que ninguna estrella sea invisible
        value: { min: 0.3, max: 0.8 },
        animation: {
          enable: true,
          speed: 0.5,
          sync: false,
          mode: "auto"
        }
      },
      shape: {
        type: "circle",
      },
      size: {
        // Aumentamos el tamaño considerablemente (antes era max 1.5)
        value: { min: 1, max: 2.5 },
      },
    },
    detectRetina: true,
  };

  return (
    <div className="absolute inset-0 -z-10 overflow-hidden bg-[#020408]">

      {/* 1. ATMÓSFERA NEGRO-VIOLETA-NEGRO
          Usamos un gradiente lineal vertical.
          - 0% Negro
          - 50% Violeta profundo (rgba(124, 58, 237, 0.15))
          - 100% Negro
      */}
      <div
        className="absolute inset-0"
        style={{
          background: `linear-gradient(
            to bottom,
            #020408 0%,
            rgba(109, 40, 217, 0.25) 40%,
            rgba(124, 58, 237, 0.25) 50%,
            rgba(109, 40, 217, 0.25) 60%,
            #020408 100%
          )`
        }}
      />

      {/* 2. CAPA DE RUIDO (Opcional, para evitar banding en el degradado) */}
      <div className="absolute inset-0 opacity-[0.03] mix-blend-overlay pointer-events-none"
           style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E")` }}
      />

      {/* 3. PARTÍCULAS (ESTRELLAS) */}
      <Particles
        id="tsparticles-stars"
        className="absolute inset-0 w-full h-full"
        options={options}
      />
    </div>
  );
}
