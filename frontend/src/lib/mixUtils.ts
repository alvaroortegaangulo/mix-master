
import { PipelineStage } from "./mixApi";

// Helper to default only MASTERING stages for Song mode
export function getSongModeStages(allStages: PipelineStage[]): string[] {
  // We want to enable stages from S7 onwards by default for 'song' mode.
  // Or specifically: S7, S8, S9, S10, S11.
  const masteringPrefixes = ["S7", "S8", "S9", "S10", "S11"];
  return allStages
    .filter((s) => masteringPrefixes.some((pre) => s.key.startsWith(pre)))
    .map((s) => s.key);
}
