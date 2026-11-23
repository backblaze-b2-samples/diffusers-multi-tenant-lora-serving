/**
 * Adapter references as the API accepts them: `name`, `name@version`, or
 * `owner/name[@version]`. Mirrors the API's identifier rules so the Generate
 * form can explain a bad reference before sending it, and can warn when an
 * owner other than the requesting tenant is named (the API answers 403).
 */
const NAME = /^[a-z0-9][a-z0-9-]{1,38}[a-z0-9]$/;
const VERSION = /^v[0-9]+(\.[0-9]+){0,2}$/;

export interface AdapterRef {
  owner: string | null;
  name: string;
  version: string | null;
}

export function parseAdapterRef(ref: string): AdapterRef | null {
  let text = ref.trim();
  let owner: string | null = null;
  if (text.includes("/")) {
    const [o, ...rest] = text.split("/");
    if (rest.length !== 1 || !NAME.test(o)) return null;
    owner = o;
    text = rest[0];
  }
  const [name, version, ...extra] = text.split("@");
  if (extra.length > 0 || !NAME.test(name)) return null;
  if (version !== undefined && !VERSION.test(version)) return null;
  return { owner, name, version: version ?? null };
}

/** Build the reference the API expects from form selections. */
export function formatAdapterRef(name: string, version?: string | null): string {
  return version ? `${name}@${version}` : name;
}

export function isCrossTenant(ref: AdapterRef, tenantId: string): boolean {
  return ref.owner !== null && ref.owner !== tenantId;
}

/** Human text for the API's isolation error codes. */
export function isolationMessage(code: string | null | undefined): string | null {
  switch (code) {
    case "cross_tenant_adapter":
      return "Rejected (403): a tenant can only use adapters from its own manifest.";
    case "adapter_not_found":
      return "Not found (404): this tenant's manifest has no such adapter or version.";
    case "manifest_tenant_mismatch":
      return "Rejected (403): the manifest points outside this tenant's prefix.";
    case "base_model_mismatch":
      return "Rejected (422): the adapter targets a different base model.";
    default:
      return null;
  }
}
