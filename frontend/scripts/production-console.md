# Consola en builds de producción

`console.log` y `console.debug` se eliminan del bundle de cliente en **producción** mediante `compiler.removeConsole` en `next.config.ts` (se conservan `console.error` y `console.warn`).

Para generar el build: `npm run build` o `npm run build:production`.

No hace falta un paso extra de post-procesado: Next.js/SWC aplica la eliminación en la compilación.
