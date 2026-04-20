# Blueprint Arquitectura: AB Logistics OS Mobile App (Driver Portal)

## 1. Visión General y Objetivo
Aplicación móvil nativa diseñada exclusivamente para los conductores (Role: `TRANSPORTISTA`). Su objetivo principal es cerrar el ciclo de vida del dato en tiempo real, habilitando la Prueba de Entrega (POD), la subida de tickets de gasto (OCR) y la geolocalización.

## 2. Stack Tecnológico Seleccionado
* **Framework:** React Native con Expo (Permite un solo código base para iOS/Android y actualizaciones Over-The-Air).
* **Estado y Caché:** TanStack Query (React Query) para sincronización con FastAPI.
* **Autenticación:** JWT vía Supabase Auth (Integrado con el backend actual).
* **Offline-First:** AsyncStorage / SQLite para guardar firmas y fotos cuando no hay cobertura, sincronizando en background al recuperar red.

## 3. Integración con Backend Existente (API Ready)
Rutas y política de estabilidad: `docs/PLATFORM_CONTRACTS.md` (prefijo **`/api/v1/`** para integraciones nuevas).

La app móvil NO requiere nuevos servicios backend, consumirá los ya auditados:
* `GET /api/v1/portes/mis-rutas`: Listado de portes asignados al JWT actual.
* `POST /api/v1/portes/{id}/pod`: Subida de firma digital (Base64/SVG) y foto del albarán sellado.
* `POST /api/v1/gastos/ocr`: Conexión directa con `ocr_service.py` para tickets de combustible.

## 4. Roadmap de Ejecución (MVP - 4 Semanas)
* **Semana 1:** Setup Expo + Auth + Ruteo Offline.
* **Semana 2:** UI de listado de Portes y navegación a origen/destino.
* **Semana 3:** Módulo de Cámara (React Native Vision Camera) y Firma (React Native Signature Canvas).
* **Semana 4:** Sincronización Background y Testeo E2E.