# AMAP Frontend — Foundation Phase

Next.js + React + TypeScript, per `docs/MASTER_SPEC.md` §14. This is a
**routing and shared-UI foundation only** — not a build of the worker,
admin, or organization business screens.

## Why it's scoped this way

Per `MASTER_SPEC.md` §32 ("Explicitly Not Yet Frozen"), the following
are undecided and block real screens:

- Exact API contracts (§18)
- Exact RBAC / permission matrix (§17)
- Exact authentication provider (§14)
- Exact supported gesture vocabulary, gesture recognition model
- Voice/STT and TTS providers

Per §28 ("Development Rules for AI Assistants"): *"Do not invent
project requirements, technologies, workflows, or architectural
changes without checking this specification first"* and *"Follow API
contracts"* — since no API contract exists yet, this scaffold makes no
network calls and assumes no auth state.

**Recommendation:** write a `docs/FRONTEND.md` foundation contract,
the same way `docs/BACKEND.md` scopes the backend foundation phase,
before building real business pages. That keeps the frontend engineer
and any AI assistant working from an explicit, frozen scope instead of
guessing at API shapes.

## What's here

- `app/` — Next.js App Router: root layout, landing page, and one
  placeholder page per product side (`/worker`, `/admin`,
  `/organization`). This is the one folder Next.js requires beyond
  your existing `admin/ organization/ shared/ worker/` — the framework
  needs a folder literally named `app/` to know what routes exist.
- `shared/components/` — `NavBar`, `SideScaffold` (the shell every
  side page uses)
- `shared/theme/tokens.ts` — palette, type, spacing tokens, mirrored
  as CSS variables in `app/globals.css`
- `admin/`, `organization/`, `worker/` — empty domain folders, ready
  for feature code once their respective contracts are approved

## What's deliberately NOT here

- No API calls (`NEXT_PUBLIC_API_BASE_URL` in `.env.example` is an
  unused placeholder)
- No authentication or session state
- No gesture/voice interaction code
- No task/workflow/action UI — those require the intent/action
  pipeline contract (MASTER_SPEC §10)

## Setup

```bash
cd frontend
npm install
cp .env.example .env.local
```

## Run

```bash
npm run dev
```

Visit http://localhost:3000 — links to `/worker`, `/admin`, and
`/organization`, each showing its current foundation state and what's
planned once the relevant contract is approved.

## Type-check / lint

```bash
npm run type-check
npm run lint
```

## Accessibility baseline (MASTER_SPEC §24)

- Visible focus outline on every interactive element (`:focus-visible`
  in `globals.css`), never suppressed
- `prefers-reduced-motion` respected
- Semantic landmarks (`nav`, `main`, `section` with `aria-label`)
- Body text sized for legibility (16px base, 1.6 line-height)

This is a baseline, not a completed accessibility audit — real screens
will need testing per MASTER_SPEC §26 (screen reader, contrast, focus
behavior, keyboard navigation) once they exist.
