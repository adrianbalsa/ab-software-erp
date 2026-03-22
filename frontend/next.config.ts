import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* Next 16: @sentry/nextjs aún no declara peer para Next 16; usamos @sentry/node + @sentry/browser vía hooks/instrumentation */
};

export default nextConfig;
