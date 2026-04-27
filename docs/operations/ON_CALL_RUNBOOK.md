# ONCALL-001: guardia operativa

## Objetivo

Dar a la persona de guardia una ruta unica para clasificar, mitigar y cerrar incidentes en AB Logistics OS. Este runbook no sustituye los runbooks especificos; sirve como indice operativo y checklist de handoff. **Transferencia a equipo externo:** `docs/operations/HANDOVER_PACKAGE.md`.

## Sistemas cubiertos

- Frontend Vercel y API/worker Railway.
- Redis para ARQ, rate limiting y caches operativas.
- VeriFactu/AEAT, certificados mTLS y cola de reintentos.
- Backups S3 UE, restore smoke y disaster recovery.
- Stripe Billing, cuotas mensuales y webhooks de pago.

## Matriz de severidad

| Severidad | Senal | Tiempo de respuesta | Owner primario |
|-----------|-------|---------------------|----------------|
| P1 critica | Servicio caido, perdida/corrupcion de datos, bloqueo fiscal VeriFactu masivo, restore necesario | Inmediato / < 4h SLA | Incident commander + Platform/Data |
| P2 alta | Redis caido, worker parado, backup diario fallido, Stripe webhooks fallando, AEAT intermitente | < 12h | Platform/Ops |
| P3 normal | Degradacion parcial, cuota agotada aislada, rechazo AEAT funcional, alerta preventiva de certificado | < 48h | Area owner |
| P4 preventiva | Limpieza, documentacion, simulacro, mejora de alertas | Planificado | Owner del area |

## Primeros 15 minutos

1. Confirmar alcance: usuarios afectados, tenant, entorno, hora de inicio y sintoma observable.
2. Ejecutar checks basicos:

```bash
curl -fsS https://<API_HOST>/live
curl -fsS https://<API_HOST>/health
curl -fsS https://<API_HOST>/health/deep
```

3. Revisar ultimo deploy de Vercel/Railway y cambios recientes de variables/secrets.
4. Clasificar severidad y nombrar incident commander si es P1/P2.
5. Abrir registro de incidente con canal, hora, owner, sistemas afectados y decision inicial.

## Decision rapida por area

| Area | Senal principal | Runbook |
|------|-----------------|---------|
| Health general | `/health` o `/health/deep` no healthy | `docs/operations/health_recovery.md` + `MONITORING_OBSERVABILITY.md` |
| Redis/worker | `checks.redis.ok=false`, `queue_depth` sostenido, worker sin consumir | `docs/operations/REDIS_001_HA_BILLING_QUEUE.md` |
| AEAT/VeriFactu | `pendiente_envio` acumulado, errores `CERT`, `XADES`, `AEAT_TIMEOUT` | `docs/operations/AEAT_VERIFACTU_HOMOLOGACION.md` (evidencia homologación: `AEAT_HOMOLOGACION_EVIDENCE_TEMPLATE.md`) |
| Certificados mTLS | Caducidad < 30/15/7 dias o lectura fallida | `docs/operations/MTLS_CERTIFICATE_RENEWAL.md` |
| Backups | `Backup Daily` rojo o sin backup < 24h | `docs/operations/BACKUP_S3_POLICY.md` |
| Restore/DR | Corrupcion, perdida de datos o reprovisionamiento | `docs/operations/DISASTER_RECOVERY.md` |
| Billing | Webhooks Stripe fallidos, checkout roto, cuotas agotadas | `docs/operations/STRIPE_BILLING.md` |
| Coste proveedor | Alertas AWS/GCP/OpenAI 50/80/100 %, anomalía de factura, riesgo de corte | `docs/operations/BILLING_PROVIDER_BUDGETS.md` |
| Topologia | Dudas de plataforma, owners, variables, dominios | `docs/operations/OPS_001_TOPOLOGIA_PLATAFORMA.md` |

## Checklist de guardia diaria

- [ ] `GET /live`, `/health` y `/health/deep` revisados.
- [ ] Redis y cola ARQ sin acumulacion sostenida.
- [ ] Worker procesa jobs y no hay `retry_exhausted` nuevo sin owner.
- [ ] Facturas `pendiente_envio` AEAT dentro de ventana esperada.
- [ ] Certificados mTLS sin alerta de 30/15/7 dias sin ticket.
- [ ] Ultimo `Backup Daily` verde y backup S3 dentro de RPO 24h.
- [ ] Eventos fallidos Stripe revisados y suscripciones `past_due/unpaid` triadas.
- [ ] Alertas abiertas tienen owner, severidad y siguiente accion.

## Checklist semanal

- [ ] Restore smoke semanal revisado, con job summary de tiempos medidos archivado si aplica.
- [ ] Tendencias Redis: memoria, clientes, bloqueos, conexiones rechazadas.
- [ ] Quotas `maps_calls_month`, `ocr_pages_month`, `ai_tokens_month` revisadas para tenants > 80%.
- [ ] Rechazos AEAT funcionales asignados a correccion de datos.
- [ ] Dashboard Stripe comparado contra empresas activas y planes internos.
- [ ] Handoff de owners actualizado en `OPS_001`.

## Handoff y cierre

Cada incidente debe cerrar con:

- Severidad final, ventana de impacto y tenant/clientes afectados.
- Causa raiz o causa probable si no hay certeza.
- Acciones ejecutadas y comandos/endpoints usados.
- Evidencia: healthchecks, workflow run, evento Stripe, fila `verifactu_envios`, backup key o logs relevantes.
- Riesgo residual y acciones preventivas con owner y fecha.
- Decision de comunicacion a cliente si aplica por SLA o impacto fiscal/comercial.

## Reglas de seguridad

- No copiar secretos, certificados, payloads fiscales completos ni datos personales en tickets o chats.
- No purgar colas ni editar cuotas/planes manualmente sin dejar evidencia administrativa.
- No restaurar base de datos sobre produccion sin aprobacion explicita del incident commander.
- No reintentar masivamente VeriFactu si la causa es XML, firma o certificado.
