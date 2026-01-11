"use client";

import { motion } from "framer-motion";

export function SonarBackground() {
  // Creamos 4 círculos que se expanden
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none z-0 bg-slate-950 flex items-center justify-center">
      {/* Background Gradient: Black top/bottom, Amber center */}
      <div className="absolute inset-0 bg-gradient-to-b from-slate-950 via-amber-900/10 to-slate-950" />

      {/* Radial accent to enhance the center amber glow */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(245,158,11,0.05)_0%,transparent_60%)]" />

      {[0, 1, 2, 3].map((index) => (
        <motion.div
          key={index}
          className="absolute border border-amber-500/10 rounded-full"
          initial={{ width: "0vw", height: "0vw", opacity: 0.8 }}
          animate={{
            width: ["0vw", "100vw"],
            height: ["0vw", "100vw"],
            opacity: [0.5, 0],
          }}
          transition={{
            duration: 10,
            repeat: Infinity,
            delay: index * 2.5, // Retraso escalonado
            ease: "linear",
          }}
          style={{
             // Añadimos un borde sutil brillante (Amber)
             boxShadow: "inset 0 0 20px rgba(245, 158, 11, 0.05)"
          }}
        />
      ))}

      {/* Centro brillante sutil */}
      <div className="absolute w-32 h-32 bg-amber-500/10 blur-3xl rounded-full" />
    </div>
  );
}
