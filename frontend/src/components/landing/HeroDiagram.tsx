"use client";

import { useEffect, useRef, type ElementType } from "react";
import {
  AdjustmentsVerticalIcon,
  ArrowsRightLeftIcon,
  ChevronDownIcon,
  Cog6ToothIcon,
  FireIcon,
  LightBulbIcon,
  ScaleIcon,
  SparklesIcon,
  SpeakerWaveIcon
} from "@heroicons/react/24/outline";

type HeroNode = {
  id: string;
  positionClass: string;
  icon: ElementType;
  iconClassName: string;
  iconWrapperClass: string;
  pulseClassName: string;
  windowClass: string;
  windowAccentClass?: string;
  title: string;
  description: string;
  showBadge?: boolean;
  badgeClassName?: string;
};

const nodes: HeroNode[] = [
  {
    id: "mixing",
    positionClass: "top-[8%] left-1/2 -translate-x-1/2 -translate-y-1/2",
    icon: AdjustmentsVerticalIcon,
    iconClassName: "h-5 w-5 lg:h-4 lg:w-4 xl:h-5 xl:w-5 2xl:h-6 2xl:w-6 text-cyan-200",
    iconWrapperClass:
      "h-12 w-12 lg:h-11 lg:w-11 xl:h-12 xl:w-12 2xl:h-14 2xl:w-14 rounded-2xl border border-cyan-400/30 bg-slate-950/70 shadow-[0_0_24px_rgba(34,211,238,0.2)] group-hover:shadow-[0_0_35px_rgba(34,211,238,0.5)]",
    pulseClassName: "rounded-2xl border-cyan-400/40",
    windowClass: "left-1/2 -translate-x-1/2 mt-4 origin-top",
    windowAccentClass: "border-t border-cyan-400/20",
    title: "Mezcla unica de Pistas",
    description:
      "La unica herramienta web que mezcla pistas individuales (stems). Sube tu bateria, bajo y voz por separado para un balance perfecto.",
    showBadge: true,
    badgeClassName: "bg-cyan-500/15 text-cyan-200"
  },
  {
    id: "ai-cleanup",
    positionClass: "top-[20%] right-[20%] translate-x-1/2 -translate-y-1/2",
    icon: SparklesIcon,
    iconClassName: "h-4 w-4 lg:h-[14px] lg:w-[14px] xl:h-4 xl:w-4 2xl:h-5 2xl:w-5 text-violet-200",
    iconWrapperClass:
      "h-10 w-10 lg:h-9 lg:w-9 xl:h-10 xl:w-10 2xl:h-12 2xl:w-12 rounded-full border border-violet-400/30 bg-slate-950/70 shadow-[0_0_22px_rgba(139,92,246,0.2)] group-hover:shadow-[0_0_32px_rgba(139,92,246,0.5)]",
    pulseClassName: "rounded-full border-violet-400/40",
    windowClass: "right-0 top-full mt-2 origin-top-right",
    windowAccentClass: "border-t border-violet-400/20",
    title: "IA para el \"Trabajo Sucio\"",
    description:
      "Nuestra IA detecta y elimina ruidos, sibilancias y frecuencias molestas automaticamente antes de que empieces a crear.",
    showBadge: false
  },
  {
    id: "mastering",
    positionClass: "top-1/2 right-[8%] translate-x-1/2 -translate-y-1/2",
    icon: SpeakerWaveIcon,
    iconClassName: "h-5 w-5 lg:h-4 lg:w-4 xl:h-5 xl:w-5 2xl:h-6 2xl:w-6 text-cyan-200",
    iconWrapperClass:
      "h-12 w-12 lg:h-11 lg:w-11 xl:h-12 xl:w-12 2xl:h-14 2xl:w-14 rounded-2xl border border-cyan-400/30 bg-slate-950/70 shadow-[0_0_24px_rgba(34,211,238,0.2)] group-hover:shadow-[0_0_35px_rgba(34,211,238,0.5)]",
    pulseClassName: "rounded-2xl border-cyan-400/40",
    windowClass: "right-full top-1/2 -translate-y-1/2 mr-4 origin-right",
    windowAccentClass: "border-r border-cyan-400/20",
    title: "Mastering Profesional",
    description:
      "Loudness competitivo para Spotify y Apple Music. Consigue ese sonido \"pegado\" y brillante sin distorsion.",
    showBadge: true,
    badgeClassName: "bg-cyan-500/15 text-cyan-200"
  },
  {
    id: "pipeline",
    positionClass: "bottom-[20%] right-[20%] translate-x-1/2 translate-y-1/2",
    icon: Cog6ToothIcon,
    iconClassName: "h-4 w-4 lg:h-[14px] lg:w-[14px] xl:h-4 xl:w-4 2xl:h-5 2xl:w-5 text-slate-100",
    iconWrapperClass:
      "h-10 w-10 lg:h-9 lg:w-9 xl:h-10 xl:w-10 2xl:h-12 2xl:w-12 rounded-full border border-white/10 bg-slate-950/70 shadow-[0_0_18px_rgba(148,163,184,0.2)] group-hover:shadow-[0_0_26px_rgba(148,163,184,0.45)]",
    pulseClassName: "rounded-full border-white/20",
    windowClass: "right-0 bottom-full mb-2 origin-bottom-right",
    title: "Personalizacion Absoluta",
    description:
      "Define tu cadena de efectos. Tu decides que procesos aplicar y en que orden, o deja que la IA decida por ti.",
    showBadge: false
  },
  {
    id: "quality",
    positionClass: "bottom-[8%] left-1/2 -translate-x-1/2 translate-y-1/2",
    icon: ScaleIcon,
    iconClassName: "h-5 w-5 lg:h-4 lg:w-4 xl:h-5 xl:w-5 2xl:h-6 2xl:w-6 text-violet-200",
    iconWrapperClass:
      "h-12 w-12 lg:h-11 lg:w-11 xl:h-12 xl:w-12 2xl:h-14 2xl:w-14 rounded-2xl border border-violet-400/30 bg-slate-950/70 shadow-[0_0_24px_rgba(139,92,246,0.2)] group-hover:shadow-[0_0_35px_rgba(139,92,246,0.5)]",
    pulseClassName: "rounded-2xl border-violet-400/40",
    windowClass: "left-1/2 -translate-x-1/2 bottom-full mb-4 origin-bottom",
    windowAccentClass: "border-b border-violet-400/20",
    title: "Calidad de Estudio",
    description:
      "Resultados indistinguibles de un estudio fisico. Algoritmos de clase mundial para tu home studio.",
    showBadge: true,
    badgeClassName: "bg-violet-500/15 text-violet-200"
  },
  {
    id: "reports",
    positionClass: "bottom-[20%] left-[20%] -translate-x-1/2 translate-y-1/2",
    icon: LightBulbIcon,
    iconClassName: "h-4 w-4 lg:h-[14px] lg:w-[14px] xl:h-4 xl:w-4 2xl:h-5 2xl:w-5 text-slate-100",
    iconWrapperClass:
      "h-10 w-10 lg:h-9 lg:w-9 xl:h-10 xl:w-10 2xl:h-12 2xl:w-12 rounded-full border border-white/10 bg-slate-950/70 shadow-[0_0_18px_rgba(148,163,184,0.2)] group-hover:shadow-[0_0_26px_rgba(148,163,184,0.45)]",
    pulseClassName: "rounded-full border-white/20",
    windowClass: "left-0 bottom-full mb-2 origin-bottom-left",
    title: "Informes de Mejoras",
    description:
      "Generamos un PDF explicando que frecuencias chocaban y como las solucionamos. Aprende mientras mejoras.",
    showBadge: false
  },
  {
    id: "studio-control",
    positionClass: "top-1/2 left-[8%] -translate-x-1/2 -translate-y-1/2",
    icon: ArrowsRightLeftIcon,
    iconClassName: "h-5 w-5 lg:h-4 lg:w-4 xl:h-5 xl:w-5 2xl:h-6 2xl:w-6 text-cyan-200",
    iconWrapperClass:
      "h-12 w-12 lg:h-11 lg:w-11 xl:h-12 xl:w-12 2xl:h-14 2xl:w-14 rounded-2xl border border-cyan-400/30 bg-slate-950/70 shadow-[0_0_24px_rgba(34,211,238,0.2)] group-hover:shadow-[0_0_35px_rgba(34,211,238,0.5)]",
    pulseClassName: "rounded-2xl border-cyan-400/40",
    windowClass: "left-full top-1/2 -translate-y-1/2 ml-4 origin-left",
    windowAccentClass: "border-l border-cyan-400/20",
    title: "Control Total + Studio",
    description:
      "No es una \"caja negra\". Entra en el modo Studio para realizar correcciones manuales finas sobre el trabajo de la IA.",
    showBadge: true,
    badgeClassName: "bg-cyan-500/15 text-cyan-200"
  },
  {
    id: "styles",
    positionClass: "top-[20%] left-[20%] -translate-x-1/2 -translate-y-1/2",
    icon: FireIcon,
    iconClassName: "h-4 w-4 lg:h-[14px] lg:w-[14px] xl:h-4 xl:w-4 2xl:h-5 2xl:w-5 text-slate-100",
    iconWrapperClass:
      "h-10 w-10 lg:h-9 lg:w-9 xl:h-10 xl:w-10 2xl:h-12 2xl:w-12 rounded-full border border-white/10 bg-slate-950/70 shadow-[0_0_18px_rgba(148,163,184,0.2)] group-hover:shadow-[0_0_26px_rgba(148,163,184,0.45)]",
    pulseClassName: "rounded-full border-white/20",
    windowClass: "left-0 top-full mt-2 origin-top-left",
    title: "Todos los Estilos",
    description:
      "Desde bandas de Rock con 20 pistas hasta Rap con solo Beat y Voz. El pipeline se adapta a tu genero.",
    showBadge: false
  }
];

export function HeroDiagram() {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const frameRef = useRef<number | null>(null);
  const baseTransform = "rotateY(-12deg) rotateX(-4deg)";

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    container.style.transform = baseTransform;

    const handleMove = (event: MouseEvent) => {
      if (window.innerWidth < 1024) return;
      const x = (window.innerWidth / 2 - event.clientX) / 45;
      const y = (window.innerHeight / 2 - event.clientY) / 45;

      if (frameRef.current) return;
      frameRef.current = window.requestAnimationFrame(() => {
        container.style.transform = `rotateY(${x}deg) rotateX(${y}deg)`;
        frameRef.current = null;
      });
    };

    const handleLeave = () => {
      container.style.transform = baseTransform;
    };

    window.addEventListener("mousemove", handleMove);
    window.addEventListener("mouseleave", handleLeave);

    return () => {
      window.removeEventListener("mousemove", handleMove);
      window.removeEventListener("mouseleave", handleLeave);
      if (frameRef.current) {
        window.cancelAnimationFrame(frameRef.current);
        frameRef.current = null;
      }
    };
  }, []);

  return (
    <div className="relative mx-auto hidden w-full max-w-[540px] aspect-square lg:block lg:max-w-[480px] xl:max-w-[540px]" style={{ perspective: "1200px" }}>
      <div
        ref={containerRef}
        className="relative h-full w-full transition-transform duration-300 ease-out"
        style={{ transformStyle: "preserve-3d" }}
      >
        <div className="relative flex h-full w-full items-center justify-center rounded-full border border-white/5 bg-white/5 shadow-2xl ring-1 ring-white/10 backdrop-blur-3xl">
          <div className="absolute inset-[15%] rounded-full border border-dashed border-white/20 animate-spin [animation-duration:60s] [animation-timing-function:linear]" />

          <div className="absolute z-20 max-w-[200px] text-center pointer-events-none">
            <div className="absolute inset-0 -z-10 mx-auto h-20 w-20 rounded-full bg-gradient-to-br from-cyan-400 to-violet-500 blur-[50px] opacity-50" />
            <h3 className="mb-2 text-xl font-bold leading-tight text-white">Control de principio a fin</h3>
            <p className="mb-1 text-xs font-semibold uppercase tracking-[0.25em] text-cyan-300">
              De amateur a experto
            </p>
            <p className="text-xs text-slate-400">Sonido de estudio, potenciado por IA</p>
          </div>

          {nodes.map((node) => {
            const Icon = node.icon;
            return (
              <div key={node.id} className={`absolute ${node.positionClass} group z-30 hover:z-50`}>
                <div className="relative">
                  <div
                    className={`flex items-center justify-center transition-all duration-300 ${node.iconWrapperClass} group-hover:scale-110`}
                  >
                    <Icon className={node.iconClassName} aria-hidden="true" />
                  </div>
                  <div className={`absolute inset-0 border opacity-0 group-hover:opacity-100 animate-ping ${node.pulseClassName}`} />
                </div>

                <div
                  className={`pointer-events-none absolute z-50 w-64 scale-95 opacity-0 transition-all duration-300 group-hover:opacity-100 group-hover:scale-100 ${node.windowClass}`}
                >
                  <div
                    className={`rounded-xl border border-white/10 bg-slate-950/95 p-4 shadow-[0_24px_60px_rgba(15,23,42,0.7)] backdrop-blur-xl ${node.windowAccentClass || ""}`}
                  >
                    {node.showBadge ? (
                      <div className="mb-2 flex items-center gap-2">
                        <div className={`rounded-md p-1.5 ${node.badgeClassName || "bg-white/5 text-white"}`}>
                          <Icon className="h-4 w-4" aria-hidden="true" />
                        </div>
                        <h4 className="text-sm font-bold text-white">{node.title}</h4>
                      </div>
                    ) : (
                      <h4 className="mb-1 text-sm font-bold text-white">{node.title}</h4>
                    )}
                    <p className="text-xs leading-relaxed text-slate-300">{node.description}</p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="absolute -bottom-12 left-0 right-0 text-center">
        <a href="#listen-difference" className="group inline-flex items-center gap-2 text-sm text-slate-400 transition-colors hover:text-white">
          <span className="border-b border-transparent transition-all group-hover:border-cyan-300">Escuchar la diferencia</span>
          <ChevronDownIcon className="h-4 w-4 transition-transform group-hover:translate-y-1" aria-hidden="true" />
        </a>
      </div>
    </div>
  );
}
