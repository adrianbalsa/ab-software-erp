"use client";

import { useEffect } from "react";

/**
 * Cliente: Sentry con NEXT_PUBLIC_SENTRY_DSN o SENTRY_DSN (expuesto al bundle).
 */
export function SentryInit() {
  useEffect(() => {
    const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;
    if (!dsn) {
      return;
    }
    void import("@sentry/browser").then((Sentry) => {
      Sentry.init({
        dsn,
        environment: process.env.NEXT_PUBLIC_VERCEL_ENV || process.env.NODE_ENV,
        tracesSampleRate: Number(process.env.NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE ?? 0.1),
      });
    });
  }, []);
  return null;
}
