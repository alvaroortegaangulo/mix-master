export type StemCounts = {
  total: number;
  vocals: number;
  drums: number;
};

type Coefficient = {
  base: number;
  dur: number;
  stemDur: number;
};

// Coefficients derived from analysis of processing times
export const ESTIMATION_COEFFICIENTS: Record<string, Coefficient> = {
  S0_SESSION_FORMAT: { base: 5, dur: 0, stemDur: 0.025 },
  S1_STEM_DC_OFFSET: { base: 1, dur: 0, stemDur: 0.0035 },
  S1_STEM_WORKING_LOUDNESS: { base: 1, dur: 0, stemDur: 0.036 },
  S1_KEY_DETECTION: { base: 2, dur: 0.04, stemDur: 0 },
  S1_VOX_TUNING: { base: 2, dur: 0, stemDur: 0.12 }, // vocal stems
  S2_GROUP_PHASE_DRUMS: { base: 1, dur: 0, stemDur: 0.02 }, // drum stems
  S3_MIXBUS_HEADROOM: { base: 2, dur: 0.05, stemDur: 0 },
  S3_LEADVOX_AUDIBILITY: { base: 1, dur: 0.11, stemDur: 0 },
  S4_STEM_HPF_LPF: { base: 1, dur: 0, stemDur: 0.02 },
  S4_STEM_RESONANCE_CONTROL: { base: 10, dur: 0, stemDur: 0.06 },
  S5_STEM_DYNAMICS_GENERIC: { base: 1, dur: 0, stemDur: 0.025 },
  S5_LEADVOX_DYNAMICS: { base: 1, dur: 0, stemDur: 0.05 }, // vocal stems
  S5_BUS_DYNAMICS_DRUMS: { base: 1, dur: 0.03, stemDur: 0 },
  S6_BUS_REVERB_STYLE: { base: 1, dur: 0.05, stemDur: 0 },
  S6_MANUAL_CORRECTION: { base: 1, dur: 0.05, stemDur: 0 },
  S7_MIXBUS_TONAL_BALANCE: { base: 2, dur: 0.04, stemDur: 0 },
  S8_MIXBUS_COLOR_GENERIC: { base: 2, dur: 0.12, stemDur: 0 },
  S9_MASTER_GENERIC: { base: 2, dur: 0.21, stemDur: 0 },
  S10_MASTER_FINAL_LIMITS: { base: 2, dur: 0.21, stemDur: 0 },
  S11_REPORT_GENERATION: { base: 3, dur: 0.11, stemDur: 0 },
};

const STAGE_STEM_TYPE: Record<string, keyof StemCounts> = {
  S1_VOX_TUNING: "vocals",
  S5_LEADVOX_DYNAMICS: "vocals",
  S2_GROUP_PHASE_DRUMS: "drums",
};

export function calculateStageEstimate(
  stageKey: string,
  duration: number,
  stemCounts: StemCounts
): number {
  const coeff = ESTIMATION_COEFFICIENTS[stageKey];
  if (!coeff) return 15; // Default fallback

  const countKey = STAGE_STEM_TYPE[stageKey] || "total";
  const count = stemCounts[countKey];

  // Skip if dependent on specific stems that are not present
  if ((countKey === "vocals" || countKey === "drums") && count === 0) {
      return 0;
  }

  return Math.ceil(
    coeff.base +
    coeff.dur * duration +
    coeff.stemDur * count * duration
  );
}

export async function getAudioDuration(file: File): Promise<number> {
  return new Promise((resolve) => {
    // Basic validation for audio types
    if (!file.type.startsWith('audio/') && !file.name.match(/\.(wav|mp3|aif|aiff|m4a|flac)$/i)) {
        resolve(180); // Default for unknown types
        return;
    }

    try {
        const objectUrl = URL.createObjectURL(file);
        const audio = new Audio();

        const cleanup = () => {
            URL.revokeObjectURL(objectUrl);
            audio.onloadedmetadata = null;
            audio.onerror = null;
        };

        audio.onloadedmetadata = () => {
            const dur = audio.duration;
            cleanup();
            resolve(Number.isFinite(dur) ? dur : 180);
        };

        audio.onerror = () => {
            cleanup();
            resolve(180); // Fallback on error
        };

        audio.src = objectUrl;
        audio.load(); // Trigger load
    } catch (e) {
        resolve(180);
    }
  });
}
