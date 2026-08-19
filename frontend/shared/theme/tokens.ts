/**
 * Design tokens for AMAP.
 *
 * Foundation-phase only: these are the shared visual primitives used by
 * the three product sides (worker / admin / organization). No business
 * logic lives here — see docs/MASTER_SPEC.md §13-14 for architecture
 * and technology direction.
 *
 * Palette rationale:
 * - Base surface is a calm, low-glare charcoal — long shifts, varied
 *   lighting, and screen readers all do better without stark black or
 *   glare-heavy white as the working surface.
 * - "Signal" (teal) marks anything interactive or successful — the one
 *   color the eye should always trust.
 * - "Caution" (amber) is reserved for confirmation/high-risk-action
 *   states (per MASTER_SPEC §4, §21 — high-risk actions may require
 *   stricter confirmation), never used decoratively.
 * - Text colors are tuned for WCAG AA contrast against surface-0/1/2.
 */

export const colors = {
  surface0: "#10141A", // page background
  surface1: "#171D26", // cards / panels
  surface2: "#212934", // raised elements, inputs
  border: "#2E3946",

  textPrimary: "#F3F5F7",
  textSecondary: "#AEB9C4",
  textMuted: "#7C8A97",

  signal: "#4FC1CE", // primary interactive / focus / success
  signalStrong: "#7FD8E2",
  caution: "#E0A83E", // confirmation / high-risk-action states only
  danger: "#E0654A", // errors

  workerAccent: "#4FC1CE",
  adminAccent: "#8C7FE0",
  organizationAccent: "#E0A83E",
} as const;

export const type = {
  display: "'Space Grotesk', 'Segoe UI', sans-serif",
  body: "'Inter', 'Segoe UI', sans-serif",
  mono: "'IBM Plex Mono', 'Consolas', monospace",
} as const;

export const spacing = {
  xs: "0.5rem",
  sm: "0.75rem",
  md: "1.25rem",
  lg: "2rem",
  xl: "3.5rem",
} as const;

export const radius = {
  sm: "6px",
  md: "10px",
  lg: "16px",
} as const;
