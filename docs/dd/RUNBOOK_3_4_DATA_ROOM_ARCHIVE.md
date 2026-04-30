# Runbook — §3.4 Archivo comité y data room

**Objetivo:** dejar **fuera del git** los PDFs/capturas y enlaces internos al comité, y **rellenar** `docs/dd/EVIDENCE_VAULT_INDEX.md` (ubicación + fecha; las refs. internas ya están reservadas en esa tabla).

**Reglas:** no pegar tokens, URLs con query secrets, ni credenciales. Enlaces a GitHub Actions: usar run ID público del repo sin PAT.

---

## 0) Antes de empezar

1. Elegir **carpeta data room** (Drive, SharePoint, Notion export, etc.) y convención de nombres (ej. `DD-2026-04-002_tls_api_2026-04-29.pdf`).
2. Opcional: guardar **borradores** en el clon bajo `docs/dd/local-evidence/` (ignorado por git salvo `.gitkeep`).
3. Abrir `docs/dd/EVIDENCE_VAULT_INDEX.md` en otra ventana para completar columnas **Ubicación** y **Fecha archivo** al cerrar cada ítem.

---

## 1) TLS — API y APP de producción

Para **cada** hostname público (API y frontend/app), en este orden:

### 1.1 SSL Labs

1. Abrir el analizador: `https://www.ssllabs.com/ssltest/analyze.html?d=<HOST>&latest`
2. Esperar resultado estable; objetivo **A o superior**.
3. Archivar en data room: PDF o captura + anotar URL del resultado (sin datos sensibles).

### 1.2 Salida local `collect_tls_evidence.sh`

Desde la raíz del repo: sustituir **`<HOST>`** por el FQDN real (p. ej. `api.tuempresa.com`). No uses el literal de los tutoriales `TU_HOST` — no resuelve en DNS.

```bash
./scripts/collect_tls_evidence.sh "api.tuempresa.com" | tee "docs/dd/local-evidence/tls-api-tuempresa-$(date -u +%Y%m%d).md"
```

Subir el `.md` o PDF generado al data room junto al informe SSL Labs del mismo host.

### 1.3 Índice

En `EVIDENCE_VAULT_INDEX.md`, fila **TLS producción — API** o **APP**: rellenar **Ubicación** y **Fecha archivo**; la columna **Ref. interna** ya es `DD-2026-04-002` o `DD-2026-04-003`.

---

## 2) Backup / restore — acta + run

1. Ejecutar o recuperar una corrida de `.github/workflows/backup_restore_smoke.yml` (URL del run en GitHub Actions).
2. Completar la plantilla en `docs/dd/PHASE3_3_1_EXTERNAL_EVIDENCE.md` §2 (acta); obtener firmas según gobierno interno.
3. Archivar PDF/acta + enlace al run en data room.
4. Rellenar fila **Acta backup/restore** (`DD-2026-04-004`) en el índice.

---

## 3) DR — informe RTO/RPO

1. Usar plantilla corta en `PHASE3_3_1_EXTERNAL_EVIDENCE.md` §3 y umbrales en `docs/operations/DISASTER_RECOVERY.md`.
2. Archivar informe firmado o acta de simulacro en data room.
3. Rellenar fila **Informe DR** (`DD-2026-04-005`).

---

## 4) Dependencias / Trivy / pentest

1. Último **deploy** CI: pasos `pip-audit`, `npm audit`, Trivy, SBOM en `.github/workflows/deploy.yml` — descargar logs o artefactos si el workflow los publica; si no, ejecutar localmente en entorno limpio y adjuntar salida (sin secretos).
2. Actualizar tabla de remediación en `PHASE3_3_1_EXTERNAL_EVIDENCE.md` §4 si hay CVEs abiertas.
3. Si hay **pentest externo**, PDF bajo NDA solo en data room; en el índice usar ref. `DD-2026-04-006` y nota "bajo NDA".
4. Rellenar fila **Export dependencias / Trivy / pentest** en el índice.

---

## 5) Acta GO — circulación y PDF

1. Completar `docs/dd/PHASE3_3_3_GO_COMMITTEE_PACKAGE.md` §C (reunión, opción GO / reservas / NO-GO, anexos, firmas).
2. Exportar a PDF (herramienta interna); circular para firma; **no** commitear el PDF firmado.
3. Archivar PDF definitivo en data room.
4. Rellenar fila **Acta decisión GO** (`DD-2026-04-001`) en el índice.

---

## 6) Cierre checklist DD

Cuando las filas del índice tengan **Ubicación** y **Fecha archivo** completas:

1. Marcar `[x]` los dos ítems de `DD_REMEDIATION_CHECKLIST.md` §3.4.
2. Ajustar dashboard §0 (estado global y % fase 3) si procede.
3. Añadir línea en §5 log del checklist con fecha y refs. usadas.

---

## Referencias

| Documento | Uso |
|-----------|-----|
| `docs/dd/EVIDENCE_VAULT_INDEX.md` | Tabla maestra de refs. |
| `docs/dd/PHASE3_3_1_EXTERNAL_EVIDENCE.md` | Plantillas §3.1 |
| `docs/dd/PHASE3_3_3_GO_COMMITTEE_PACKAGE.md` | Plantilla decisión §C |
