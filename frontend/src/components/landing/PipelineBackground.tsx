"use client";

import { motion } from "framer-motion";

type PipelineBackgroundProps = {
  className?: string;
};

export function PipelineBackground({ className }: PipelineBackgroundProps) {
  const paths = [
    "M0 100 C 200 100, 300 300, 600 300",
    "M0 200 C 250 200, 350 400, 700 400",
    "M0 400 C 300 400, 400 150, 800 150",
    "M0 600 C 400 600, 500 350, 900 350",
  ];

  return (
    <div
      className={`absolute inset-0 size-full overflow-hidden pointer-events-none z-0 ${className || ""}`}
      aria-hidden="true"
    >
      <svg
        className="absolute inset-0 size-full opacity-45"
        viewBox="0 0 900 600"
        fill="none"
        preserveAspectRatio="none"
      >
        {paths.map((path, index) => (
          <g key={index}>
            <path
              d={path}
              stroke="rgba(148, 163, 184, 0.12)"
              strokeWidth="2"
              fill="none"
            />

            <motion.path
              d={path}
              stroke={`url(#gradient-${index})`}
              strokeWidth="2"
              fill="none"
              initial={{ pathLength: 0, opacity: 0 }}
              animate={{
                pathLength: [0, 1, 1],
                pathOffset: [0, 0, 1],
                opacity: [0, 1, 0],
              }}
              transition={{
                duration: 6 + ((index * 13) % 4),
                repeat: Infinity,
                ease: "linear",
                delay: index * 2,
              }}
            />

            <defs>
              <linearGradient id={`gradient-${index}`} x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="transparent" />
                <stop offset="50%" stopColor="#fb7185" />
                <stop offset="100%" stopColor="transparent" />
              </linearGradient>
            </defs>
          </g>
        ))}
      </svg>

      <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(2,6,23,0)_0%,rgba(2,6,23,0.88)_70%)]" />
      <div className="absolute inset-0 bg-gradient-to-b from-slate-950/70 via-transparent to-slate-950/80" />
      <div className="absolute inset-0 backdrop-blur-[1px]" />
    </div>
  );
}
