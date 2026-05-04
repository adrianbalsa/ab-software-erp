/**
 * Re-export del catálogo canónico en `frontend/src/lib/marketingPlanCatalog.ts`.
 * Útil en monorepo completo (imports `@shared/...`). El build de Vercel con Root
 * Directory `frontend/` no incluye esta carpeta; el frontend importa `./marketingPlanCatalog`.
 */
export * from "../frontend/src/lib/marketingPlanCatalog";
