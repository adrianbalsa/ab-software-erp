# Secret Rotation Policy v1

Fecha efectiva: `2026-04-29`  
Owner: `Adrian (solo-founder)`  
Ámbito: backend, frontend server-side, CI/CD, integraciones externas y certificados mTLS.

## 1) Objetivo

Reducir riesgo por exposición de credenciales mediante rotación periódica, revocación controlada y evidencia auditable de cada cambio.

## 2) Principios obligatorios

- Todo secreto de aplicación se consume mediante `get_secret_manager()`.
- Queda prohibido introducir lecturas directas de secretos con `os.getenv()` en `backend/app/**`.
- Toda rotación debe dejar evidencia: fecha, alcance, secreto afectado (sin valor), validación y rollback.
- Ninguna rotación productiva se ejecuta sin ventana definida y plan de reversión.

## 3) Clasificación y periodicidad

- **Clase A (alta criticidad, 30 días):**
  - `JWT_SECRET_KEY`, claves de cifrado (`FERNET/ENCRYPTION_KEY`), `SUPABASE_SERVICE_KEY`, `STRIPE_SECRET_KEY`, `GOCARDLESS_ACCESS_TOKEN`.
- **Clase B (media, 60 días):**
  - claves LLM (`OPENAI/ANTHROPIC/GEMINI/AZURE_OPENAI`), webhooks críticos, secretos operativos de integración.
- **Clase C (certificados, según validez + umbral):**
  - certificados mTLS AEAT y material asociado; rotación antes de umbral 30/15/7 días.

## 4) Procedimiento estándar de rotación

1. Preparación:
   - definir alcance (`dev/staging/prod`) y secreto objetivo;
   - generar nuevo valor en gestor de secretos correspondiente (`env/vault/aws`);
   - registrar `rotation_id` y ventana.
2. Despliegue:
   - actualizar secreto en backend configurado;
   - aplicar redeploy/reload de servicios consumidores.
3. Validación:
   - healthchecks (`/live`, `/health`, `/ready`);
   - pruebas funcionales del dominio afectado (auth, pagos, IA, fiscal, etc.);
   - validación de guardrails CI y test suite relevante.
4. Cierre:
   - registrar evidencia y resultado;
   - retirar valor antiguo (revocación/expiración) tras ventana de estabilidad.

## 5) Rollback

- Si la validación falla:
  - restaurar secreto anterior inmediatamente;
  - reiniciar servicios;
  - documentar causa raíz y nueva fecha de intento.

## 6) Evidencia mínima por rotación

- `rotation_id`
- fecha/hora UTC
- secreto (nombre lógico; nunca valor)
- entorno
- validaciones ejecutadas y resultado
- estado final (`success` / `rolled_back`)
- responsable

## 7) Guardrails técnicos vigentes

- CI bloquea nuevos `os.getenv(<secreto crítico>)` en `backend/app/**`.
- CI emite warning en `backend/scripts/**` y `scripts/**` para migración progresiva.

