import { withSentryConfig } from "@sentry/nextjs";
import type { NextConfig } from "next";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const isProd = process.env.NODE_ENV === "production";
const projectRoot = dirname(fileURLToPath(import.meta.url));

const nextConfig: NextConfig = {
  /* Imagen Docker: copiar .next/standalone + .next/static (usuario no-root). */
  output: "standalone",
  turbopack: {
    root: projectRoot,
  },
  compiler: isProd
    ? {
        removeConsole: { exclude: ["error", "warn"] },
      }
    : undefined,
  async redirects() {
    return [
      {
        source: "/precios",
        destination: "/pricing",
        permanent: true,
      },
      {
        source: "/help",
        destination: "/#help",
        permanent: true,
      },
    ];
  },
  async rewrites() {
    /*
     * Auth público (sin middleware de bloqueo en este proyecto): /login, /forgot-password, /reset-password.
     * Enlace del correo Resend: /auth/reset-password?token=… → /reset-password (route group (auth)).
     */
    return [{ source: "/auth/reset-password", destination: "/reset-password" }];
  },
};

export default withSentryConfig(nextConfig, {
  /* Túnel same-origin para reducir bloqueo por ad blockers (SDK enruta ingest por esta ruta). */
  tunnelRoute: true,
  silent: true,
  org: process.env.SENTRY_ORG,
  project: process.env.SENTRY_PROJECT,
});
