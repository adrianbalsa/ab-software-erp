# Decisión técnica: Next.js 16 / React 19

**Estado:** aceptada  
**Fecha:** 2026-04-26  
**Alcance:** `frontend/` y `landing/`

## Decisión

Mantener el stack actual en **Next.js 16.x** y **React 19.x**. No se ejecuta downgrade preventivo mientras `npm run build`, lint y smoke E2E sigan en verde.

## Motivo

- El repositorio ya está alineado con el stack moderno documentado para due diligence: App Router, React 19, TypeScript 5 y Tailwind 4.
- Next 16 exige validar puntos concretos, no un rollback genérico: APIs de request asíncronas (`cookies`, `headers`, `params`, `searchParams` en server pages), renombre de middleware a proxy si se usa, y configuración `turbopack` top-level.
- El código actual no usa `middleware.ts`, `next/router`, `revalidateTag` ni `cacheHandler`; las rutas con `useSearchParams` están en componentes cliente o bajo `Suspense`.
- Ambos paquetes declaran `node >=20.9.0`, coherente con el requisito de Next 16 y con builds `standalone`.

## Controles Añadidos

- `frontend/tests/platform-smoke.spec.ts`: smoke Chromium sobre shell de app, ruta con `useSearchParams` (`/pricing`) y rutas legales estáticas, capturando `pageerror` y errores de consola.
- `npm run test:e2e:platform`: ejecución dedicada para CI/local sin depender de credenciales de portal cliente.
- Se elimina el spec externo de ejemplo de Playwright para que la suite E2E cubra producto real.

## Criterios De Downgrade

Hacer downgrade controlado solo si aparece una regresión reproducible atribuible a Next 16/React 19 y no corregible con cambios locales razonables. Señales válidas:

- `next build` falla por cambio de contrato de Next/React.
- Error de runtime reproducible en rutas críticas (`/login`, `/dashboard`, `/facturas`, `/portal-cliente/*`) ligado al framework.
- Incompatibilidad real de dependencia sin versión compatible disponible.
- Problema de despliegue `standalone` que bloquee producción o rollback operativo.

## Plan De Downgrade Si Fuera Necesario

1. Fijar versiones objetivo en `frontend/package.json` y `landing/package.json` (Next 15.x estable + React 18/19 según matriz compatible).
2. Regenerar lockfiles con el mismo gestor (`npm install`) en cada paquete afectado.
3. Ejecutar `npm run build`, `npm run lint`, `npm run test:e2e:platform` y los E2E de portal con credenciales cuando estén disponibles.
4. Documentar el motivo exacto del rollback y abrir tarea para reintento de upgrade con reproducción mínima.
