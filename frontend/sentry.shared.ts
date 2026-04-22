/**
 * Muestreo y saneado de breadcrumbs compartidos entre runtime client / server / edge.
 * Fase de pruebas: trazas y perfiles al 100 % salvo override explícito por env.
 */

import type { Breadcrumb } from "@sentry/nextjs";

const SENSITIVE_KEY_RE =
  /password|passwd|secret|token|authorization|auth|cookie|email|mail|phone|iban|nif|dni|cif|ssn|credit|card|cvv/i;

function clamp01(n: number): number {
  return Math.min(1, Math.max(0, n));
}

/** Trazas APM: 1.0 por defecto (fase pruebas). Reducir con `NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE`. */
export function getSentryTracesSampleRate(): number {
  const raw = process.env.NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE;
  if (raw !== undefined && raw !== "") {
    const n = Number(raw);
    if (!Number.isNaN(n)) {
      return clamp01(n);
    }
  }
  return 1.0;
}

/** Perfiles: 1.0 por defecto en fase pruebas. Reducir con `NEXT_PUBLIC_SENTRY_PROFILES_SAMPLE_RATE`. */
export function getSentryProfilesSampleRate(): number {
  const raw = process.env.NEXT_PUBLIC_SENTRY_PROFILES_SAMPLE_RATE;
  if (raw !== undefined && raw !== "") {
    const n = Number(raw);
    if (!Number.isNaN(n)) {
      return clamp01(n);
    }
  }
  return 1.0;
}

function redactValue(value: unknown, depth: number): unknown {
  if (depth > 12) {
    return "[Truncated]";
  }
  if (value === null || value === undefined) {
    return value;
  }
  if (typeof value === "string") {
    return value.replace(/[^\s@]+@[^\s@]+\.[^\s@]+/g, "[email]");
  }
  if (Array.isArray(value)) {
    return value.map((v) => redactValue(v, depth + 1));
  }
  if (typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      if (SENSITIVE_KEY_RE.test(k)) {
        out[k] = "[Filtered]";
      } else {
        out[k] = redactValue(v, depth + 1);
      }
    }
    return out;
  }
  return value;
}

export function scrubSentryBreadcrumb(crumb: Breadcrumb): Breadcrumb | null {
  const next: Breadcrumb = { ...crumb };
  if (next.data !== undefined && typeof next.data === "object" && next.data !== null) {
    next.data = redactValue(next.data, 0) as Record<string, unknown>;
  }
  if (typeof next.message === "string") {
    next.message = next.message.replace(/[^\s@]+@[^\s@]+\.[^\s@]+/g, "[email]");
  }
  return next;
}
