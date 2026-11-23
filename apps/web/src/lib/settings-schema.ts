import { z } from "zod";

import { SIZE_OPTIONS, STEP_OPTIONS } from "@/lib/demo-preferences";
import { THEME_OPTIONS } from "@/lib/theme-preference";

/**
 * Validation for the Settings form (`components/settings/settings-form.tsx`).
 * Kept outside the component so the rules are unit-tested without rendering.
 */
export const settingsSchema = z.object({
  theme: z.enum(THEME_OPTIONS),
  defaultSteps: z.enum(STEP_OPTIONS),
  defaultSize: z.enum(SIZE_OPTIONS),
});

export type SettingsValues = z.infer<typeof settingsSchema>;
