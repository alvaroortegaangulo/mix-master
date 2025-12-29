"use client";

type ElectricDividerProps = {
  className?: string;
};

export function ElectricDivider({ className }: ElectricDividerProps) {
  return (
    <div className={`relative w-full py-3 ${className || ""}`} aria-hidden="true">
      <div className="relative mx-auto h-2.5 sm:h-3 w-[92%] max-w-6xl rounded-full overflow-hidden border border-teal-400/30 bg-slate-950/70 shadow-[0_0_18px_rgba(45,212,191,0.35)]">
        <div className="absolute inset-0 tube-core" />
        <div className="absolute inset-0 tube-flow" />
        <div className="absolute inset-0 tube-sparks" />
      </div>

      <style jsx>{`
        .tube-core {
          background: linear-gradient(
            90deg,
            rgba(15, 118, 110, 0.2) 0%,
            rgba(45, 212, 191, 0.45) 50%,
            rgba(15, 118, 110, 0.2) 100%
          );
        }

        .tube-flow {
          width: 200%;
          background: linear-gradient(
            90deg,
            rgba(45, 212, 191, 0) 0%,
            rgba(45, 212, 191, 0.2) 25%,
            rgba(45, 212, 191, 0.9) 50%,
            rgba(45, 212, 191, 0.2) 75%,
            rgba(45, 212, 191, 0) 100%
          );
          animation: electric-flow 2.8s linear infinite;
          mix-blend-mode: screen;
          opacity: 0.9;
          will-change: transform;
        }

        .tube-sparks {
          background-image: repeating-linear-gradient(
            90deg,
            rgba(45, 212, 191, 0) 0 12px,
            rgba(94, 234, 212, 0.65) 12px 14px,
            rgba(45, 212, 191, 0) 14px 26px
          );
          animation: electric-sparks 0.9s linear infinite;
          opacity: 0.5;
          mix-blend-mode: screen;
        }

        @keyframes electric-flow {
          0% {
            transform: translateX(-60%);
          }
          100% {
            transform: translateX(10%);
          }
        }

        @keyframes electric-sparks {
          0% {
            background-position: 0 0;
          }
          100% {
            background-position: 140px 0;
          }
        }
      `}</style>
    </div>
  );
}
