# DD-2026-04-006 — Dependency and Security Evidence Pack

**Ref. interna:** DD-2026-04-006  
**Empresa:** AB Logistics OS  
**Fecha de corte (UTC):** 2026-04-30  
**Versión:** 1.0  
**Clasificación:** Interno / Due Diligence

---

## 1) Objetivo y alcance

Consolidar la evidencia de seguridad de dependencias y supply-chain requerida por DD:

- auditoría de dependencias Python (`pip-audit`),
- auditoría de dependencias Node (`npm audit`, severidad critical),
- escaneo de imagen backend (`Trivy`),
- SBOM CycloneDX (`Syft`),
- y pentest externo (si aplica).

Fuente de control automatizado: `.github/workflows/deploy.yml` (job `security-scan`).

---

## 2) Evidencia recopilada

| Control | Fuente técnica | Artefacto de expediente | Estado |
|---|---|---|---|
| Dependency Audit (backend) | `deploy.yml` → `pip-audit -r backend/requirements.txt` | `DD-2026-04-006_deps-pip-audit_2026-04-30.*` | [ ] |
| Dependency Audit (frontend) | `deploy.yml` → `npm audit --audit-level=critical` | `DD-2026-04-006_deps-npm-audit_2026-04-30.*` | [ ] |
| Image Scan (backend) | `deploy.yml` → Trivy (`severity: CRITICAL,HIGH`) | `DD-2026-04-006_trivy_2026-04-30.*` | [ ] |
| SBOM | `deploy.yml` → `syft dir:. -o cyclonedx-json=sbom.cyclonedx.json` + artifact upload | `DD-2026-04-006_sbom_2026-04-30.json` | [ ] |
| Pentest externo (si aplica) | Proveedor externo | `DD-2026-04-006_pentest_2026-04-30.pdf` o nota N/A | [ ] |

---

## 3) Resultado ejecutivo

- Estado general de controles: **[PENDIENTE CONFIRMACIÓN FINAL]**
- Vulnerabilidades CRITICAL abiertas sin compensación: **[SI/NO]**
- Vulnerabilidades HIGH abiertas: **[SI/NO]**
- Si existen HIGH abiertas: plan de remediación con owner y fecha comprometida: **[ADJUNTO/NO APLICA]**

---

## 4) Matriz de hallazgos y remediación

| ID | Origen | Paquete / CVE | Severidad | Estado | Owner | ETA | Mitigación / Nota |
|---|---|---|---|---|---|---|---|
| R-001 | [pip-audit/npm/Trivy/pentest] | [completar] | [HIGH/CRITICAL] | [open/mitigated/accepted] | Adrián Balsa | [YYYY-MM-DD] | [completar] |

> Si no hay hallazgos relevantes en la fecha de corte, dejar una fila: `N/A — sin hallazgos CRITICAL abiertos`.

---

## 5) Declaración de cierre DD-2026-04-006

Declaro que la evidencia de seguridad y dependencias incluida en este paquete corresponde al corte indicado y es suficiente para sustentar el punto `DD-2026-04-006` en el expediente de Due Diligence, sin perjuicio del ciclo continuo de remediación de vulnerabilidades no críticas.

---

**Firma responsable:** ___________________________  
**Nombre:** Adrián Balsa Guerrero  
**Cargo:** Founder & CEO  
**Fecha de firma:** 2026-04-30

