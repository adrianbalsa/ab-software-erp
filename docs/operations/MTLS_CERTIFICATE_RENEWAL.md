# CERT-001: renovacion de certificados mTLS

Objetivo: evitar interrupciones en integraciones con TLS mutua, especialmente AEAT VeriFactu, por certificados expirados o no renovados a tiempo.

## Monitorizacion

El backend expone la caducidad de certificados mTLS en:

```http
GET /health/deep
```

Check esperado:

```json
{
  "checks": {
    "aeat_mtls_certificates": {
      "ok": true,
      "alert_thresholds_days": [30, 15, 7],
      "certificates_scanned": 1
    }
  }
}
```

El check pasa a `ok=false` cuando un certificado entra en ventana de alerta:

- `warning`: quedan 30 dias o menos.
- `high`: quedan 15 dias o menos.
- `critical`: quedan 7 dias o menos.
- `expired`: certificado caducado.
- `missing` / `read_error`: ruta ausente, fichero no montado o certificado no legible.

Configurar el monitor externo (Railway, Better Stack, UptimeRobot, Grafana, etc.) para consultar `/health/deep` y alertar si el estado HTTP no es 200 o si `checks.aeat_mtls_certificates.ok=false`.

Ademas, si se define `MTLS_CERT_EXPIRY_ALERT_WEBHOOK_URL` (o, como fallback, `ALERT_WEBHOOK_URL` / `DISCORD_WEBHOOK_URL`), el backend envia una alerta best-effort al detectar el umbral. Las alertas estan limitadas por proceso a una por certificado/nivel cada 12 horas.

## Variables

Configuracion global:

```bash
AEAT_CLIENT_P12_PATH=/run/secrets/aeat/client.p12
AEAT_CLIENT_P12_PASSWORD=<secret>
```

Alternativa PEM:

```bash
AEAT_CLIENT_CERT_PATH=/run/secrets/aeat/client.pem
AEAT_CLIENT_KEY_PATH=/run/secrets/aeat/client.key
AEAT_CLIENT_KEY_PASSWORD=<secret-si-aplica>
```

Alerta dedicada opcional:

```bash
MTLS_CERT_EXPIRY_ALERT_WEBHOOK_URL=https://hooks.example.com/mtls-cert-expiry
```

No guardar certificados, claves privadas ni passwords en el repositorio. Montar ficheros como secretos del proveedor de despliegue y usar permisos `0400` o equivalentes.

## Operacion por entorno

### Desarrollo local

- Mantener `AEAT_VERIFACTU_ENABLED=false` salvo pruebas controladas. En este modo `/health/deep` marca `aeat_mtls_certificates.skipped=true` si no hay certificado configurado.
- Para validar el check sin enviar a AEAT, montar un certificado de prueba en una ruta local fuera del repo y definir `AEAT_CLIENT_P12_PATH` o `AEAT_CLIENT_CERT_PATH` + `AEAT_CLIENT_KEY_PATH`.
- No usar certificados reales de produccion en portatiles. Si se necesita reproducir una incidencia, usar un `.p12` de homologacion con password rotada despues de la prueba.

### Homologacion / staging

- Definir `AEAT_VERIFACTU_ENABLED=true` solo cuando exista URL de pruebas y certificado mTLS de homologacion montado.
- Usar rutas estables de secreto, por ejemplo `/run/secrets/aeat/client.p12`, y verificar despues de cada deploy:

```bash
curl -fsS https://staging-api.example.com/health/deep | jq '.status, .checks.aeat_mtls_certificates'
```

- El endpoint debe devolver HTTP 200 y `status=healthy` para permitir envios. Si devuelve HTTP 503 por `warning`, `high` o `critical`, renovar antes de promover a produccion aunque el certificado aun no haya expirado.
- Ejecutar al menos un envio de homologacion tras rotar certificado o cambiar `AEAT_VERIFACTU_SUBMIT_URL_TEST`.

### Produccion

- `AEAT_VERIFACTU_ENABLED=true` exige certificado mTLS montado y legible. Si el certificado falta, es ilegible o esta caducado, `/health/deep` devuelve HTTP 503 y los envios AEAT se bloquean antes de intentar SOAP con un error claro (`CERT`, `CERT_READ` o `CERT_EXPIRED`).
- Los monitores externos deben alertar por cualquiera de estas condiciones:
  - HTTP distinto de 200 en `/health/deep`.
  - `status!="healthy"`.
  - `checks.aeat_mtls_certificates.ok=false`.
- Renovar con al menos 30 dias de margen. La ventana `warning/high/critical` degrada readiness para forzar intervencion operativa antes de la caducidad.
- Tras renovar, redeplegar/reiniciar backend y workers para refrescar montajes de secretos y temporales PEM derivados de `.p12`.

### Multi-tenant / certificados por empresa

- Si una empresa define `aeat_client_p12_path`, tiene prioridad sobre las rutas globales. Si no, se usa `aeat_client_cert_path` + `aeat_client_key_path` y finalmente el fallback global.
- Revisar que las rutas de tabla `empresas` apunten a ficheros existentes en todos los pods/instancias que puedan ejecutar envios AEAT.
- `/health/deep` escanea hasta 500 empresas con certificado configurado y muestra como maximo 25 entradas para no exponer ruido operativo.

## Runbook de renovacion

1. Solicitar o emitir el nuevo certificado cliente con el mismo NIF/razon social que usa el emisor fiscal.
2. Validar localmente la fecha de caducidad antes de subirlo:

```bash
openssl x509 -in client.pem -noout -subject -issuer -enddate
```

Para `.p12`:

```bash
openssl pkcs12 -in client.p12 -nokeys -clcerts | openssl x509 -noout -subject -issuer -enddate
```

3. Subir el nuevo `.p12` o par PEM al gestor de secretos/volumen seguro del entorno.
4. Actualizar `AEAT_CLIENT_P12_PATH` o `AEAT_CLIENT_CERT_PATH` / `AEAT_CLIENT_KEY_PATH` si cambia la ruta montada. Rotar tambien `AEAT_CLIENT_P12_PASSWORD` o `AEAT_CLIENT_KEY_PASSWORD` si cambia.
5. Reiniciar el backend o redeplegar para garantizar que todos los workers ven el nuevo montaje.
6. Ejecutar:

```bash
curl -fsS https://api.example.com/health/deep | jq '.checks.aeat_mtls_certificates'
```

7. Confirmar que `ok=true`, `days_remaining > 30` y el `subject_cn`/emisor corresponden al certificado esperado.
8. Hacer un envio de homologacion o una prueba controlada VeriFactu si la renovacion afecta a AEAT.
9. Registrar la evidencia: fecha de renovacion, `expires_at`, operador, entorno y resultado del health check.

## Rollback

Si el nuevo certificado falla en lectura o handshake:

1. Restaurar el secreto/volumen anterior si aun no ha caducado.
2. Reiniciar/redeplegar backend.
3. Verificar `/health/deep`.
4. Revisar errores `CERT`, `CERT_READ` o transporte AEAT en `verifactu_envios`.

No borrar el certificado anterior hasta que el nuevo haya pasado health check y prueba de envio.
