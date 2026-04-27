# Checklist Ejecutable de Go-Live

Objetivo: cerrar salida a produccion y auditoria interna de forma verificable, siguiendo el roadmap en 3 fases (legal/cripto, eficiencia economica, produccion + handover).

Uso recomendado:

1. Asignar responsable por bloque (Security, Backend, DevOps, Finance Ops).
2. Ejecutar cada accion en orden.
3. Adjuntar evidencia (captura/log/ticket) por item.
4. Marcar solo cuando cumpla el criterio de cierre.

---

## Fase 1 - Blindaje legal y criptografico (bloqueadores compliance)

### 1) Seudonimizacion de logs (audit trail)

**Orden de ejecucion (canonico)**

1. **Backend** — Implementar y desplegar la **rotacion de claves Fernet** (material en secretos: `PII_ENCRYPTION_KEY` / `PII_ENCRYPTION_KEY_PREVIOUS` o alias; lectura ordenada en `SecretManagerService` + cifrado en `fernet_encrypt_string`) y la **seudonimizacion de PII** en trazas de auditoria (`AuditLogsService` → RPC `audit_logs_insert_api_event`). Evidencia: tests unitarios y revision de rutas que escriben en `audit_logs`.
2. **Operaciones** — Generar en el **ITSM** el ticket de change / registro de rotacion alineado con la plantilla Ops (ventana, responsable, rollback).
3. **Cierre (gobierno / Ops)** — Pegar **URL o ID** del ticket bajo `ITSM_ROTACION_PII_FERNET`, marcar el checkbox **Evidencia ITSM** arriba, y declarar **`HITO_1_1_COMPLIANCE_OPS: [COMPLIANT]`** (mas abajo). El literal global **`[COMPLIANT]`** del hito completo aplica solo cuando Backend + Ops esten cerrados. El **paso 1 (Backend)** ya esta cerrado en repo: ver `HITO_1_1_COMPLIANCE_BACKEND`.

- [x] **Accion**
  - Verificar que `AuditLogsService` enmascara NIF, email y nombre.
  - Confirmar que no se persiste PII en claro en `audit_logs`.
  - Revisar rotacion de claves de cifrado PII (`PII_ENCRYPTION_KEY` + `_PREVIOUS`) en `SecretManagerService`.
- [x] **Como ejecutar**
  - Correr tests: `backend/tests/unit/test_audit_logs_service.py`.
  - Hacer muestreo SQL de `audit_logs` en entorno de pruebas y comprobar ausencia de valores en claro.
  - Validar backend de secretos activo (`SECRET_MANAGER_BACKEND`) y proceso de rotacion documentado.
- [x] **Evidencia minima**
  - Output de tests en verde.
  - Captura/consulta de filas pseudonimizadas (plantilla SQL debajo; ejecutar en staging y archivar resultado).
  - [ ] **Evidencia ITSM** — **URL del ticket** en el ITSM y/o **ID concreto** reproducible en acta o data room (p. ej. `https://<itsm>/browse/SEC-1234`, `CHG-5678`) para el **change / registro de rotacion** de claves PII Fernet (`PII_ENCRYPTION_KEY` / `*_PREVIOUS`). Permanece **pendiente en el roadmap de seguridad** hasta generar ese identificador en el ITSM productivo; al obtenerlo, pegarlo en el campo de cierre administrativo (mas abajo) y marcar este checkbox.
- [x] **Criterio de cierre**
  - No aparece NIF/nombre/email en claro en registros auditados.

**Cierre tecnico (Fase 1.1)**

| Verificacion | Evidencia en repo |
| --- | --- |
| Pseudonimizacion antes de `audit_logs_insert_api_event` | `backend/app/services/audit_logs_service.py`: `_mask_*`, `_pseudonymize_audit_payload`, export `pseudonymize_audit_payload`. Usado tambien en `webhooks_gocardless.py`, `security_secret_rotation_audit.py` (RPC sync) y sustituye RPC crudo en `finance_service.py` (fuel allocation). |
| Tests | `pytest backend/tests/unit/test_audit_logs_service.py` (4 tests: NIF, email, nombre, payload anidado). |
| Cifrado PII en reposo (NIF/IBAN, etc.) vs trazas | Fernet: `app.core.security.fernet_encrypt_string` usa `get_secret_manager().list_fernet_pii_raw_keys(include_previous=True)`; orden primario + `*_PREVIOUS` en `backend/app/services/secret_manager_service.py`. |
| Rotacion operativa PII | `python scripts/rotate_secrets.py --kind pii --dry-run` (instrucciones sin imprimir secretos previos); auditoria opcional con `SECURITY_AUDIT_EMPRESA_ID` + Supabase service role. |

**Alcance del criterio** — La pseudonimizacion en `AuditLogsService` aplica a eventos insertados vía RPC `audit_logs_insert_api_event` (middleware y servicios FastAPI). Las filas escritas por triggers SQL (`audit_row_change` / `process_audit_log`) copian `to_jsonb(OLD/NEW)`; el tratamiento de PII alli depende de como este almacenado en las tablas de negocio (p. ej. NIF cifrado con Fernet en columnas). Para el muestreo SQL, priorizar `table_name IN ('api_requests','clientes',...)` segun fuentes que usen el servicio Python.

**Muestreo SQL (staging / lectura service role)** — comprobar que `old_data` / `new_data` no contienen patrones completos de NIF ni emails en claro:

```sql
-- Canal API (pseudonimizado en backend antes del insert)
select id, table_name, action, created_at,
       left(new_data::text, 400) as new_preview,
       left(old_data::text, 400) as old_preview
from public.audit_logs
where table_name = 'api_requests'
order by created_at desc
limit 50;

-- Panorama general (incluye triggers de tablas de negocio; ver nota de alcance arriba)
select id, table_name, action, created_at,
       left(new_data::text, 200) as new_preview
from public.audit_logs
order by created_at desc
limit 30;

-- Heuristica NIF espanol en JSON del canal API (ajustar ventana)
select count(*) filter (where new_data::text ~ '[0-9]{8}[A-HJ-NP-TV-Z]') as possible_plain_nif
from public.audit_logs
where table_name = 'api_requests'
  and created_at > now() - interval '30 days';
```

**Cierre administrativo del hito (ITSM)** — Sustituir el marcador por el enlace o ID real cuando exista; es el **cierre de gobernanza** que complementa la evidencia en repo (codigo + tests + `rotate_secrets.py`).

`ITSM_ROTACION_PII_FERNET:` _________________________________________________

**Estado del hito 1.1 (por capas)**

- **`HITO_1_1_COMPLIANCE_BACKEND` (paso 1 — codigo y tests):** **[COMPLIANT]** — Pseudonimizacion unificada: `AuditLogsService`, export `pseudonymize_audit_payload` para RPC directos (`webhooks_gocardless`, `security_secret_rotation_audit` sync), `AuditLogsService` en reparto combustible (`finance_service`); fragmento sensible `actor`; tests `backend/tests/unit/test_audit_logs_service.py` en verde.
- **`HITO_1_1_COMPLIANCE_OPS` (pasos 2–3 — ITSM + acta):** **PENDIENTE** — Sustituir por **`[COMPLIANT]`** cuando exista ticket de rotacion PII y este pegado en `ITSM_ROTACION_PII_FERNET` con checkbox **Evidencia ITSM** marcado.

**Hito 1.1 completo (Backend + Ops):** hasta entonces usar **`[COMPLIANT]`** solo en sentido acotado al backend arriba; el **Go** sin condiciones para 1.1 requiere ademas **`HITO_1_1_COMPLIANCE_OPS: [COMPLIANT]`**.

**Plantilla Ops del ticket** — Asunto sugerido: `ROT-PII-Fernet` o `CHG — Rotacion PII Fernet`. Campos minimos: fecha, responsable, `SECRET_MANAGER_BACKEND` activo, confirmacion de despliegue `PII_ENCRYPTION_KEY` + `PII_ENCRYPTION_KEY_PREVIOUS` (o alias `FERNET_PII_KEY*`) segun `scripts/rotate_secrets.py`, ventana de cambio y rollback.

**Justificacion tecnica y estrategica (por que exige el ITSM un ID o enlace concreto)**

- **Trazabilidad ante auditoria (M&A / Big Four):** Los auditores contrastan implementacion tecnica con **gestion del cambio** (change management). Un ticket ITSM acotado es evidencia de que la rotacion de secretos esta **procedimentada**, no solo descrita en el repositorio.
- **Cumplimiento y madurez operativa:** Demuestra que la rotacion forma parte del **ciclo de vida** de la infraestructura y del bunker de secretos, no un parche puntual documentado solo en codigo.
- **De Conditional Go a Go completo:** El CISO puede exigir **referencias externas** al repo que validen gobernanza de secretos; el enlace o ID ITSM es la prueba portable para el paquete de diligencia y el acta de **Go** sin condiciones sobre este sub-hito.

Con **`HITO_1_1_COMPLIANCE_BACKEND: [COMPLIANT]`** el riesgo tecnico de PII en trazas API queda acotado en repo. Hasta **`HITO_1_1_COMPLIANCE_OPS: [COMPLIANT]`** (ticket ITSM + evidencia), el sub-hito conserva **conditional go** de gobernanza para CISO / diligencia M&A.

### 2) Genesis Hash fiscal (VeriFactu)

**Orden de ejecucion (canonico)**

1. **Backend** — Sin semilla en código: génesis solo vía `get_secret_manager().get_verifactu_genesis_hash` → `get_verifactu_genesis_hash_for_issuer` (`backend/app/services/verifactu_genesis.py`). Ausencia de secreto → `RuntimeError('verifactu_genesis_hash_missing_for_issuer')`. Backends JSON (Vault/AWS) alineados con env: mapa `VERIFACTU_GENESIS_HASHES` / alias + fallback `VERIFACTU_GENESIS_HASH` global (`JsonMapSecretManager`).
2. **Operaciones / Security** — Definir en el gestor de secretos activo (`SECRET_MANAGER_BACKEND`) el JSON o variables con hashes SHA-256 hex (64 chars) por `empresa_id` y/o NIF; no commitear valores.
3. **Cierre** — Tests en verde + comprobar que produccion/staging tienen el secreto cargado (sin pegar el hash en el repo). Marcar **`HITO_1_2_COMPLIANCE_BACKEND`** abajo.

- [x] **Accion**
  - Confirmar que no existe semilla hardcodeada de genesis.
  - Cargar `VERIFACTU_GENESIS_HASHES` (o `VERIFACTU_GENESIS_HASH`) por runtime/secretos.
- [x] **Como ejecutar**
  - Correr: `pytest backend/tests/unit/test_verifactu_genesis.py backend/tests/unit/test_aws_secrets_manager_backend.py backend/tests/unit/test_vault_kv_secret_manager.py -q`
  - Validar resolucion por `issuer_id` / `issuer_nif` (`_lookup_verifactu_genesis_hash` en `secret_manager_service.py`).
- [x] **Evidencia minima**
  - Salida de tests en verde (incl. mapa per-issuer, hash global en JSON AWS/Vault, y `get_verifactu_genesis_hash_for_issuer`).
  - Contrato de variables documentado en `.env.example` (comentarios `VERIFACTU_GENESIS_*`, sin valores reales).
- [x] **Criterio de cierre**
  - Emision/validacion de cadena fiscal sin fallback hardcodeado.

**Cierre tecnico (Fase 1.2)**

| Verificacion | Evidencia en repo |
| --- | --- |
| Sin literal de 64 hex en `backend/app` | Revision estatica: ningun `.py` bajo `backend/app` contiene cadena hex de 64 caracteres (hashes solo en tests/scripts). |
| Resolucion centralizada | `verifactu_genesis.py` + `SecretManagerService.get_verifactu_genesis_hash` (env + `JsonMapSecretManager` con fallback `VERIFACTU_GENESIS_HASH`). |
| Multi-clave en JSON secreto | `_lookup_verifactu_genesis_hash`: `VERIFACTU_GENESIS_HASHES`, `VERIFACTU_GENESIS_HASH_BY_EMISOR`, `VERIFACTU_GENESIS_HASH_BY_ISSUER`; match por `issuer_id` o NIF normalizado. |
| Consumidores de cadena | `facturas_service`, `verifactu_service`, `verifactu_xml_service`, `core/verifactu.py`, `verifactu_chain_repair.py` importan `get_verifactu_genesis_hash_for_issuer`. |

**Estado del hito 1.2**

- **`HITO_1_2_COMPLIANCE_BACKEND` (codigo + tests + contrato env):** **[COMPLIANT]**
- **`HITO_1_2_COMPLIANCE_OPS` (secretos reales en runtime prod/staging):** **PENDIENTE** — Confirmar con checklist de despliegue que el JSON/variables existen en Vault o AWS SM (o env inyectado); no duplicar valores en git.

**Auditoria rapida en repo (sin revelar secretos)**

```bash
cd backend && pytest tests/unit/test_verifactu_genesis.py tests/unit/test_aws_secrets_manager_backend.py tests/unit/test_vault_kv_secret_manager.py -q
```

### 3) Seguridad S3 y backups

**Orden de ejecucion (canonico)**

1. **Infra / Ops** — Bucket dedicado (o prefijo aislado) en region **`eu-*`**, **Public Access Block** completo, **default encryption** (SSE-S3 o SSE-KMS), **lifecycle** con expiracion **35 dias** sobre el prefijo de backups (plantilla JSON en `docs/operations/BACKUP_S3_POLICY.md`). IAM con permisos listados en esa politica (incl. lecturas de PAB/encryption/lifecycle para CI).
2. **GitHub Actions** — Secretos `BACKUP_*` / Supabase alineados con `BACKUP_S3_POLICY.md`. Los workflows `backup_daily.yml` y `backup_restore_smoke.yml` validan region UE, cifrado del objeto y ejecutan `scripts/validate_backup_s3_bucket.sh` (PAB + encryption de bucket + lifecycle 35d).
3. **Cierre** — Runs verdes de **Backup Daily** y **Backup Restore Smoke** + evidencia Ops (capturas o export JSON de consola AWS opcional en data room). Marcar **`HITO_1_3_COMPLIANCE_BACKEND`** / Ops abajo.

- [x] **Accion**
  - Bucket de backups en region UE (`eu-*`).
  - Default encryption activa (AES256 o KMS).
  - Public access block habilitado.
  - Lifecycle de 35 dias aplicada al prefijo de backups.
- [x] **Como ejecutar**
  - Ejecutar workflow **Backup Daily** y **Backup Restore Smoke** (`workflow_dispatch` o cron).
  - Revisar `docs/operations/BACKUP_S3_POLICY.md` y script `scripts/validate_backup_s3_bucket.sh`.
  - Opcional consola/CLI AWS: region, encryption, PAB, lifecycle (redundante si CI en verde).
- [x] **Evidencia minima**
  - Run de `backup_daily` y `backup_restore_smoke` en verde (incluye paso de validacion de bucket).
  - [ ] **Evidencia Ops** — Capturas o export de configuracion del bucket en AWS (consola/CLI) archivadas en data room o ITSM; **PENDIENTE** hasta primer ciclo documentado en prod/staging.
  - JSON de lifecycle con expiracion 35 dias (plantilla en BCK-001; comprobacion automatica en CI vía `validate_backup_s3_bucket.sh`).
- [x] **Criterio de cierre**
  - Backup cifrado, en UE y restaurable con prueba semanal satisfactoria.

**Cierre tecnico (Fase 1.3)**

| Verificacion | Evidencia en repo |
| --- | --- |
| Region UE + coherencia bucket / `BACKUP_AWS_REGION` | `backup_daily.yml` y `backup_restore_smoke.yml` (`get-bucket-location`, prefijo `eu-*`). |
| Cifrado en upload + cabecera objeto | `aws s3 cp` con `--sse AES256` o KMS; `head-object` `ServerSideEncryption` AES256 \| aws:kms. |
| PAB + default encryption + lifecycle 35d | `scripts/validate_backup_s3_bucket.sh` + documentacion `BACKUP_S3_POLICY.md` §Validacion automatica. |
| Restore semanal + integridad | `backup_restore_smoke.yml` (descarga, tar, psql, RLS/tablas criticas, summary). |
| VPS legacy | `infra/backup_system.sh`: region UE, SSE en `cp`, validacion opcional post-upload. |

**Estado del hito 1.3**

- **`HITO_1_3_COMPLIANCE_BACKEND` (pipelines + script + politica en repo):** **[COMPLIANT]**
- **`HITO_1_3_COMPLIANCE_OPS` (bucket real + runs GH + capturas):** **PENDIENTE** — Confirmar en AWS cuenta productiva/staging: bucket conforme + dos workflows en verde; archivar enlaces a runs y, si aplica, capturas en acta Ops.

**Auditoria rapida (local, sin AWS)**

```bash
bash -n scripts/validate_backup_s3_bucket.sh
```

### 4) Migracion a Argon2id

**Orden de ejecucion (canonico)**

1. **Backend (completado en repo)** — Hash primario **Argon2id** (`PasswordHasher`, `type=ID`, `memory_cost=65536`, `time_cost=3`, `parallelism=4`) en `app/core/security.py`. Verificacion dual: prefijo `$argon2id$` o **64 hex SHA-256** legacy (`verify_password_against_stored`). Tras login OK con legacy y sin `password_must_reset`, **rehash lazy** en `AuthService._lazy_upgrade_password_hash`.
2. **Base de datos** — Columna `public.usuarios.password_must_reset` + indice (migracion `20260426225500_password_must_reset_legacy_sha256.sql`): bloquea sesion con credencial valida hasta `/reset-password` cuando Ops marca cuentas legacy (script `backend/scripts/mark_legacy_sha256_passwords.py` o job worker equivalente).
3. **Cierre Ops** — Tras despliegue de migracion, ejecutar marcado controlado de legacy si aplica; monitorizar logins y ratio Argon2 vs SHA-256 en periodo acordado; archivar acta o export de cuentas migradas. Marcar **`HITO_1_4_COMPLIANCE_OPS`** abajo.

- [x] **Accion**
  - Confirmar hashing primario Argon2id.
  - Mantener validacion dual para cuentas legacy SHA-256.
  - Rehash automatico al login exitoso.
- [x] **Como ejecutar**
  - `pytest backend/tests/test_security_passwords.py backend/tests/test_auth_bunker.py -q`
  - Revisar migracion `supabase/migrations/20260426225500_password_must_reset_legacy_sha256.sql` y flujo `AuthService.authenticate` / `set_password_for_username`.
- [x] **Evidencia minima**
  - Tests verdes: Argon2 roundtrip, flag legacy lazy, login bloqueado con `password_must_reset`, migracion lazy tras login, marcado masivo legacy, reset de password limpia flags.
  - [ ] **Evidencia Ops** — Registro de cuentas marcadas/migradas en ventana controlada (ticket, SQL agregado anonimizado o dashboard interno); **PENDIENTE** hasta primer ciclo en prod documentado.
- [x] **Criterio de cierre**
  - Nuevos hashes en Argon2id y sin bloqueo de login para usuarios legacy (salvo `password_must_reset` intencional).

**Cierre tecnico (Fase 1.4)**

| Verificacion | Evidencia en repo |
| --- | --- |
| Argon2id como algoritmo primario | `hash_password_argon2id` → `_password_hasher.hash` con `argon2.Type.ID` (`security.py`). |
| Dual-read legacy SHA-256 | `password_hash_uses_legacy_sha256` + comparacion `hmac.compare_digest` con `sha256_hex(plain)`. |
| Lazy upgrade post-login | `AuthService.authenticate` → `needs_argon2_upgrade` → `_lazy_upgrade_password_hash` (update `password_hash` + `password_must_reset=false` + `needs_rehash=false`). |
| Bloqueo controlado legacy | `password_must_reset` + `PasswordResetRequired`; tests `test_password_must_reset_bloquea_login_*`, `test_set_password_for_username_*`. |
| Migracion SQL + tooling | `20260426225500_password_must_reset_legacy_sha256.sql`; `20260427120000_compliance_hito_14_columns_and_stats.sql` (`needs_rehash`, `pseudonymized_at`, RPCs batch + stats); `scripts/mark_legacy_sha256_passwords.py`; `AuthService.mark_legacy_sha256_passwords_for_reset`; job ARQ `mark_legacy_sha256_passwords` en `worker.py`. |
| Marcado OPS / evidencia M&A | `scripts/compliance_mark.py` (dry-run / apply por lotes); `scripts/generate_compliance_report.py` → `backend/reports/compliance_evidence_*.md` (gitignored). |

**Estado del hito 1.4**

- **`HITO_1_4_COMPLIANCE_BACKEND` (crypto + auth + tests + migraciones + scripts evidencia):** **[COMPLIANT]**
- **`HITO_1_4_COMPLIANCE_OPS` (despliegue Supabase + marcado/monitorizacion):** **PENDIENTE** — Aplicar migraciones en proyecto; ejecutar `compliance_mark.py --apply` si aplica; generar y archivar `compliance_evidence_*.md` + ticket (sin PII ni secretos en el archivo).

**Auditoria rapida (local)**

```bash
cd backend && pytest tests/test_security_passwords.py tests/test_auth_bunker.py -q
```

**Flujo OPS resumido (tras `supabase db push` / migracion aplicada)**

```bash
cd backend
python scripts/compliance_mark.py --dry-run
python scripts/compliance_mark.py --apply --batch-size 500 --max-rounds 200
python scripts/generate_compliance_report.py --out reports/compliance_evidence_LATAM_Q2.md
test -f reports/compliance_evidence_LATAM_Q2.md && echo "OK informe generado"
```

---

## Fase 2 - Escudo economico y eficiencia (margen y control de coste)

### 1) Cache de rutas en Redis (Cache-Aside)

- [x] **Accion**
  - Activar cache-aside en rutas/coste (Truck API + Google Maps).
  - Reducir llamadas redundantes geocoding/routing.
- [x] **Como ejecutar**
  - Verificar configuracion `REDIS_URL` y TTLs (`GEO_CACHE_TTL_SECONDS`).
  - Ejecutar pruebas funcionales de rutas repetidas y comparar hit ratio/coste.
- [x] **Evidencia minima**
  - Metricas de cache hit/miss (`GET /health/deep` → `checks.geocoding_cache`: `routes_v2`, `truck_routes`, `distance_matrix`; geocoding sigue en `hits`/`misses`).
  - Caida medible de llamadas externas por misma consulta.
- [x] **Criterio de cierre**
  - Reduccion sostenida de consumo Maps sin degradar exactitud funcional.

### 2) Rate limiting multi-tenant

- [x] **Accion**
  - Aplicar limites por `tenant_id/empresa_id`.
  - Devolver `HTTP 429` en abuso.
- [x] **Como ejecutar**
  - Configurar `TENANT_RATE_LIMIT_DEFAULT` + `TENANT_RATE_LIMIT_OVERRIDES`.
  - Ejecutar pruebas de carga por tenant aislado.
- [x] **Evidencia minima**
  - Logs `rate_limit tenant exceeded` / `rate_limit bucket exceeded` con `key=`, `tenant_id=`, `bucket=`.
  - Casos de prueba con 429 en tenant excedido y no impacto cruzado (`tests/test_rate_limiting.py`).
- [x] **Criterio de cierre**
  - Aislamiento de cuota confirmado entre tenants.

### 3) Idempotencia de webhooks Stripe

- [x] **Accion**
  - Unificar recepcion en `/api/v1/webhooks/stripe`.
  - Evitar doble procesamiento por `event_id`.
- [x] **Como ejecutar**
  - Simular reentrega del mismo evento 2+ veces.
  - Confirmar claim/finalize en tabla de idempotencia.
- [x] **Evidencia minima**
  - Un solo efecto de negocio por `event_id` (`webhook_events`: `claim_webhook_event` → `finalize_stripe_webhook_claim` / `release_stripe_webhook_claim` en `stripe_service.handle_webhook`).
  - Trazas: log `webhook idempotency: duplicate delivery` (claim) + `stripe webhook idempotent replay ignored event_id=…` (router).
- [x] **Criterio de cierre**
  - Replays no generan suscripciones/cargos duplicados.

### 4) Hard limits y alertas de billing

- [x] **Accion**
  - Configurar presupuestos y alertas en AWS, OpenAI y GCP.
  - Definir umbrales de corte operativo (soft y hard).
- [x] **Como ejecutar**
  - Crear alertas 50/80/100 por proveedor.
  - Definir runbook de actuacion y owner on-call.
- [x] **Evidencia minima**
  - Capturas de budgets + reglas de notificacion (email/slack): **artefacto interno** (no git público); checklist de registro en `BILLING_PROVIDER_BUDGETS.md` §7.
  - Documento de respuesta ante sobrecoste aprobado: **`docs/operations/BILLING_PROVIDER_BUDGETS.md`** (runbook §6 + matriz on-call).
- [x] **Criterio de cierre**
  - Cualquier sobreconsumo genera alerta automatica y accion definida.

---

## Fase 3 - Produccion real y handover (operacion sin founder lock)

### 1) Homologacion AEAT real

**Preparacion en repo (no sustituye el envio AEAT):**

- [x] Plantilla de evidencia: `docs/operations/AEAT_HOMOLOGACION_EVIDENCE_TEMPLATE.md`.
- [x] Comprobacion de prerequisitos: `cd backend && PYTHONPATH=. python scripts/check_aeat_homologacion_readiness.py` (documentado en `AEAT_VERIFACTU_HOMOLOGACION.md` y `backend/scripts/README.md`).

- [ ] **Accion**
  - Inyectar certificados mTLS (`p12` o `pem/key`) via secretos.
  - Ejecutar envio real al entorno de pruebas AEAT.
  - Archivar respuesta tecnica para auditoria.
- [ ] **Como ejecutar**
  - Seguir `docs/operations/AEAT_VERIFACTU_HOMOLOGACION.md`.
  - Validar estado `Aceptado` y ausencia de errores no recuperables.
- [ ] **Evidencia minima**
  - Solicitud/respuesta AEAT (sin exponer datos sensibles).
  - Registro de cadena fiscal de factura enviada.
- [ ] **Criterio de cierre**
  - Envio homologado con respuesta aceptada y evidencia archivada.

### 2) Despliegue infra final (Railway/Vercel)

**Preparacion en repo:**

- [x] Checklist operativo (DNS, TLS, CORS, Redis, smoke): `docs/operations/DEPLOY_FINAL_TLS_CHECKLIST.md`.
- [x] Comprobacion local de config (sin red): `cd backend && PYTHONPATH=. python scripts/check_deploy_infra_readiness.py` (`--strict` endurece salida solo con `ENVIRONMENT=production`).

- [ ] **Accion**
  - Dominios finales activos (`app.*`, `api.*`).
  - CORS y `ALLOWED_HOSTS` estrictos en produccion.
  - Redis HA con TLS habilitado.
- [ ] **Como ejecutar**
  - Probar resolucion DNS y certificados TLS.
  - Ejecutar smoke de autenticacion y endpoints criticos.
  - Validar conexion Redis TLS y failover.
- [ ] **Evidencia minima**
  - Capturas/config de dominios y variables de entorno.
  - Resultado de smoke tests de despliegue.
- [ ] **Criterio de cierre**
  - App/API operativas en dominios finales con superficie de ataque reducida.

### 3) Monitoreo y salud profunda

**Preparacion en repo:**

- [x] `GET /health/deep` ya expuesto (`health_checks.run_deep_health`); contrato y alertas: `docs/operations/MONITORING_OBSERVABILITY.md`.
- [x] Sonda ampliada: `python backend/scripts/check_golive_readiness.py --base-url … [--strict] [--summarize-deep]`.

- [ ] **Accion**
  - Exponer `GET /health/deep` (API + DB + Redis).
  - Integrar Sentry/Better Stack con alertas a Slack/Email.
- [ ] **Como ejecutar**
  - Ejecutar: `python backend/scripts/check_golive_readiness.py --base-url https://api.tu-dominio --strict`
  - Forzar incidente controlado para validar disparo de alerta.
- [ ] **Evidencia minima**
  - Historial de checks de salud.
  - Alerta recibida en canal on-call.
- [ ] **Criterio de cierre**
  - Deteccion de fallo en menos de 5 minutos con notificacion automatica.

### 4) Activos de transferencia (handover)

**Preparacion en repo:**

- [x] **Indice de transferencia:** `docs/operations/HANDOVER_PACKAGE.md` (orden de lectura + tabla de owners).
- [x] **Acta / checklist accesos (plantilla):** `docs/operations/HANDOVER_ACTA_TEMPLATE.md`.
- [x] **VeriFactu end-to-end (operacion):** `docs/operations/VERIFACTU_OPERATIONS_RUNBOOK.md`.
- [x] Topologia y DR ya publicados; tras handover, registrar fecha en `OPS_001_TOPOLOGIA_PLATAFORMA.md` § Revisión handover.

- [ ] **Accion**
  - Documentar logica fiscal VeriFactu end-to-end.
  - Publicar topologia operativa para equipo externo.
  - Cerrar runbook de guardias y recuperacion.
- [ ] **Como ejecutar**
  - Revisar y actualizar:
    - `docs/operations/OPS_001_TOPOLOGIA_PLATAFORMA.md`
    - `docs/operations/ON_CALL_RUNBOOK.md`
    - `docs/operations/DISASTER_RECOVERY.md`
- [ ] **Evidencia minima**
  - Sesion de handover grabada o acta firmada.
  - Checklist de accesos/rotacion de credenciales completado.
- [ ] **Criterio de cierre**
  - Equipo externo puede operar incidencias criticas sin dependencia del fundador.

---

## Gate final de salida (Escenario B)

Marcar go-live completado solo si todos los puntos siguientes estan en verde:

- [ ] Fase 1 completa (0 bloqueadores legales/fiscales abiertos). *Notas:* **1.1–1.3** Backend **[COMPLIANT]** con Ops pendiente donde aplica (ITSM, genesis, S3). **1.4** Backend Argon2id + tests + migracion SQL **[COMPLIANT]**; Ops `HITO_1_4_COMPLIANCE_OPS` (marcado/monitorizacion prod) pendiente. Sin evidencias Ops sigue **conditional go** donde aplique.
- [ ] Fase 2 completa (costes controlados y abuso limitado por tenant).
- [ ] Fase 3 completa (produccion estable + monitorizada + transferida). *Notas:* **3.1–3.3** y **3.4** incluyen artefactos de repo (scripts/plantillas/runbooks); los checkboxes operativos (AEAT real, DNS/TLS prod, alertas vivas, acta firmada) siguen en manos del equipo hasta cerrarlos.
- [ ] Auditoria tecnica interna cerrada con evidencias.
- [ ] Decision formal de paso a Escenario B (`EUR 1.1M - 1.8M`) documentada.
