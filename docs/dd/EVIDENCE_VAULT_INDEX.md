# Índice de evidencias DD (data room / actas firmadas)

**Uso:** registrar **solo referencias** a documentos que viven **fuera del repositorio** (PDF firmado, capturas SSL Labs, exports CI, actas de restore). No pegues enlaces con tokens ni secretos.

**Ejecución paso a paso:** `docs/dd/RUNBOOK_3_4_DATA_ROOM_ARCHIVE.md`

**Instrucciones:** al archivar cada archivo en Drive / SharePoint / data room, completar aquí **Ubicación** y **Fecha archivo**. La columna **Ref. interna** ya está reservada para citar en email al comité (no cambiar el código salvo conflicto con otro expediente).

**Índice rellenado (2026-04-30):** la columna **Ubicación** usa el prefijo lógico `Data room / DD-2026-04-evidence /` más el nombre de archivo canónico. Sustituye `Data room` por la ruta o URL interna real de tu expediente (sin tokens ni secretos) cuando subas los PDF definitivos.

| Documento | Ubicación (carpeta o URL interna) | Ref. interna | Fecha archivo | Notas |
|-----------|-----------------------------------|--------------|---------------|--------|
| Acta decisión GO / GO con reservas (PDF firmado) | Data room / DD-2026-04-evidence / DD-2026-04-001_acta-GO_2026-04-30.pdf | `DD-2026-04-001` | 2026-04-30 | Plantilla: `PHASE3_3_3_GO_COMMITTEE_PACKAGE.md` §C |
| TLS producción — **API** (SSL Labs + salida `collect_tls_evidence.sh`) | Data room / DD-2026-04-evidence / DD-2026-04-002_tls-api-prod_2026-04-30.pdf | `DD-2026-04-002` | 2026-04-30 | Host API público; criterios: `PHASE3_3_1_EXTERNAL_EVIDENCE.md` §1 |
| TLS producción — **APP** (SSL Labs + salida `collect_tls_evidence.sh`) | Data room / DD-2026-04-evidence / DD-2026-04-003_tls-app-prod_2026-04-30.pdf | `DD-2026-04-003` | 2026-04-30 | Excepción controlada: SSL Labs devolvió `Assessment failed` / `Unexpected failure` en múltiples intentos (host `app.ablogistics-os.com` y raíz). Se adjunta evidencia local válida (`collect_tls_evidence.sh`: cert + vigencia + HSTS) y capturas del fallo del escáner externo. Reintento SSL Labs comprometido en 24-48h y actualización de expediente. |
| Acta backup/restore firmada + enlace run smoke (o restore ensayo) | Data room / DD-2026-04-evidence / DD-2026-04-004_backup-restore-acta_2026-04-30.pdf | `DD-2026-04-004` | 2026-04-30 | Plantilla: `PHASE3_3_1_EXTERNAL_EVIDENCE.md` §2; workflow `backup_restore_smoke.yml` |
| Informe DR (RTO/RPO medidos) | Data room / DD-2026-04-evidence / DD-2026-04-005_dr-informe-rto-rpo_2026-04-30.pdf | `DD-2026-04-005` | 2026-04-30 | Plantilla: `PHASE3_3_1_EXTERNAL_EVIDENCE.md` §3; `DISASTER_RECOVERY.md` |
| Export dependencias / Trivy / SBOM / pentest (si aplica) | Data room / DD-2026-04-evidence / DD-2026-04-006_deps-trivy-sbom_2026-04-30.pdf | `DD-2026-04-006` | 2026-04-30 | Paquete listo para firma: `docs/dd/DD-2026-04-006_SECURITY_EVIDENCE_PACK.md` (fuentes: `deploy.yml` + pentest si aplica). Al archivar, adjuntar evidencia de `pip-audit`, `npm audit`, Trivy y SBOM. |

## Convención sugerida para nombres en data room

`DD-2026-04-00N_<tema>_<YYYY-MM-DD>.pdf` (o `.md` si solo texto), alineado con **Ref. interna** de la tabla.

## Nota de excepción (DD-2026-04-003)

Se registra excepción documental temporal para TLS de APP por indisponibilidad del escáner externo SSL Labs en la fecha de corte (`Assessment failed: Unexpected failure` / `Failed to communicate with the secure server`). No se observan indicadores de fallo TLS en la verificación local: certificado válido para `app.ablogistics-os.com`, cadena emitida por Let's Encrypt y cabecera HSTS activa. El expediente incluye: (1) salida local del script de captura TLS, (2) capturas de fallo SSL Labs, y (3) compromiso de reintento en 24-48h para anexar rating externo cuando el servicio estabilice.

## Borrador local en el clon

La carpeta `docs/dd/local-evidence/` está preparada en el repo: el contenido **excepto** `.gitkeep` está ignorado (ver `.gitignore` en la raíz). Podéis guardar ahí borradores; el índice debe apuntar al **archivo definitivo** en data room cuando exista.
