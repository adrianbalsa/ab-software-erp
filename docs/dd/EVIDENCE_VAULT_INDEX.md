# Índice de evidencias DD (data room / actas firmadas)

**Uso:** registrar referencias a documentos del expediente (PDF firmado, capturas SSL Labs, exports CI, actas de restore). Parte del data room puede vivir **dentro del clon** bajo `Data room DD 2026-04/`; si compartes URL pública, nunca incluyas tokens ni secretos.

**Ejecución paso a paso:** `docs/dd/RUNBOOK_3_4_DATA_ROOM_ARCHIVE.md`

**Instrucciones:** al archivar cada archivo en Drive / SharePoint / data room, completar aquí **Ubicación** y **Fecha archivo**. La columna **Ref. interna** ya está reservada para citar en email al comité (no cambiar el código salvo conflicto con otro expediente).

**Índice rellenado (2026-04-30):** la columna **Ubicación** indica la ruta **en el clon `Scanner`** (relativa a la raíz del repo). Para copias en Drive/SharePoint, conserva el mismo nombre de archivo o anota el alias en **Notas**.

| Documento | Ubicación (carpeta o URL interna) | Ref. interna | Fecha archivo | Notas |
|-----------|-----------------------------------|--------------|---------------|--------|
| Acta decisión GO / GO con reservas (PDF firmado) | `Data room DD 2026-04/Acta de decisión GO.pdf` (alias canónico sugerido: `DD-2026-04-001_acta-GO_2026-04-30.pdf`) | `DD-2026-04-001` | 2026-04-30 | Plantilla: `PHASE3_3_3_GO_COMMITTEE_PACKAGE.md` §C |
| Cierre expediente DD (memoria de cierre) | `Data room DD 2026-04/Cierre Due Diligence DD-2026-04.pdf` | — | 2026-04-30 | Referencia cruzada `DD-2026-04-001` … `006`. |
| TLS producción — **API** (SSL Labs + capturas) | `Data room DD 2026-04/DD-2026-04-002_tls-api-ssllabs_2026-04-30.png_pdf.png`, `Data room DD 2026-04/Certificado A+ API SSL.png` | `DD-2026-04-002` | 2026-04-30 | Criterios: `PHASE3_3_1_EXTERNAL_EVIDENCE.md` §1 |
| TLS producción — **APP** (evidencia local + hardening) | `Data room DD 2026-04/Datos app ssl.png`, `Data room DD 2026-04/Hardenize_prueba_app1.png`, `Data room DD 2026-04/Hardenize_prueba_app2.png`, `Data room DD 2026-04/M1-Live.png` | `DD-2026-04-003` | 2026-04-30 | Excección SSL Labs en APP (nota § abajo). Opcional: consolidar en un PDF `DD-2026-04-003_tls-app-prod_2026-04-30.pdf`. |
| Acta backup/restore (restore ensayo manual) | `Data room DD 2026-04/DD-2026-04-004_backup-restore-acta_2026-04-30.pdf` | `DD-2026-04-004` | 2026-04-30 | Corte 2026-04-30: total restore técnico ~90 min; RPO ≤24 h; RTO observado 8 h en acta. CI: `backup_restore_smoke.yml`. |
| Informe DR (RTO/RPO medidos) | `Data room DD 2026-04/DD-2026-04-005_dr-informe-rto-rpo_2026-04-30.pdf` | `DD-2026-04-005` | 2026-04-30 | Simulacro 2026-04-30: RPO/RTO objetivo ≤24 h cumplidos; restore técnico ~95 min. `DISASTER_RECOVERY.md`. |
| Export dependencias / Trivy / SBOM / pentest (si aplica) | `Data room DD 2026-04/DD-2026-04-006_deps-trivy-sbom_2026-04-30.pdf` | `DD-2026-04-006` | 2026-04-30 | `docs/dd/DD-2026-04-006_SECURITY_EVIDENCE_PACK.md`; pipeline `.github/workflows/deploy.yml` job `security-scan`. Pentest externo: N/A en corte (según PDF firmado). |

## Convención sugerida para nombres en data room

`DD-2026-04-00N_<tema>_<YYYY-MM-DD>.pdf` (o `.md` si solo texto), alineado con **Ref. interna** de la tabla.

## Nota de excepción (DD-2026-04-003)

Se registra excepción documental temporal para TLS de APP por indisponibilidad del escáner externo SSL Labs en la fecha de corte (`Assessment failed: Unexpected failure` / `Failed to communicate with the secure server`). No se observan indicadores de fallo TLS en la verificación local: certificado válido para `app.ablogistics-os.com`, cadena emitida por Let's Encrypt y cabecera HSTS activa. El expediente incluye: (1) salida local del script de captura TLS, (2) capturas de fallo SSL Labs, y (3) compromiso de reintento en 24-48h para anexar rating externo cuando el servicio estabilice.

## Borrador local en el clon

La carpeta `docs/dd/local-evidence/` está preparada en el repo: el contenido **excepto** `.gitkeep` está ignorado (ver `.gitignore` en la raíz). Podéis guardar ahí borradores; el índice debe apuntar al **archivo definitivo** en data room cuando exista.

## Data room versionada en el repo (`Scanner`)

La carpeta **`Data room DD 2026-04/`** en la raíz del monorepo contiene los PDF y capturas alineados con la tabla anterior. **Ojo:** puede incluir artefactos sensibles de producción; valora `.gitignore` o un bucket privado si no debe publicarse en remoto.
