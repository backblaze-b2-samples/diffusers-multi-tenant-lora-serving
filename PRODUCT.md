# Product

## Users

ML platform engineers who serve image generation for many customers from a pool of
shared GPU workers, and the AI coding agents that help them. Their context: each
customer brings custom LoRA styles; they cannot keep every adapter loaded on every
GPU, and loading the wrong customer's adapter would leak one tenant's model into
another tenant's images. They read this sample to see a storage and serving
pattern they can adopt: adapters and manifests in Backblaze B2, stateless workers,
tenant-scoped resolution.

## Product Purpose

A working reference for multi-tenant LoRA serving on one shared Diffusers SDXL base
model. B2 holds every tenant's adapters under its own prefix with a checksummed
manifest; a dispatcher resolves each request through the requesting tenant's
manifest and rejects cross-tenant adapters; credential-free workers fetch exactly
one adapter through a short-lived presigned URL into a verified cache, load it,
generate, and unload it; a killed worker's job finishes on another worker with the
same seed and the same image. Success = an engineer runs it locally with two
workers, sees isolation, cache hits and recovery work against a real bucket, and
can lift the pattern into their own platform.

## Maturity and Support Boundary

This is a maintained open-source template/sample, not a complete hosted SaaS product.
It is built with production-minded controls and can be adapted for production use with
caution, but adopters own product-specific validation, security, deployment, and
operations. Repository defects and feature requests go through the public GitHub issue
tracker; B2 account, billing, service, and API questions go through Backblaze Support.
The template/sample itself is not covered by the Backblaze service level agreement,
and no SLA is provided for the repository software.

## Brand Personality

Confident, precise, quietly professional. Voice is direct and free of hype ("Stop
wiring boilerplate and start building"). The interface should feel like a modern
developer tool, considered, calm, trustworthy, not a marketing showpiece. It is a
**neutral foundation**: the design carries craft through restraint,
not through a strong opinionated identity of its own.

## Anti-references

- **Generic AI/SaaS slop.** No gradient text, hero-metric templates, identical
  icon-card grids, tracked uppercase eyebrows, or decorative glassmorphism. These are
  the exact AI tells this sample avoids.
- **Over-branded / loud.** No heavy brand-color drenching, decorative motion, or flashy
  effects. It is scaffolding to be rebranded, not a hero page.
- **Toy / prototype feel.** No missing states, inconsistent components, or placeholder
  polish. Must read as polished, dependable scaffolding.
- **Enterprise-drab.** No Bootstrap-era gray boxes or dense-but-lifeless admin-panel
  look. Considered, like modern dev tools (Linear, GitHub Primer, Stripe).

## Design Principles

- **Practice what you preach.** The sample must model the engineering quality it
  asks agents to produce. Slop here propagates into every project built on it.
- **Neutral foundation, easy to rebrand.** Identity lives in tokens (`globals.css`) and
  one config file. Screens are built from the shared UI kit so a rebrand is a token
  swap, not a rewrite.
- **Earned familiarity over novelty.** Use standard, trusted affordances (top bar +
  side nav, command palette, data tables). The tool disappears into the task.
- **Every state is designed.** Default, hover, focus, active, disabled, loading (skeleton),
  empty (teaches the interface), and error (says what's wrong + offers retry): never
  half-shipped.
- **Consistency is the feature.** One button vocabulary, one form-control set, one icon
  style across every screen. Divergence is a bug.

## Accessibility & Inclusion

Target **WCAG 2.1 AA**. Body text ≥ 4.5:1, large/bold text ≥ 3:1, visible focus
indicators on every interactive element, full keyboard navigation, correct semantic
landmarks and heading order, labelled form controls, and a `prefers-reduced-motion`
alternative for every animation. Full light and dark theme parity.
