// Single source of truth for app identity. Rename here to rebrand a clone of this starter.
export const APP_NAME = "Diffusers Multi-Tenant LoRA Serving";
export const APP_DESCRIPTION =
  "Serve many tenants' LoRA adapters from Backblaze B2 on one shared Diffusers base model";

/**
 * URL- and storage-safe form of APP_NAME ("My Sample App" -> "my-sample-app").
 * Derived, never declared a second time: anything that needs an app-namespaced
 * identifier (a `localStorage` key, a cache prefix) builds on this, so a
 * rebrand cannot leave one stale copy behind for a grep to miss.
 */
export const APP_SLUG = APP_NAME.toLowerCase()
  .replace(/[^a-z0-9]+/g, "-")
  .replace(/^-+|-+$/g, "");
