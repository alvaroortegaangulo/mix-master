// frontend/src/components/StemsProfilePanel.tsx
"use client";

import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { MagnifyingGlassIcon, XMarkIcon } from "@heroicons/react/24/outline";
import { useLocale, useTranslations } from "next-intl";

type StemProfile = {
  id: string;
  fileName: string;
  extension: string;
  profile: string;
};

type Accent = "amber" | "teal";

type Props = {
  stems: StemProfile[];
  onChangeProfile: (id: string, profile: string) => void;
  accent?: Accent;
};

type AccentTheme = {
  wrapper: string;
  title: string;
  description: string;
  card: string;
  text: string;
  muted: string;
  selectBorder: string;
  selectFocus: string;
};

const ACCENT_THEMES: Record<Accent, AccentTheme> = {
  amber: {
    wrapper: "border-amber-500/40 bg-amber-500/10 text-amber-50 shadow-lg shadow-amber-500/20",
    title: "text-amber-100",
    description: "text-amber-200",
    card: "border-amber-500/30 bg-amber-500/5",
    text: "text-amber-50",
    muted: "text-amber-200/80",
    selectBorder: "border-amber-500/60",
    selectFocus: "focus:border-amber-400 focus:ring-1 focus:ring-amber-400",
  },
  teal: {
    wrapper: "border-teal-500/40 bg-teal-500/10 text-teal-50 shadow-lg shadow-teal-500/20",
    title: "text-teal-100",
    description: "text-teal-200",
    card: "border-teal-500/30 bg-teal-500/5",
    text: "text-teal-50",
    muted: "text-teal-200/80",
    selectBorder: "border-teal-500/60",
    selectFocus: "focus:border-teal-400 focus:ring-1 focus:ring-teal-400",
  },
};

type ProfileCategory =
  | "all"
  | "drums"
  | "bass"
  | "guitars"
  | "keys"
  | "vocals"
  | "fx"
  | "ambience"
  | "other";

type ProfileOption = {
  value: string;
  label: string;
  category: Exclude<ProfileCategory, "all">;
  variant: string;
  keywords: string[];
};

const CATEGORY_ORDER: Array<Exclude<ProfileCategory, "all">> = [
  "drums",
  "bass",
  "guitars",
  "keys",
  "vocals",
  "fx",
  "ambience",
  "other",
];

const PROFILE_SEARCH_TERMS: Record<string, string[]> = {
  auto: ["auto", "automatic", "detect", "recommended"],
  Kick: ["kick", "bombo", "bass drum"],
  Snare: ["snare", "caja"],
  Percussion: ["percussion", "percusion", "bongos", "conga"],
  Bass_Electric: ["bass", "bajo", "sub"],
  Acoustic_Guitar: ["acoustic", "guitar", "guitarra acustica"],
  Electric_Guitar_Rhythm: ["electric", "guitar", "guitarra electrica"],
  Keys_Piano: ["piano", "keys", "teclas"],
  Synth_Pads: ["synth", "sinte", "pads", "pad"],
  Lead_Vocal_Melodic: ["vocal", "voz", "lead", "melodic"],
  Lead_Vocal_Rap: ["rap", "vocal", "voz"],
  Backing_Vocals: ["backing", "vocals", "coros"],
  FX_EarCandy: ["fx", "effects", "ear candy", "cymbals", "platos"],
  Ambience_Atmos: ["ambience", "ambient", "atm", "ambiente"],
  Other: ["other", "otros", "misc", "synth", "keyboard", "teclado", "sintetizador"],
};

const PROFILE_IMAGES: Partial<Record<string, string>> = {
  Kick: "/instruments/kick.webp",
  Snare: "/instruments/snare.webp",
  Percussion: "/instruments/bongos.webp",
  Bass_Electric: "/instruments/bass.webp",
  Acoustic_Guitar: "/instruments/guitar-acoustic.webp",
  Electric_Guitar_Rhythm: "/instruments/guitar-electric.webp",
  Keys_Piano: "/instruments/piano-keys.webp",
  Synth_Pads: "/instruments/synth-controller.webp",
  Lead_Vocal_Melodic: "/instruments/vocal-lead.webp",
  Lead_Vocal_Rap: "/instruments/vocal-lead.webp",
  Backing_Vocals: "/instruments/vocal-backing.webp",
  FX_EarCandy: "/instruments/cymbals.webp",
  Ambience_Atmos: "/instruments/ambience-wave.webp",
  Other: "/instruments/synth-keyboard.webp",
};

const BASE_SVG_PROPS = {
  viewBox: "0 0 160 120",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 3,
  strokeLinecap: "round",
  strokeLinejoin: "round",
  className: "h-full w-full text-teal-100/80",
} as const;

const InstrumentArt = ({ variant }: { variant: string }) => {
  switch (variant) {
    case "kick":
      return (
        <svg {...BASE_SVG_PROPS}>
          <circle cx="80" cy="60" r="32" />
          <circle cx="80" cy="60" r="18" />
          <rect x="48" y="32" width="64" height="56" rx="12" opacity="0.2" fill="currentColor" />
        </svg>
      );
    case "snare":
      return (
        <svg {...BASE_SVG_PROPS}>
          <circle cx="80" cy="60" r="28" />
          <line x1="52" y1="46" x2="108" y2="74" />
          <line x1="52" y1="74" x2="108" y2="46" />
          <rect x="58" y="34" width="44" height="52" rx="8" opacity="0.18" fill="currentColor" />
        </svg>
      );
    case "percussion":
      return (
        <svg {...BASE_SVG_PROPS}>
          <circle cx="62" cy="64" r="16" />
          <circle cx="98" cy="64" r="16" />
          <rect x="48" y="40" width="28" height="48" rx="6" opacity="0.2" fill="currentColor" />
          <rect x="84" y="40" width="28" height="48" rx="6" opacity="0.2" fill="currentColor" />
        </svg>
      );
    case "bass":
      return (
        <svg {...BASE_SVG_PROPS}>
          <rect x="82" y="32" width="48" height="8" rx="4" />
          <rect x="110" y="28" width="16" height="16" rx="4" />
          <ellipse cx="62" cy="70" rx="22" ry="16" />
          <circle cx="70" cy="70" r="4" />
          <line x1="84" y1="36" x2="70" y2="60" />
        </svg>
      );
    case "acoustic":
      return (
        <svg {...BASE_SVG_PROPS}>
          <ellipse cx="64" cy="70" rx="22" ry="16" />
          <ellipse cx="84" cy="52" rx="18" ry="12" />
          <rect x="96" y="38" width="40" height="8" rx="4" />
          <circle cx="64" cy="70" r="4" />
        </svg>
      );
    case "electric":
      return (
        <svg {...BASE_SVG_PROPS}>
          <rect x="52" y="54" width="42" height="26" rx="8" />
          <rect x="92" y="50" width="14" height="8" rx="4" />
          <rect x="100" y="36" width="40" height="8" rx="4" />
          <circle cx="72" cy="67" r="4" />
        </svg>
      );
    case "keys":
      return (
        <svg {...BASE_SVG_PROPS}>
          <rect x="26" y="46" width="108" height="36" rx="8" />
          <line x1="46" y1="46" x2="46" y2="82" />
          <line x1="66" y1="46" x2="66" y2="82" />
          <line x1="86" y1="46" x2="86" y2="82" />
          <line x1="106" y1="46" x2="106" y2="82" />
          <rect x="40" y="46" width="10" height="20" rx="2" fill="currentColor" opacity="0.2" />
          <rect x="60" y="46" width="10" height="20" rx="2" fill="currentColor" opacity="0.2" />
          <rect x="80" y="46" width="10" height="20" rx="2" fill="currentColor" opacity="0.2" />
          <rect x="100" y="46" width="10" height="20" rx="2" fill="currentColor" opacity="0.2" />
        </svg>
      );
    case "synth":
      return (
        <svg {...BASE_SVG_PROPS}>
          <rect x="28" y="40" width="104" height="44" rx="10" />
          <circle cx="50" cy="56" r="6" />
          <circle cx="70" cy="56" r="6" />
          <circle cx="90" cy="56" r="6" />
          <line x1="42" y1="74" x2="118" y2="74" />
        </svg>
      );
    case "vocal":
      return (
        <svg {...BASE_SVG_PROPS}>
          <rect x="66" y="30" width="28" height="44" rx="12" />
          <line x1="80" y1="74" x2="80" y2="94" />
          <path d="M64 94h32" />
        </svg>
      );
    case "rap":
      return (
        <svg {...BASE_SVG_PROPS}>
          <rect x="64" y="32" width="32" height="40" rx="12" />
          <line x1="80" y1="72" x2="90" y2="92" />
          <path d="M72 94h36" />
        </svg>
      );
    case "backing":
      return (
        <svg {...BASE_SVG_PROPS}>
          <rect x="52" y="36" width="22" height="34" rx="10" />
          <rect x="86" y="36" width="22" height="34" rx="10" />
          <line x1="62" y1="70" x2="62" y2="92" />
          <line x1="96" y1="70" x2="96" y2="92" />
          <path d="M48 92h32" />
          <path d="M82 92h32" />
        </svg>
      );
    case "fx":
      return (
        <svg {...BASE_SVG_PROPS}>
          <path d="M36 76l20-24 16 12 28-20 24 32" />
          <circle cx="118" cy="46" r="6" />
          <circle cx="52" cy="52" r="4" />
        </svg>
      );
    case "ambience":
      return (
        <svg {...BASE_SVG_PROPS}>
          <path d="M30 80c18-20 82-20 100 0" />
          <path d="M42 68c14-14 62-14 76 0" />
          <circle cx="80" cy="56" r="8" />
        </svg>
      );
    case "auto":
      return (
        <svg {...BASE_SVG_PROPS}>
          <rect x="50" y="40" width="60" height="40" rx="10" />
          <path d="M62 60h36" />
          <path d="M80 44v-10" />
          <circle cx="80" cy="30" r="6" />
        </svg>
      );
    default:
      return (
        <svg {...BASE_SVG_PROPS}>
          <rect x="36" y="36" width="88" height="48" rx="12" />
          <line x1="36" y1="60" x2="124" y2="60" />
          <line x1="80" y1="36" x2="80" y2="84" />
        </svg>
      );
  }
};

export function StemsProfilePanel({ stems, onChangeProfile, accent = "amber" }: Props) {
  const t = useTranslations("MixTool");
  const locale = useLocale();
  const theme = ACCENT_THEMES[accent];
  const [isSelectorOpen, setIsSelectorOpen] = useState(false);
  const [activeStemId, setActiveStemId] = useState<string | null>(null);
  const [activeCategory, setActiveCategory] = useState<ProfileCategory>("all");
  const [searchTerm, setSearchTerm] = useState("");
  const [isMounted, setIsMounted] = useState(false);

  const profileOptions = useMemo<ProfileOption[]>(
    () => [
      {
        value: "auto",
        label: t("autoRecommended"),
        category: "other",
        variant: "auto",
        keywords: PROFILE_SEARCH_TERMS.auto,
      },
      {
        value: "Kick",
        label: t("profileOptions.Kick"),
        category: "drums",
        variant: "kick",
        keywords: PROFILE_SEARCH_TERMS.Kick,
      },
      {
        value: "Snare",
        label: t("profileOptions.Snare"),
        category: "drums",
        variant: "snare",
        keywords: PROFILE_SEARCH_TERMS.Snare,
      },
      {
        value: "Percussion",
        label: t("profileOptions.Percussion"),
        category: "drums",
        variant: "percussion",
        keywords: PROFILE_SEARCH_TERMS.Percussion,
      },
      {
        value: "Bass_Electric",
        label: t("profileOptions.Bass_Electric"),
        category: "bass",
        variant: "bass",
        keywords: PROFILE_SEARCH_TERMS.Bass_Electric,
      },
      {
        value: "Acoustic_Guitar",
        label: t("profileOptions.Acoustic_Guitar"),
        category: "guitars",
        variant: "acoustic",
        keywords: PROFILE_SEARCH_TERMS.Acoustic_Guitar,
      },
      {
        value: "Electric_Guitar_Rhythm",
        label: t("profileOptions.Electric_Guitar_Rhythm"),
        category: "guitars",
        variant: "electric",
        keywords: PROFILE_SEARCH_TERMS.Electric_Guitar_Rhythm,
      },
      {
        value: "Keys_Piano",
        label: t("profileOptions.Keys_Piano"),
        category: "keys",
        variant: "keys",
        keywords: PROFILE_SEARCH_TERMS.Keys_Piano,
      },
      {
        value: "Synth_Pads",
        label: t("profileOptions.Synth_Pads"),
        category: "keys",
        variant: "synth",
        keywords: PROFILE_SEARCH_TERMS.Synth_Pads,
      },
      {
        value: "Lead_Vocal_Melodic",
        label: t("profileOptions.Lead_Vocal_Melodic"),
        category: "vocals",
        variant: "vocal",
        keywords: PROFILE_SEARCH_TERMS.Lead_Vocal_Melodic,
      },
      {
        value: "Lead_Vocal_Rap",
        label: t("profileOptions.Lead_Vocal_Rap"),
        category: "vocals",
        variant: "rap",
        keywords: PROFILE_SEARCH_TERMS.Lead_Vocal_Rap,
      },
      {
        value: "Backing_Vocals",
        label: t("profileOptions.Backing_Vocals"),
        category: "vocals",
        variant: "backing",
        keywords: PROFILE_SEARCH_TERMS.Backing_Vocals,
      },
      {
        value: "FX_EarCandy",
        label: t("profileOptions.FX_EarCandy"),
        category: "drums",
        variant: "fx",
        keywords: PROFILE_SEARCH_TERMS.FX_EarCandy,
      },
      {
        value: "Ambience_Atmos",
        label: t("profileOptions.Ambience_Atmos"),
        category: "ambience",
        variant: "ambience",
        keywords: PROFILE_SEARCH_TERMS.Ambience_Atmos,
      },
      {
        value: "Other",
        label: t("profileOptions.Other"),
        category: "keys",
        variant: "other",
        keywords: PROFILE_SEARCH_TERMS.Other,
      },
    ],
    [t],
  );

  const profileLabelByValue = useMemo(() => {
    const map: Record<string, string> = {};
    profileOptions.forEach((option) => {
      map[option.value] = option.label;
    });
    map.auto = t("auto");
    return map;
  }, [profileOptions, t]);

  const categoryLabels = useMemo(
    () => ({
      drums: t("profileGroups.drums"),
      bass: t("profileGroups.bass"),
      guitars: t("profileGroups.guitars"),
      keys: t("profileGroups.keys"),
      vocals: t("profileGroups.vocals"),
      fx: t("profileGroups.fx"),
      ambience: t("profileGroups.ambience"),
      other: t("profileGroups.other"),
    }),
    [t],
  );

  const categoryCounts = useMemo(() => {
    const counts: Record<Exclude<ProfileCategory, "all">, number> = {
      drums: 0,
      bass: 0,
      guitars: 0,
      keys: 0,
      vocals: 0,
      fx: 0,
      ambience: 0,
      other: 0,
    };
    profileOptions.forEach((option) => {
      counts[option.category] += 1;
    });
    return counts;
  }, [profileOptions]);

  const categories = useMemo(
    () => [
      { key: "all" as ProfileCategory, label: t("stemsProfileSelector.all"), count: profileOptions.length },
      ...CATEGORY_ORDER.map((key) => ({
        key,
        label: categoryLabels[key],
        count: categoryCounts[key],
      })),
    ],
    [categoryCounts, categoryLabels, profileOptions.length, t],
  );

  const activeStem = stems.find((stem) => stem.id === activeStemId) || null;
  const activeProfileValue = activeStem?.profile ?? "auto";

  const openSelector = (stemId: string) => {
    setActiveStemId(stemId);
    setActiveCategory("all");
    setSearchTerm("");
    setIsSelectorOpen(true);
  };

  const closeSelector = () => {
    setIsSelectorOpen(false);
    setActiveStemId(null);
    setSearchTerm("");
  };

  useEffect(() => {
    setIsMounted(true);
  }, []);

  useEffect(() => {
    if (!isMounted || !isSelectorOpen) return;
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = originalOverflow;
    };
  }, [isMounted, isSelectorOpen]);

  useEffect(() => {
    if (!isSelectorOpen) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        closeSelector();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isSelectorOpen]);

  const normalizedSearch = searchTerm.trim().toLowerCase();
  const matchesSearch = (option: ProfileOption) => {
    if (!normalizedSearch) return true;
    const haystack = [option.label, option.value, ...option.keywords].join(" ").toLowerCase();
    return haystack.includes(normalizedSearch);
  };

  const filteredOptions = profileOptions.filter((option) => {
    const matchesCategory = activeCategory === "all" || option.category === activeCategory;
    return matchesCategory && matchesSearch(option);
  });

  const groupedOptions =
    activeCategory === "all"
      ? CATEGORY_ORDER.map((category) => ({
          key: category,
          label: categoryLabels[category],
          options: profileOptions.filter(
            (option) => option.category === category && matchesSearch(option),
          ),
        })).filter((group) => group.options.length > 0)
      : [];

  const handleSelectOption = (value: string) => {
    if (!activeStem) return;
    onChangeProfile(activeStem.id, value);
    closeSelector();
  };

  const gridClassName = "flex flex-wrap gap-2";
  const groupGridClassName = "flex flex-wrap items-start gap-4";

  const getCardLabel = (option: ProfileOption) => {
    if (locale === "es") {
      return option.label;
    }
    const imageSrc = PROFILE_IMAGES[option.value];
    if (!imageSrc) return option.label;
    const fileName = imageSrc.split("/").pop() ?? "";
    const baseName = fileName.replace(/\.(png|webp)$/i, "");
    if (!baseName) return option.label;
    const imageLabel = baseName
      .split("-")
      .map((word) => (word ? `${word[0].toUpperCase()}${word.slice(1)}` : ""))
      .join(" ");
    return imageLabel;
  };

  const renderOptionCard = (option: ProfileOption) => {
    const isSelected = option.value === activeProfileValue;
    const imageSrc = PROFILE_IMAGES[option.value];
    const cardLabel = getCardLabel(option);
    return (
      <button
        key={option.value}
        type="button"
        onClick={() => handleSelectOption(option.value)}
        className={[
          "group w-[120px] shrink-0 rounded-xl border p-1.5 text-left transition",
          isSelected
            ? "border-teal-400/70 bg-teal-500/10 shadow-[0_0_14px_rgba(45,212,191,0.2)]"
            : "border-slate-800/80 bg-slate-900/40 hover:border-teal-500/40 hover:bg-slate-900/70",
        ].join(" ")}
        aria-pressed={isSelected}
      >
        <div className="relative h-[96px] overflow-hidden rounded-lg border border-slate-800 bg-slate-950/60">
          <div className="absolute inset-0 rounded-lg bg-[radial-gradient(circle_at_50%_20%,rgba(45,212,191,0.2),transparent_65%)]" />
          <div className="relative flex h-full items-center justify-center p-1.5">
            {imageSrc ? (
              <img
                src={imageSrc}
                alt={cardLabel}
                className="h-full w-full object-contain"
                loading="lazy"
                draggable={false}
              />
            ) : (
              <InstrumentArt variant={option.variant} />
            )}
          </div>
        </div>
        <p className="mt-1 min-h-[28px] text-[10px] font-medium leading-snug text-slate-100 break-words">
          {cardLabel}
        </p>
      </button>
    );
  };

  const selectorOverlay =
    isSelectorOpen && activeStem && isMounted
      ? createPortal(
          <div
            className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
            onClick={(event) => {
              if (event.target === event.currentTarget) {
                closeSelector();
              }
            }}
          >
            <div
              className="flex max-h-[90vh] w-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-slate-800 bg-slate-950/95 shadow-2xl"
              role="dialog"
              aria-modal="true"
            >
              <div className="flex items-start justify-between gap-4 border-b border-slate-800 px-5 py-4">
                <div>
                  <h4 className="text-base font-semibold text-white">
                    {t("stemsProfileSelector.title")}
                  </h4>
                  <p className="mt-1 text-[11px] text-slate-400">
                    {t("stemsProfileSelector.subtitle")}{" "}
                    <span className="text-teal-300">
                      {activeStem.fileName}
                      {activeStem.extension ? `.${activeStem.extension}` : ""}
                    </span>
                  </p>
                </div>
                <button
                  type="button"
                  onClick={closeSelector}
                  className="rounded-full border border-slate-800 bg-slate-900/70 p-2 text-slate-300 transition hover:text-white"
                  aria-label={t("stemsProfileSelector.cancel")}
                >
                  <XMarkIcon className="h-4 w-4" />
                </button>
              </div>

              <div className="grid flex-1 min-h-0 grid-cols-1 gap-4 p-5 lg:grid-cols-[200px_1fr]">
                <aside className="max-h-full overflow-y-auto rounded-xl border border-slate-800 bg-slate-950/70 px-3 py-4">
                  <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
                    {t("stemsProfileSelector.categories")}
                  </p>
                  <div className="mt-3 space-y-1.5">
                    {categories.map((category) => {
                      const isActive = activeCategory === category.key;
                      return (
                        <button
                          key={category.key}
                          type="button"
                          onClick={() => setActiveCategory(category.key)}
                          className={[
                            "flex w-full items-center justify-between rounded-lg px-3 py-2 text-[11px] font-medium transition",
                            isActive
                              ? "bg-teal-500/15 text-teal-200 border border-teal-500/30"
                              : "text-slate-400 hover:bg-slate-900/70 hover:text-slate-100",
                          ].join(" ")}
                        >
                          <span>{category.label}</span>
                          <span className="rounded-full border border-slate-700 px-2 py-0.5 text-[10px] text-slate-500">
                            {category.count}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </aside>

                <div className="flex min-h-0 flex-col">
                  <div className="relative">
                    <MagnifyingGlassIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
                    <input
                      type="text"
                      value={searchTerm}
                      onChange={(event) => setSearchTerm(event.target.value)}
                      placeholder={t("stemsProfileSelector.searchPlaceholder")}
                      className="w-full rounded-lg border border-slate-800 bg-slate-950/60 py-2 pl-9 pr-3 text-xs text-slate-200 placeholder:text-slate-600 focus:border-teal-500/60 focus:outline-none"
                    />
                  </div>

                  <div className="mt-3 flex-1 overflow-y-auto pr-1 custom-scrollbar">
                    {activeCategory === "all" ? (
                      <div className={groupGridClassName}>
                        {groupedOptions.map((group) => (
                          <div
                            key={group.key}
                            className="w-fit max-w-full rounded-xl border border-slate-900/70 bg-slate-950/40 p-2.5"
                          >
                            <p className="mb-2 text-[9px] font-semibold uppercase tracking-[0.22em] text-slate-500">
                              {group.label}
                            </p>
                            <div className={gridClassName}>
                              {group.options.map(renderOptionCard)}
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className={gridClassName}>
                        {filteredOptions.map(renderOptionCard)}
                      </div>
                    )}
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-end border-t border-slate-800 px-5 py-3">
                <button
                  type="button"
                  onClick={closeSelector}
                  className="rounded-lg border border-slate-700 bg-slate-900/60 px-4 py-2 text-[11px] font-semibold uppercase tracking-widest text-slate-300 transition hover:text-white"
                >
                  {t("stemsProfileSelector.cancel")}
                </button>
              </div>
            </div>
          </div>,
          document.body,
        )
      : null;

  if (!stems.length) return null;

  return (
    <aside className={`rounded-2xl border ${theme.wrapper} p-4 text-xs`}>
      <div className="space-y-2">
        {stems.map((stem) => {
          const currentLabel = profileLabelByValue[stem.profile] || t("auto");
          const extension = stem.extension ? `.${stem.extension}` : "";
          return (
            <div
              key={stem.id}
              className={`flex items-center justify-between gap-3 rounded-lg border ${theme.card} px-2.5 py-2`}
            >
              <div className="min-w-0">
                <p className={`truncate text-[11px] font-medium ${theme.text}`}>
                  {stem.fileName}
                  {extension && <span className={theme.muted}>{extension}</span>}
                </p>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <span className="max-w-[150px] truncate rounded-full border border-amber-400/60 bg-amber-500/15 px-2 py-0.5 text-[10px] font-semibold text-amber-200">
                  {currentLabel}
                </span>
                <button
                  type="button"
                  onClick={() => openSelector(stem.id)}
                  className={`shrink-0 rounded-lg border ${theme.selectBorder} bg-slate-950/80 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-widest ${theme.text} transition hover:bg-slate-900/80`}
                  aria-haspopup="dialog"
                  aria-expanded={isSelectorOpen && activeStemId === stem.id}
                >
                  {t("stemsProfileSelector.select")}
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {selectorOverlay}
    </aside>
  );
}
