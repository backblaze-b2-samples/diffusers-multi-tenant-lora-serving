/**
 * Generate-form defaults, stored in this browser only.
 *
 * Two demo preferences: the default step count and image size that prefill
 * the Generate and Compare forms. They are saved to `localStorage` (there is
 * no account system) and namespaced by the app slug.
 *
 * Theme is NOT here; it is owned by `next-themes` (see `theme-preference.ts`).
 */

import { APP_SLUG } from "@/lib/app-config";

export const STEP_OPTIONS = ["15", "25", "40"] as const;
export const SIZE_OPTIONS = ["768", "1024"] as const;
export type StepOption = (typeof STEP_OPTIONS)[number];
export type SizeOption = (typeof SIZE_OPTIONS)[number];

export interface DemoPreferences {
  defaultSteps: StepOption;
  defaultSize: SizeOption;
}

export const DEMO_PREFERENCES_DEFAULTS: DemoPreferences = {
  defaultSteps: "25",
  defaultSize: "1024",
};

/** Namespaced by app slug so two of these apps on one origin cannot collide. */
export const DEMO_PREFERENCES_STORAGE_KEY = `${APP_SLUG}-demo-preferences`;

function oneOf<T extends string>(options: readonly T[], value: unknown, fallback: T): T {
  return typeof value === "string" && (options as readonly string[]).includes(value)
    ? (value as T)
    : fallback;
}

/**
 * Read the stored preferences, tolerating a missing, corrupt or partial blob by
 * falling back field by field. SSR-safe: returns the defaults without `window`.
 */
export function loadDemoPreferences(): DemoPreferences {
  if (typeof window === "undefined") return { ...DEMO_PREFERENCES_DEFAULTS };
  let stored: unknown;
  try {
    const raw = window.localStorage.getItem(DEMO_PREFERENCES_STORAGE_KEY);
    if (!raw) return { ...DEMO_PREFERENCES_DEFAULTS };
    stored = JSON.parse(raw);
  } catch {
    return { ...DEMO_PREFERENCES_DEFAULTS };
  }
  if (typeof stored !== "object" || stored === null) return { ...DEMO_PREFERENCES_DEFAULTS };
  const s = stored as Record<string, unknown>;
  return {
    defaultSteps: oneOf(STEP_OPTIONS, s.defaultSteps, DEMO_PREFERENCES_DEFAULTS.defaultSteps),
    defaultSize: oneOf(SIZE_OPTIONS, s.defaultSize, DEMO_PREFERENCES_DEFAULTS.defaultSize),
  };
}

/** Persist; returns false when there is no `window` or storage is blocked. */
export function saveDemoPreferences(values: DemoPreferences): boolean {
  if (typeof window === "undefined") return false;
  try {
    window.localStorage.setItem(DEMO_PREFERENCES_STORAGE_KEY, JSON.stringify(values));
    return true;
  } catch {
    return false;
  }
}
