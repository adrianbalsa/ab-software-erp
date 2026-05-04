import type { NextConfig } from "next";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const landingDir = dirname(fileURLToPath(import.meta.url));
/** Raíz del monorepo (incluye `shared/`) — no usar solo `landing/` o Turbopack bloquea imports a `../shared`. */
const monorepoRoot = join(landingDir, "..");

const nextConfig: NextConfig = {
  output: "standalone",
  turbopack: {
    root: monorepoRoot,
  },
};

export default nextConfig;
