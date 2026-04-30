# Runbook de incidentes P1 v1 (detección, contención, comunicación, RCA)

**Versión:** 1.0 · **Vigencia:** desde 2026-04-29 · **Owner:** Adrian (solo-founder)  
**Audiencia:** quien recibe una alerta P1 (servicio caído, datos en riesgo, VeriFactu bloqueado masivo, restore).  
**Relación con otros docs:** este documento es el **flujo P1**; el índice de guardia y matrices sigue en `ON_CALL_RUNBOOK.md`. No duplicar reglas de alerta: ver `ALERT_RULES_P1_V1.md` y `SLO_MINIMAL_V1.md`.

---

## 0) Definición de P1 (recordatorio)

Usar la matriz de `ON_CALL_RUNBOOK.md` § *Matriz de severidad*. En P1 asumir:

- Respuesta **inmediata** (objetivo &lt; 15 min hasta primera acción documentada).
- **Incident commander** = quien está de guardia (en solo-founder, tú mismo); anótalo en el registro del incidente.

---

## 1) Detección (0–15 min)

### 1.1 Confirmar que es real (no falso positivo de red)

Ejecutar desde un entorno de confianza (laptop con red estable o segundo probe):

```bash
curl -fsS -o /dev/null -w "%{http_code}\n" "https://<API_HOST>/live"
curl -fsS -o /dev/null -w "%{http_code}\n" "https://<API_HOST>/health"
curl -fsS "https://<API_HOST>/health/deep" | head -c 2000
```

- Si `/live` falla → proceso o edge caído (Railway/Vercel API).
- Si `/live` OK y `/health/deep` es **503** → leer `checks` en el JSON (`ALERT_RULES_P1_V1.md` §2).
- Si solo `/health` falla pero `/health/deep` parcial → priorizar el check que marca `ok: false` en deep.

### 1.2 Correlacionar con alertas y despliegues

1. Revisar **último deploy** (Railway API, Vercel) y cambios de variables en las últimas 24 h.
2. Abrir **Sentry** filtro `production`, ventana desde inicio del incidente.
3. Revisar monitores **M1/M2** (`ALERT_RULES_P1_V1.md` §1) y hora del primer fallo.

### 1.3 Abrir registro mínimo del incidente

Crear un documento o ticket con:

| Campo | Contenido |
|-------|-----------|
| ID / título | `INC-YYYYMMDD-…` + síntoma corto |
| Inicio (UTC) | Hora de primera alerta o primer fallo confirmado |
| Impacto | ¿Login imposible? ¿API 5xx global? ¿Solo VeriFactu? ¿Tenant(s)? |
| Comandador | Nombre |
| Estado | `OPEN` → `CONTAINED` → `RECOVERED` → `CLOSED` |

---

## 2) Contención (parar el daño o limitar el blast radius)

**Orden sugerido (elige lo aplicable; no todo a la vez):**

| Paso | Acción | Cuándo |
|------|--------|--------|
| C1 | **No** desplegar nuevos cambios hasta clasificar causa | Siempre en P1 |
| C2 | Si el incidente viene de un **deploy reciente** y hay riesgo claro → **rollback** al deployment anterior (Railway / Vercel) | Regresión obvia |
| C3 | Si hay **abuso o tráfico anómalo** → activar rate limit / WAF en el edge si existe; si no, considerar bloqueo de IP en proveedor | 429 masivos o patrón de ataque |
| C4 | Si hay **corrupción de datos o riesgo de escritura errónea** → poner API en modo solo lectura **solo** si existe procedimiento acordado; si no, escalar a decisión explícita antes de mutar tráfico | Riesgo de datos |
| C5 | VeriFactu / AEAT: **no** reintentos masivos; seguir `AEAT_VERIFACTU_HOMOLOGACION.md` y `ON_CALL_RUNBOOK.md` (reglas de seguridad) | Errores CERT/XADES/timeout |

**Referencias técnicas por área:** tabla *Decisión rápida por área* en `ON_CALL_RUNBOOK.md`.

---

## 3) Comunicación

### 3.1 Interna (obligatoria en P1)

En el canal on-call (Slack / etc.), publicar **un solo hilo** por incidente con:

```
[INC-…] P1 — <síntoma>
Inicio UTC: …
Impacto: …
Estado: investigando | contenido | recuperado
Próxima actualización: +30 min o antes si hay cambio
```

Actualizar el hilo al cerrar **contención** y al **recuperar**.

### 3.2 Externa (clientes / partners)

Solo si hay impacto contractual, fiscal o prolongado (&gt; 1 h) según tu criterio de negocio:

- Mensaje breve: reconocimiento, impacto cualitativo, sin culpar a terceros ni filtrar detalles técnicos internos.
- Enlazar estado interno al ticket; **no** pegar secretos ni datos personales (`ON_CALL_RUNBOOK.md` § *Reglas de seguridad*).

---

## 4) Recuperación

Seguir el runbook específico del subsistema una vez identificado el área (health, Redis, AEAT, backups, Stripe, etc.) — ver enlaces en `ON_CALL_RUNBOOK.md`.

**Criterio de “recuperado”:**

- `/live` y `/health/deep` en **200** con `status: "healthy"` durante al menos **dos** ciclos de monitor (o 10 min manuales).
- Sentry sin nuevo pico del mismo error en **15 min**.
- Función de negocio mínima verificada (p. ej. login de prueba en staging; en prod solo si hay usuario de prueba acordado).

---

## 5) RCA (post-incidente, dentro de 72 h hábiles recomendado)

Completar en el mismo ticket o anexo:

| Pregunta | Notas |
|----------|--------|
| ¿Qué falló exactamente? | Síntoma observable + componente |
| ¿Cuándo empezó y cuánto duró? | UTC, ventana de impacto |
| ¿Causa raíz o causa probable? | 5 porqués breve; si no hay certeza, listar hipótesis descartadas |
| ¿Qué funcionó bien? | Alertas, rollback, comunicación |
| ¿Qué cambia para que no se repita? | Ticket de seguimiento con owner y fecha |

**Evidencia a archivar (enlaces internos, sin secretos):** capturas de health, línea de tiempo Sentry, deploy ID, consultas SQL agregadas (counts), extracto de logs sin PII.

---

## 6) Checklist de cierre del incidente

- [ ] Estado final documentado (`CLOSED`) con hora UTC de fin.
- [ ] Severidad final y comparación con `SLO_MINIMAL_V1.md` (¿se violó SLO?).
- [ ] RCA enlazada o pegada (resumen).
- [ ] Acciones preventivas con owner (aunque sea “revisar alerta en 1 semana”).
- [ ] Reglas de alerta actualizadas si hubo falso positivo o gap (`ALERT_RULES_P1_V1.md`).

---

## Referencias

- `docs/operations/ON_CALL_RUNBOOK.md` — índice de guardia, severidades, primeros 15 min.
- `docs/operations/ALERT_RULES_P1_V1.md` — M1/M2, Sentry S1–S3, tabla `checks`.
- `docs/operations/SLO_MINIMAL_V1.md` — SLI/SLO.
- `docs/operations/MONITORING_OBSERVABILITY.md` — herramientas y simulacros.
- `docs/operations/health_recovery.md` — interpretación de estados de salud.
- `docs/operations/HANDOVER_PACKAGE.md` — transferencia a terceros si aplica.
