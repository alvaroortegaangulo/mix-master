"use client";

type ElectricDividerProps = {
  className?: string;
};

export function ElectricDivider({ className }: ElectricDividerProps) {
  return (
    <div className={`relative w-full flex justify-center ${className || ""}`} aria-hidden="true">
      <div className="relative h-0.5 sm:h-1 overflow-hidden" style={{ width: "2cm" }}>
        <div className="absolute inset-0 divider-base" />
        <div className="absolute inset-0 divider-flow" />
      </div>

      <style jsx>{`
        .divider-base {
          background: linear-gradient(
            90deg,
            rgba(45, 212, 191, 0.2) 0%,
            rgba(45, 212, 191, 0.7) 50%,
            rgba(45, 212, 191, 0.2) 100%
          );
          box-shadow: 0 0 14px rgba(45, 212, 191, 0.35);
        }

        .divider-flow {
          width: 200%;
          background: linear-gradient(
            90deg,
            rgba(45, 212, 191, 0) 0%,
            rgba(94, 234, 212, 0.25) 30%,
            rgba(94, 234, 212, 0.95) 50%,
            rgba(94, 234, 212, 0.25) 70%,
            rgba(45, 212, 191, 0) 100%
          );
          animation: electric-flow 3.1s linear infinite;
          opacity: 0.85;
          will-change: transform;
        }

        @keyframes electric-flow {
          0% {
            transform: translateX(-60%);
          }
          100% {
            transform: translateX(10%);
          }
        }
      `}</style>
    </div>
  );
}
