"use client";

import { useEffect, useState } from "react";
import { ChevronDown, ShieldAlert, Wand2 } from "lucide-react";
import type { GenerationRequest } from "@diffusers-multi-tenant-lora-serving/shared";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { JobImage } from "@/components/jobs/job-image";
import { SCALE_OPTIONS, scaleOption } from "@/lib/adapter-form";
import { formatAdapterRef, isolationMessage, parseAdapterRef } from "@/lib/adapter-ref";
import { ApiError } from "@/lib/api-client";
import { SIZE_OPTIONS, STEP_OPTIONS, loadDemoPreferences } from "@/lib/demo-preferences";
import { useAdapter, useAdapters, useCreateGeneration, useJob, useTenants } from "@/lib/queries";

const BASE = "__base__";

interface GenerateFormProps {
  /** Lock the tenant and preselect an adapter (adapter detail page). */
  tenantId?: string;
  adapter?: string;
}

/** One request: a tenant, one of its adapters (or the base model), prompt and seed. */
export function GenerateForm({ tenantId, adapter }: GenerateFormProps) {
  const { data: tenants = [] } = useTenants();
  const [tenant, setTenant] = useState(tenantId ?? "");
  const [adapterName, setAdapterName] = useState(adapter ?? BASE);
  const [version, setVersion] = useState("");
  const [prompt, setPrompt] = useState("");
  const [seed, setSeed] = useState("");
  const [steps, setSteps] = useState<string>(STEP_OPTIONS[1]);
  const [size, setSize] = useState<string>(SIZE_OPTIONS[1]);
  const [scale, setScale] = useState("");
  const [rawRef, setRawRef] = useState("");
  const [jobId, setJobId] = useState<string>();
  const create = useCreateGeneration();
  const { data: adapters = [] } = useAdapters(tenant || undefined);
  const detail = useAdapter(tenant, adapterName === BASE ? "" : adapterName);
  const { data: job } = useJob(jobId);

  useEffect(() => {
    const prefs = loadDemoPreferences();
    setSteps(prefs.defaultSteps);
    setSize(prefs.defaultSize);
  }, []);
  useEffect(() => {
    if (!tenant && tenants.length > 0) setTenant(tenants[0].tenant_id);
  }, [tenant, tenants]);
  const versions = adapterName === BASE ? [] : (detail.data?.versions ?? []);
  const currentVersion = detail.data?.current_version ?? "";
  const defaultScale = detail.data ? scaleOption(detail.data.default_scale) : "";

  const rawParsed = rawRef.trim() ? parseAdapterRef(rawRef) : undefined;
  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const ref = rawRef.trim()
      ? rawRef.trim()
      : adapterName === BASE
        ? null
        : formatAdapterRef(adapterName, version || currentVersion);
    const body: GenerationRequest = {
      adapter: ref,
      prompt,
      seed: seed === "" ? null : Number(seed),
      steps: Number(steps) as GenerationRequest["steps"],
      size: Number(size) as GenerationRequest["size"],
      scale: scale ? Number(scale) : null,
    };
    create.mutate({ tenantId: tenant, body }, { onSuccess: (j) => setJobId(j.job_id) });
  };
  const err = create.error instanceof ApiError ? create.error : null;
  const isolation = isolationMessage(err?.code);

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
      <form onSubmit={onSubmit} className="space-y-4" aria-label="Generate">
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="space-y-1.5">
            <Label>Tenant</Label>
            <Select value={tenant} onValueChange={(v) => { setTenant(v); setAdapterName(BASE); }} disabled={!!tenantId}>
              <SelectTrigger aria-label="Tenant"><SelectValue placeholder="Pick a tenant" /></SelectTrigger>
              <SelectContent>
                {tenants.map((t) => <SelectItem key={t.tenant_id} value={t.tenant_id}>{t.tenant_id}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>Adapter</Label>
            <Select value={adapterName} onValueChange={(v) => { setAdapterName(v); setVersion(""); setScale(""); }}>
              <SelectTrigger aria-label="Adapter"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value={BASE}>None (base model)</SelectItem>
                {adapters.map((a) => <SelectItem key={a.adapter} value={a.adapter}>{a.display_name}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>Version</Label>
            <Select value={version || currentVersion} onValueChange={setVersion} disabled={adapterName === BASE}>
              <SelectTrigger aria-label="Version"><SelectValue placeholder="—" /></SelectTrigger>
              <SelectContent>
                {versions.map((v) => <SelectItem key={v.version} value={v.version}>{v.version}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="gen-prompt">Prompt</Label>
          <Textarea id="gen-prompt" value={prompt} onChange={(e) => setPrompt(e.target.value)}
            placeholder="a lighthouse on a cliff at sunset" required rows={3} />
          {detail.data && detail.data.trigger_words.length > 0 && (
            <p className="text-xs text-muted-foreground">Trigger words: {detail.data.trigger_words.join(", ")}</p>
          )}
        </div>
        <div className="grid gap-4 sm:grid-cols-4">
          <div className="space-y-1.5">
            <Label htmlFor="gen-seed">Seed</Label>
            <Input id="gen-seed" type="number" min={0} value={seed} onChange={(e) => setSeed(e.target.value)} placeholder="42" />
            <p className="text-[11px] text-muted-foreground">same seed and adapter give the same image</p>
          </div>
          <div className="space-y-1.5">
            <Label>Steps</Label>
            <Select value={steps} onValueChange={setSteps}>
              <SelectTrigger aria-label="Steps"><SelectValue /></SelectTrigger>
              <SelectContent>{STEP_OPTIONS.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>Size</Label>
            <Select value={size} onValueChange={setSize}>
              <SelectTrigger aria-label="Size"><SelectValue /></SelectTrigger>
              <SelectContent>{SIZE_OPTIONS.map((s) => <SelectItem key={s} value={s}>{s} × {s}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>Scale</Label>
            <Select value={scale || defaultScale} onValueChange={setScale} disabled={adapterName === BASE && !rawRef}>
              <SelectTrigger aria-label="Scale"><SelectValue placeholder="adapter default" /></SelectTrigger>
              <SelectContent>{SCALE_OPTIONS.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
            </Select>
          </div>
        </div>
        <Collapsible>
          <CollapsibleTrigger className="flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground">
            <ChevronDown className="h-3.5 w-3.5" /> Advanced: raw adapter reference
          </CollapsibleTrigger>
          <CollapsibleContent className="space-y-1.5 pt-2">
            <Label htmlFor="gen-raw">Adapter reference (overrides the selection)</Label>
            <Input id="gen-raw" value={rawRef} onChange={(e) => setRawRef(e.target.value)} placeholder="globex/papercut" />
            <p className="text-[11px] text-muted-foreground">
              Try another tenant&apos;s adapter to see the isolation check reject it.
              {rawParsed === null && " This reference is not well formed."}
            </p>
          </CollapsibleContent>
        </Collapsible>
        {err && (
          <Alert variant="destructive">
            <ShieldAlert />
            <AlertTitle>{isolation ?? "Request failed"}</AlertTitle>
            <AlertDescription>
              <span><code>{err.code ?? err.status}</code>: {err.message}. No job was created.</span>
            </AlertDescription>
          </Alert>
        )}
        <Button type="submit" disabled={!tenant || !prompt || create.isPending}>
          <Wand2 className="h-3.5 w-3.5" />
          {create.isPending ? "Queuing…" : "Generate"}
        </Button>
      </form>
      <div>{job ? <JobImage job={job} /> : <div className="aspect-square rounded-lg border border-dashed border-border" />}</div>
    </div>
  );
}
