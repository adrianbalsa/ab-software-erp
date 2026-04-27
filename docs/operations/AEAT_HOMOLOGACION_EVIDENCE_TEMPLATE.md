# Plantilla de evidencia — homologación VeriFactu / AEAT (Fase 3.1)

**Uso:** duplicar este fichero fuera del repositorio público (data room, ITSM, carpeta M&A) y completar los campos tras un envío real al **entorno de pruebas** AEAT. No pegar XML completo, NIF de terceros ni certificados.

| Campo | Valor |
|--------|--------|
| Fecha UTC del envío | |
| Entorno | Homologación (`AEAT_VERIFACTU_USE_PRODUCTION=false`) |
| Responsable | |
| `factura_id` (UUID) | |
| `empresa_id` emisor (UUID, opcional) | |
| Estado final `facturas.aeat_sif_estado` | |
| Código / descripción AEAT (`aeat_sif_codigo` / `aeat_sif_descripcion`) | |
| CSV AEAT (si aplica) | |
| Hash huella cadena (últimos 16 hex, opcional) | |

## Trazabilidad técnica (referencias, no datos sensibles)

- **Fila(s) `public.verifactu_envios`:** IDs o `created_at` del último intento aceptado (export SQL agregado sin `request_body` completo si contiene PII).
- **HTTP / SOAP:** `http_status`, `soap_action` (desde `verifactu_envios` o logs redactados).
- **Resultado:** copiar solo fragmento de respuesta AEAT necesario para auditoría (códigos, estado), no body SOAP íntegro.

## Consulta SQL sugerida (ejecutar en entorno controlado)

```sql
select id, factura_id, estado, codigo_error, descripcion_error,
       csv_aeat, http_status, soap_action, created_at
from public.verifactu_envios
where factura_id = '<UUID_FACTURA>'
order by created_at desc
limit 5;
```

## Criterio de aceptación (homologación)

- Estado `Aceptado` o `Aceptado con Errores` según criterios de la prueba acordada con AEAT; o rechazo **documentado** si la prueba era negativa controlada.
- Sin errores no recuperables (`XSD_REQUEST`, `CERT`, `XADES`, etc.) no explicados en el acta.

## Firma / archivo

| Rol | Nombre | Fecha |
|-----|--------|-------|
| Ejecutor técnico | | |
| Revisión fiscal (si aplica) | | |

---

*Referencia de procedimiento: `docs/operations/AEAT_VERIFACTU_HOMOLOGACION.md`.*
