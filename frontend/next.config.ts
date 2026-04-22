import { withSentryConfig } from "@sentry/nextjs";
import type { NextConfig } from "next";

const isProd = process.env.NODE_ENV === "production";

const nextConfig: NextConfig = {
  /* Imagen Docker: copiar .next/standalone + .next/static (usuario no-root). */
  output: "standalone",
  compiler: isProd
    ? {
        removeConsole: { exclude: ["error", "warn"] },
      }
    : undefined,
  async redirects() {
    return [
      {
        source: "/precios",
        destination: "/#pricing",
        permanent: true,
      },
      {
        source: "/help",
        destination: "/#help",
        permanent: true,
      },
    ];
  },
};

export default withSentryConfig(nextConfig, {
  /* Túnel same-origin para reducir bloqueo por ad blockers (SDK enruta ingest por esta ruta). */
  tunnelRoute: true,
  silent: true,
  org: process.env.SENTRY_ORG,
  project: process.env.SENTRY_PROJECT,
});
