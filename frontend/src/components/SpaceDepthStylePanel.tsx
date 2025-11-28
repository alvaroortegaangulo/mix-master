"use client";

import { useState } from "react";

export type SpaceBus = {
  key: string;
  label: string;
  description?: string;
};

type Props = {
  /** Lista de buses que queremos mostrar (drums, bass, guitars, etc.) */
  buses: SpaceBus[];
  /**
   * Mapa busKey -> estilo seleccionado.
   * Si no hay entrada para un bus, se considera "auto".
   */
  value: Record<string, string>;
  /** Callback cuando cambia el estilo de un bus */
  onChange: (busKey: string, style: string) => void;
};

const STYLE_OPTIONS: { value: string; label: string }[] = [
  { value: "Flamenco_Rumba", label: "Flamenco / Rumba" },
  { value: "EDM_Club", label: "EDM / Club" },
  {
    value: "Acoustic_SingerSongwriter",
    label: "Acoustic / Singer-songwriter",
  },
];


type StyleBusDoc = {
  title: string;
  summary: string;
  params: string;
};

type StyleDoc = {
  label: string;
  description: string;
  buses: Record<string, StyleBusDoc>;
};

/**
 * Documentación de presets de espacio/profundidad por estilo y bus.
 * Se usa para tooltips / ventana de información en el panel.
 */
const STYLE_DOCS: Record<string, StyleDoc> = {
  auto: {
    label: "Auto (según material)",
    description:
      "Modo automático conservador. Usa rooms y plates cortos, envíos moderados y filtros agresivos en graves para evitar que la mezcla se emborrone. Es un punto de partida seguro si no se elige un estilo específico.",
    buses: {
      drums: {
        title: "Drums bus",
        summary:
          "Room corto y discreto que une el kit sin convertirlo en un wash de reverb.",
        params:
          "Reverb: Room (~0.7 s) · Predelay: 8–12 ms · Send: -18 a -20 dB (~10–13 %) · HP: ~260–320 Hz · LP: ~11 kHz.",
      },
      bass: {
        title: "Bass bus",
        summary:
          "Bajo prácticamente seco; sólo una sombra de room muy filtrado para evitar bola de graves.",
        params:
          "Reverb: Room muy corto · Predelay: 5 ms · Send: -26 dB (~5 %) · HP: ~90 Hz · LP: ~7–8 kHz.",
      },
      guitars: {
        title: "Guitars bus",
        summary:
          "Plate corto y controlado con un poco de delay; abre estéreo sin tapar medios.",
        params:
          "Reverb: Plate (~1.3–1.5 s) · Predelay: ~20 ms · Send: -18 dB (~13 %) · Delay: 260–280 ms, fb ~0.18–0.20 · HP: ~200–220 Hz · LP: ~11.5 kHz.",
      },
      keys_synth: {
        title: "Keys / Synths bus",
        summary:
          "Hall compacto y filtrado que da atmósfera sin inundar la mezcla.",
        params:
          "Reverb: Hall (~2.0 s) · Predelay: 22–28 ms · Send: -18 dB (~13 %) · Delay: 320–350 ms, fb ~0.18–0.22 · HP: ~220–260 Hz · LP: ~15 kHz.",
      },
      lead_vocal: {
        title: "Lead vocal bus",
        summary:
          "Plate vocal corto con predelay medio y slapback suave para engordar la voz sin perder claridad.",
        params:
          "Reverb: Plate (~1.5–1.7 s) · Predelay: 70–80 ms · Send: -16 dB (~16 %) · Delay: 140–170 ms, fb ~0.2 · HP: ~160–180 Hz · LP: ~12 kHz.",
      },
      backing_vocals: {
        title: "Backing vocals bus",
        summary:
          "Hall moderado que coloca los coros algo más atrás, creando un colchón alrededor de la lead.",
        params:
          "Reverb: Hall (~2.1–2.3 s) · Predelay: 40–60 ms · Send: -14 dB (~20 %) · HP: ~180–200 Hz · LP: ~13.5 kHz.",
      },
      fx: {
        title: "FX / Ear candy bus",
        summary:
          "Hall más largo y creativo pero filtrado en graves para transiciones y detalles sin exceso de barro.",
        params:
          "Reverb: Hall (~2.3–2.6 s) · Predelay: ~30–40 ms · Send: -12 dB (~25 %) · Delay: 360–400 ms, fb ~0.32–0.35 · HP: ~260 Hz · LP: ~17 kHz.",
      },
      misc: {
        title: "Other / Misc bus",
        summary:
          "Room neutro para cualquier fuente no clasificada; aporta cohesión sin colas llamativas.",
        params:
          "Reverb: Room (~0.8 s) · Predelay: ~15 ms · Send: -20 dB (~10 %) · HP: ~220–250 Hz · LP: ~13 kHz.",
      },
    },
  },

  flamenco_rumba: {
    label: "Flamenco / Rumba",
    description:
      "Configuración pensada para producciones flamencas y rumba-pop: sonido natural y cercano, guitarras y voz con plate corto y predelays generosos, muy poco FX en graves.",
    buses: {
      drums: {
        title: "Drums bus (Flamenco / Rumba)",
        summary:
          "Room discreto que une percusiones/palmas sin restar definición rítmica.",
        params:
          "Reverb: Room (~0.7 s) · Predelay: ~10 ms · Send: -20 dB (~10 %) · HP: ~320 Hz · LP: ~11 kHz.",
      },
      bass: {
        title: "Bass bus (Flamenco / Rumba)",
        summary:
          "Bajo casi seco, centrado y muy claro; sólo un toque de room para cohesión.",
        params:
          "Reverb: Prácticamente seca · Predelay: ~5 ms · Send: -40 dB (~1 %) · HP: ~80 Hz · LP: ~6.5 kHz.",
      },
      guitars: {
        title: "Guitars bus (Flamenco / Rumba)",
        summary:
          "Plate clásico con predelay para no tapar el ataque de la guitarra flamenca y un eco corto que abre pero no embadurna.",
        params:
          "Reverb: Plate (~1.4–1.6 s) · Predelay: ~28 ms · Send: -18 dB (~13 %) · Delay: ~210 ms, fb ~0.16 · Chorus suave (0.8 Hz, depth ~0.10) · HP: ~220 Hz · LP: ~11.5 kHz.",
      },
      keys_synth: {
        title: "Keys / Synths bus (Flamenco / Rumba)",
        summary:
          "Hall moderado, más de colchón que protagonista, para pianos/keys de apoyo.",
        params:
          "Reverb: Hall (~2.0 s) · Predelay: ~24 ms · Send: -20 dB (~10 %) · Delay: ~280 ms, fb ~0.18 · HP: ~240 Hz · LP: ~15 kHz.",
      },
      lead_vocal: {
        title: "Lead vocal bus (Flamenco / Rumba)",
        summary:
          "Voz flamenca muy al frente, con plate vocal elegante y slapback corto, predelay largo para mantener toda la articulación.",
        params:
          "Reverb: Plate (~1.6–1.8 s) · Predelay: ~90 ms · Send: -16 dB (~16 %) · Delay: ~150 ms (slap), fb ~0.22 · Chorus muy ligero · HP: ~170 Hz · LP: ~12 kHz.",
      },
      backing_vocals: {
        title: "Backing vocals bus (Flamenco / Rumba)",
        summary:
          "Coros algo más largos y húmedos, envolviendo a la lead sin competir con ella.",
        params:
          "Reverb: Hall (~2.1–2.3 s) · Predelay: ~60 ms · Send: -14 dB (~20 %) · Delay: ~260 ms, fb ~0.26 · HP: ~190 Hz · LP: ~13.5 kHz.",
      },
      fx: {
        title: "FX / Ear candy bus (Flamenco / Rumba)",
        summary:
          "FX ambientales y golpes creativos con colas más grandes y algo de movimiento, pero muy filtrados en graves.",
        params:
          "Reverb: Hall (~2.4–2.6 s) · Predelay: ~40 ms · Send: -12 dB (~25 %) · Delay: ~380 ms, fb ~0.32 · Phaser suave · HP: ~260 Hz · LP: ~16.5 kHz.",
      },
      misc: {
        title: "Other / Misc bus (Flamenco / Rumba)",
        summary:
          "Room neutro corto para cualquier fuente extra, manteniendo una sensación de sala realista.",
        params:
          "Reverb: Room (~0.8 s) · Predelay: ~18 ms · Send: -20 dB (~10 %) · HP: ~230 Hz · LP: ~13 kHz.",
      },
    },
  },

  urban_trap: {
    label: "Urbano / Trap / Hip-hop",
    description:
      "Drums y 808 ultra secos, voz con plate/hall brillante y predelays largos; FX grandes y creativos pero muy filtrados en graves.",
    buses: {
      drums: {
        title: "Drums bus (Urban / Trap)",
        summary:
          "Room mínimo que pega la batería, pero el golpe sigue extremadamente seco.",
        params:
          "Reverb: Room (~0.6–0.7 s) · Predelay: ~6 ms · Send: -22 dB (~8 %) · HP: ~350 Hz · LP: ~10 kHz.",
      },
      bass: {
        title: "Bass bus (Urban / Trap)",
        summary:
          "Sub-bass prácticamente sin reverb; el low end va totalmente seco para máxima pegada.",
        params:
          "Reverb: Prácticamente seca · Predelay: ~5 ms · Send: -50 dB (~0.3 %) · HP: ~70 Hz · LP: ~6 kHz.",
      },
      guitars: {
        title: "Guitars bus (Urban / Trap)",
        summary:
          "Plate controlado + eco medio para integrar guitarras y samples sin estorbar el beat.",
        params:
          "Reverb: Plate (~1.4–1.6 s) · Predelay: ~24 ms · Send: -20 dB (~10 %) · Delay: ~260 ms, fb ~0.20 · Chorus suave · HP: ~230 Hz · LP: ~11.5 kHz.",
      },
      keys_synth: {
        title: "Keys / Synths bus (Urban / Trap)",
        summary:
          "Hall moderado para pads y keys que rellenan sin comerle espacio a la voz.",
        params:
          "Reverb: Hall (~2.0 s) · Predelay: ~30 ms · Send: -18 dB (~13 %) · Delay: ~320 ms, fb ~0.26 · HP: ~260 Hz · LP: ~16 kHz.",
      },
      lead_vocal: {
        title: "Lead vocal bus (Urban / Trap)",
        summary:
          "Lead muy al frente con plate moderno y eco 1/8–1/4, predelay largo para claridad absoluta en la dicción.",
        params:
          "Reverb: Plate (~1.6–1.8 s) · Predelay: ~100 ms · Send: -14 dB (~20 %) · Delay: ~260 ms, fb ~0.28 · Chorus ligero · HP: ~180 Hz · LP: ~12.5 kHz.",
      },
      backing_vocals: {
        title: "Backing vocals bus (Urban / Trap)",
        summary:
          "Dobles y ad-libs más húmedos y atrás, creando el entorno típico del género.",
        params:
          "Reverb: Hall (~2.1–2.3 s) · Predelay: ~70 ms · Send: -12 dB (~25 %) · Delay: ~320 ms, fb ~0.30 · HP: ~200 Hz · LP: ~13.5 kHz.",
      },
      fx: {
        title: "FX / Ear candy bus (Urban / Trap)",
        summary:
          "FX muy espaciales con colas largas y phaser suave para efectos de transición y atmósfera.",
        params:
          "Reverb: Hall (~2.5–2.7 s) · Predelay: ~45 ms · Send: -10 dB (~32 %) · Delay: ~420 ms, fb ~0.38 · Phaser suave · HP: ~280 Hz · LP: ~18 kHz.",
      },
      misc: {
        title: "Other / Misc bus (Urban / Trap)",
        summary:
          "Room discreto para cohesionar fuentes sueltas sin hacer la mezcla más turbia.",
        params:
          "Reverb: Room (~0.7–0.8 s) · Predelay: ~16 ms · Send: -22 dB (~8 %) · HP: ~250 Hz · LP: ~13 kHz.",
      },
    },
  },

  rock: {
    label: "Rock / Pop-rock",
    description:
      "Baterías con room reconocible, guitarras con plate y delays medios, voces con plate vocal clásico, coros algo más largos.",
    buses: {
      drums: {
        title: "Drums bus (Rock)",
        summary:
          "Room rock que da sensación de sala pero mantiene pegada en caja y bombo.",
        params:
          "Reverb: Room (~0.7 s) · Predelay: ~14 ms · Send: -18 dB (~13 %) · HP: ~280 Hz · LP: ~11 kHz.",
      },
      bass: {
        title: "Bass bus (Rock)",
        summary:
          "Bajo prácticamente seco; sólo un toque mínimo de espacio implícito para no restar contundencia.",
        params:
          "Reverb: Casi seca · Predelay: ~5 ms · Send: -45 dB (~0.6 %) · HP: ~80 Hz · LP: ~6.5 kHz.",
      },
      guitars: {
        title: "Guitars bus (Rock)",
        summary:
          "Plate clásico rock con eco medio; sitúa las guitarras alrededor de la voz sin invadirla.",
        params:
          "Reverb: Plate (~1.4–1.6 s) · Predelay: ~26 ms · Send: -18 dB (~13 %) · Delay: ~280 ms, fb ~0.20 · Chorus suave · HP: ~220 Hz · LP: ~11.5 kHz.",
      },
      keys_synth: {
        title: "Keys / Synths bus (Rock)",
        summary:
          "Hall moderado para órganos/keys que acompañan, manteniéndose detrás del muro de guitarras.",
        params:
          "Reverb: Hall (~2.0 s) · Predelay: ~24 ms · Send: -18 dB (~13 %) · Delay: ~320 ms, fb ~0.22 · HP: ~240 Hz · LP: ~15 kHz.",
      },
      lead_vocal: {
        title: "Lead vocal bus (Rock)",
        summary:
          "Plate vocal rock con predelay medio y eco muy corto; voz muy presente con cola reconocible.",
        params:
          "Reverb: Plate (~1.6–1.8 s) · Predelay: ~70 ms · Send: -16 dB (~16 %) · Delay: ~170 ms, fb ~0.22 · HP: ~170 Hz · LP: ~12 kHz.",
      },
      backing_vocals: {
        title: "Backing vocals bus (Rock)",
        summary:
          "Coros más largos y abiertos que la lead, creando sensación de “coro de estadio” suave.",
        params:
          "Reverb: Hall (~2.1–2.3 s) · Predelay: ~50 ms · Send: -14 dB (~20 %) · Delay: ~260 ms, fb ~0.26 · HP: ~190 Hz · LP: ~13.5 kHz.",
      },
      fx: {
        title: "FX / Ear candy bus (Rock)",
        summary:
          "FX con colas algo más largas y phaser suave para transiciones y detalles creativos.",
        params:
          "Reverb: Hall (~2.4–2.6 s) · Predelay: ~30 ms · Send: -12 dB (~25 %) · Delay: ~360 ms, fb ~0.35 · Phaser suave · HP: ~260 Hz · LP: ~16.5 kHz.",
      },
      misc: {
        title: "Other / Misc bus (Rock)",
        summary:
          "Room neutro para cualquier elemento residual, sin llamar la atención.",
        params:
          "Reverb: Room (~0.8 s) · Predelay: ~15–18 ms · Send: -20 dB (~10 %) · HP: ~230–250 Hz · LP: ~13 kHz.",
      },
    },
  },

  latin_pop: {
    label: "Latin pop / Reggaeton",
    description:
      "Similar al urban, pero un punto más suave y musical: voces pop modernas, drums elegantes y FX presentes pero no extremos.",
    buses: {
      drums: {
        title: "Drums bus (Latin pop)",
        summary:
          "Room suave que suaviza transitorios y da cohesión en grooves bailables.",
        params:
          "Reverb: Room (~0.7 s) · Predelay: ~10 ms · Send: -20 dB (~10 %) · HP: ~320 Hz · LP: ~10.5 kHz.",
      },
      bass: {
        title: "Bass bus (Latin pop)",
        summary:
          "Bajo centrado y definido, con el low end típico de reggaeton/latin pop sin colas largas.",
        params:
          "Reverb: Casi seca · Predelay: ~5 ms · Send: -45 dB (~0.6 %) · HP: ~80 Hz · LP: ~6.5 kHz.",
      },
      guitars: {
        title: "Guitars bus (Latin pop)",
        summary:
          "Plate musical y eco medio que asientan las guitarras en el groove.",
        params:
          "Reverb: Plate (~1.4–1.6 s) · Predelay: ~24 ms · Send: -18 dB (~13 %) · Delay: ~240 ms, fb ~0.20 · HP: ~220 Hz · LP: ~11.5 kHz.",
      },
      keys_synth: {
        title: "Keys / Synths bus (Latin pop)",
        summary:
          "Hall compacto para teclados y pads que acompañan sin robar foco a la voz.",
        params:
          "Reverb: Hall (~2.0 s) · Predelay: ~28 ms · Send: -18 dB (~13 %) · Delay: ~300 ms, fb ~0.24 · HP: ~240 Hz · LP: ~15 kHz.",
      },
      lead_vocal: {
        title: "Lead vocal bus (Latin pop)",
        summary:
          "Lead vocal moderna con plate pop y eco con groove, muy clara y presente.",
        params:
          "Reverb: Plate (~1.6–1.8 s) · Predelay: ~90 ms · Send: -15 dB (~18 %) · Delay: ~230 ms, fb ~0.26 · HP: ~180 Hz · LP: ~12.5 kHz.",
      },
      backing_vocals: {
        title: "Backing vocals bus (Latin pop)",
        summary:
          "Coros envolventes que rodean la lead, perfectos para estribillos grandes.",
        params:
          "Reverb: Hall (~2.1–2.3 s) · Predelay: ~60 ms · Send: -13 dB (~22 %) · Delay: ~280 ms, fb ~0.28 · HP: ~200 Hz · LP: ~13.5 kHz.",
      },
      fx: {
        title: "FX / Ear candy bus (Latin pop)",
        summary:
          "FX con colas amplias pero musicales, ideales para transiciones y lifts.",
        params:
          "Reverb: Hall (~2.4–2.6 s) · Predelay: ~40 ms · Send: -11 dB (~28 %) · Delay: ~380 ms, fb ~0.34 · Phaser suave · HP: ~270 Hz · LP: ~17.5 kHz.",
      },
      misc: {
        title: "Other / Misc bus (Latin pop)",
        summary:
          "Room discreto para elementos varios, aporta pegamento sin exceso de wash.",
        params:
          "Reverb: Room (~0.8 s) · Predelay: ~16 ms · Send: -22 dB (~8 %) · HP: ~250 Hz · LP: ~13 kHz.",
      },
    },
  },

  edm: {
    label: "EDM / Club",
    description:
      "Drums y bass extremadamente secos, pads y FX muy espaciales con halls grandes y colas largas filtradas en graves.",
    buses: {
      drums: {
        title: "Drums bus (EDM)",
        summary:
          "Room mínimo que une la batería pero deja el kick mega seco y contundente.",
        params:
          "Reverb: Room (~0.6–0.7 s) · Predelay: ~6 ms · Send: -22 dB (~8 %) · HP: ~380 Hz · LP: ~10 kHz.",
      },
      bass: {
        title: "Bass bus (EDM)",
        summary:
          "Sub y bass casi completamente secos, dando toda la pegada al low end.",
        params:
          "Reverb: Casi seca · Predelay: ~5 ms · Send: -55 dB (~0.2 %) · HP: ~70 Hz · LP: ~5.5 kHz.",
      },
      guitars: {
        title: "Guitars bus (EDM)",
        summary:
          "Plate ligero y delay medio para guitarras complementarias; nunca protagonistas.",
        params:
          "Reverb: Plate (~1.4–1.6 s) · Predelay: ~22 ms · Send: -20 dB (~10 %) · Delay: ~260 ms, fb ~0.24 · HP: ~230 Hz · LP: ~11.5 kHz.",
      },
      keys_synth: {
        title: "Keys / Synths bus (EDM)",
        summary:
          "Pads y supersaws hiper amplios con hall grande y modulación suave, típicos de EDM.",
        params:
          "Reverb: Hall (~2.4–2.8 s) · Predelay: ~35 ms · Send: -14 dB (~25 %) · Delay: ~350 ms, fb ~0.32 · Chorus profundo (depth ~0.22) · HP: ~260 Hz · LP: ~17 kHz.",
      },
      lead_vocal: {
        title: "Lead vocal bus (EDM)",
        summary:
          "Lead vocal flotando sobre el muro de synths con hall moderno y delays claros.",
        params:
          "Reverb: Hall (~2.0–2.3 s) · Predelay: ~90 ms · Send: -15 dB (~18 %) · Delay: ~280 ms, fb ~0.30 · HP: ~190 Hz · LP: ~13 kHz.",
      },
      backing_vocals: {
        title: "Backing vocals bus (EDM)",
        summary:
          "Coros en un plano más ambient, cohesionados con pads y FX.",
        params:
          "Reverb: Hall (~2.3–2.5 s) · Predelay: ~60 ms · Send: -13 dB (~22 %) · Delay: ~320 ms, fb ~0.32 · HP: ~210 Hz · LP: ~14 kHz.",
      },
      fx: {
        title: "FX / Ear candy bus (EDM)",
        summary:
          "Risers, impacts y sweeps con colas exageradas y movimiento estéreo.",
        params:
          "Reverb: Hall (~2.6–3.0 s) · Predelay: ~40 ms · Send: -10 dB (~32 %) · Delay: ~420 ms, fb ~0.40 · Phaser marcado · HP: ~300 Hz · LP: ~19 kHz.",
      },
      misc: {
        title: "Other / Misc bus (EDM)",
        summary:
          "Room neutro para elementos extra, sin añadir wash adicional a una mezcla ya muy espacial.",
        params:
          "Reverb: Room (~0.8 s) · Predelay: ~16–18 ms · Send: -20 a -22 dB (~8–10 %) · HP: ~240–260 Hz · LP: ~13–14 kHz.",
      },
    },
  },

  ballad_ambient: {
    label: "Balada / Ambient",
    description:
      "Halls largos y etéreos pero muy filtrados en graves. Mucho espacio y profundidad, pero con claridad en voz y bajo.",
    buses: {
      drums: {
        title: "Drums bus (Balada / Ambient)",
        summary:
          "Room suave que da aire a la batería sin convertirla en pura reverb.",
        params:
          "Reverb: Room (~0.7 s) · Predelay: ~12 ms · Send: -20 dB (~10 %) · HP: ~320 Hz · LP: ~10 kHz.",
      },
      bass: {
        title: "Bass bus (Balada / Ambient)",
        summary:
          "Bajo definido, casi seco, que sostiene la mezcla mientras el espacio lo aportan las capas superiores.",
        params:
          "Reverb: Casi seca · Predelay: ~5 ms · Send: -45 dB (~0.6 %) · HP: ~80 Hz · LP: ~6.5 kHz.",
      },
      guitars: {
        title: "Guitars bus (Balada / Ambient)",
        summary:
          "Guitarras atmosféricas que se convierten casi en pads dentro del hall.",
        params:
          "Reverb: Hall (~2.3–2.5 s) · Predelay: ~30 ms · Send: -18 dB (~13 %) · Delay: ~280 ms, fb ~0.26 · Chorus suave · HP: ~240 Hz · LP: ~12 kHz.",
      },
      keys_synth: {
        title: "Keys / Synths bus (Balada / Ambient)",
        summary:
          "Pads/keys con colas largas y modulación lenta; base del ambiente general.",
        params:
          "Reverb: Hall (~2.6–2.8 s) · Predelay: ~35 ms · Send: -16 dB (~16 %) · Delay: ~360 ms, fb ~0.32 · HP: ~260 Hz · LP: ~16 kHz.",
      },
      lead_vocal: {
        title: "Lead vocal bus (Balada / Ambient)",
        summary:
          "Voz principal flotante, con hall vocal grande pero predelay largo para conservar claridad.",
        params:
          "Reverb: Hall (~2.2–2.5 s) · Predelay: ~95 ms · Send: -16 dB (~16 %) · Delay: ~260 ms, fb ~0.28 · HP: ~180 Hz · LP: ~12.5 kHz.",
      },
      backing_vocals: {
        title: "Backing vocals bus (Balada / Ambient)",
        summary:
          "Coros casi tipo “pad vocal”, muy ambient y rodeando a la lead.",
        params:
          "Reverb: Hall (~2.6–2.8 s) · Predelay: ~70 ms · Send: -14 dB (~20 %) · Delay: ~320 ms, fb ~0.32 · HP: ~200 Hz · LP: ~13.5 kHz.",
      },
      fx: {
        title: "FX / Ear candy bus (Balada / Ambient)",
        summary:
          "FX etéreos y suaves que se fusionan con pads y coros, ampliando el espacio percibido.",
        params:
          "Reverb: Hall (~2.8–3.0 s) · Predelay: ~45 ms · Send: -12 dB (~25 %) · Delay: ~420 ms, fb ~0.38 · Phaser suave · HP: ~280 Hz · LP: ~18 kHz.",
      },
      misc: {
        title: "Other / Misc bus (Balada / Ambient)",
        summary:
          "Room neutro para fuentes secundarias, sumando profundidad sin descontrol.",
        params:
          "Reverb: Room (~0.8 s) · Predelay: ~18 ms · Send: -20 dB (~10 %) · HP: ~230–250 Hz · LP: ~13 kHz.",
      },
    },
  },

  acoustic: {
    label: "Acústico / Singer-songwriter",
    description:
      "Pensado para producciones íntimas: rooms cortos, plates suaves en voz y casi todo relativamente seco. Natural y cercano.",
    buses: {
      drums: {
        title: "Drums bus (Acoustic)",
        summary:
          "Si hay batería/percusiones, suenan en sala pequeña, sin convertirse en un mar de reverb.",
        params:
          "Reverb: Room (~0.6–0.7 s) · Predelay: ~8 ms · Send: -22 dB (~8 %) · HP: ~320 Hz · LP: ~10 kHz.",
      },
      bass: {
        title: "Bass bus (Acoustic)",
        summary:
          "Bajo muy cercano, casi sin FX; prioriza sensación de directo.",
        params:
          "Reverb: Casi seca · Predelay: ~5 ms · Send: -50 dB (~0.3 %) · HP: ~90 Hz · LP: ~6.5 kHz.",
      },
      guitars: {
        title: "Guitars bus (Acoustic)",
        summary:
          "Guitarras acústicas con room corto y delay discreto, como en una sala pequeña bien microfoneada.",
        params:
          "Reverb: Room (~0.7–0.9 s) · Predelay: ~18 ms · Send: -20 dB (~10 %) · Delay: ~220 ms, fb ~0.16 · HP: ~220 Hz · LP: ~11.5 kHz.",
      },
      keys_synth: {
        title: "Keys / Synths bus (Acoustic)",
        summary:
          "Pianos y keys muy contenidos en espacio, soporte a la voz más que protagonista.",
        params:
          "Reverb: Room (~0.8 s) · Predelay: ~20 ms · Send: -20 dB (~10 %) · Delay: ~260 ms, fb ~0.18 · HP: ~230 Hz · LP: ~13.5 kHz.",
      },
      lead_vocal: {
        title: "Lead vocal bus (Acoustic)",
        summary:
          "Voz íntima y cercana, con plate suave y slapback corto; sensación de cantante en la misma habitación.",
        params:
          "Reverb: Plate (~1.4–1.6 s) · Predelay: ~70 ms · Send: -17 dB (~14 %) · Delay: ~150 ms, fb ~0.22 · HP: ~180 Hz · LP: ~12 kHz.",
      },
      backing_vocals: {
        title: "Backing vocals bus (Acoustic)",
        summary:
          "Coros discretos que arropan la lead sin quitar protagonismo al mensaje.",
        params:
          "Reverb: Hall (~2.0–2.2 s) · Predelay: ~55 ms · Send: -15 dB (~18 %) · Delay: ~260 ms, fb ~0.24 · HP: ~200 Hz · LP: ~13 kHz.",
      },
      fx: {
        title: "FX / Ear candy bus (Acoustic)",
        summary:
          "FX ambiente muy suave, para dar profundidad sin romper la estética acústica.",
        params:
          "Reverb: Hall (~2.2–2.4 s) · Predelay: ~35 ms · Send: -13 dB (~22 %) · Delay: ~360 ms, fb ~0.30 · HP: ~260 Hz · LP: ~17 kHz.",
      },
      misc: {
        title: "Other / Misc bus (Acoustic)",
        summary:
          "Room pequeño que ayuda a que todo parezca grabado en la misma sala.",
        params:
          "Reverb: Room (~0.8 s) · Predelay: ~16 ms · Send: -22 dB (~8 %) · HP: ~230 Hz · LP: ~13 kHz.",
      },
    },
  },
};

export function SpaceDepthStylePanel({ buses, value, onChange }: Props) {
  const [info, setInfo] = useState<{ busKey: string; style: string } | null>(
    null,
  );

  if (!buses.length) return null;

  const currentStyleDoc =
    info && STYLE_DOCS[info.style]
      ? STYLE_DOCS[info.style]
      : info
      ? STYLE_DOCS["auto"]
      : undefined;
  const currentBusDoc =
    info && currentStyleDoc
      ? currentStyleDoc.buses[info.busKey] ??
        currentStyleDoc.buses["misc"] ??
        undefined
      : undefined;

  return (
    <>
      <aside className="rounded-2xl border border-slate-800/80 bg-slate-900/80 p-4 text-xs shadow-lg">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-300">
          Space / Depth by bus
        </h3>
        <p className="mt-1 text-[11px] text-slate-400">
          Elige el carácter de reverb, delay y modulación para cada bus. Estos
          presets controlan rooms, plates, halls, springs y filtros para que la
          mezcla tenga profundidad sin ensuciarse.
        </p>

        <div className="mt-3 space-y-2">
          {buses.map((bus) => {
            const selectedStyle = value[bus.key] ?? "auto";

            return (
              <div
                key={bus.key}
                className="flex items-center justify-between gap-2 rounded-lg bg-slate-950/60 px-2.5 py-2"
              >
                <div className="min-w-0">
                  <p className="truncate text-[11px] font-medium text-slate-100">
                    {bus.label}
                  </p>
                  {bus.description && (
                    <p className="mt-0.5 text-[10px] text-slate-400">
                      {bus.description}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-1">
                  <select
                    className="max-w-[10rem] rounded-md border border-slate-700 bg-slate-900 px-2 py-1 text-[11px] text-slate-100 outline-none focus:border-teal-400 focus:ring-1 focus:ring-teal-400"
                    value={selectedStyle}
                    onChange={(e) => onChange(bus.key, e.target.value)}
                  >
                    {STYLE_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    className="inline-flex h-6 w-6 items-center justify-center rounded-full border border-slate-600 text-[10px] font-semibold text-slate-200 hover:border-teal-400 hover:text-teal-300"
                    onClick={() =>
                      setInfo({
                        busKey: bus.key,
                        style: selectedStyle,
                      })
                    }
                    aria-label="Ver detalles de Space/Depth para este bus"
                  >
                    i
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </aside>

      {info && currentStyleDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="max-h-[80vh] w-full max-w-xl overflow-y-auto rounded-2xl border border-slate-700 bg-slate-950 p-4 shadow-2xl">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-wide text-teal-300">
                  Space / Depth preset
                </p>
                <h4 className="text-sm font-semibold text-slate-50">
                  {currentStyleDoc.label}
                </h4>
                <p className="mt-1 text-[11px] text-slate-300">
                  {currentStyleDoc.description}
                </p>
              </div>
              <button
                type="button"
                className="ml-2 inline-flex h-6 w-6 items-center justify-center rounded-full border border-slate-600 text-[11px] text-slate-200 hover:border-teal-400 hover:text-teal-300"
                onClick={() => setInfo(null)}
                aria-label="Cerrar"
              >
                ✕
              </button>
            </div>

            {currentBusDoc && (
              <div className="mt-3 rounded-xl bg-slate-900/80 p-3">
                <p className="text-[11px] font-semibold text-slate-100">
                  En este bus ({currentBusDoc.title}):
                </p>
                <p className="mt-1 text-[11px] text-slate-300">
                  {currentBusDoc.summary}
                </p>
                <p className="mt-1 text-[11px] text-slate-400">
                  {currentBusDoc.params}
                </p>
              </div>
            )}

            <div className="mt-4 border-t border-slate-800 pt-3">
              <p className="text-[11px] font-semibold text-slate-200">
                Detalle por bus en este estilo
              </p>
              <div className="mt-2 space-y-2">
                {Object.entries(currentStyleDoc.buses).map(
                  ([busKey, busDoc]) => (
                    <div
                      key={busKey}
                      className={`rounded-lg border px-2.5 py-2 ${
                        info.busKey === busKey
                          ? "border-teal-400/80 bg-teal-950/40"
                          : "border-slate-800 bg-slate-900/60"
                      }`}
                    >
                      <p className="text-[11px] font-semibold text-slate-100">
                        {busDoc.title}
                      </p>
                      <p className="mt-0.5 text-[11px] text-slate-300">
                        {busDoc.summary}
                      </p>
                      <p className="mt-0.5 text-[11px] text-slate-400">
                        {busDoc.params}
                      </p>
                    </div>
                  ),
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
