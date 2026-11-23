"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronDown, ShieldAlert, ShieldQuestion, Wand2 } from "lucide-react";
import type { GenerationRequest } from "@diffusers-multi-tenant-lora-serving/shared";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { JobImage } from "@/components/jobs/job-image";
import { PROMPT_PLACEHOLDER, SCALE_OPTIONS, SEED_PLACEHOLDER, scaleOption } from "@/lib/adapter-form";
import { formatAdapterRef, isolationMessage, parseAdapterRef } from "@/lib/adapter-ref";
import { ApiError } from "@/lib/api-client";
import { SIZE_OPTIONS, STEP_OPTIONS } from "@/lib/demo-preferences";
import { isTerminal } from "@/lib/job-state";
import { forgetActiveJob, readActiveJobId, readJobIdFromUrl, rememberActiveJob, writeJobIdToUrl } from "@/lib/job-deep-link";
import { useDemoPreferences } from "@/lib/use-demo-preferences";
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
  const [tenantChoice, setTenant] = useState(tenantId ?? "");
  const tenant = tenantChoice || tenants[0]?.tenant_id || "";
  // Unset means "the tenant's first adapter", so the default submit uses one.
  // Radix Select fires onValueChange("") when its value switches before the
  // matching item has mounted (the adapter list loads after the tenant); the
  // handlers below ignore that empty value so it cannot blank the selection.
  const [adapterChoice, setAdapterName] = useState<string | undefined>(adapter);
  const [version, setVersion] = useState("");
  const [prompt, setPrompt] = useState("");
  const [seed, setSeed] = useState("");
  const prefs = useDemoPreferences();
  const [stepsChoice, setSteps] = useState("");
  const [sizeChoice, setSize] = useState("");
  const steps = stepsChoice || prefs.defaultSteps;
  const size = sizeChoice || prefs.defaultSize;
  const [scale, setScale] = useState("");
  const [rawRef, setRawRef] = useState("");
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [jobId, setJobId] = useState<string>();
  const create = useCreateGeneration();
  const { data: adapters = [] } = useAdapters(tenant || undefined);
  const adapterName = adapterChoice ?? adapters[0]?.adapter ?? BASE;
  // Another tenant's adapter, for the one-click isolation check.
  const otherTenant = tenants.find((t) => t.tenant_id !== tenant && t.adapter_count > 0)?.tenant_id;
  const { data: otherAdapters = [] } = useAdapters(otherTenant);
  const foreignRef = otherTenant && otherAdapters[0] ? `${otherTenant}/${otherAdapters[0].adapter}` : undefined;

  // Resume the active job after a reload (URL) or, on the Generate page,
  // sidebar navigation (sessionStorage); the queries keep polling it. A form
  // locked to one tenant (adapter detail page) only resumes from its URL.
  const restoredId = useRef<string | undefined>(undefined);
  useEffect(() => {
    const active = tenantId ? readJobIdFromUrl() : readActiveJobId();
    if (!active) return;
    restoredId.current = active;
    if (!readJobIdFromUrl()) writeJobIdToUrl(active);
    // eslint-disable-next-line react-hooks/set-state-in-effect -- one-time sync from the URL/storage on mount
    setJobId(active);
  }, [tenantId]);
  const detail = useAdapter(tenant, adapterName === BASE ? "" : adapterName);
  const { data: job } = useJob(jobId);
  useEffect(() => {
    if (!job) return;
    // Refill the form from a restored job once, so it matches the result card.
    if (restoredId.current === job.job_id) {
      restoredId.current = undefined;
      /* eslint-disable react-hooks/set-state-in-effect -- one-time restore from the resumed job */
      if (!tenantId) setTenant(job.tenant_id);
      setAdapterName(job.adapter ?? BASE);
      setVersion(job.version ?? "");
      setPrompt(job.prompt);
      /* eslint-enable react-hooks/set-state-in-effect */
    }
    if (isTerminal(job.state)) forgetActiveJob(job.job_id);
  }, [job, tenantId]);

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
    create.mutate({ tenantId: tenant, body }, {
      onSuccess: (j) => {
        setJobId(j.job_id);
        writeJobIdToUrl(j.job_id);
        if (!tenantId) rememberActiveJob(j.job_id);
      },
    });
  };
  const err = create.error instanceof ApiError ? create.error : null;
  const isolation = isolationMessage(err?.code);
  const changeRawRef = (v: string) => {
    setRawRef(v);
    if (create.error) create.reset(); // the old rejection no longer describes this reference
  };
  const tryForeign = () => {
    if (!foreignRef) return;
    setAdvancedOpen(true);
    changeRawRef(foreignRef);
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
      <form onSubmit={onSubmit} className="space-y-4" aria-label="Generate">
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="space-y-1.5">
            <Label>Tenant</Label>
            <Select value={tenant} onValueChange={(v) => { if (!v) return; setTenant(v); setAdapterName(undefined); setVersion(""); setScale(""); }} disabled={!!tenantId}>
              <SelectTrigger aria-label="Tenant"><SelectValue placeholder="Pick a tenant" /></SelectTrigger>
              <SelectContent>
                {tenants.map((t) => <SelectItem key={t.tenant_id} value={t.tenant_id}>{t.tenant_id}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>Adapter</Label>
            <Select value={adapterName} onValueChange={(v) => { if (!v) return; setAdapterName(v); setVersion(""); setScale(""); }}>
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
              <SelectTrigger aria-label="Version"><SelectValue placeholder="-" /></SelectTrigger>
              <SelectContent>
                {versions.map((v) => <SelectItem key={v.version} value={v.version}>{v.version}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="gen-prompt">Prompt</Label>
          <Textarea id="gen-prompt" value={prompt} onChange={(e) => setPrompt(e.target.value)}
            placeholder={PROMPT_PLACEHOLDER} required rows={3} />
          {detail.data && detail.data.trigger_words.length > 0 && (
            <p className="text-xs text-muted-foreground">Trigger words: {detail.data.trigger_words.join(", ")}</p>
          )}
        </div>
        <div className="grid gap-4 sm:grid-cols-4">
          <div className="space-y-1.5">
            <Label htmlFor="gen-seed">Seed</Label>
            <Input id="gen-seed" type="number" min={0} value={seed} onChange={(e) => setSeed(e.target.value)} placeholder={SEED_PLACEHOLDER} />
            <p className="text-[11px] text-muted-foreground">empty picks a random seed; same seed and adapter give the same image</p>
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
        {foreignRef && (
          <div className="flex flex-wrap items-center gap-2 rounded-md border border-border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
            <ShieldQuestion className="h-3.5 w-3.5 shrink-0" aria-hidden />
            <span>Tenant isolation: ask for another tenant&apos;s adapter as <code className="font-mono">{tenant}</code> and the dispatcher rejects it.</span>
            <Button type="button" variant="outline" size="sm" className="h-7 text-xs" onClick={tryForeign}>
              Try <code className="font-mono">{foreignRef}</code>
            </Button>
          </div>
        )}
        <Collapsible open={advancedOpen} onOpenChange={setAdvancedOpen}>
          <CollapsibleTrigger className="flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground">
            <ChevronDown className="h-3.5 w-3.5" /> Advanced: raw adapter reference
          </CollapsibleTrigger>
          <CollapsibleContent className="space-y-1.5 pt-2">
            <Label htmlFor="gen-raw">Adapter reference (overrides the selection)</Label>
            <Input id="gen-raw" value={rawRef} onChange={(e) => changeRawRef(e.target.value)} placeholder={foreignRef ?? "globex/papercut"} />
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
        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit" disabled={!tenant || !prompt.trim() || create.isPending} aria-describedby="gen-submit-hint">
            <Wand2 className="h-3.5 w-3.5" />
            {create.isPending ? "Queuing…" : "Generate"}
          </Button>
          {(!tenant || !prompt.trim()) && (
            <p id="gen-submit-hint" className="text-xs text-muted-foreground">
              {!tenant ? "Publish an adapter first: there is no tenant to generate for." : "Enter a prompt to generate."}
            </p>
          )}
        </div>
      </form>
      <div>{job ? <JobImage job={job} /> : <div className="aspect-square rounded-lg border border-dashed border-border" />}</div>
    </div>
  );
}
