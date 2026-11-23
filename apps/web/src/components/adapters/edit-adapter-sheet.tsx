"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Pencil } from "lucide-react";
import { toast } from "sonner";
import type { AdapterDetail } from "@diffusers-multi-tenant-lora-serving/shared";

import { Button } from "@/components/ui/button";
import { Form, FormControl, FormDescription, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { SCALE_OPTIONS, scaleOption, splitTriggerWords } from "@/lib/adapter-form";
import { useUpdateAdapter } from "@/lib/queries";

const editSchema = z.object({
  display_name: z.string().min(1, "Required").max(80),
  default_scale: z.enum(SCALE_OPTIONS),
  trigger_words: z.string(),
  current_version: z.string().min(1),
});
type EditValues = z.infer<typeof editSchema>;

function valuesFor(a: AdapterDetail): EditValues {
  const scale = scaleOption(a.default_scale);
  return {
    display_name: a.display_name,
    default_scale: (SCALE_OPTIONS as readonly string[]).includes(scale) ? (scale as EditValues["default_scale"]) : "1.0",
    trigger_words: a.trigger_words.join(", "),
    current_version: a.current_version,
  };
}

/** Edit the tenant-manifest entry: name, default scale, trigger words, current version. */
export function EditAdapterSheet({ adapter }: { adapter: AdapterDetail }) {
  const [open, setOpen] = useState(false);
  const update = useUpdateAdapter(adapter.tenant_id, adapter.adapter);
  const form = useForm<EditValues>({ resolver: zodResolver(editSchema), values: valuesFor(adapter) });

  const onSubmit = (v: EditValues) =>
    update.mutate(
      {
        display_name: v.display_name,
        default_scale: Number(v.default_scale),
        trigger_words: splitTriggerWords(v.trigger_words),
        current_version: v.current_version,
      },
      {
        onSuccess: () => {
          toast.success("Adapter updated", { description: "The tenant manifest in B2 was rewritten." });
          setOpen(false);
        },
        onError: (e) => toast.error("Update failed", { description: e.message }),
      },
    );

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button variant="outline" size="sm" className="h-8">
          <Pencil className="h-3.5 w-3.5" />
          Edit
        </Button>
      </SheetTrigger>
      <SheetContent>
        <SheetHeader>
          <SheetTitle>Edit {adapter.adapter}</SheetTitle>
          <SheetDescription>Changes the tenant manifest entry. Published weights never change.</SheetDescription>
        </SheetHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4 px-4">
            <FormField
              control={form.control}
              name="display_name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Display name</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="default_scale"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Default scale</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange}>
                    <FormControl>
                      <SelectTrigger aria-label="Default scale">
                        <SelectValue />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {SCALE_OPTIONS.map((s) => (
                        <SelectItem key={s} value={s}>
                          {s}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="trigger_words"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Trigger words</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormDescription>Comma separated</FormDescription>
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="current_version"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Current version</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange}>
                    <FormControl>
                      <SelectTrigger aria-label="Current version">
                        <SelectValue />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {adapter.versions.map((v) => (
                        <SelectItem key={v.version} value={v.version}>
                          {v.version}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormDescription>Requests without @version resolve to this one.</FormDescription>
                </FormItem>
              )}
            />
            <Button type="submit" disabled={update.isPending} className="w-full">
              {update.isPending ? "Saving…" : "Save"}
            </Button>
          </form>
        </Form>
      </SheetContent>
    </Sheet>
  );
}
