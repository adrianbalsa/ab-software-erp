import type { NextConfig } from "next";

const isProd = process.env.NODE_ENV === "production";

const nextConfig: NextConfig = {
  /* Imagen Docker: copiar .next/standalone + .next/static (usuario no-root). */
  output: "standalone",
  /* Next 16: @sentry/nextjs aún no declara peer para Next 16; usamos @sentry/node + @sentry/browser vía hooks/instrumentation */
  compiler: isProd
    ? {
        removeConsole: { exclude: ["error", "warn"] },
      }
    : undefined,
};

export default nextConfig;
