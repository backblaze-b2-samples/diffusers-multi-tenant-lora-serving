"use client";

import { useSyncExternalStore } from "react";

import {
  DEMO_PREFERENCES_DEFAULTS,
  DEMO_PREFERENCES_STORAGE_KEY,
  loadDemoPreferences,
  type DemoPreferences,
} from "@/lib/demo-preferences";

let cached: { raw: string | null; value: DemoPreferences } | null = null;

function snapshot(): DemoPreferences {
  let raw: string | null = null;
  try {
    raw = window.localStorage.getItem(DEMO_PREFERENCES_STORAGE_KEY);
  } catch {
    raw = null;
  }
  if (!cached || cached.raw !== raw) cached = { raw, value: loadDemoPreferences() };
  return cached.value;
}

function subscribe(onChange: () => void) {
  window.addEventListener("storage", onChange);
  return () => window.removeEventListener("storage", onChange);
}

/** The stored Generate defaults; the built-in defaults during server render. */
export function useDemoPreferences(): DemoPreferences {
  return useSyncExternalStore(subscribe, snapshot, () => DEMO_PREFERENCES_DEFAULTS);
}
