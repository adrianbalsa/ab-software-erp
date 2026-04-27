# AEAT-001: homologacion VeriFactu

Objetivo: validar compatibilidad real del flujo VeriFactu con el entorno de homologacion AEAT. La prueba se considera cerrada solo cuando un XML valido se envia con certificado cliente, se recibe respuesta AEAT y queda trazabilidad de errores o reintentos.

## Estado actual

- El payload `RegFactuSistemaFacturacion` se genera desde `backend/app/services/verifactu_sender.py` y `backend/app/services/suministro_lr_xml.py`.
- El nodo `RegistroAlta` se firma con XAdES-BES antes del envio.
- La peticion se valida contra `backend/app/services/aeat_client_py/xsd/SuministroLR.xsd` cuando `AEAT_VERIFACTU_XSD_VALIDATE_REQUEST=true`.
- El envio usa SOAP 1.2, Zeep, WSDL oficial y mTLS.
- Los intentos se persisten en `public.verifactu_envios`; el resumen operativo de factura queda en `facturas.aeat_sif_*`.

Verificacion local ejecutada:

```bash
cd backend
pytest tests/test_verifactu_sender_xml.py tests/unit/test_aeat_parser.py
```

Resultado: `10 passed`. Esta verificacion cubre XML compatible con XSD local, parseo de respuestas, rechazo, SOAP/AEAT tipado y clasificacion de transporte. No sustituye la llamada real de homologacion.

## Prerrequisitos para homologacion

Configurar en el entorno donde corre el backend:

```bash
AEAT_VERIFACTU_ENABLED=true
AEAT_VERIFACTU_USE_PRODUCTION=false
AEAT_BLOQUEAR_PROD_EN_DESARROLLO=true
AEAT_VERIFACTU_SUBMIT_URL_TEST=<endpoint homologacion AEAT>
AEAT_VERIFACTU_XSD_VALIDATE_REQUEST=true
AEAT_CLIENT_P12_PATH=<ruta segura al certificado .p12>
AEAT_CLIENT_P12_PASSWORD=<password en secret manager o entorno seguro>
```

Alternativa PEM:

```bash
AEAT_CLIENT_CERT_PATH=<ruta segura al certificado PEM>
AEAT_CLIENT_KEY_PATH=<ruta segura a la clave PEM>
AEAT_CLIENT_KEY_PASSWORD=<si aplica>
```

No guardar certificados ni passwords en el repo. En produccion, priorizar `SecretManagerService`/backend de secretos y rutas montadas con permisos restringidos.

La caducidad del certificado mTLS queda monitorizada en `GET /health/deep` bajo `checks.aeat_mtls_certificates`, con umbrales 30/15/7 dias. Runbook de renovacion: `docs/operations/MTLS_CERTIFICATE_RENEWAL.md`.

## Checks operativos

### Diario

- Confirmar `GET /health/deep` y revisar `checks.aeat_mtls_certificates` si VeriFactu esta activo.
- Revisar facturas con `aeat_sif_estado=pendiente_envio` y antiguedad superior a la ventana normal de reintento.
- Revisar errores recientes `AEAT_TIMEOUT`, `AEAT_CONNECTION`, `REINTENTO_AGOTADO`, `XSD_REQUEST`, `CERT`, `CERT_READ` y `XADES`.
- Validar que no hay uso accidental de endpoint productivo fuera de produccion (`AEAT_BLOQUEAR_PROD_EN_DESARROLLO=true`).

Consulta sugerida para guardia:

```sql
select
  aeat_sif_estado,
  aeat_sif_codigo,
  count(*) as total,
  min(aeat_sif_actualizado_en) as oldest_update,
  max(aeat_sif_actualizado_en) as newest_update
from public.facturas
where is_finalized = true
  and aeat_sif_estado is not null
group by aeat_sif_estado, aeat_sif_codigo
order by total desc;
```

### Semanal

- Ejecutar un envio controlado en homologacion o revisar evidencia del ultimo envio real.
- Confirmar que XSD local y WSDL/endpoint configurado siguen alineados con la documentacion AEAT vigente.
- Revisar certificados mTLS con horizonte de 30 dias y registrar owner de renovacion.
- Revisar que los rechazos funcionales estan asignados a correccion de datos y no quedan en reintento ciego.

### Mensual

- Archivar evidencia de trazabilidad: XML/request hash si aplica, respuesta AEAT, fila `verifactu_envios` y auditoria.
- Ejecutar prueba negativa controlada en staging para confirmar clasificacion de errores no recuperables.
- Revisar que `retry-pending` mantiene limite, ventana temporal y permisos esperados.

## Ejecucion de la prueba

1. Crear o localizar una factura finalizada (`is_finalized=true`) con `fingerprint` y datos fiscales completos.
2. Confirmar que la factura pertenece al emisor del certificado AEAT.
3. Ejecutar el envio por el flujo existente:

```python
from app.services.verifactu_sender import enviar_factura_aeat

result = await enviar_factura_aeat("<factura_id>")
print({
    "factura_id": result.get("id"),
    "estado": result.get("aeat_sif_estado"),
    "csv": result.get("aeat_sif_csv"),
    "codigo": result.get("aeat_sif_codigo"),
    "descripcion": result.get("aeat_sif_descripcion"),
})
```

Tambien puede dispararse desde el flujo de finalizacion de factura cuando `AEAT_VERIFACTU_ENABLED=true`.

## Evidencia esperada

Consultar la tabla de trazabilidad:

```sql
select
  factura_id,
  estado,
  codigo_error,
  descripcion_error,
  csv_aeat,
  http_status,
  soap_action,
  created_at
from public.verifactu_envios
where factura_id = :factura_id
order by created_at desc;
```

Criterios de aceptacion:

- `estado` en `Aceptado` o `Aceptado con Errores`, o rechazo AEAT documentado si la prueba buscaba validar una casuistica negativa.
- `http_status` informado cuando hay respuesta HTTP.
- `response_snippet` persistido para inspeccion, sin exponerlo en logs publicos.
- `facturas.aeat_sif_estado`, `aeat_sif_codigo`, `aeat_sif_descripcion` y `aeat_sif_actualizado_en` actualizados.

## Errores y reintentos

El sender reintenta automaticamente hasta `AEAT_HTTP_MAX_ATTEMPTS=6` con backoff exponencial ante:

- HTTP `429`, `500`, `502`, `503`, `504`.
- Errores de transporte `AEAT_TRANSPORT`.

No reintenta validaciones locales no recuperables:

- `XSD_REQUEST`: XML no compatible con XSD antes del envio.
- `SOAP_MALFORMED`: SOAP no bien formado.
- `CERT` / `CERT_READ`: certificado ausente o ilegible.
- `XADES`: error de firma o composicion del registro firmado.

Clasificacion persistida:

- `pendiente_envio` con `AEAT_TIMEOUT`, `AEAT_CONNECTION` o `REINTENTO_AGOTADO`: queda listo para reintento operativo.
- `rechazado`: AEAT respondio con rechazo funcional; requiere correccion de datos, no reintento ciego.
- `aceptado_con_errores`: registrar advertencias y revisar si exige accion fiscal.

Reintento operativo:

```http
POST /api/v1/verifactu/retry-pending
```

El endpoint procesa facturas del tenant con `aeat_sif_estado = pendiente_envio`, creadas en las ultimas 48 horas, con limite de 50 y ejecucion secuencial.

## Runbook de incidente AEAT

1. Clasificar el fallo: certificado, XML/firma, conectividad AEAT, rechazo funcional o acumulacion de cola.
2. Si falla certificado (`CERT`, `CERT_READ` o alerta de caducidad), pausar reintentos manuales y seguir `docs/operations/MTLS_CERTIFICATE_RENEWAL.md`.
3. Si falla XML/firma (`XSD_REQUEST`, `SOAP_MALFORMED`, `XADES`), abrir incidencia de backend; no ejecutar reintento masivo hasta corregir la causa.
4. Si falla transporte o AEAT responde `429/5xx`, esperar al backoff automatico y revisar `verifactu_envios`; solo usar `retry-pending` cuando la dependencia vuelva a estar estable.
5. Si hay rechazo funcional, asignar correccion fiscal/datos al owner de negocio y conservar evidencia de respuesta.
6. Cerrar el incidente con: rango horario, facturas afectadas, estados finales, CSV si existe, acciones tomadas y decision sobre comunicacion a clientes.

## Preparacion Fase 3.1 (repo)

Antes del envío real a la AEAT:

1. Variables y certificados: ejecutar desde `backend/` (requiere `.env` con al menos la misma carga que la API):

```bash
cd backend
PYTHONPATH=. python scripts/check_aeat_homologacion_readiness.py
# Opcional: tratar XSD desactivado como fallo
PYTHONPATH=. python scripts/check_aeat_homologacion_readiness.py --strict
```

2. Evidencia post-envío: copiar `docs/operations/AEAT_HOMOLOGACION_EVIDENCE_TEMPLATE.md` a almacenamiento **interno** y completarlo (sin PII/XML completos en git público).

3. Tests de regresión XML/parser (no sustituyen la llamada AEAT):

```bash
cd backend
pytest tests/test_verifactu_sender_xml.py tests/unit/test_aeat_parser.py -q
```

## Resultado de esta sesion

El **envío SOAP real** a homologación AEAT depende de certificados y endpoints que no viven en el repositorio; debe ejecutarlo el operador con credenciales de pruebas. La compatibilidad local XML/parser/reintentos queda cubierta por tests; la comprobación de prerequisitos por `check_aeat_homologacion_readiness.py` y el archivo de evidencia cierran la **preparación documental** de la Fase 3.1 hasta obtener respuesta `Aceptado` en entorno AEAT.
