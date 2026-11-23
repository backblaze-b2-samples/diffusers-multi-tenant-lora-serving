<!-- last_verified: 2026-11-23 -->
# Feature: Settings

## Purpose
Set the theme and the defaults the Generate and Compare forms start from, and show the dispatcher's configuration read-only.

## Used By
- UI: `/settings` (`SettingsForm`, `ServerConfigCard`)
- API: `GET /settings/server`
- Storage: `next-themes`' own key for Theme; `localStorage` (`diffusers-multi-tenant-lora-serving-demo-preferences`) for default steps and size. No server-side preferences store

## Core Functions
- `apps/web/src/lib/theme-preference.ts`: `THEME_OPTIONS`, `DEFAULT_THEME`, `normalizeTheme()`
- `apps/web/src/lib/demo-preferences.ts`: `STEP_OPTIONS`, `SIZE_OPTIONS`, `loadDemoPreferences()`, `saveDemoPreferences()`
- `apps/web/src/lib/use-demo-preferences.ts`: the stored defaults as a hook (server render uses the built-in defaults)
- `apps/web/src/lib/settings-schema.ts`: zod rules for the form
- `apps/web/src/components/settings/settings-form.tsx`: Theme radio group, Default steps and Default size selects
- `apps/web/src/components/settings/server-config-card.tsx`: base model, app prefix, URL lifetimes, job lease, workers online, license allowlist
- `services/api/app/runtime/server_settings.py`: `GET /settings/server`

## Canonical Files
- `apps/web/src/components/settings/settings-form.tsx` (selector for every finite-option field)

## Inputs
- theme: `"light" | "dark" | "system"`
- defaultSteps: `"15" | "25" | "40"` (default 25); defaultSize: `"768" | "1024"` (default 1024)

## Outputs
- Theme applied immediately and persisted by `next-themes`
- Defaults stored in this browser; new Generate and Compare forms read them
- `ServerConfig` (read-only)

## Flow
- Mount -> hydrate Theme from `next-themes` and the defaults from `localStorage`
- Submit -> apply the theme, store the defaults, toast what happened (a warning when storage is blocked)
- Server card -> `GET /settings/server`; values come from the dispatcher's environment

## Edge Cases
- Corrupt or partial stored blob -> each field falls back to its default
- Storage blocked -> theme still changes; warning toast

## UX States
- Loading: server card skeleton
- Error: server card `ErrorState` with retry

## Verification
- Test files: `apps/web/src/lib/demo-preferences.test.ts`, `settings-schema.test.ts`, `theme-preference.test.ts`; `apps/web/e2e/adapters.spec.ts` (server card)
- Focused verify command: `pnpm test:web`
- Default pre-PR verify command: `pnpm verify`
- Full local verify command: `pnpm verify:full`
- Pass criteria: tests green

## Related Docs
- [Generate and Compare](generate.md)
- [frontend-conventions.md](../frontend-conventions.md)
