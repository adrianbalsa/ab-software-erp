# Fase 3.1 — Evidencias externas requeridas (DD)

**Objetivo:** reunir criterios, procedimientos y plantillas para el comité de inversión / auditoría, enlazando con automatización y runbooks ya presentes en el repositorio.

**Nota operativa:** las capturas firmadas por terceros (SSL Labs, acta de restore en prod, informe de pentest) se archivan **fuera del git** (drive interno, data room). Este documento define *qué* debe existir y *dónde* está la fuente técnica en el repo.

---

## 1) Resultado SSL/TLS externo (nota alta)

| Elemento | Fuente en repo | Acción |
|------------|----------------|--------|
| Criterios de despliegue TLS, DNS, CORS | `docs/operations/DEPLOY_FINAL_TLS_CHECKLIST.md` | Ejecutar checklist en **producción** antes del cierre. |
| Configuración referencia (TLS 1.2/1.3, HSTS, ciphers) | `infrastructure/nginx/default.conf` | Revisar que el edge desplegado coincide con esta referencia o equivalente (Railway/Vercel). |
| Captura local reproducible | `scripts/collect_tls_evidence.sh <hostname>` | Adjuntar salida en el expediente junto al informe SSL Labs. |

**Evidencia externa obligatoria:** informe **SSL Labs** (o equivalente acordado con el comité) para `api.*` y `app.*` de producción, con **rating objetivo A o superior**. Si hay degradación documentada, incluir plan de remediación y fecha.

---

## 2) Backup / restore — informe y acta firmable

| Elemento | Fuente en repo |
|------------|----------------|
| Runbook de restauración | `docs/operations/DISASTER_RECOVERY.md` |
| Política bucket S3 | `docs/operations/BACKUP_S3_POLICY.md` |
| Validación automática bucket | `scripts/validate_backup_s3_bucket.sh` |
| Smoke semanal / manual | `.github/workflows/backup_restore_smoke.yml` |

**Evidencia requerida:** una ejecución **documentada** (idealmente el *job summary* del workflow de smoke o un restore real en entorno de ensayo) más **acta firmada** según plantilla siguiente.

### Plantilla — Acta de prueba backup/restore

```text
ACTA — Prueba backup / restore AB Logistics OS
Fecha ejecución (UTC): 
Ejecutor técnico: 
Responsable firmante (dirección / seguridad): 

Origen backup:
  - URI S3 (sin credenciales): 
  - Región: 
  - Timestamp lógico del backup (RPO medido): 

Entorno destino: [ smoke CI | staging | otro: ___ ]

Fases medidas (segundos, del job o cronómetro):
  - RESTORE_DOWNLOAD_SECONDS: 
  - RESTORE_EXTRACT_SECONDS: 
  - RESTORE_APPLY_SECONDS: 
  - RESTORE_INTEGRITY_SECONDS: 

Resultado integridad: [ OK | KO ]   Detalle: 

RPO comprobado (hora incidente simulado − hora backup): 
Observaciones y desviaciones respecto a DISASTER_RECOVERY.md:

Firma ejecutor: ______________   Firma responsable: ______________
```

---

## 3) DR — informe con RTO/RPO reales

El marco de métricas y la plantilla de registro están en `docs/operations/DISASTER_RECOVERY.md` (sección *Tiempos medidos y evidencia*).

**Evidencia requerida:** al menos **un simulacro documentado** (anual o el periodo que exija el comité) con:

| Métrica | Valor medido | Umbral de referencia |
|---------|--------------|----------------------|
| RPO real | | ≤ 24 h salvo excepción aprobada |
| RTO real (procedimiento → servicio mínimo) | | ≤ 24 h para restore DB desde S3 (referencia interna) |
| Tiempo técnico restore (suma fases) | | Comparar con último smoke |

### Plantilla — Informe corto DR

```text
INFORME DR — AB Logistics OS
Fecha simulacro (UTC): 
Escenario: [ pérdida DB | región caída | otro: ___ ]

RPO real:        minutos
RTO real:        minutos
Tiempo técnico restore:   minutos
Tiempo validación funcional (login / factura crítica):   minutos

Bloqueos encontrados: 
Lecciones aprendidas: 

Aprobación comité / dirección: ______________   Fecha: 
```

---

## 4) Pentest / dependencias — informe actualizado y plan de remediación

| Control | Dónde está |
|---------|------------|
| **pip-audit** (backend) | `.github/workflows/deploy.yml` — paso *Dependency Audit (backend - pip-audit)* |
| **npm audit** (frontend, nivel critical) | mismo workflow — *Dependency Audit (frontend - npm audit)* |
| **Trivy** imagen backend (HIGH/CRITICAL, `exit-code: 0` informativo) | mismo workflow — *Security Scan (Trivy image)* |
| **SBOM** CycloneDX | mismo workflow — *Generate SBOM (Syft)* |

**Pentest externo:** si el comité exige informe de terceros, adjuntar PDF bajo NDA y enlazar **solo** el código de seguimiento interno (sin datos sensibles) en el data room.

### Plan de remediación — tabla viva (copiar a issue tracker)

| ID | Origen | Paquete / CVE | Severidad | Estado | Dueño | ETA | Notas |
|----|--------|---------------|-----------|--------|-------|-----|-------|
| R-001 | pip-audit / npm audit / Trivy / pentest | | | abierto | | | |

**Criterio de cierre §3.1:** tabla sin filas **abiertas** de severidad **CRITICAL** sin compensación documentada; HIGH con plan y fecha.

---

## 5) Checklist de archivo para el comité

**Orden operativo y data room:** `docs/dd/RUNBOOK_3_4_DATA_ROOM_ARCHIVE.md` (§3.4 DD). Índice de refs.: `docs/dd/EVIDENCE_VAULT_INDEX.md`.

- [ ] PDF o enlace SSL Labs + salida de `scripts/collect_tls_evidence.sh` para **API** y **APP** prod (`DD-2026-04-002`, `DD-2026-04-003`).
- [ ] Acta backup/restore firmada + enlace al run de `backup_restore_smoke` (o acta de restore real) (`DD-2026-04-004`).
- [ ] Informe DR con RTO/RPO rellenados (`DD-2026-04-005`).
- [ ] Export más reciente de `pip-audit` / `npm audit` (o log del job deploy) + tabla de remediación actualizada (`DD-2026-04-006`).

---

## 6) Referencias cruzadas

- Runbook archivo §3.4: `docs/dd/RUNBOOK_3_4_DATA_ROOM_ARCHIVE.md`
- Paquete handover: `docs/operations/HANDOVER_PACKAGE.md`
- Postura seguridad: `docs/legal/COMPLIANCE_AND_SECURITY_POSTURE.md`
- Rotación secretos (fase 3.2 relacionada): `docs/security/SECRET_ROTATION_POLICY.md`
