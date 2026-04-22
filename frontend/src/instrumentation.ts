/**
 * Carga la configuración de Sentry por runtime (Node server vs Edge).
 * Los archivos `sentry.*.config.ts` en la raíz del frontend definen `Sentry.init`.
 */
export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    await import("../sentry.server.config");
  } else if (process.env.NEXT_RUNTIME === "edge") {
    await import("../sentry.edge.config");
  }
}
