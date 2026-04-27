# 📝 AB Logistics OS - Mission Scratchpad

## ✅ Conciliación al cerrar un paso (obligatorio)
Cuando un entregable quede **verificado en repo** (merge + smoke razonable): **actualizar de inmediato** este `SCRATCHPAD.md` — checklist (`[ ]` → `[x]`), fila **Fase 10**, bullets “Pendiente” y narrativa al pie — para que **no quede ninguna contradicción** con el código. Si se pospone un ítem, dejar explícito *por qué* en una línea.

## 🎯 OBJETIVO ACTUAL
- **Desarrollo técnico core (Fases 1–9 + móvil 4.x): ✅ 100%** — El producto es funcional y demostrable; el foco operativo pasa al **blindaje pre-exit** (auditoría M&A, €2M+).
- [🟡] **Fase 5 (DD) — Pre-Exit Remediation & Market Hardening (D0–D15): parcial** — Avance verificado en código (2026-04): dashboard financiero vía `vw_dashboard_summary` + `round_fiat`; km operativos con `quantize_operational_km` / `aggregate_portes_km_bultos` (sin `float(sum)` en esas rutas); **coste €/km** centralizado (`COSTE_OPERATIVO_EUR_KM` + `GET /api/v1/config/operational-pricing` + front); **`auto_reconcile_all`** por `empresas` paginadas (`AUTO_RECONCILE_*`); cola móvil con **DLQ** (`abl_sync_dlq_v1` + UI Pendientes/home); IBAN cifrado en alta/patch empresa; **verificación ESG externa cerrada en código** (QR público sin `subject_id`; `ESG_PUBLIC_VERIFY_RATELIMIT`; `GET /api/v1/esg/certificate-registry`; `GET /api/v1/esg/emissions-export-iso14083` + `for_external_auditor`; `POST /api/v1/esg/certificate/externally-verify/{code}` owner + webhook HMAC existente; UI Sostenibilidad/Auditoría; help `/help/esg-external-verification`); certificado ESG con QR + `GET /v1/public/verify-esg/...`; **export paquete auditor** (`GET /api/v1/export/audit-package` + ZIP + UI Finanzas/Auditoría + help `/help/audit-evidence-pack`); **pricing/copy add-ons** alineados a matriz `plans.py` (39/149/449 € + add-ons), landing, `/help/billing`, `STRIPE_BILLING.md`, `production.env.example` (`NEXT_PUBLIC_STRIPE_PRICE_*`). Pendiente: *Compliance Deck*. APIs GLEC/EEA → **futuro** (sin ROI en alcance actual; ver sección *Futuro*). Ver sección dedicada.
- [x] **Limpieza de "Fugas de Valor" (Fase 1 — saneamiento global)**: Rutas críticas sin ``os.getenv`` para claves LLM/OCR; inventario ampliado en `README_SECURITY.md`; script `force_sync_user_password.py` sin contraseña por defecto en repo; `.gitignore` para `backend/.venv_test_finance/`.
- [x] **Fase 4.2 (móvil) — Módulo POD base funcional**: ruta `app/(app)/porte/[id].tsx` con detalle + captura firma (`react-native-signature-canvas`) + foto (`expo-camera`) + geostamp (`expo-location`); subida de assets a Supabase bucket `pod-assets` y sincronización API con estrategia dual: `PATCH /api/v1/portes/{id}` (contrato objetivo) y fallback automático a `POST /api/v1/portes/{id}/firmar-entrega` (backend actual).
- [x] **Fase 4.3 (móvil) — Resiliencia & Visualización**: cola offline POD en `AsyncStorage` (`src/services/sync_service.ts`) con reproceso automático al abrir app y al recuperar red (`NetInfo`); banner discreto de pendientes en `app/(app)/index.tsx`; preview legal PDF en `app/(app)/porte/preview-[id].tsx` (WebView contra `/api/v1/portes/{id}/albaran-entrega` con bearer token); feedback premium con `expo-haptics` al confirmar firma.
- [x] **Fase 4.4 (fullstack) — Poder Financiero con OCR**: módulo móvil de gastos (`app/(app)/gastos/index.tsx` + `app/(app)/gastos/nuevo.tsx`) con captura cámara + compresión (`expo-image-manipulator`) + confirmación editable; backend `POST /api/v1/gastos/ocr` para extracción (`proveedor`, `cif`, `base_imponible`, `iva`, `total`, `fecha`) vía **visión LLM (LiteLLM: GPT‑4o / Gemini)**; persistencia en bucket `tickets-gastos` y vinculación opcional `porte_id` para trazabilidad de margen real.
- [x] **Cierre Fase 4 — Offline unificado + soporte operativo**: cola polimórfica única (`POD | GASTO`) con reintentos automáticos/manuales, pantalla operativa `app/(app)/pendientes.tsx`, categorización estructurada de gastos y migración SQL para `gastos.porte_id` + enum de categoría; terreno preparado para **Fase 10 — Pre-Exit Remediation** (sprint DD) sin reabrir el núcleo móvil.
- [x] **Onboarding producto/ops — plan operativo 2 semanas**: runbook creado en `docs/operations/ONBOARDING_PLAYBOOK.md` con fases día a día, roles, KPIs, criterio de go-live y mitigaciones.

**Desarrollo Técnico: ✅ Completado al 100% (Stripe, i18n, BI, Mapas)** — Certificación `npx tsc --noEmit` (frontend) sin errores; tipos Leaflet + `leaflet.heat` en `frontend/src/types/leaflet-heat.d.ts` (`heatLayer` fusionado al módulo `leaflet`, módulo `leaflet.heat` declarado); mapa admin `AdminHeatmapMapClient` cargado con `dynamic(..., { ssr: false })` en `app/admin/dashboard/map/page.tsx`.

**Pre-Exit Hardening (DD): 🟡 Parcial** — Checklist D0–D15 avanzado (dashboard, km/money saneados, **€/km parametrizado**, **conciliación masiva acotada**, **DLQ móvil**, IBAN, **ESG verificación externa + export ISO sin PII + rate limit público**, **paquete auditor ZIP**, **matriz precios/copy**); queda *Compliance Deck* en Fase 10. **GLEC/EEA API** queda en backlog *Futuro* (ROI).

## 🔮 Futuro (sin compromiso de alcance actual)
- **Integración APIs GLEC / EEA** para factores de emisión **dinámicos** — pospuesto por **ROI de producto** en esta fase; el motor comercial sigue con **ISO 14083** y constantes documentadas (`ISO_14083_DIESEL_CO2_KG_PER_LITRE`, etc.). Reabrir solo si hay mandato comercial/regulatorio explícito.

## ⚖️ Valoración técnica — `get_settings()` vs `SecretManagerService` (bootstrap)

| Criterio | Conclusión |
| :--- | :--- |
| **Rol hoy** | `Settings` (`app/core/config.py`, `get_settings` en caché) agrega **toda** la config vía `getenv`: CORS, hosts, Supabase URLs, JWT, Stripe, GoCardless, Fernet, SMTP, OAuth, AEAT, etc. `SecretManagerService` es la **fuente de verdad** para rotación/banca/cifrado multi-key y ahora también LLM/OCR; parte de los mismos nombres se leen en ambos sitios. |
| **¿Hidratar `Settings` solo desde SecretManager?** | **No recomendado como big-bang.** Vault/AWS JSON **no** modela hoy flags operativos (`DEBUG`, `AEAT_*`, series VeriFactu, CORS, `DATABASE_URL` compuesta desde `POSTGRES_*`). Meterlos en el mismo JSON mezcla secretos con config y complica políticas IAM/Vault. |
| **Riesgo de divergencia** | Medio: código que siga usando `get_settings().STRIPE_SECRET_KEY` vs `get_secret_manager().get_stripe_secret_key()` puede desalinearse tras `bump_integration_secret_version` + reinicio parcial. **Mitigación ya alineada:** integraciones sensibles (banca, cifrado, IA) deben ir por `get_secret_manager()`. |
| **Dependencia circular** | `EnvSecretManager.get_jwt_secret_key()` hace fallback a `get_settings().JWT_SECRET_KEY`. Invertir el orden (Settings ← SecretManager primero) exige **romper el ciclo** (módulo mínimo de solo JWT, o lectura lazy post-import). |
| **Coste / beneficio** | Refactor para que `Settings` **no** contenga secretos implica tocar `stripe_service`, `encryption`, cookies/sesión, OAuth, worker, tests y el `settings = get_settings()` al importar `config`. Beneficio marginal si el inventario Vault ya replica las mismas claves y los servicios críticos ya usan el manager. |
| **Recomendación** | **Mantener** `get_settings()` como **bootstrap de aplicación** (no secretos + URLs + flags + supuestos de entorno Railway). **Seguir** exigiendo secretos de negocio en código de dominio vía `get_secret_manager()`. **Opcional (fase 2):** marcar en doc/tipos los campos de `Settings` que son *snapshot* de secretos como *deprecated for new code* y migrar lecturas restantes (`stripe_service`, etc.) al manager; o añadir helpers `get_stripe_secret_key()` que deleguen al manager sin duplicar env. |
| **DD / narrativa** | Para un comprador: *“Los secretos rotativos y de integración pasan por una interfaz única con backends auditables; la config estática y de despliegue se resuelve en `Settings` al arranque.”* Es defendible y está alineado con el cierre #115. |

## 🗺️ Master Roadmap unificado — Exit verano 2026

*Leyenda estado: **✅ Cerrado** = entregable principal verificado en repo (no reabrir sin nuevo alcance). **🟡 Parcial** = bloques cerrados, queda trabajo explícito. **⬜ Pendiente**.*

| Fase | Estado | Entregable estratégico |
| :---: | :--- | :--- |
| **1** | ✅ Cerrado | **Due Diligence técnica & IP** — Bloques fiscales / secretos / ESG auditables; saneamiento global de lecturas directas de secretos en IA/OCR y endurecimiento de utilidades locales. |
| **2** | ✅ Cerrado | **Motor fiscal VeriFactu** — Huellas, cadena, persistencia y auditorías alineadas a cierres DD (NIF, series, stress). |
| **3** | ✅ Cerrado | **Secretos, seguridad base & ESG comercial** — `SecretManagerService` + Vault/AWS; factor CO₂ ISO 14083; certificación y exports auditables. |
| **4** | ✅ Cerrado | **Movilidad y captura (Driver App)** — POD, firma digital, OCR de gastos y sincronización offline unificada (cola polimórfica POD/GASTO). |
| **5** | ✅ Cerrado | **Inteligencia financiera (bancos E2E)** — GoCardless y conciliación asistida por IA (tesorería + e2e; ver tabla de componentes). |
| **6** | ✅ Cerrado | **Robustez y resiliencia** — Sentry (`APP_RELEASE` / SHA, `SENTRY_TRACES_SAMPLE_RATE`), correlación `X-Request-ID` en logs JSON, liveness `/live` vs readiness `/health`+`/health/deep`, DRP en `docs/operations/DISASTER_RECOVERY.md`. |
| **7** | ✅ Cerrado | **Compliance y blindaje legal** — RGPD, SLA contractuales y ciberseguro (postura demostrable): `GET /api/v1/public/compliance`, `GET /.well-known/security.txt`, `docs/legal/COMPLIANCE_AND_SECURITY_POSTURE.md`, `SECURITY_CONTACT_EMAIL`. |
| **8** | ✅ **i18n Universal (Frontend + Backend)** | **i18n + Help Center + portal** — catálogo gettext en backend (`backend/locale/es/...`), columnas `preferred_language` en `usuarios` y `empresas`; PDFs (facturas, POD, certificados ESG / exportaciones fiscales) y correos según idioma del usuario. Hub `/help` bilingüe con búsqueda y artículos (`help/articles.ts`: getting-started, company-onboarding separado del backlog “onboarding producto”, ERP facturación, portal, billing); superficies ERP i18n; E2E portal opt-in `frontend/tests/portal-cliente.spec.ts`. **Fuera del cierre de código:** onboarding de producto/ops como vía propia. **Stripe Billing:** ✅ **Automatizado** — webhooks `invoice.paid` / `invoice.payment_failed` / `customer.subscription.deleted` → columnas `empresas.subscription_status` e `is_active`; endpoint `POST /api/v1/webhooks/stripe` (`app/api/v1/webhooks/stripe.py`) con firma vía `SecretManagerService`; portal Stripe desde `QuotaStatusCard`; E2E `tests/e2e/test_stripe_webhooks.py`; runbook `docs/operations/STRIPE_BILLING.md`. |
| **9** | ✅ Cerrado | **Ecosistema y salida** — Webhooks B2B bajo `/api/v1/webhooks` (suscripciones, catálogo de eventos, prueba firmada); despacho con HMAC/reintentos (`webhook_service`, `webhook_dispatcher`); **M&A Data Room** — paquete de evidencias alineado a compliance público (`GET /api/v1/public/compliance`, `docs/legal/COMPLIANCE_AND_SECURITY_POSTURE.md`, `README_SECURITY.md`, contratos en `docs/PLATFORM_CONTRACTS.md`). |
| **10** | 🟡 **Parcial** | **Pre-Exit Remediation & Market Hardening (D0–D15)** — *Hecho (código):* KPIs owner `DashboardService.stats()` con `vw_dashboard_summary` + `round_fiat`; km operativos con `quantize_operational_km` / agregados sin `float(sum)` en rutas dashboard operativas; **€/km** unificado (`app/core/constants.py`, endpoint `GET /api/v1/config/operational-pricing`, mapas/BI/Vampire Radar/IA/backoffice); **`auto_reconcile_all`** paginado sobre `empresas` (sin `SELECT` global en facturas/bank_transactions para descubrir tenants; env `AUTO_RECONCILE_*`); IBAN con `pii_crypto` en `AdminService`; **ESG externo:** verificación pública endurecida (sin `subject_id`; `ESG_PUBLIC_VERIFY_RATELIMIT`); `GET /api/v1/esg/certificate-registry`; `GET /api/v1/esg/emissions-export-iso14083` (`for_external_auditor`); `POST /api/v1/esg/certificate/externally-verify/{code}` owner + webhook HMAC; UI Sostenibilidad/Auditoría; help `esg-external-verification`; ESG audit-ready (QR, hash, `pending_external_audit` Enterprise); `MAX_TRIES=3` + **DLQ local** (`abl_sync_dlq_v1`, reencolar/descartar, banner home) en `sync_service.ts` / pantalla Pendientes; **paquete auditor** `GET /api/v1/export/audit-package` + `audit_package_export.py` + UI auditoría; **pricing/copy** (39/149/449 + add-ons) en landing, i18n precios, Help billing, `STRIPE_BILLING.md`. *Pendiente:* *Compliance Deck* 10p. *GLEC/EEA APIs:* backlog **Futuro** (ROI). *(Fase histórica **5** = bancos E2E, cerrada.)* |

### Fase 8 — checklist Help Center (código)
- [x] Hub `/help` + `/help/[slug]` + búsqueda (título, extracto, slug, cuerpo simplificado).
- [x] Artículos: primeros pasos, onboarding empresa (separado de “onboarding producto”), idioma (frontend + backend), facturación ERP, portal cliente, billing (orientación + enlace runbook Stripe + matriz add-ons), **audit-evidence-pack** (ZIP paquete auditor), **esg-external-verification** (workflow verificación externa + export ISO).
- [x] Enlaces desde shell, precios, cuota (`QuotaStatusCard` → `/help/billing`), facturas ERP → `/help/erp-invoicing`, pie portal.

*Polo temporal del roadmap (mayor esfuerzo restante): **Fase 10 — Pre-Exit Remediation & Market Hardening (D0–D15)** — blindaje post-DD para exit €2M+; el core móvil (Fase 4.x) está cerrado.*

## Fase 5: Pre-Exit Remediation & Market Hardening (D0–D15)

*Sprint operativo enlazado a la Due Diligence técnica y comercial (`DD_AB_LOGISTICS_OS_EXIT_REPORT.md`). Objetivo: el producto **deja de ser solo funcional** y pasa a estar **blindado** para auditoría M&A y cierre de ronda / exit **€2M+**.*

### Identidad contable (criterio de aceptación transversal)

Toda agregación monetaria en reporting debe respetar la identidad contable acordada con finanzas y comprador:

$$\text{Margen Neto} = \text{Ingresos} - \sum \text{Gastos (ROUND\_HALF\_EVEN)}$$

*Implicación técnica:* prohibido depender de `float(sum(...))` en rutas de dashboard donde los céntimos suman; usar **Decimal** + **`round_fiat`** (o equivalente auditado) en `dashboard_service.py` y alinear exports/BI con el mismo redondeo.

### Saneamiento financiero
- [x] **Decimal / agregación dashboard:** `DashboardService.stats()` vía `vw_dashboard_summary` + `round_fiat` en EUR; **km** con `quantize_operational_km` (no `round_fiat` sobre km). `stats_operativos_*` usan `aggregate_portes_km_bultos` (``math_engine``) sin `float(sum())`.
- [x] **Coste operativo €/km parametrizado:** constante `COSTE_OPERATIVO_EUR_KM` (env homónimo) + `GET /api/v1/config/operational-pricing`; front `operationalPricing.ts` (`VampireMap`, `FleetIntelligenceMap`, `vampire-radar`, BI); backend maps/geo/ai/advisor/BI/finance alineados; fallbacks CO₂ vía `calculate_co2_emissions` donde el dato es emisiones, no €/km. `production.env.example` documentado.

### Seguridad y performance
- [x] Cifrar **IBAN** en **`AdminService.create_empresa()`** / patch (`_encrypt_iban_for_storage` + `pii_crypto`).
- [x] **N+1 en `DashboardService.stats()`:** lectura única a **`vw_dashboard_summary`** (`supabase/migrations/20260420200000_vw_dashboard_summary.sql`).
- [x] **`auto_reconcile_all()`:** enumeración por **`empresas` paginada** (`filter_not_deleted`, opcional `is_active`, `AUTO_RECONCILE_EMPRESA_PAGE_SIZE`); sin volcar todas las filas de `facturas` / `bank_transactions` solo para extraer `empresa_id`. Parámetro opcional `empresa_id=` para job por tenant.

### Resiliencia móvil
- [x] **Cola offline + DLQ:** `MAX_TRIES` en **`sync_service.ts`**; ítems agotados van a **`SYNC_DLQ_KEY`** (`abl_sync_dlq_v1`) con `deadletteredAt`; `clearSyncErrors` / `migrateExhaustedToDlq` mueven a DLQ sin borrar payload; `reenqueueFromDlq` / `removeDeadLetter`; UI **Pendientes** (sección DLQ) y aviso en home si `dlqSize > 0`.

---

## Portal cliente (desglose entregas)
| Bloque | Estado | Contenido |
| :--- | :--- | :--- |
| **1** | ✅ | Riesgo comercial en portal (modal + i18n ES/EN), mandato inicial/refresco post-GoCardless, URL de éxito canónica. |
| **2** | ✅ | Textos Mis Portes / Sostenibilidad vía `pages.portalClienteMisPortes` y `pages.portalClienteSostenibilidad`; fechas y números con `formatPortalDateTime` / `formatPortalDecimal` (`lib/portalLocaleFormat.ts`). |
| **3** | ✅ | Pie portal (aside + footer móvil): ayuda, privacidad, aviso legal, mailto soporte (`NEXT_PUBLIC_SUPPORT_EMAIL`); host API solo en dev o API localhost (`isPortalApiBaseDebugVisible`). |
| **4** | ✅ | Playwright `frontend/tests/portal-cliente.spec.ts`: `baseURL` vía `PLAYWRIGHT_TEST_BASE_URL` / `PLAYWRIGHT_BASE_URL`; flujo **A** JWT Mis portes → riesgo → Facturas + **a11y** (bloque 6); flujo **B** login → Facturas + axe. Sin env los tests se omiten. Scripts `npm run test:e2e` / `test:e2e:portal`. |
| **5** | ✅ | Help Center: artículo bilingüe \`/help/portal-cliente\` (\`help/articles.ts\`, categoría **support**) — acceso, riesgo/SEPA, módulos, pie, variables E2E. |
| **6** | ✅ | Estados vacíos (\`PortalClienteEmptyState\`), errores (\`PortalClienteAlert\`), tablas \`caption\` sr-only + \`scope="col"\`, carga \`aria-busy\`/\`aria-live\`, modal riesgo (foco + \`aria-describedby\`), mandato \`SetupMandateCard\` (\`aria-labelledby\`/\`aria-busy\`); i18n. **E2E:** \`@axe-core/playwright\` sin violaciones \`critical\`/\`serious\` en Mis portes y Facturas (JWT en serie); tras login, axe en Facturas. **SR:** checklist manual debajo. |

#### Checklist manual SR — portal cliente (VoiceOver / NVDA)
*Ejecución humana; contrastes y matices solo los cubre la pasada real con lector.*

**VoiceOver (macOS)** — Activar/desactivar: **⌘ F5**. Navegación rápida: **VO** (⌃ ⌥) + **U** (rotor) → Encabezados / Formularios / Tablas.
1. **Mis portes** (con modal de riesgo si aplica): al abrir, el VO debe anunciar el **diálogo**; el foco debería ir al **primer checkbox**; **VO + →** lee título asociado (\`aria-labelledby\`) y texto introductorio (\`aria-describedby\`). Tras confirmar, el foco vuelve al documento sin quedar atrapado.
2. **Tablas**: en rotor → Tablas, dos tablas con nombre coherente con el **caption** (activos / histórico). Entrar en tabla (**VO + Mayús + ↓**) y recorrer celdas; cabeceras con \`scope="col"\`.
3. **Actualizar**: **Tab** hasta el botón; el nombre accesible debe incluir la intención (lista activos + historial), no solo “Actualizar”.
4. **Facturas**: si carga vacía, **status** con mensaje vacío + pista; si hay datos, tabla con caption de facturas. **⌘ F5** al terminar para no dejar VO activo por error.

**NVDA (Windows)** — **Insert+Q** salir al terminar. Modo exploración: **Insert+Espacio** si hiciera falta. **T** / **Mayús+T** saltar entre tablas; **H** encabezados.
1. Misma ruta **Mis portes** → modal: foco en checkbox, **Insert+Tab** revisa nombre/rol del diálogo.
2. Tablas y **Facturas** como arriba; comprobar que **alertas** de error (si fuerzas error de red) se anuncian al entrar en la región.

**Comando E2E a11y (automático):** \`PLAYWRIGHT_TEST_BASE_URL=… E2E_PORTAL_CLIENTE_JWT='…' npm run test:e2e:portal\` (y pareja email/password para el tramo login + axe).

## 🚩 RED FLAGS TÉCNICOS — ✅ cerrados (referencia M&A; no repetir salvo regresión o cambio normativo)
- [x] **Unificación de Hashes**: (igual) + **cierres DD**: auditoría fingerprint con NIF emisor descifrado y NIF receptor vía `clientes`; `VERIFACTU_SERIE_*` en `Settings`; stress VeriFactu alineado a `HUELLA_EMISION`; `tests/unit/test_verifactu_compliance.py`; doc `backend/docs/FISCAL_PERSISTENCE.md` (triple huella).
- [x] **Sinceridad de Secretos (DD #115) — CERRADO**: Interfaz única + backends Vault KV v2 (`token` / `kubernetes` / `approle`), AWS Secrets Manager (JSON), env / `SaaSEnvSecretProvider`; inventario, rotación y tests en `README_SECURITY.md` y `tests/unit/test_*secret*`.
- [x] **Factor CO2 / ESG comercial (ISO 14083)**: Factor diésel unificado `2.67 kg CO₂eq/L` vía `ISO_14083_DIESEL_CO2_KG_PER_LITRE`; eco/auditoría/BI/reportes alineados; certificado PDF (ReportLab) + CSV YTD portal (`/api/v1/portal/esg/export-csv`) misma tripleta GLEC que certificado; tests `tests/unit/test_esg_logic.py`.

### Módulo ESG — ampliación Pre-Exit (D0–D15)
- [⏸️] **Integración APIs GLEC / EEA** (factores dinámicos) — **futuro / pospuesto por ROI**; ver sección *Futuro*; sin ticket activo en sprint DD.
- [x] **Coste operativo €/km vs CO₂:** el **€/km de producto** está centralizado (no literales `0,62` en rutas de margen/mapas/IA); los **kg CO₂/km por Euro** siguen en `esg_engine` (convivencia explícita; no mezclar con coste € en matrices CIP/reportes).
- [x] **Verificación externa (SGS / BV):** QR + `GET /v1/public/verify-esg/{code}` (respuesta **sin** `subject_id`; rate limit por IP `ESG_PUBLIC_VERIFY_RATELIMIT`); hash SHA-256 del PDF; estados `self_certified` / `pending_external_audit` / `externally_verified`; webhook HMAC `POST /api/v1/webhooks/esg-external-verify`; **owner:** `POST /api/v1/esg/certificate/externally-verify/{code}`; **export ISO sin PII** `GET /api/v1/esg/emissions-export-iso14083` + `for_external_auditor`; **registro** `GET /api/v1/esg/certificate-registry`; UI **Sostenibilidad → Auditoría**; help `/help/esg-external-verification`.

## 🏗️ ESTADO DE COMPONENTES CRÍTICOS
| Módulo | Estado | Auditoría M&A |
| :--- | :--- | :--- |
| **VeriFactu** | 🟢 Estable | Huella XML (`generar_hash_factura`) documentada; auditorías API/Advisor/IA materializan NIFs. |
| **Banking E2E** | 🟢 | Migración `bank_accounts.access_token_encrypted` + `bank_transactions.status_reconciled`; `banking_service.py` (GoCardless vía ``SecretManagerService``/``SaaSEnvSecretProvider``); conciliación: LogisAdvisor historial cliente + LLM; auditoría `bank_reconciliation` + POST middleware; UI tesorería (conectar + pendientes); tests `tests/e2e/test_banking_flow.py` y `test_banking_reconciliation_flow.py`. |
| **Portal Cliente** | ✅ Cerrado | Bloques 1–6: riesgo/mandato, i18n, pie, E2E opt-in, help \`/help/portal-cliente\`, vacíos/errores/a11y (tablas, modal riesgo, mandato, facturas). |
| **Secret Manager** | 🟢 Cierre DD #115 + SEC-001 | Ver tabla de cierre formal abajo; génesis VeriFactu por emisor queda fuera de `.env` y se resuelve vía Secret Manager. |

## ✅ Cierre formal — Secretos / Hallazgo 115 (2026-04-19)
| Criterio | Evidencia en repo |
| :--- | :--- |
| **Interfaz única** | `SecretManagerService` en `backend/app/services/secret_manager_service.py`. |
| **Backends auditables** | `env` / `railway` / `mock`; `vault` (KV v2 + auth); `aws` / `secretsmanager` (JSON). |
| **Sin “Vault falso”** | Nombres y logs alineados a comportamiento real; fallback documentado. |
| **Rotación y runbook** | `README_SECURITY.md`; CLI `scripts/rotate_secrets.py`. |
| **Tests automatizados** | `tests/unit/test_vault_kv_secret_manager.py`, `tests/unit/test_aws_secrets_manager_backend.py`. |
| **Fuera de alcance (post-cierre)** | Smoke end-to-end en Vault/AWS reales con IAM y políticas del cliente (operación, no gap de código). |

## 🔐 Secretos (DD #115 — referencia)
- **Código**: `backend/app/services/secret_manager_service.py` — `SecretManagerService`; `vault` → KV v2 + auth `token` | `kubernetes` | `approle`; `aws`/`secretsmanager` → JSON en AWS Secrets Manager; sin config → env / `SaaSEnvSecretProvider`.
- **Runbook**: `README_SECURITY.md` (inventario de variables, rotación multi-key Fernet, auditoría).
- **Operación**: `python scripts/rotate_secrets.py` (empezar con `--dry-run`); tras cambios en panel PaaS, reiniciar workers y usar `bump_integration_secret_version` donde aplique.

## 📊 Hitos de valoración (Exit verano 2026)

| Hito | Fase | Producto | Objetivo |
| :--- | :---: | :--- | :--- |
| Inteligencia financiera operativa (bancos E2E + conciliación) | **5** | ✅ Cerrado | **€1.5M** |
| Compliance y blindaje legal demostrable (RGPD, SLA, ciberseguro) | **7** | ✅ Cerrado | **€1.8M** |
| Ecosistema integrable + paquete Data Room para M&A | **9** | ✅ Cerrado | **€2M+** |
| **Compliance Deck** (10 páginas, inversores / M&A) | **10** | ⬜ Pendiente | **€2M+** (narrativa + evidencias DD) |

*La columna **Producto** indica si el entregable técnico asociado al hito está cerrado; el importe sigue siendo objetivo de valoración / narrativa M&A, no “cerrado” en sentido financiero.*

## 💼 Estrategia comercial — actualización Pre-Exit (pricing & add-ons)

### Tiers SaaS (mensual, orientativo)
| Tier | Precio |
| :--- | :---: |
| **Starter** | **€39** / mes |
| **Pro** | **€149** / mes |
| **Enterprise** | **€399** / mes |

### Revenue stream: add-ons
| Add-on | Precio |
| :--- | :---: |
| **OCR Packs** (bloques consumo) | **€15** |
| **Webhooks Premium** | **€49** |
| **LogisAdvisor Pro** | **€29** |

*Runbooks de billing/Stripe y Help Center deben alinearse a esta matriz en la siguiente iteración de copy y catálogo (Fase 10).*

## 📊 Métricas de valoración (ROI) — contexto
- **Trayectoria / baseline de IP** (pre-roadmap unificado): ~€1.2M–€1.5M según estado de producto y DD.
- **Tramo consolidado tras cierre Fase 4 (Movilidad + OCR + resiliencia offline):** **€1.5M–€1.8M**.
- **Factor de diferenciación**: IA LogisAdvisor (detección de rutas vampiro).
- **Compliance comercial**: certificado ISO 14083 (2.67 kg/L) como gancho de venta.

## 📎 CONTEXTO DE DESARROLLO (Píldoras)
- **Base de Datos**: Supabase (PostgreSQL). RLS activo en todas las tablas.
- **Testing**: `pytest tests/e2e/test_banking_reconciliation_flow.py tests/e2e/test_banking_flow.py`
- **Factor Crítico**: El encadenamiento de VeriFactu NO puede romperse bajo ninguna circunstancia.

---

## Ritual de cierre — narrativa M&A (actualización DD)

El **AB Logistics OS** ya no se posiciona únicamente como *producto funcional*: la **Fase 10** (y el sprint DD en esta sección) consolidan el camino hacia **blindaje M&A** — con parte del checklist ya cerrada en código (dashboard agregado, **€/km parametrizado**, **`auto_reconcile_all` acotado**, **DLQ móvil**, IBAN, ESG verificable por QR) y el resto explícito arriba (APIs GLEC/EEA, *Compliance Deck*). La narrativa de **exit €2M+** sigue anclada a cerrar esos ítems y al deck de inversores.