# Informe Gap de Cumplimiento AEAT  
## Redondeo Monetario y Precision Decimal (Backend)

Fecha: 2026-04-28  
Ambito auditado: `backend/app/` + stress test temporal `scripts/check_math_precision.py`

## 1) Objetivo de la revision

Verificar si la gestion de precision decimal y redondeo monetario en facturacion cumple el criterio operativo solicitado para AEAT:

- uso de `Decimal` en calculo monetario (evitar deriva binaria de `float`),
- redondeo exacto a 2 decimales con `ROUND_HALF_UP`,
- invariante de coherencia de IVA para evitar el "centimo huerfano".

## 2) Evidencia ejecutada

Se ejecuto:

- `python3 scripts/check_math_precision.py`

Resultado observado:

- Caso A: `100 x 0.10` => `10.00` (OK con Decimal)
- Caso B: `19.99` con `-15%` y `+21% IVA` => `20.56` (OK con `ROUND_HALF_UP`)
- Caso C (float deliberado): aparecieron artefactos IEEE (`9.99999999999998`, `20.559714999999997`)
- Veredicto del script: `FAIL` (correcto segun criterio de control anti-float)

Conclusión tecnica de evidencia:

- con `Decimal` el calculo monetario se comporta correctamente,
- con `float` pueden aparecer residuos binarios no aceptables para evidencia fiscal.

## 3) Hallazgos de codigo (estado actual)

### 3.1 Hallazgo principal (Gap)

El motor financiero central (`backend/app/core/math_engine.py`) usa:

- `Decimal` de forma consistente para calculo monetario, pero
- redondeo `ROUND_HALF_EVEN` (redondeo bancario), no `ROUND_HALF_UP`.

Impacto:

- Si la politica de cumplimiento objetivo exige explicita y unicamente `ROUND_HALF_UP`, existe gap de implementacion.

### 3.2 Invariante de coherencia (fortaleza existente)

El motor incluye una invariante de cierre contable:

- `total = base + IVA + RE - IRPF`,
- validacion de integridad (`RoundingIntegrityError`) si se rompe la coherencia.

Tambien hay acumulacion por lineas y por buckets de IVA, lo que reduce riesgo de descuadre silencioso.

### 3.3 Uso de `float` fuera del nucleo fiscal

Se detectan conversiones a `float` en servicios y salidas de API/reporting (ej. `facturas_service`, `admin_service`), mayoritariamente para serializacion o metricas.

Riesgo:

- bajo/medio si esas rutas no recalculan importes fiscales persistidos,
- medio/alto si algun flujo reutiliza esos `float` para recalculo posterior.

## 4) Matriz de Gap AEAT (criterio solicitado)

1. Uso de decimal exacto en nucleo de facturacion  
   - Estado: **Cumple parcialmente**
   - Motivo: usa `Decimal`, pero convive con conversiones `float` en capas perifericas.

2. Redondeo oficial requerido `ROUND_HALF_UP` a 2 decimales  
   - Estado: **No cumple**
   - Motivo: estandar actual centralizado en `ROUND_HALF_EVEN`.

3. Invariante anti "centimo huerfano" (IVA lineas vs total)  
   - Estado: **Cumple**
   - Motivo: existe cierre contable explicito e integridad de redondeo en `MathEngine`.

## 5) Plan de cambios minimos (propuesto)

Objetivo: migrar a `ROUND_HALF_UP` con minimo impacto funcional y maximo control.

### Cambio minimo 1 (nucleo)

En `backend/app/core/math_engine.py`:

- sustituir `ROUND_HALF_EVEN` por `ROUND_HALF_UP` en:
  - contexto `_MATH_CTX`,
  - `quantize_currency`,
  - helpers que cuantizan importes monetarios (`round_fiat`, `quantize_financial`, etc.).

Nota: limitar el cambio a cuantizacion monetaria (EUR) y no mezclar automaticamente con cuantizacion de otras magnitudes no fiscales salvo decision explicita.

### Cambio minimo 2 (alineacion documental y contratos)

Actualizar docstrings y comentarios que hoy declaran `ROUND_HALF_EVEN` para evitar ambiguedad de auditoria.

### Cambio minimo 3 (blindaje anti regresion)

Actualizar tests monetarios para nuevo criterio HALF_UP y anadir pruebas frontera:

- `0.005 -> 0.01`
- `1.005 -> 1.01`
- escenarios de descuento global + IVA por lineas + agregados.

### Cambio minimo 4 (contencion de float en perimetro fiscal)

En puntos de serializacion de facturacion:

- mantener persistencia y recalc en `Decimal`,
- relegar `float` solo a salida JSON final,
- evitar reentrada de `float` como fuente para recomputo fiscal.

## 6) Riesgo de cambio y mitigacion

Riesgo principal:

- variacion de centimos en casos frontera historicos al pasar de HALF_EVEN a HALF_UP.

Mitigaciones:

- ejecutar suite de pruebas de `math_engine` y facturacion,
- comparar snapshot de facturas de muestra (antes/despues) en entorno controlado,
- desplegar con feature flag de redondeo (opcional) si se requiere transicion gradual.

## 7) Criterio de aceptacion para cerrar gap

Se considera gap cerrado cuando se cumpla simultaneamente:

1. `math_engine` cuantiza importes monetarios con `ROUND_HALF_UP`.
2. Todos los tests fiscales relevantes pasan con el nuevo criterio.
3. `scripts/check_math_precision.py` termina en `PASS` para los casos Decimal y mantiene deteccion de artefactos float como control negativo.
4. Documentacion tecnica refleja explicitamente la politica de redondeo vigente.

## 8) Veredicto ejecutivo

Estado actual:

- **Arquitectura de precision**: solida (nucleo en `Decimal` + invariantes de cierre)
- **Cumplimiento estricto del criterio AEAT solicitado (`ROUND_HALF_UP`)**: **pendiente**

Con los cambios minimos descritos, el sistema puede alinearse rapidamente al criterio solicitado sin reescritura amplia del dominio de facturacion.
