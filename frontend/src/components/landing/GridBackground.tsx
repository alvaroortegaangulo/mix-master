"use client";

import { memo } from "react";

export const GridBackground = memo(function GridBackground() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none z-0">
      {/* Background Gradient: Black -> Teal -> Black */}
      <div className="absolute inset-0 bg-gradient-to-b from-black via-teal-900/30 to-black" />

      {/* 3D Container */}
      <div
        className="absolute inset-0 [perspective:1000px]"
        style={{
          maskImage: 'radial-gradient(ellipse at top, transparent 0%, black 60%)',
          WebkitMaskImage: 'radial-gradient(ellipse at top, transparent 0%, black 60%)'
        }}
      >
        {/* Infinite Plane */}
        <div
          className="absolute inset-[-100%] w-[300%] h-[300%] origin-top animate-grid-flow"
          style={{
            backgroundSize: '50px 50px',
            backgroundImage: `
              linear-gradient(to right, rgba(255, 255, 255, 0.05) 1px, transparent 1px),
              linear-gradient(to bottom, rgba(255, 255, 255, 0.05) 1px, transparent 1px)
            `,
            transform: 'rotateX(75deg) translateY(-100px) translateZ(-200px)',
          }}
        />
      </div>

      {/* Ambient Light / Vignette */}
      <div className="absolute inset-0 bg-gradient-to-t from-slate-950 via-transparent to-transparent" />
    </div>
  );
});
