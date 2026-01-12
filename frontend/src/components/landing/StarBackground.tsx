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
    // CORRECCIÓN CRÍTICA: Desactivamos el modo pantalla completa para que
    // las partículas se limiten solo al contenedor padre (la sección Pipeline).
    fullScreen: {
      enable: false,
      zIndex: -1, // Aseguramos que quede detrás del contenido
    },
    background: {
      color: {
        value: "transparent",
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
        speed: 0.4,
        straight: false,
      },
      number: {
        density: {
          enable: true,
          width: 1920,
          height: 1080,
        },
        value: 150,
      },
      opacity: {
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
        value: { min: 1, max: 2.5 },
      },
    },
    detectRetina: true,
  };

  return (
    // El contenedor padre ya tiene relative/absolute en la sección que lo llama,
    // pero aquí aseguramos que ocupe el 100% de ESE contenedor.
    <div className="absolute inset-0 -z-10 overflow-hidden bg-[#020408]">

      {/* 1. ATMÓSFERA NEGRO-VIOLETA-NEGRO */}
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

      {/* 2. CAPA DE RUIDO */}
      <div className="absolute inset-0 opacity-[0.03] mix-blend-overlay pointer-events-none"
           style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E")` }}
      />

      {/* 3. PARTÍCULAS (Confinadas gracias a fullScreen: false) */}
      <Particles
        id="tsparticles-stars"
        className="absolute inset-0 w-full h-full"
        options={options}
      />
    </div>
  );
}