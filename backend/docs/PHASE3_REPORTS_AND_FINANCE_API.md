# Fase 3 — Informes PDF y API financiera

## ReportService (`app/services/report_service.py`)

- **Factura inmutable**: `GET /reports/facturas/{factura_id}/pdf`  
  - Líneas **solo** desde `porte_lineas_snapshot` (nunca tabla `portes` en vivo).  
  - Muestra `hash_registro`, QR con URL `VERIFACTU_VALIDATION_BASE_URL/verificar?factura_id=…&hash_registro=…`.

- **Certificado huella CO₂**: `GET /reports/esg/certificado-huella?periodo=YYYY-MM`  
  - Datos de `EcoService.emisiones_combustible_por_mes`; referencia Euro 6: `ESG_CO2_KG_PER_L_EURO6_REF` (defecto 2,64 kg CO₂/L).

## Finanzas

- `GET /finance/dashboard` → `FinanceDashboardOut` (snake_case):  
  `ingresos`, `gastos`, `ebitda`, `total_km_estimados_snapshot`, `margen_km_eur`, `ingresos_vs_gastos_mensual`.

- `GET /finance/summary` sigue existiendo; **ingresos** = suma de bases en **facturas** (reconocimiento por facturación).

## Eco

- `GET /eco/emisiones-mensuales` — serie para gráficos y certificados por mes.

## Dependencias

`reportlab`, `qrcode[pil]`, `Pillow`, `fpdf2` (ver `requirements.txt`).
