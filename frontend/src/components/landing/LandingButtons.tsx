"use client";

import { useHomeView } from "../../context/HomeViewContext";
import { PlayCircleIcon } from "@heroicons/react/24/solid";

export function HeroTryItButton() {
  const { handleTryIt } = useHomeView();

  return (
    <button
      onClick={handleTryIt}
      className="group relative inline-flex items-center justify-center gap-2 overflow-hidden rounded-full bg-teal-400 px-8 py-4 text-lg font-bold text-slate-950 transition-all hover:bg-teal-300 hover:scale-105 focus:outline-none focus:ring-4 focus:ring-teal-500/30"
    >
      {/* Simple Circle Icon */}
      <svg
        width="24"
        height="24"
        viewBox="0 0 24 24"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="stroke-current stroke-2"
      >
        <circle cx="12" cy="12" r="9" />
      </svg>
      <span>Mix my Tracks</span>
    </button>
  );
}

export function DemoScrollButton() {
  return (
    <button
      onClick={() => document.getElementById('benefits')?.scrollIntoView({ behavior: 'smooth' })}
      className="group relative inline-flex items-center justify-center gap-2 overflow-hidden rounded-full bg-slate-800/80 px-8 py-4 text-lg font-semibold text-white transition-all hover:bg-slate-700 hover:scale-105 focus:outline-none focus:ring-4 focus:ring-purple-500/30 border border-slate-700"
    >
      <PlayCircleIcon className="h-6 w-6 text-white" />
      <span>Listen to Demos</span>
    </button>
  );
}

export function BottomTryItButton() {
  const { handleTryIt } = useHomeView();

  return (
    <button
      onClick={handleTryIt}
      className="bg-white text-slate-950 px-10 py-4 rounded-full text-lg font-bold hover:bg-teal-50 transition shadow-xl shadow-teal-500/10"
    >
      Start Mixing for Free
    </button>
  );
}
