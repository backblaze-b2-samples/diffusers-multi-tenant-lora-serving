"use client";

import { useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useTheme } from "next-themes";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { ServerConfigCard } from "./server-config-card";
import { DEFAULT_THEME, THEME_OPTIONS, normalizeTheme } from "@/lib/theme-preference";
import { settingsSchema, type SettingsValues } from "@/lib/settings-schema";
import {
  DEMO_PREFERENCES_DEFAULTS,
  SIZE_OPTIONS,
  STEP_OPTIONS,
  loadDemoPreferences,
  saveDemoPreferences,
} from "@/lib/demo-preferences";

// Theme is owned by next-themes and applied for real. The two Generate
// defaults are stored in this browser and prefill the Generate and Compare
// forms. The Server card is read-only dispatcher configuration.
const defaultValues: SettingsValues = { ...DEMO_PREFERENCES_DEFAULTS, theme: DEFAULT_THEME };

export function SettingsForm() {
  const [submitting, setSubmitting] = useState(false);
  const { setTheme, theme } = useTheme();
  const hydratedRef = useRef(false);
  const form = useForm<SettingsValues>({ resolver: zodResolver(settingsSchema), defaultValues });

  // Hydrate once, after next-themes has resolved the active theme on the client.
  useEffect(() => {
    if (hydratedRef.current || theme === undefined) return;
    hydratedRef.current = true;
    form.reset({ ...loadDemoPreferences(), theme: normalizeTheme(theme) });
  }, [form, theme]);

  const onSubmit = (values: SettingsValues) => {
    setSubmitting(true);
    setTheme(values.theme);
    const { theme: _theme, ...prefs } = values;
    const stored = saveDemoPreferences(prefs);
    setSubmitting(false);
    if (stored) {
      toast.success("Preferences saved in this browser", {
        description: "New Generate and Compare forms start from these defaults.",
      });
    } else {
      toast.warning("Theme applied; defaults not stored", {
        description: "Your browser blocked local storage, so the defaults won't persist.",
      });
    }
  };

  return (
    <div className="space-y-6">
      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
          <Card>
            <CardHeader className="border-b border-border py-4 px-5">
              <CardTitle className="card-title">Preferences</CardTitle>
            </CardHeader>
            <CardContent className="p-5 space-y-6">
              <FormField
                control={form.control}
                name="theme"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Theme</FormLabel>
                    <FormControl>
                      <RadioGroup onValueChange={field.onChange} value={field.value} className="flex gap-6">
                        {THEME_OPTIONS.map((t) => (
                          <label key={t} className="flex items-center gap-2 text-sm capitalize cursor-pointer">
                            <RadioGroupItem value={t} />
                            {t}
                          </label>
                        ))}
                      </RadioGroup>
                    </FormControl>
                    <FormDescription>Applied when you save. The header toggle changes it too.</FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="defaultSteps"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Default steps</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl>
                        <SelectTrigger className="w-40" aria-label="Default steps">
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {STEP_OPTIONS.map((s) => (
                          <SelectItem key={s} value={s}>
                            {s} steps
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormDescription>Prefills Generate. More steps: more detail, slower.</FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="defaultSize"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Default size</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl>
                        <SelectTrigger className="w-40" aria-label="Default size">
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {SIZE_OPTIONS.map((s) => (
                          <SelectItem key={s} value={s}>
                            {s} × {s}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormDescription>SDXL is trained at 1024; 768 renders faster.</FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </CardContent>
          </Card>
          <div className="flex items-center justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => form.reset({ ...DEMO_PREFERENCES_DEFAULTS, theme: DEFAULT_THEME })}
            >
              Reset
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? "Saving..." : "Save changes"}
            </Button>
          </div>
        </form>
      </Form>
      <ServerConfigCard />
    </div>
  );
}
