"use client";

import { useState } from "react";
import Link from "next/link";
import { Columns3 } from "lucide-react";
import type { CompareRequest } from "@diffusers-multi-tenant-lora-serving/shared";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { JobImage } from "@/components/jobs/job-image";
import { PROMPT_PLACEHOLDER, SEED_PLACEHOLDER } from "@/lib/adapter-form";
import { SIZE_OPTIONS, STEP_OPTIONS } from "@/lib/demo-preferences";
import { useDemoPreferences } from "@/lib/use-demo-preferences";
import { useAdapters, useCompareAdapters, useRun, useTenants } from "@/lib/queries";

const MAX_ADAPTERS = 4;

/** One prompt and one seed across several of a tenant's adapters, plus the base model. */
export function CompareForm() {
  const { data: tenants = [] } = useTenants();
  const [tenantChoice, setTenant] = useState("");
  const tenant = tenantChoice || tenants[0]?.tenant_id || "";
  const [picked, setPicked] = useState<string[] | null>(null);
  const [includeBase, setIncludeBase] = useState(true);
  const [prompt, setPrompt] = useState("");
  const [seed, setSeed] = useState("");
  const prefs = useDemoPreferences();
  const [stepsChoice, setSteps] = useState("");
  const [sizeChoice, setSize] = useState("");
  const steps = stepsChoice || prefs.defaultSteps;
  const size = sizeChoice || prefs.defaultSize;
  const [runId, setRunId] = useState("");
  const { data: adapters = [] } = useAdapters(tenant || undefined);
  const compare = useCompareAdapters();
  const run = useRun(runId);

  // Default: all of the tenant's adapters (up to the limit).
  const selected = picked ?? adapters.slice(0, MAX_ADAPTERS).map((a) => a.adapter);

  const toggle = (name: string, on: boolean) =>
    setPicked(on ? [...selected, name].slice(0, MAX_ADAPTERS) : selected.filter((n) => n !== name));

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const body: CompareRequest = {
      tenant_id: tenant,
      adapters: selected,
      include_base: includeBase,
      prompt,
      seed: seed === "" ? null : Number(seed),
      steps: Number(steps) as CompareRequest["steps"],
      size: Number(size) as CompareRequest["size"],
    };
    compare.mutate(body, { onSuccess: (r) => setRunId(r.run_id) });
  };

  return (
    <div className="space-y-6">
      <form onSubmit={onSubmit} className="space-y-4" aria-label="Compare adapters">
        <div className="grid gap-4 sm:grid-cols-[200px_minmax(0,1fr)]">
          <div className="space-y-1.5">
            <Label>Tenant</Label>
            <Select value={tenant} onValueChange={(v) => { setTenant(v); setPicked(null); }}>
              <SelectTrigger aria-label="Compare tenant"><SelectValue placeholder="Pick a tenant" /></SelectTrigger>
              <SelectContent>
                {tenants.map((t) => <SelectItem key={t.tenant_id} value={t.tenant_id}>{t.tenant_id}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <fieldset className="space-y-1.5">
            <legend className="text-sm font-medium">Adapters (max {MAX_ADAPTERS})</legend>
            <div className="flex flex-wrap gap-4 pt-1.5">
              {adapters.map((a) => (
                <label key={a.adapter} className="flex items-center gap-2 text-sm cursor-pointer">
                  <Checkbox checked={selected.includes(a.adapter)} onCheckedChange={(v) => toggle(a.adapter, v === true)} />
                  {a.display_name}
                </label>
              ))}
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <Switch checked={includeBase} onCheckedChange={setIncludeBase} aria-label="Include base model" />
                Include base model
              </label>
            </div>
          </fieldset>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="cmp-prompt">Prompt</Label>
          <Textarea id="cmp-prompt" value={prompt} onChange={(e) => setPrompt(e.target.value)}
            placeholder={PROMPT_PLACEHOLDER} required rows={2} />
        </div>
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="space-y-1.5">
            <Label htmlFor="cmp-seed">Seed</Label>
            <Input id="cmp-seed" type="number" min={0} value={seed} onChange={(e) => setSeed(e.target.value)} placeholder={SEED_PLACEHOLDER} />
          </div>
          <div className="space-y-1.5">
            <Label>Steps</Label>
            <Select value={steps} onValueChange={setSteps}>
              <SelectTrigger aria-label="Compare steps"><SelectValue /></SelectTrigger>
              <SelectContent>{STEP_OPTIONS.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>Size</Label>
            <Select value={size} onValueChange={setSize}>
              <SelectTrigger aria-label="Compare size"><SelectValue /></SelectTrigger>
              <SelectContent>{SIZE_OPTIONS.map((s) => <SelectItem key={s} value={s}>{s} × {s}</SelectItem>)}</SelectContent>
            </Select>
          </div>
        </div>
        {compare.error && (
          <Alert variant="destructive">
            <AlertTitle>Compare rejected</AlertTitle>
            <AlertDescription>{compare.error.message}. No job was created.</AlertDescription>
          </Alert>
        )}
        <Button type="submit" disabled={!tenant || !prompt || selected.length === 0 || compare.isPending}>
          <Columns3 className="h-3.5 w-3.5" />
          {compare.isPending ? "Queuing…" : "Compare adapters"}
        </Button>
      </form>
      {run.data && (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Run <Link className="font-mono underline" href={`/runs/${run.data.run_id}`}>{run.data.run_id}</Link>,
            seed {run.data.jobs[0]?.seed}
          </p>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {run.data.jobs.map((j) => <JobImage key={j.job_id} job={j} />)}
          </div>
        </div>
      )}
    </div>
  );
}
