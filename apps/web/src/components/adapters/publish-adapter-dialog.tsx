"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Plus } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { SCALE_OPTIONS } from "@/lib/adapter-form";
import { usePublishAdapter, useServerConfig, useTenants } from "@/lib/queries";

const NEW_TENANT = "__new__";
const NAME = /^[a-z0-9][a-z0-9-]{1,38}[a-z0-9]$/;
const nameField = z.string().regex(NAME, "Lowercase letters, digits and hyphens (3-40 characters)");

export const publishSchema = z
  .object({
    tenantChoice: z.string().min(1, "Pick a tenant"),
    newTenant: z.string().optional(),
    adapter: nameField,
    version: z.string().regex(/^v[0-9]+(\.[0-9]+){0,2}$/, "Use v1, v1.2 or v1.2.3"),
    source: z.enum(["huggingface", "upload"]),
    hf_repo_id: z.string().optional(),
    hf_filename: z.string().optional(),
    hf_revision: z.string().optional(),
    file: z.instanceof(File).nullable().optional(),
    license: z.string().min(1, "Pick the adapter's license"),
    default_scale: z.string().optional(),
    trigger_words: z.string().optional(),
  })
  .superRefine((v, ctx) => {
    if (v.tenantChoice === NEW_TENANT && !NAME.test(v.newTenant ?? "")) {
      ctx.addIssue({ code: "custom", path: ["newTenant"], message: "Lowercase letters, digits and hyphens" });
    }
    if (v.source === "huggingface" && !(v.hf_repo_id && v.hf_filename)) {
      ctx.addIssue({ code: "custom", path: ["hf_repo_id"], message: "Repository and filename are required" });
    }
    if (v.source === "upload" && !v.file?.name.endsWith(".safetensors")) {
      ctx.addIssue({ code: "custom", path: ["file"], message: "Choose a .safetensors file" });
    }
  });

type PublishValues = z.infer<typeof publishSchema>;

/** Create an adapter, or a new version of one (same tenant and adapter name). */
export function PublishAdapterDialog({ defaultTenant }: { defaultTenant?: string }) {
  const [open, setOpen] = useState(false);
  const { data: tenants = [] } = useTenants();
  const { data: server } = useServerConfig();
  const publish = usePublishAdapter();
  const form = useForm<PublishValues>({
    resolver: zodResolver(publishSchema),
    defaultValues: {
      tenantChoice: defaultTenant ?? "",
      newTenant: "",
      adapter: "",
      version: "",
      source: "huggingface",
      hf_repo_id: "",
      hf_filename: "",
      hf_revision: "",
      file: null,
      license: "",
      default_scale: "",
      trigger_words: "",
    },
  });
  const source = form.watch("source");
  const tenantChoice = form.watch("tenantChoice");

  const onSubmit = (v: PublishValues) => {
    const tenant_id = v.tenantChoice === NEW_TENANT ? (v.newTenant ?? "") : v.tenantChoice;
    publish.mutate(
      {
        tenant_id,
        adapter: v.adapter,
        version: v.version,
        license: v.license,
        source: v.source,
        default_scale: Number(v.default_scale || "1.0"),
        trigger_words: v.trigger_words,
        hf_repo_id: v.hf_repo_id,
        hf_filename: v.hf_filename,
        hf_revision: v.hf_revision,
        file: v.file ?? null,
      },
      {
        onSuccess: (d) => {
          toast.success(`Published ${d.tenant_id}/${d.adapter}@${d.current_version}`, {
            description: "Weight, version manifest, then tenant manifest written to B2.",
          });
          setOpen(false);
          form.reset();
        },
        onError: (e) => toast.error("Publish failed", { description: e.message }),
      },
    );
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" className="h-8">
          <Plus className="h-3.5 w-3.5" />
          Publish adapter
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Publish adapter</DialogTitle>
          <DialogDescription>
            A new adapter, or a new version of an existing one. Only SDXL LoRAs in safetensors format.
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" aria-label="Publish adapter">
            <FormField
              control={form.control}
              name="tenantChoice"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Tenant</FormLabel>
                  <Select onValueChange={field.onChange} value={field.value}>
                    <FormControl>
                      <SelectTrigger aria-label="Tenant">
                        <SelectValue placeholder="acme" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {tenants.map((t) => (
                        <SelectItem key={t.tenant_id} value={t.tenant_id}>
                          {t.tenant_id}
                        </SelectItem>
                      ))}
                      <SelectItem value={NEW_TENANT}>New tenant…</SelectItem>
                    </SelectContent>
                  </Select>
                  <FormDescription>lowercase letters, digits and hyphens</FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
            {tenantChoice === NEW_TENANT && (
              <FormField
                control={form.control}
                name="newTenant"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>New tenant id</FormLabel>
                    <FormControl>
                      <Input placeholder="acme" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            )}
            <div className="grid grid-cols-2 gap-4">
              <FormField
                control={form.control}
                name="adapter"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Adapter</FormLabel>
                    <FormControl>
                      <Input placeholder="pixel-art" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="version"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Version</FormLabel>
                    <FormControl>
                      <Input placeholder="v1" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <p className="-mt-2 text-xs text-muted-foreground">
              Versions are immutable; publish v2 to change weights.
            </p>
            <FormField
              control={form.control}
              name="source"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Source</FormLabel>
                  <FormControl>
                    <RadioGroup value={field.value} onValueChange={field.onChange} className="flex gap-6">
                      <label className="flex items-center gap-2 text-sm cursor-pointer">
                        <RadioGroupItem value="huggingface" /> Hugging Face
                      </label>
                      <label className="flex items-center gap-2 text-sm cursor-pointer">
                        <RadioGroupItem value="upload" /> Upload file
                      </label>
                    </RadioGroup>
                  </FormControl>
                </FormItem>
              )}
            />
            {source === "huggingface" ? (
              <div className="space-y-3 rounded-md border border-border p-3">
                <FormField
                  control={form.control}
                  name="hf_repo_id"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Repository</FormLabel>
                      <FormControl>
                        <Input placeholder="nerijs/pixel-art-xl" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="hf_filename"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Filename</FormLabel>
                      <FormControl>
                        <Input placeholder="pixel-art-xl.safetensors" {...field} />
                      </FormControl>
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="hf_revision"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Revision</FormLabel>
                      <FormControl>
                        <Input placeholder="a commit sha keeps the fixture reproducible" {...field} />
                      </FormControl>
                    </FormItem>
                  )}
                />
              </div>
            ) : (
              <FormField
                control={form.control}
                name="file"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Adapter file</FormLabel>
                    <FormControl>
                      <Input
                        type="file"
                        accept=".safetensors"
                        onChange={(e) => field.onChange(e.target.files?.[0] ?? null)}
                      />
                    </FormControl>
                    <FormDescription>SDXL LoRA in safetensors format</FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
            )}
            <div className="grid grid-cols-2 gap-4">
              <FormField
                control={form.control}
                name="license"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>License</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl>
                        <SelectTrigger aria-label="License">
                          <SelectValue placeholder="Select a license" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {(server?.license_allowlist ?? []).map((l) => (
                          <SelectItem key={l} value={l}>
                            {l}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
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
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl>
                        <SelectTrigger aria-label="Default scale">
                          <SelectValue placeholder="1.0" />
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
            </div>
            <FormField
              control={form.control}
              name="trigger_words"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Trigger words</FormLabel>
                  <FormControl>
                    <Input placeholder="pixel art" {...field} />
                  </FormControl>
                  <FormDescription>Comma separated</FormDescription>
                </FormItem>
              )}
            />
            <DialogFooter>
              <Button type="submit" disabled={publish.isPending}>
                {publish.isPending ? "Publishing…" : "Publish"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
