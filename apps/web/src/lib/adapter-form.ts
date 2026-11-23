/** Scale choices offered wherever an adapter scale is picked. */
export const SCALE_OPTIONS = ["0.5", "0.8", "1.0", "1.2"] as const;

/** Prompt placeholder: phrased as an example so it never reads as pre-filled text. */
export const PROMPT_PLACEHOLDER = "Describe the image, e.g. a lighthouse on a cliff at sunset";
/** An empty seed field means the dispatcher picks a random seed. */
export const SEED_PLACEHOLDER = "Random";

/** "1" -> "1.0": match a stored scale to a SCALE_OPTIONS entry. */
export function scaleOption(scale: number): string {
  return scale.toFixed(1);
}

/** Split a comma-separated trigger-words input into clean words. */
export function splitTriggerWords(text: string): string[] {
  return text
    .split(",")
    .map((w) => w.trim())
    .filter(Boolean);
}
