import { test, expect, type Page, type Route } from "@playwright/test";

/**
 * Adapter registry and Generate smoke suite with the API mocked at the network
 * layer, so it needs no B2 credentials, no GPU and no running API.
 */

const TENANTS = [
  { tenant_id: "acme", adapter_count: 1, version_count: 1, total_bytes: 170543052, updated_at: "2026-11-23T00:00:00Z" },
  { tenant_id: "globex", adapter_count: 1, version_count: 1, total_bytes: 340786114, updated_at: "2026-11-23T00:00:00Z" },
];
const ACME_ADAPTERS = [
  {
    tenant_id: "acme", adapter: "pixel-art", display_name: "Pixel Art", current_version: "v1",
    version_count: 1, default_scale: 1, license: "creativeml-openrail-m", size_bytes: 170543052,
  },
];

// The page (127.0.0.1:3000) and the API (localhost:8000) are different origins,
// so a fulfilled response needs CORS headers or the browser discards it.
const CORS = {
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET, POST, PATCH, DELETE, OPTIONS",
  "access-control-allow-headers": "content-type",
};

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({ status, headers: CORS, contentType: "application/json", body: JSON.stringify(body) });
}

async function mockApi(page: Page) {
  await page.route(/:8000\//, (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    const method = route.request().method();
    if (method === "OPTIONS") return route.fulfill({ status: 204, headers: CORS });
    if (path === "/health") return json(route, { status: "healthy", b2_connected: true, base_model: "sdxl", workers_online: 0 });
    if (path === "/tenants") return json(route, TENANTS);
    if (path === "/tenants/acme/adapters" && method === "GET") return json(route, ACME_ADAPTERS);
    if (path === "/tenants/globex/adapters") return json(route, []);
    if (path === "/settings/server") {
      return json(route, {
        base_model: "stabilityai/stable-diffusion-xl-base-1.0", app_prefix: "lora-serving/",
        adapter_url_ttl_seconds: 300, output_url_ttl_seconds: 600, job_lease_seconds: 30,
        workers_online: 0, license_allowlist: ["creativeml-openrail-m", "openrail++", "apache-2.0", "mit"],
      });
    }
    if (path === "/tenants/acme/generations" && method === "POST") {
      return json(route, {
        detail: "tenant 'acme' cannot use adapters owned by another tenant",
        code: "cross_tenant_adapter",
      }, 403);
    }
    if (path === "/jobs" || path === "/runs" || path === "/workers" || path === "/library") return json(route, []);
    return json(route, { detail: "Not Found" }, 404);
  });
}

test.beforeEach(async ({ page }) => {
  await mockApi(page);
});

test("adapters page lists each tenant's adapters", async ({ page }) => {
  await page.goto("/adapters");
  await expect(page.getByRole("heading", { name: "Adapters", level: 1 })).toBeVisible();
  await expect(page.getByRole("link", { name: "Pixel Art" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "creativeml-openrail-m" })).toBeVisible();
});

test("publish form validates before sending anything", async ({ page }) => {
  await page.goto("/adapters");
  await page.getByRole("button", { name: "Publish adapter" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByPlaceholder("pixel-art", { exact: true }).fill("Bad Name");
  await dialog.getByPlaceholder("v1", { exact: true }).fill("1");
  await dialog.getByRole("button", { name: "Publish" }).click();
  await expect(dialog.getByText("Lowercase letters, digits and hyphens (3-40 characters)")).toBeVisible();
  await expect(dialog.getByText("Use v1, v1.2 or v1.2.3")).toBeVisible();
  await expect(dialog.getByText("Pick the adapter's license")).toBeVisible();
});

test("generate form shows the cross-tenant rejection", async ({ page }) => {
  await page.goto("/generate");
  const form = page.getByRole("form", { name: "Generate" });
  await form.getByLabel("Prompt").fill("a lighthouse on a cliff at sunset");
  await form.getByText("Advanced: raw adapter reference").click();
  await form.getByPlaceholder("globex/papercut").fill("globex/papercut");
  await form.getByRole("button", { name: "Generate" }).click();
  await expect(form.getByText(/a tenant can only use adapters from its own manifest/)).toBeVisible();
  await expect(form.getByText("cross_tenant_adapter")).toBeVisible();
});

test("settings shows the read-only server card", async ({ page }) => {
  await page.goto("/settings");
  await expect(page.getByText("stabilityai/stable-diffusion-xl-base-1.0")).toBeVisible();
  await expect(page.getByRole("combobox", { name: "Default steps" })).toBeVisible();
});
