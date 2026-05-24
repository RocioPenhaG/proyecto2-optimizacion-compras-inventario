# TC03 - Módulo predictivo y análisis de tendencias

Conjunto de casos de prueba del **Release 3** orientados al modelado predictivo de consumo, la persistencia de resultados de tendencia, las proyecciones futuras, los reportes comparativos, la visualización gráfica y la integración con el ecosistema analítico existente. Cada ítem principal (TC03.1 a TC03.7) incluye su propia tabla de actividades, descripción, objetivo, precondiciones, pasos y resultado esperado.

---

## TC03.1 — Implementación del algoritmo de regresión lineal sobre datos históricos

### Descripción

El sistema construye, por cada producto con historial suficiente, una serie temporal diaria de consumo (movimientos OUT agregados desde `HechoConsumo`) y aplica **regresión lineal simple (OLS)** con eje temporal discreto (x = 0, 1, …, n−1). El algoritmo se ejecuta dentro del ETL analítico al finalizar la materialización de hechos, sin recalcular regresiones en tiempo de consulta del dashboard.

### Tabla de casos de prueba

| Item | Descripción | Entradas | Sistema/Módulo | Resultado Esperado |
|------|-------------|----------|----------------|-------------------|
| TC03.1.1 | Verificar que el ETL agrupa consumo OUT por producto y fecha antes de invocar la regresión. | Movimientos OUT en inventario para al menos 3 fechas distintas y un producto de prueba; ejecución de corrida analítica. | Backend — `guardar_resultados_tendencia_lineal` (`etl.py`). | La serie utilizada contiene un valor por día con consumo; el número de puntos coincide con `puntos_usados` en el resultado persistido. |
| TC03.1.2 | Validar que productos con menos de 3 días de consumo en la ventana **no** generan registro de tendencia. | Producto A con ≥ 3 días OUT; producto B con 1 o 2 días OUT en el mismo rango. | Backend — ETL analítico; umbral `minimo_puntos=3`. | Solo el producto A aparece en `ResultadoTendenciaLineal`; el producto B queda fuera del listado de tendencias de la corrida. |
| TC03.1.3 | Comprobar que la regresión calcula métricas de ajuste (R², MAE, RMSE) además de coeficientes, cuando la serie es válida. | Corrida exitosa con producto de serie no constante (variación en consumo diario). | Backend — `_calcular_regresion_lineal`; modelo `ResultadoTendenciaLineal`. | Los campos `r2`, `mae` y `rmse` se almacenan (o quedan nulos solo si la serie es degenerada); no se interrumpe la corrida por error de cálculo. |

### Objetivo

Confirmar que el algoritmo de regresión lineal se aplica correctamente sobre datos históricos de consumo diario, respetando umbrales mínimos de puntos y produciendo resultados persistibles por corrida y producto.

### Precondiciones

- `HechoConsumo` poblado con salidas OUT en el rango de fechas de la corrida de prueba.
- Corrida analítica configurada con ventana de tendencia (p. ej. 30 días).
- Acceso al backend (shell, admin o logs) o a la API de tendencias para verificar resultados.

### Pasos

1. Registrar el consumo diario esperado de un producto de prueba en `HechoConsumo` para el rango de la corrida.
2. Ejecutar la corrida analítica (comando `run_etl_analitico` o tarea programada) y esperar estado exitoso.
3. Consultar `ResultadoTendenciaLineal` para el producto y validar `puntos_usados`, fechas de inicio/fin y existencia de métricas del modelo.
4. Repetir la verificación con un producto de menos de 3 días y confirmar ausencia de registro.

### Resultado esperado

La regresión lineal se ejecuta solo sobre series elegibles (≥ 3 puntos), persiste resultados trazables por corrida y no afecta productos sin historial suficiente.

---

## TC03.2 — Cálculo de pendiente e intercepto del modelo

### Descripción

A partir de la regresión OLS, el sistema calcula la **pendiente** (variación diaria estimada del consumo) y el **intercepto** (valor base del modelo en x = 0), y deriva la **predicción del período siguiente** como `intercepto + pendiente × n`, donde n es la cantidad de puntos de la serie. Estos valores alimentan tablas, APIs y reglas de reposición orientativa.

### Tabla de casos de prueba

| Item | Descripción | Entradas | Sistema/Módulo | Resultado Esperado |
|------|-------------|----------|----------------|-------------------|
| TC03.2.1 | Validar coherencia entre consumo histórico, pendiente e intercepto en un escenario de tendencia creciente conocida. | Serie diaria monótona creciente (p. ej. 2, 4, 6, 8 unidades); corrida que la procese. | Backend — `_calcular_regresion_lineal`; tests unitarios o consulta ORM. | `pendiente` > 0; `prediccion_siguiente` mayor que el último consumo observado si la tendencia es estrictamente creciente. |
| TC03.2.2 | Verificar persistencia de `pendiente` e `intercepto` en `ResultadoTendenciaLineal` y exposición vía API. | `corrida_id` y `producto_id` de prueba; token de usuario con permiso analytics. | API — `GET /api/analytics/etl/corridas/{corrida_id}/tendencias/`. | La respuesta JSON incluye `pendiente` y `prediccion_siguiente` como enteros; los valores coinciden con los almacenados en base de datos (redondeo aplicado en API). |
| TC03.2.3 | Comprobar interpretación de pendiente negativa o nula en la columna de variación diaria del dashboard. | Tendencia con pendiente ≤ 0 en producto de prueba. | Frontend — `AnalyticsCorridasSection` (columna variación / interpretación). | Se muestra variación diaria formateada (p. ej. `+0` o valor negativo) e interpretación textual acorde (estable o decreciente). |

### Objetivo

Asegurar que pendiente, intercepto y predicción inmediata se calculan con fórmulas consistentes, se persisten correctamente y se presentan de forma comprensible al usuario.

### Precondiciones

- TC03.1 cumplido: existe al menos un `ResultadoTendenciaLineal` válido para la corrida de prueba.
- Usuario autenticado para consulta API o acceso al dashboard de corridas ETL.

### Pasos

1. Obtener de base de datos `pendiente`, `intercepto`, `puntos_usados` y `prediccion_siguiente` de un producto de prueba.
2. Recalcular manualmente `prediccion_siguiente = intercepto + pendiente × n` y comparar con el valor persistido (tolerancia por redondeo decimal).
3. Invocar la API de tendencias por corrida y contrastar campos expuestos con la base de datos.
4. En el dashboard, localizar el mismo producto y verificar variación diaria e interpretación en pantalla.

### Resultado esperado

Los coeficientes del modelo y la predicción del día siguiente son numéricamente coherentes entre ETL, persistencia, API y capa de visualización.

---

## TC03.3 — Creación de tablas de resultados del modelo predictivo

### Descripción

Los resultados del modelado se materializan en tablas analíticas dedicadas: **`ResultadoTendenciaLineal`** (coeficientes, métricas, rango de fechas y vínculo a corrida/producto) y **`ProyeccionConsumoFuturo`** (proyección diaria por horizonte). Estas estructuras permiten auditoría, consulta administrativa y exposición vía APIs REST.

### Tabla de casos de prueba

| Item | Descripción | Entradas | Sistema/Módulo | Resultado Esperado |
|------|-------------|----------|----------------|-------------------|
| TC03.3.1 | Verificar creación masiva de filas en `ResultadoTendenciaLineal` al cerrar una corrida con múltiples productos elegibles. | Corrida con N productos que superan el mínimo de puntos; conteo previo de candidatos. | Backend — ETL; modelo `ResultadoTendenciaLineal`; campo `productos_candidatos_tendencia` en corrida. | El número de resultados guardados ≤ candidatos; cada fila referencia `corrida_id` y `producto_id` válidos; `periodicidad` = DAILY. |
| TC03.3.2 | Validar consulta del listado de tendencias por corrida con columnas operativas (stock, reposición sugerida, rango de fechas). | `corrida_id` de prueba; productos con registro de stock. | API — `tendencias_por_corrida`; vista tabla en `AnalyticsCorridasSection`. | La tabla muestra producto, stock actual/mínimo, días analizados, variación, predicción siguiente, sugerido y rango `fecha_inicio`–`fecha_fin`. |
| TC03.3.3 | Comprobar visibilidad y trazabilidad en Django Admin de tendencias y proyecciones asociadas a una corrida. | Usuario staff; corrida con tendencias y proyecciones generadas. | Django Admin — `ResultadoTendenciaLineal`, `ProyeccionConsumoFuturo`. | Los registros son listables y filtrables por corrida/producto; la eliminación en cascada o por retención no afecta `HechoConsumo` operativo. |

### Objetivo

Demostrar que las tablas de resultados del modelo predictivo se crean, consultan y administran correctamente, manteniendo trazabilidad por corrida analítica.

### Precondiciones

- Corrida analítica finalizada con éxito y parámetro de horizonte de proyección definido.
- Permisos de lectura en API analytics y, opcionalmente, acceso a Django Admin.

### Pasos

1. Tras la corrida, contar registros en `ResultadoTendenciaLineal` filtrados por `corrida_id`.
2. Consumir `GET /api/analytics/etl/corridas/{corrida_id}/tendencias/` y validar estructura y cantidad de `results`.
3. Abrir el dashboard, seleccionar la corrida y revisar la tabla **Detalle de tendencias lineales**.
4. En Admin, buscar la misma corrida y confirmar consistencia de IDs y productos.

### Resultado esperado

Las tablas de resultados reflejan fielmente el output del ETL predictivo y son consultables desde API, interfaz y herramientas de administración.

---

## TC03.4 — Generación de proyecciones de consumo futuro

### Descripción

Extendiendo pendiente e intercepto, el módulo proyecta consumo **hacia adelante** por un horizonte de días configurable (`proyeccion_horizonte_dias`, por defecto 30). Cada día futuro obtiene un `valor_diario` (truncado a cero si el modelo es negativo) y un `consumo_acumulado` progresivo, persistido en `ProyeccionConsumoFuturo` o calculado bajo demanda para resúmenes.

### Tabla de casos de prueba

| Item | Descripción | Entradas | Sistema/Módulo | Resultado Esperado |
|------|-------------|----------|----------------|-------------------|
| TC03.4.1 | Verificar persistencia de proyecciones diarias tras el ETL para cada tendencia de la corrida. | Corrida con `proyeccion_horizonte_dias = H` (p. ej. 30); al menos una tendencia válida. | Backend — `guardar_proyecciones_consumo_futuro` (`etl.py`). | Existen H filas por tendencia (o el total documentado en retorno del ETL); `horizonte_dias` va de 1 a H; fechas posteriores a `fecha_fin`. |
| TC03.4.2 | Validar truncamiento a cero de proyecciones negativas (consumo no puede ser negativo). | Tendencia con pendiente muy negativa o intercepto bajo en datos de prueba. | Backend — `generar_proyecciones_consumo`. | Todos los `valor_diario` persistidos o calculados son ≥ 0. |
| TC03.4.3 | Comprobar generación de resumen de proyecciones por períodos calendario (semana, mes, etc.) cuando hay datos suficientes. | Lista de proyecciones diarias; `fecha_fin` de la tendencia; ≥ 7 puntos históricos si aplica confiabilidad. | Backend — `resumen_proyecciones_completo` (`proyecciones.py`). | El resumen incluye agregados por ventanas definidas; no falla con lista vacía (retorna estructura vacía o mensaje coherente). |

### Objetivo

Validar que las proyecciones de consumo futuro se generan con horizonte configurable, reglas de negocio (no negativos) y capacidad de agregación para reportes.

### Precondiciones

- Resultados de tendencia lineal existentes para la corrida de prueba (TC03.1–TC03.3).
- Parámetro `proyeccion_horizonte_dias` conocido y registrado en `CorridaAnalitica.parametros` si aplica.

### Pasos

1. Ejecutar o revisar corrida con guardado de proyecciones habilitado.
2. Consultar `ProyeccionConsumoFuturo` para un `tendencia_id` y verificar cantidad de filas y secuencia de `horizonte_dias`.
3. Identificar una tendencia con proyección teórica negativa y confirmar valor almacenado = 0.
4. Invocar función o endpoint que serialice resumen de proyecciones y validar totales acumulados.

### Resultado esperado

Las proyecciones futuras se almacenan de forma consistente, respetan restricciones de dominio (≥ 0) y soportan resúmenes para análisis de períodos.

---

## TC03.5 — Desarrollo de reportes comparativos históricos

### Descripción

El Release 3 incorpora mecanismos para **contrastar consumo real** registrado en el historial con la **línea de tendencia ajustada** en las mismas fechas y con la **predicción/proyección** hacia el futuro. Esto se materializa en la API de detalle visual, en resúmenes de proyección (consumo mensual original vs ajustado) y en alertas operativas ligadas a solicitudes de compra.

### Tabla de casos de prueba

| Item | Descripción | Entradas | Sistema/Módulo | Resultado Esperado |
|------|-------------|----------|----------------|-------------------|
| TC03.5.1 | Validar API de detalle visual: serie `historico` vs `tendencia` vs `prediccion` del día siguiente. | `tendencia_id` con ≥ 2 fechas en historial; token autorizado. | API — `GET /api/analytics/etl/tendencias/{tendencia_id}/visual/`. | JSON con tres bloques diferenciados; `historico[].consumo` coincide con `HechoConsumo`; `tendencia[].valor` sigue intercepto + pendiente × índice; `prediccion` en fecha = `fecha_fin + 1 día`. |
| TC03.5.2 | Verificar reporte de proyecciones con contraste consumo mensual original y ajustado (cuando hay confiabilidad). | Tendencia con ≥ 7 puntos; historial mensual en ventana. | Backend — `evaluar_metadatos_proyeccion_producto` / `construir_reporte_proyecciones_futuras`. | El reporte expone campos de consumo original y ajustado; marca `proyeccion_ajustada` o alerta cuando corresponde. |
| TC03.5.3 | Comprobar alertas de proyección en el flujo de solicitudes de compra (desvío detectado). | Solicitud con producto que tenga proyección operativa en última corrida y condición de alerta. | Módulo compras — `solicitud_alerta_proyeccion_consumo` / serializadores. | La API de solicitudes indica `alerta_proyeccion_consumo` o detalle de alertas cuando las reglas de negocio se cumplen. |

### Objetivo

Confirmar que los reportes y APIs comparativos permiten interpretar desvíos entre lo observado, lo estimado por el modelo y lo proyectado, apoyando decisiones de compra e inventario.

### Precondiciones

- Tendencia lineal y, preferentemente, proyecciones persistidas para el producto de prueba.
- Datos de solicitudes y stock disponibles si se prueba TC03.5.3.
- Usuario con permisos analytics (y compras si aplica alertas).

### Pasos

1. Llamar a la API visual y exportar o anotar valores de un mismo día en `historico` y `tendencia`.
2. Comparar el último consumo real con `prediccion.valor` del día siguiente.
3. Generar o consultar fila de reporte de proyección para el producto y revisar campos original vs ajustado.
4. Abrir una solicitud de compra de prueba y verificar indicadores de alerta por proyección.

### Resultado esperado

Los reportes comparativos muestran de forma clara las tres perspectivas (real, tendencia, proyectado) y habilitan alertas operativas cuando hay desvíos relevantes.

---

## TC03.6 — Visualización de tendencias de consumo en gráficos

### Descripción

El dashboard analítico presenta, en la sección **Corridas analíticas (ETL)**, una tabla de tendencias y un **gráfico de líneas** (Chart.js) que superpone consumo histórico, valores ajustados por el modelo y el punto de predicción del período siguiente, con textos interpretativos de variación diaria y reposición sugerida.

### Tabla de casos de prueba

| Item | Descripción | Entradas | Sistema/Módulo | Resultado Esperado |
|------|-------------|----------|----------------|-------------------|
| TC03.6.1 | Verificar renderizado del panel y tabla de tendencias al seleccionar una corrida con resultados. | Usuario Compras/Gerencia/Admin; corrida con `resultados_tendencia_count` > 0. | Frontend — `AnalyticsCorridasSection`; `data-testid` tendencias-tabla. | Se muestra **Detalle de tendencias lineales** con filas ordenadas por predicción siguiente; columnas de stock, variación y sugerido visibles. |
| TC03.6.2 | Validar gráfico de línea al seleccionar una fila de producto con datos suficientes. | `tendencia_id` con historial ≥ 2 puntos; API visual respondiendo 200. | Frontend — gráfico `tendencias-chart-linea`; API visual. | Canvas visible; leyenda o series distinguen histórico, tendencia y predicción; texto de predicción menciona tendencia lineal. |
| TC03.6.3 | Comprobar mensaje de datos insuficientes cuando el historial tiene menos de 2 puntos. | Tendencia con 0 o 1 punto (si existe en datos de prueba) o simulación vía API. | Frontend — `tendencias-visual-insuficiente`; API con `detail` opcional. | No se fuerza gráfico erróneo; se muestra mensaje claro de insuficiencia de datos. |

### Objetivo

Asegurar que la visualización gráfica de tendencias es accesible, coherente con la API de detalle y maneja correctamente casos límite de datos.

### Precondiciones

- Frontend en ejecución con usuario autenticado.
- Corrida analítica con al menos una tendencia; preferible producto con ≥ 2 días de historial para gráfico completo.

### Pasos

1. Ingresar al dashboard y desplazarse a **Corridas analíticas (ETL)**.
2. Seleccionar una corrida con tendencias y confirmar carga de la tabla.
3. Clic en una fila de producto con historial suficiente y esperar carga del gráfico.
4. Opcional: seleccionar producto con historial insuficiente y verificar mensaje alternativo.

### Resultado esperado

La interfaz muestra tabla y gráfico alineados con los datos de la API visual, con experiencia de usuario clara en escenarios con y sin datos suficientes.

---

## TC03.7 — Integración del módulo predictivo con el sistema analítico

### Descripción

El módulo predictivo no opera de forma aislada: reutiliza **corridas ETL**, **APIs analíticas** y alimenta el **análisis inteligente** (demanda vs consumo) mediante la pendiente de la última tendencia por producto, además de exponer reposición sugerida en la tabla de tendencias y proyecciones en reglas de compras.

### Tabla de casos de prueba

| Item | Descripción | Entradas | Sistema/Módulo | Resultado Esperado |
|------|-------------|----------|----------------|-------------------|
| TC03.7.1 | Validar que el endpoint demanda vs consumo clasifica hábito (creciente/decreciente/estable) usando pendiente de la última tendencia ETL por producto. | Producto con tendencia reciente de pendiente > 0.2; filtro `desde`/`hasta` del dashboard. | API — `GET /api/analytics/demanda-vs-consumo/`; `habito_detectado` en `demanda_consumo.py`. | `habito_detectado` = "Consumo creciente" (u otra etiqueta acorde a umbrales ±0.2); no se recalcula regresión en este endpoint. |
| TC03.7.2 | Verificar listado de corridas con conteo de tendencias y selección que dispara carga de detalle predictivo. | API `GET /api/analytics/etl/corridas/`; dashboard con múltiples corridas. | Frontend — tabla corridas; backend — `ultimas_corridas`, `tendencias_por_corrida`. | Al elegir corrida se actualiza panel de tendencias; el conteo en columna **Tendencias** es coherente con API. |
| TC03.7.3 | Comprobar flujo extremo a extremo: corrida ETL → persistencia → API → UI → hábito en análisis integral, sin inconsistencia de producto/fechas. | Mismo `producto_id` y rango temporal en todas las capas; una ejecución de corrida en la ventana de prueba. | ETL + APIs + `AnalisisIntegralConsumoSection` (tab Análisis inteligente). | Mismo producto aparece con predicción en tabla de tendencias y con hábito coherente en análisis inteligente; fechas del filtro global aplican al consumo comparado. |

### Objetivo

Demostrar que el módulo predictivo del Release 3 está integrado de forma coherente con el sistema analítico existente y aporta valor a las vistas y reglas que ya consumen datos de consumo y stock.

### Precondiciones

- Corrida ETL reciente exitosa con tendencias y proyecciones.
- Dashboard con filtro temporal configurado (7, 30, 90 días o personalizado).
- Usuario con permisos para analytics y visualización de análisis integral.

### Pasos

1. Ejecutar corrida y anotar `corrida_id` y un `producto_id` de referencia.
2. Consultar tendencias de esa corrida y anotar `pendiente` y `prediccion_siguiente`.
3. Llamar a demanda vs consumo con el mismo rango de fechas del dashboard y verificar `habito_detectado` del producto.
4. En UI, abrir corridas ETL y análisis integral con el mismo filtro y confirmar consistencia visual y de etiquetas.

### Resultado esperado

El pipeline predictivo se integra sin duplicar lógica del Release 2: una sola fuente de tendencias (ETL) alimenta APIs, gráficos, hábitos detectados y alertas operativas de forma consistente.

---

## Referencia rápida — ítems del Release 3

| Ítem principal | Actividades |
|----------------|-------------|
| TC03.1 | TC03.1.1, TC03.1.2, TC03.1.3 |
| TC03.2 | TC03.2.1, TC03.2.2, TC03.2.3 |
| TC03.3 | TC03.3.1, TC03.3.2, TC03.3.3 |
| TC03.4 | TC03.4.1, TC03.4.2, TC03.4.3 |
| TC03.5 | TC03.5.1, TC03.5.2, TC03.5.3 |
| TC03.6 | TC03.6.1, TC03.6.2, TC03.6.3 |
| TC03.7 | TC03.7.1, TC03.7.2, TC03.7.3 |
