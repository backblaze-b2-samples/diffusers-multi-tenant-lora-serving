/** Scale choices offered wherever an adapter scale is picked. */
export const SCALE_OPTIONS = ["0.5", "0.8", "1.0", "1.2"] as const;

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
