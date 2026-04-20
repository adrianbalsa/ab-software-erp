# Postura de cumplimiento y ciberseguridad (Due Diligence)

**Versión:** 1.0  
**Última revisión:** 2026-04-19  
**Alcance:** AB Logistics OS (API FastAPI + Supabase + front Vercel)

Este documento agrupa la **evidencia técnica y legal** que suele solicitarse en auditorías B2B, RGPD y ciberseguridad, enlazando artefactos ya versionados en el repositorio y endpoints públicos de transparencia.

## 1. RGPD y tratamiento de datos

| Tema | Evidencia |
| :--- | :--- |
| Rol Responsable / Encargado | `docs/legal/PRIVACY_POLICY.md` §1 |
| DPA (encargo de tratamiento) | `docs/legal/DPA_DATA_PROCESSING_AGREEMENT.md` |
| Condiciones de servicio | `docs/legal/TERMS_OF_SERVICE.md` |
| Lista de subencargados (categorías y proveedores) | `GET /api/v1/public/compliance` → campo `subprocessors` (JSON) |
| Derecho al olvido / anonimización técnica | `POST /api/v1/admin/compliance/anonymize/{user_id}` (admin empresa); servicio `backend/app/services/compliance.py` |
| Cifrado y secretos | `README_SECURITY.md`, `SecretManagerService` (`backend/app/services/secret_manager_service.py`) |

El ejercicio de derechos de **interesados finales** del Cliente se canaliza, contractualmente, a través del **Responsable** (el Cliente); la plataforma asiste técnicamente según capacidades documentadas.

## 2. SLA contractuales y medición operativa

| Tema | Evidencia |
| :--- | :--- |
| Texto legal del SLA | `docs/legal/SLA.md` (uptime 99,9 % mensual, RPO/RTO, matriz de soporte) |
| Resumen machine-readable | `GET /api/v1/public/compliance` → campo `sla` |
| Healthchecks para monitorización | `GET /live` (liveness), `GET /health` (readiness con dependencias), `GET /health/deep` (diagnóstico profundo), `GET /ready` |

Los objetivos RPO/RTO del SLA están alineados con el plan de continuidad en `docs/operations/DISASTER_RECOVERY.md`.

## 3. Ciberseguridad (postura demostrable)

| Control | Implementación |
| :--- | :--- |
| Transporte y cookies | HTTPS en producción; `Strict-Transport-Security` vía `SecurityHeadersMiddleware` cuando `ENVIRONMENT=production`; cookies de sesión `SameSite=Lax` y `https_only` según `COOKIE_SECURE`. |
| Cabeceras HTTP | `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy` (`backend/app/middleware/security_headers.py`). |
| Aislamiento multi-tenant | RLS en Postgres/Supabase; contexto de tenant en middleware (`tenant_rbac_context`). |
| Límites de abuso | Rate limiting (SlowAPI, login, rutas fiscales sensibles). |
| Trazabilidad | `X-Request-ID`, logs JSON de acceso, auditoría API (`audit_logs`). |
| Errores en producción | Sentry con `send_default_pii=False`; release vía `APP_RELEASE` / SHA de despliegue. |
| Divulgación coordinada | `GET /.well-known/security.txt` (RFC 9116); contacto vía `SECURITY_CONTACT_EMAIL` (plantillas e IaC usan `security@ablogistics-os.com`; el buzón debe existir en correo/DNS y estar monitorizado). |
| Secretos | Sin lectura directa de claves críticas con `os.getenv` en servicios de aplicación; ver `.cursorrules` y `README_SECURITY.md`. |

## 4. Mantenimiento de este paquete

1. Cualquier cambio relevante de proveedores (subencargados) debe reflejarse en **`public_compliance.py`** y en **`docs/legal/PRIVACY_POLICY.md`** el mismo PR.  
2. Cambios de SLA (porcentajes, plazos) deben actualizar **`docs/legal/SLA.md`** y el diccionario **`SLA_SUMMARY`** en código.  
3. Renovar anualmente el campo `Expires` de `security.txt` (se calcula en runtime a +365 días; revisar contacto y política asociada).  
4. **Operación:** asegurar que `SECURITY_CONTACT_EMAIL` apunta a un buzón con MX operativos (p. ej. Google Workspace, Resend routing, o proveedor acordado) y reglas de escalado para informes de vulnerabilidad.
