import { zodResolver } from "@hookform/resolvers/zod";
import { describe, expect, it } from "vitest";

import { settingsSchema, type SettingsValues } from "@/lib/settings-schema";

const valid: SettingsValues = { theme: "dark", defaultSteps: "25", defaultSize: "1024" };

async function resolve(values: unknown) {
  const resolver = zodResolver(settingsSchema);
  return resolver(values as SettingsValues, undefined, {
    fields: {},
    shouldUseNativeValidation: false,
  });
}

describe("settingsSchema", () => {
  it("accepts a valid form through the resolver", async () => {
    const result = await resolve(valid);
    expect(result.errors).toEqual({});
    expect(result.values).toEqual(valid);
  });

  it("rejects values outside the option lists", () => {
    expect(settingsSchema.safeParse({ ...valid, theme: "sepia" }).success).toBe(false);
    expect(settingsSchema.safeParse({ ...valid, defaultSteps: "12" }).success).toBe(false);
    expect(settingsSchema.safeParse({ ...valid, defaultSize: "512" }).success).toBe(false);
  });
});
