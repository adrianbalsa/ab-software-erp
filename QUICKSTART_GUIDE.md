# AB Logistics OS — Guía de inicio rápido (Quickstart)

**Audiencia:** Dirección, finanzas y responsables operativos.  
**Objetivo:** Traducir las capacidades del producto en **decisiones con retorno medible**: menos riesgo fiscal y reputacional, más margen por kilómetro, menor TCO de flota y negociación con cargadores basada en datos.

---

## Bienvenido al Búnker

El **Búnker** es el **centro de mando unificado** de su empresa logística: operación, cumplimiento normativo, analítica de rutas y escenarios económicos en un solo entorno. Aquí obtiene **control total** sobre lo que factura, lo que cuesta servir cada ruta y el estado del activo rodante, sin depender de hojas dispersas ni de “sensaciones” de taller.

| Valor ejecutivo | Qué aporta a su P&L y su riesgo |
|-----------------|----------------------------------|
| **Visibilidad** | Un cuadro de mando alimentado por el mismo motor de cálculo que usa la operación diaria |
| **Cumplimiento** | Trazabilidad VeriFactu y estados AEAT visibles antes del cierre |
| **Rentabilidad** | Priorización de rutas por margen neto frente a huella de CO₂ y volumen |
| **Anticipación** | Alertas de flota y simulación de costes **antes** de firmar revisiones tarifarias |

> **Tip de ahorro:** Reserve **10 minutos semanales** al cuadro de mando y a la matriz CIP. En transporte, dejar de servir rutas de bajo margen sin datos suele liberar **2–3 puntos de margen** equivalentes sin tocar estructura fija.

**Llamada a la acción:** Complete el onboarding, emita su primera factura con trazabilidad y abra **Analítica** para etiquetar sus cinco rutas críticas del mes.

---

## Pilar 1 — Blindaje fiscal (VeriFactu)

**ROI:** Reduce multas, reprocesos contables, horas de consultoría en inspección y el coste reputacional de incoherencias entre factura y AEAT.

### Cómo emitir facturas alineadas con la AEAT

1. **Origen limpio:** Genere la factura desde la operación (portes) con datos maestros consistentes (NIF, series, bases e impuestos).  
2. **Registro VeriFactu:** Finalice el circuito de registro cuando el proceso lo indique (huella, cadena, remisión cuando aplique).  
3. **Control previo al cierre:** Revise el **badge VeriFactu** en el listado de facturas; no cierre el mes con incidencias sin plan de rectificación.

### Estados del badge (referencia rápida)

El badge refleja el resultado de la remisión o el estado operativo respecto a la AEAT:

| Badge en pantalla | Significado | Acción recomendada |
|-------------------|-------------|---------------------|
| **Pendiente AEAT** | Sin resultado definitivo o en cola | Seguimiento; reintento según política interna |
| **Aceptada** | Envío aceptado por la AEAT | Archivar, conciliar y seguir con tesorería |
| **Con Errores** | Aceptación con incidencias registradas | Revisar tooltip/detalle; corregir maestro o rectificar según procedimiento |
| **Rechazada** | Validación no superada (`rechazado` o `error_tecnico`) | Corregir datos de emisión; valorar **factura rectificativa** o nuevo envío según normativa aplicable |

> **Tip de ahorro:** Revisar badges **el mismo día del cierre fiscal** evita arrastrar incidencias al asiento y reduce picos de horas externas en cierre trimestral.

**Llamada a la acción:** Asigne un único responsable de “cierre fiscal + badge” y documente el SLA de revisión (p. ej. 24 h tras emisión).

---

## Pilar 2 — Optimización de rutas (Matriz CIP)

**ROI:** Reasigna capacidad y precio hacia rutas que aportan margen y ESG defendible; corta sangrías donde el coste energético y operativo no se recupera.

### Cómo interpretar el gráfico de burbujas

La **Matriz CIP** es un diagrama de dispersión donde cada punto es una **ruta**:

| Elemento visual | Qué mide |
|-----------------|----------|
| **Eje horizontal** | Margen neto de la ruta (más a la derecha = más rentable) |
| **Eje vertical** | Emisiones de CO₂ asociadas (más arriba = mayor huella) |
| **Tamaño de la burbuja** | Volumen: número de portes (más grande = más peso en su operación) |
| **Líneas de referencia** | Promedios de margen y CO₂: dividen el gráfico en cuadrantes |

### Cuadrantes y colores (lectura rápida)

| Zona (respecto a los promedios) | Perfil | Decisión típica |
|---------------------------------|--------|------------------|
| **Margen alto · CO₂ bajo** (verde en el gráfico) | **Ruta Estrella** | Proteger capacidad, tarifa y servicio; candidata a volumen adicional |
| **Margen alto · CO₂ alto** (ámbar) | Rentable pero intensiva | Optimizar vehículo/carga, rutas o acuerdos “verdes” con clientes sensibles a huella |
| **Margen bajo · CO₂ bajo** (azul) | Eficiente en huella, débil en euros | Subir tarifa o revisar coste oculto (tiempos de carga, esperas) |
| **Margen bajo · CO₂ alto** (rosa / rojo) | **Ruta Vampiro** | Renegociar precio, cambiar modal o **dejar de servir** salvo acuerdo expreso que cubra coste total |

**Definiciones operativas:**

- **Ruta Estrella:** Por encima del margen medio y por debajo del CO₂ medio (ideal: alto retorno por unidad de huella).  
- **Ruta Vampiro:** Por debajo del margen medio y por encima del CO₂ medio: **drena margen** y encarece el cumplimiento ESG.

> **Tip de ahorro:** Fije un **margen mínimo por ruta** validado con el simulador de escenarios; comunicarlo a comercial evita “premios” a clientes que destruyen EBITDA.

**Llamada a la acción:** Etiquete mensualmente el top 5 Estrella y el top 5 Vampiro y lleve el listado a la reunión comercial.

---

## Pilar 3 — Salud del activo (Flota)

**ROI:** Pasa del mantenimiento reactivo a **coste planificado**: menos inmovilizaciones, menos multas y menos combustible “fantasma”.

### Alertas de mantenimiento

En el **cuadro de mando** y en **Flota → Mantenimiento** verá alertas por tipo:

| Origen típico | Qué vigila | Impacto si se ignora |
|---------------|------------|----------------------|
| **ITV / caducidades** | Ventanas legales | Multas, parada administrativa, coste de urgencia |
| **Seguro** | Continuidad de cobertura | Riesgo legal y operativo |
| **Revisión por km** | Planes preventivos | Averías caras, pérdida de cliente por incumplimiento |

Las alertas del listado rápido del dashboard usan **prioridad** (alta / media / baja) según proximidad y criticidad. En mantenimiento por km verá además urgencias tipo **CRÍTICO** o **ADVERTENCIA** en la barra de desgaste: resuelva en advertencia para pagar **casi la mitad** que en emergencia (grúa, sustitución exprés, cliente perdido).

### Consumo medio

En **Flota → Combustible** (u otras vistas de eficiencia disponibles) use el **consumo por vehículo** como termómetro: desvíos persistentes suelen indicar formación, neumáticos, rutas mal asignadas o anomalías que conviene auditar **antes** de la avería.

> **Tip de ahorro:** Una revisión preventiva programada en ventana “advertencia” suele costar **40–60 % menos** que la misma intervención en modo urgencia, sin contar el coste de oportunidad del vehículo parado.

**Llamada a la acción:** Calendario fijo semanal de 15 minutos: dashboard de alertas + un vehículo “en observación” por consumo.

---

## Pilar 4 — Simulador de escenarios

**ROI:** Convierte subidas de combustible, salarios o peajes en **cifras de EBITDA y tarifa**, no en discusiones a viva voz. Negocia con el cargador mostrando el **punto de ruptura** que el propio sistema calcula.

### Uso de los sliders

Ruta en la app: **Finanzas → Simulador de impacto económico** (perfil dirección). Cada slider mueve un **porcentaje de variación** sobre esa partida de coste:

| Slider | Rango orientativo | Uso en negociación con cargadores |
|--------|-------------------|-----------------------------------|
| **Combustible** | Variación % del coste energético | Trasladar repuntos a tarifa o cláusula de revisión indexada |
| **Salarios** | Variación % del coste laboral | Justificar revisión anual o complementos en rutas de largo recorrido |
| **Peajes** | Variación % del coste de peaje | Ajustar precio en corredores autopista sensibles |

Tras cada ajuste (con recálculo automático o **Recalcular ahora**), interprete:

| Salida en pantalla | Cómo usarla |
|--------------------|-------------|
| **Impacto estimado en beneficio (€/mes)** | Orden de magnitud del golpe al resultado mensual |
| **Impacto EBITDA (€ y %)** | Efecto en la ventana de meses que muestra el motor |
| **Punto de ruptura tarifario** | **Incremento de tarifa (%)** necesario para mantener el margen: llévelo tal cual a la mesa |

> **Tip de ahorro:** Presente **dos escenarios** (base y conservador) con el mismo pantallazo; acelera el cierre contractual y evita regalar margen “por prudencia” sin números.

**Llamada a la acción:** Antes de cada renovación anual con un cargador top, genere un PDF o captura del simulador con los supuestos acordados internamente.

---

## Próximos pasos (checklist ejecutivo)

| # | Acción | Resultado esperado |
|---|--------|--------------------|
| 1 | Roles y onboarding completos | Menos errores maestros y trazabilidad por usuario |
| 2 | Primera factura VeriFactu + revisión de badge | Cierre fiscal sin sorpresas AEAT |
| 3 | Sesión de 20 min. en Matriz CIP | Lista priorizada Estrella / Vampiro |
| 4 | Ritmo semanal de alertas de flota | Caída de incidentes evitables |
| 5 | Simulador antes de firmar condiciones | Negociación con **break-even tarifario** explícito |

---

*Documento orientado a valor de negocio. Las pantallas y rutas pueden evolucionar; alinee esta guía con su despliegue y con `QUICKSTART_GUIDE.md` en el repositorio del proyecto.*
