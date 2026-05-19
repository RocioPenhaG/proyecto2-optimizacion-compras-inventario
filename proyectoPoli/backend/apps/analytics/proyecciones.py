"""
Utilidades de proyección de consumo: agregación por períodos calendario e integración operativa.
"""
from calendar import monthrange
from collections import defaultdict
from datetime import date, timedelta

from django.db.models import Q, Sum

from .etl import DEFAULT_PROYECCION_HORIZONTE_DIAS
from .models import CorridaAnalitica, HechoConsumo, ProyeccionConsumoFuturo

CONFIABILIDAD_ALTA = "Alta"
CONFIABILIDAD_MEDIA = "Media"
CONFIABILIDAD_BAJA = "Baja"
CONFIABILIDAD_DATOS_INSUFICIENTES = "Datos insuficientes"
CONFIABILIDAD_TENDENCIA_INESTABLE = "Tendencia inestable"

ALERTA_DATOS_INSUFICIENTES = "Datos insuficientes"
ALERTA_PROYECCION_AJUSTADA = "Proyección ajustada"
ALERTA_STOCK_INSUFICIENTE = "Stock insuficiente"
ALERTA_SIN_ALERTA = "Sin alerta"

MULTIPLICADOR_LIMITE_MENSUAL = 3
MIN_PUNTOS_CONFIABLES = 7

_RESUMEN_CANTIDAD_KEYS = (
    "consumo_proyectado_7d",
    "consumo_proyectado_14d",
    "consumo_proyectado_30d",
    "consumo_proyectado_semana",
    "consumo_proyectado_mes",
    "consumo_proyectado_trimestre",
)


def cantidad_entera(value):
    """Cantidad de unidades para API/UI: siempre entero redondeado."""
    if value is None:
        return None
    return int(round(float(value)))


def _as_date(value):
    if value is None:
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _lunes_semana_siguiente(fecha_fin: date) -> date:
    lunes_actual = fecha_fin - timedelta(days=fecha_fin.weekday())
    return lunes_actual + timedelta(days=7)


def _primer_dia_mes_siguiente(fecha_fin: date) -> date:
    if fecha_fin.month == 12:
        return date(fecha_fin.year + 1, 1, 1)
    return date(fecha_fin.year, fecha_fin.month + 1, 1)


def _ultimo_dia_mes(anio: int, mes: int) -> date:
    return date(anio, mes, monthrange(anio, mes)[1])


def _primer_dia_trimestre_siguiente(fecha_fin: date) -> date:
    trimestre = (fecha_fin.month - 1) // 3
    if trimestre == 3:
        return date(fecha_fin.year + 1, 1, 1)
    return date(fecha_fin.year, trimestre * 3 + 4, 1)


def _ultimo_dia_trimestre(primer_dia: date) -> date:
    mes_fin = primer_dia.month + 2
    return date(primer_dia.year, mes_fin, monthrange(primer_dia.year, mes_fin)[1])


def _suma_consumo_en_rango(por_fecha: dict, inicio: date, fin: date) -> float:
    total = 0.0
    dia = inicio
    while dia <= fin:
        total += float(por_fecha.get(dia, 0.0))
        dia += timedelta(days=1)
    return total


def resumen_proyecciones_completo(proyecciones, fecha_fin):
    """
    Combina acumulados rodantes (7/14/30 d) y totales por semana/mes/trimestre calendario siguiente.
    ``proyecciones``: lista de dicts con fecha, horizonte_dias, valor_diario, consumo_acumulado.
    """
    if not proyecciones:
        return {
            "consumo_proyectado_7d": None,
            "consumo_proyectado_14d": None,
            "consumo_proyectado_30d": None,
            "consumo_proyectado_semana": None,
            "consumo_proyectado_mes": None,
            "consumo_proyectado_trimestre": None,
            "periodo_semana_desde": None,
            "periodo_semana_hasta": None,
            "periodo_mes_desde": None,
            "periodo_mes_hasta": None,
            "periodo_trimestre_desde": None,
            "periodo_trimestre_hasta": None,
        }

    fecha_fin = _as_date(fecha_fin)
    por_fecha = {}
    acumulados = {}
    for fila in proyecciones:
        f = _as_date(fila.get("fecha"))
        if f is None:
            continue
        por_fecha[f] = float(fila.get("valor_diario") or 0)
        h = fila.get("horizonte_dias")
        if h is not None:
            acumulados[int(h)] = float(fila.get("consumo_acumulado") or 0)

    def acum(h):
        return acumulados.get(h)

    sem_desde = _lunes_semana_siguiente(fecha_fin)
    sem_hasta = sem_desde + timedelta(days=6)
    mes_desde = _primer_dia_mes_siguiente(fecha_fin)
    mes_hasta = _ultimo_dia_mes(mes_desde.year, mes_desde.month)
    tri_desde = _primer_dia_trimestre_siguiente(fecha_fin)
    tri_hasta = _ultimo_dia_trimestre(tri_desde)

    return {
        "consumo_proyectado_7d": acum(7),
        "consumo_proyectado_14d": acum(14),
        "consumo_proyectado_30d": acum(30),
        "consumo_proyectado_semana": _suma_consumo_en_rango(por_fecha, sem_desde, sem_hasta),
        "consumo_proyectado_mes": _suma_consumo_en_rango(por_fecha, mes_desde, mes_hasta),
        "consumo_proyectado_trimestre": _suma_consumo_en_rango(por_fecha, tri_desde, tri_hasta),
        "periodo_semana_desde": sem_desde,
        "periodo_semana_hasta": sem_hasta,
        "periodo_mes_desde": mes_desde,
        "periodo_mes_hasta": mes_hasta,
        "periodo_trimestre_desde": tri_desde,
        "periodo_trimestre_hasta": tri_hasta,
    }


def _corrida_proyecciones_reciente():
    return (
        CorridaAnalitica.objects.filter(estado__in=(CorridaAnalitica.Estado.SUCCESS, CorridaAnalitica.Estado.OK))
        .order_by("-fecha_ejecucion")
        .first()
    )


def _horizonte_corrida(corrida):
    params = corrida.parametros if isinstance(corrida.parametros, dict) else {}
    raw = params.get("proyeccion_horizonte_dias")
    if raw is not None:
        try:
            return max(1, int(raw))
        except (TypeError, ValueError):
            pass
    return DEFAULT_PROYECCION_HORIZONTE_DIAS


def _stock_producto(producto):
    try:
        return int(producto.stock.qty_on_hand)
    except Exception:
        return 0


def consumo_mensual_promedio_historico(producto_id, fecha_inicio, fecha_fin):
    """
    Promedio mensual de consumo OUT en la ventana de la tendencia
    (extrapolación: total / días × 30).
    """
    fecha_inicio = _as_date(fecha_inicio)
    fecha_fin = _as_date(fecha_fin)
    if not fecha_inicio or not fecha_fin:
        return None
    total = (
        HechoConsumo.objects.filter(
            producto_id=producto_id,
            tipo_movimiento="OUT",
            fecha__gte=fecha_inicio,
            fecha__lte=fecha_fin,
        ).aggregate(s=Sum("cantidad_total"))["s"]
        or 0
    )
    dias = max(1, (fecha_fin - fecha_inicio).days + 1)
    return float(total) / dias * 30.0


def evaluar_confiabilidad(tendencia, consumo_mes_proyectado, consumo_mensual_promedio_historico):
    puntos = int(tendencia.puntos_usados or 0)
    if puntos < MIN_PUNTOS_CONFIABLES:
        return CONFIABILIDAD_DATOS_INSUFICIENTES

    hist = consumo_mensual_promedio_historico
    mes = consumo_mes_proyectado
    if hist and hist > 0 and mes is not None and mes > hist * MULTIPLICADOR_LIMITE_MENSUAL:
        return CONFIABILIDAD_TENDENCIA_INESTABLE

    r2 = tendencia.r2
    if r2 is None:
        return CONFIABILIDAD_BAJA
    r2f = float(r2)
    if r2f < 0.30:
        return CONFIABILIDAD_BAJA
    if r2f < 0.60:
        return CONFIABILIDAD_MEDIA
    return CONFIABILIDAD_ALTA


def ajustar_consumo_mensual(consumo_mes_original, consumo_mensual_promedio_historico):
    """
    Devuelve (original_entero, ajustado_entero, proyeccion_ajustada).
    """
    original = cantidad_entera(consumo_mes_original)
    if original is None:
        return None, None, False

    hist = consumo_mensual_promedio_historico
    if not hist or hist <= 0:
        return original, original, False

    limite = cantidad_entera(hist * MULTIPLICADOR_LIMITE_MENSUAL)
    if limite is not None and original > limite:
        return original, limite, True
    return original, original, False


def evaluar_alerta_reporte(puntos_usados, proyeccion_ajustada, stock_actual, consumo_mes_ajustado):
    if int(puntos_usados or 0) < MIN_PUNTOS_CONFIABLES:
        return ALERTA_DATOS_INSUFICIENTES
    if proyeccion_ajustada:
        return ALERTA_PROYECCION_AJUSTADA
    if consumo_mes_ajustado is not None and stock_actual < consumo_mes_ajustado:
        return ALERTA_STOCK_INSUFICIENTE
    return ALERTA_SIN_ALERTA


def reposicion_orientativa(puntos_usados, consumo_mes_ajustado, stock_actual):
    if int(puntos_usados or 0) < MIN_PUNTOS_CONFIABLES:
        return None
    if consumo_mes_ajustado is None:
        return None
    return max(0, int(consumo_mes_ajustado) - int(stock_actual))


def _consumo_30_dias_ajustado(consumo_30_est, mes_orig, mes_ajust, proyeccion_ajustada):
    if consumo_30_est is None:
        return mes_ajust
    if not proyeccion_ajustada or not mes_orig or not mes_ajust or mes_orig <= 0:
        return consumo_30_est
    return cantidad_entera(consumo_30_est * mes_ajust / mes_orig)


def evaluar_cobertura_estimada_texto(cobertura_dias, mostrar_proyeccion, consumo_diario):
    if not mostrar_proyeccion:
        return "Historial insuficiente"
    if consumo_diario is None or consumo_diario <= 0:
        return "Sin consumo estimado"
    if cobertura_dias is None:
        return "Sin consumo estimado"
    if cobertura_dias < 7:
        return "Menos de 7 días"
    if cobertura_dias <= 30:
        return f"Aprox. {cobertura_dias} días"
    return "Más de 30 días"


def evaluar_accion_sugerida(
    mostrar_proyeccion,
    stock_actual,
    stock_minimo,
    cobertura_dias,
):
    if not mostrar_proyeccion:
        return "Revisar historial de consumo"
    if stock_actual < stock_minimo:
        return "Reponer por stock mínimo"
    if cobertura_dias is not None and cobertura_dias < 7:
        return "Reponer pronto"
    if cobertura_dias is not None and cobertura_dias <= 30:
        return "Planificar reposición"
    return "Stock suficiente"


def evaluar_estado_operativo(
    mostrar_proyeccion,
    stock_actual,
    stock_minimo,
    cobertura_dias,
    confiabilidad,
    proyeccion_ajustada,
):
    if not mostrar_proyeccion:
        return "Datos insuficientes"
    if stock_actual < stock_minimo or (cobertura_dias is not None and cobertura_dias < 7):
        return "Stock crítico"
    if proyeccion_ajustada or confiabilidad in (
        CONFIABILIDAD_BAJA,
        CONFIABILIDAD_TENDENCIA_INESTABLE,
    ):
        return "Revisar"
    if cobertura_dias is not None and cobertura_dias <= 30:
        return "Planificar"
    return "Suficiente"


def calcular_campos_vista_operativa(tendencia, resumen_api, meta_base):
    """Campos simplificados para la tabla operativa del reporte de proyección."""
    puntos = int(meta_base["puntos_usados"])
    stock_actual = meta_base["stock_actual"]
    stock_minimo = int(meta_base.get("stock_minimo") or 0)
    confiabilidad = meta_base["confiabilidad"]
    proyeccion_ajustada = bool(meta_base.get("proyeccion_ajustada"))

    mostrar_proyeccion = puntos >= MIN_PUNTOS_CONFIABLES and confiabilidad != CONFIABILIDAD_DATOS_INSUFICIENTES

    consumo_30_est = resumen_api.get("consumo_proyectado_30d")
    if consumo_30_est is None:
        consumo_30_est = meta_base.get("consumo_mes_original")
    mes_orig = meta_base.get("consumo_mes_original")
    mes_ajust = meta_base.get("consumo_mes_ajustado")
    consumo_30_ajust = _consumo_30_dias_ajustado(consumo_30_est, mes_orig, mes_ajust, proyeccion_ajustada)

    consumo_diario = None
    if mostrar_proyeccion and consumo_30_ajust is not None and consumo_30_ajust > 0:
        consumo_diario = max(1, int(round(consumo_30_ajust / 30)))

    cobertura_dias = None
    if mostrar_proyeccion and consumo_diario and consumo_diario > 0:
        cobertura_dias = int(round(stock_actual / consumo_diario))

    cobertura_texto = evaluar_cobertura_estimada_texto(cobertura_dias, mostrar_proyeccion, consumo_diario)
    accion = evaluar_accion_sugerida(mostrar_proyeccion, stock_actual, stock_minimo, cobertura_dias)
    estado = evaluar_estado_operativo(
        mostrar_proyeccion,
        stock_actual,
        stock_minimo,
        cobertura_dias,
        confiabilidad,
        proyeccion_ajustada,
    )

    return {
        "mostrar_proyeccion": mostrar_proyeccion,
        "consumo_30_dias_estimado": consumo_30_est if mostrar_proyeccion else None,
        "consumo_30_dias_ajustado": consumo_30_ajust if mostrar_proyeccion else None,
        "consumo_diario_promedio_estimado": consumo_diario,
        "cobertura_dias": cobertura_dias,
        "cobertura_estimada": cobertura_texto,
        "accion_sugerida": accion,
        "estado_operativo": estado,
        "proyeccion_limitada": proyeccion_ajustada and mostrar_proyeccion,
        "detalle_tecnico": {
            "prediccion_siguiente": cantidad_entera(tendencia.prediccion_siguiente),
            "consumo_proyectado_semana": resumen_api.get("consumo_proyectado_semana"),
            "consumo_mes_original": mes_orig,
            "consumo_mes_ajustado": mes_ajust,
            "consumo_proyectado_trimestre": resumen_api.get("consumo_proyectado_trimestre"),
            "consumo_proyectado_7d": resumen_api.get("consumo_proyectado_7d"),
            "consumo_proyectado_14d": resumen_api.get("consumo_proyectado_14d"),
            "consumo_proyectado_30d": consumo_30_est,
            "r2": meta_base.get("r2"),
            "puntos_usados": puntos,
            "confiabilidad": confiabilidad,
            "consumo_mensual_promedio_historico": meta_base.get("consumo_mensual_promedio_historico"),
            "proyeccion_ajustada": proyeccion_ajustada,
            "limite_superior_mensual": meta_base.get("limite_superior_mensual"),
            "fecha_fin_tendencia": tendencia.fecha_fin.isoformat()
            if hasattr(tendencia.fecha_fin, "isoformat")
            else str(tendencia.fecha_fin),
        },
    }


def evaluar_metadatos_proyeccion_producto(tendencia, resumen_api, producto):
    """Campos de confiabilidad, ajuste mensual, alerta y reposición orientativa."""
    puntos = int(tendencia.puntos_usados or 0)
    stock_actual = _stock_producto(producto)
    stock_minimo = int(producto.stock_minimo or 0)
    hist_mensual = consumo_mensual_promedio_historico(
        producto.id, tendencia.fecha_inicio, tendencia.fecha_fin
    )
    hist_mensual_entero = cantidad_entera(hist_mensual)

    mes_original = resumen_api.get("consumo_proyectado_mes")
    mes_orig_int, mes_ajustado, proyeccion_ajustada = ajustar_consumo_mensual(mes_original, hist_mensual)

    confiabilidad = evaluar_confiabilidad(tendencia, mes_orig_int, hist_mensual)
    alerta = evaluar_alerta_reporte(puntos, proyeccion_ajustada, stock_actual, mes_ajustado)
    reposicion = reposicion_orientativa(puntos, mes_ajustado, stock_actual)

    meta_base = {
        "puntos_usados": puntos,
        "r2": float(tendencia.r2) if tendencia.r2 is not None else None,
        "confiabilidad": confiabilidad,
        "alerta": alerta,
        "stock_actual": stock_actual,
        "stock_minimo": stock_minimo,
        "consumo_mensual_promedio_historico": hist_mensual_entero,
        "consumo_mes_original": mes_orig_int,
        "consumo_mes_ajustado": mes_ajustado,
        "proyeccion_ajustada": proyeccion_ajustada,
        "reposicion_orientativa": reposicion,
        "limite_superior_mensual": cantidad_entera(hist_mensual * MULTIPLICADOR_LIMITE_MENSUAL)
        if hist_mensual and hist_mensual > 0
        else None,
        "alerta_stock": alerta not in (ALERTA_SIN_ALERTA, ALERTA_DATOS_INSUFICIENTES),
        "cantidad_sugerida_reposicion": reposicion if reposicion is not None else 0,
    }
    vista = calcular_campos_vista_operativa(tendencia, resumen_api, meta_base)
    return {**meta_base, **vista}


def mapa_proyecciones_operativas(producto_ids=None):
    """
    Proyecciones de la última corrida exitosa, indexadas por producto_id.
    Incluye resúmenes calendario y consumo promedio diario proyectado (7 primeros días).
    """
    corrida = _corrida_proyecciones_reciente()
    if not corrida:
        return {}

    qs = ProyeccionConsumoFuturo.objects.filter(corrida=corrida).select_related(
        "tendencia", "producto", "producto__stock"
    )
    if producto_ids is not None:
        qs = qs.filter(producto_id__in=producto_ids)

    por_producto = defaultdict(lambda: {"filas": [], "tendencia": None, "producto": None})
    for fila in qs.order_by("producto_id", "horizonte_dias"):
        bucket = por_producto[fila.producto_id]
        bucket["filas"].append(
            {
                "fecha": fila.fecha,
                "horizonte_dias": fila.horizonte_dias,
                "valor_diario": float(fila.valor_diario),
                "consumo_acumulado": float(fila.consumo_acumulado),
            }
        )
        bucket["tendencia"] = fila.tendencia
        bucket["producto"] = fila.producto

    out = {}
    for pid, bucket in por_producto.items():
        tendencia = bucket["tendencia"]
        producto = bucket["producto"]
        filas = bucket["filas"]
        if not tendencia or not producto or not filas:
            continue
        resumen = serializar_resumen_proyecciones_api(
            resumen_proyecciones_completo(filas, tendencia.fecha_fin)
        )
        n = min(7, len(filas))
        promedio_diario = sum(f["valor_diario"] for f in filas[:n]) / n if n else 0.0
        meta = evaluar_metadatos_proyeccion_producto(tendencia, resumen, producto)
        out[pid] = {
            **resumen,
            **meta,
            "consumo_promedio_diario_proyectado": cantidad_entera(promedio_diario),
            "corrida_id": corrida.id,
        }
    return out


def calcular_cobertura_dias(stock_actual: int, consumo_promedio_diario: float):
    if stock_actual <= 0:
        return 0, "Sin stock"
    if consumo_promedio_diario > 0:
        dias = int(round(stock_actual / consumo_promedio_diario))
        return dias, f"{dias} días"
    if consumo_promedio_diario == 0:
        return None, "Sin consumo reciente"
    return None, "No disponible"


def evaluar_cobertura_con_proyeccion(stock_actual: int, consumo_historico_diario: float, info_proyeccion):
    """
    Usa la proyección cuando existe y es más conservadora (menor cobertura en días).
    """
    hist_dias, hist_texto = calcular_cobertura_dias(stock_actual, consumo_historico_diario)
    proy_diario = (info_proyeccion or {}).get("consumo_promedio_diario_proyectado") or 0.0
    if proy_diario <= 0:
        return {
            "cobertura_dias": hist_dias,
            "cobertura_texto": hist_texto,
            "cobertura_fuente": "historico",
            "consumo_promedio_diario_usado": consumo_historico_diario,
        }

    proy_dias, proy_texto = calcular_cobertura_dias(stock_actual, proy_diario)
    usar_proyeccion = hist_dias is None or (proy_dias is not None and proy_dias <= hist_dias)
    if usar_proyeccion:
        texto = proy_texto if proy_texto == "Sin stock" else f"{proy_texto} (proyectado)"
        return {
            "cobertura_dias": proy_dias,
            "cobertura_texto": texto,
            "cobertura_fuente": "proyeccion",
            "consumo_promedio_diario_usado": proy_diario,
        }
    return {
        "cobertura_dias": hist_dias,
        "cobertura_texto": hist_texto,
        "cobertura_fuente": "historico",
        "consumo_promedio_diario_usado": consumo_historico_diario,
    }


def ajustar_riesgo_recomendacion_con_proyeccion(
    stock_actual: int,
    stock_minimo: int,
    cobertura_dias,
    riesgo: str,
    recomendacion: str,
    info_proyeccion,
):
    """Eleva riesgo/recomendación si el stock no cubre el consumo proyectado del período."""
    if not info_proyeccion:
        return riesgo, recomendacion, False

    semana = info_proyeccion.get("consumo_proyectado_semana")
    mes_ajustado = info_proyeccion.get("consumo_mes_ajustado") or info_proyeccion.get("consumo_proyectado_mes")
    confiabilidad = info_proyeccion.get("confiabilidad")
    alerta_proyeccion = False

    if confiabilidad == CONFIABILIDAD_DATOS_INSUFICIENTES:
        return riesgo, recomendacion, False

    if semana is not None and stock_actual < semana:
        alerta_proyeccion = True
        if stock_actual <= 0 or (cobertura_dias is not None and cobertura_dias <= 7):
            riesgo = "Alto"
            recomendacion = "Reponer urgente (proyección semanal supera stock)"
        elif riesgo != "Alto":
            riesgo = "Medio" if riesgo == "Bajo" else riesgo
            if recomendacion in ("Sin acción inmediata", "Monitorear", "Sin acción inmediata."):
                recomendacion = "Reponer según proyección semanal"
            elif recomendacion == "Reponer pronto":
                recomendacion = "Reponer pronto (proyección semanal)"

    if (
        mes_ajustado is not None
        and stock_actual < mes_ajustado
        and stock_actual <= stock_minimo
    ):
        alerta_proyeccion = True
        if riesgo == "Bajo":
            riesgo = "Medio"
        if recomendacion == "Monitorear":
            recomendacion = "Reponer según proyección mensual (orientativa)"

    if info_proyeccion.get("proyeccion_ajustada") and recomendacion == "Monitorear":
        recomendacion = "Revisar proyección ajustada"

    return riesgo, recomendacion, alerta_proyeccion


def construir_reporte_proyecciones_futuras(buscar=None, solo_alerta=False, limit=200):
    """
    Reporte agregado por producto a partir de la última corrida con proyecciones.
    No requiere seleccionar corrida ni tendencia en el cliente.
    """
    corrida = _corrida_proyecciones_reciente()
    if not corrida:
        return None, []

    qs = ProyeccionConsumoFuturo.objects.filter(corrida=corrida).select_related(
        "producto", "tendencia", "producto__stock"
    )
    if buscar:
        term = buscar.strip()
        if term:
            qs = qs.filter(Q(producto__nombre__icontains=term) | Q(producto__sku__icontains=term))

    por_producto = defaultdict(lambda: {"filas": [], "tendencia": None, "producto": None})
    for fila in qs.order_by("producto_id", "horizonte_dias"):
        bucket = por_producto[fila.producto_id]
        bucket["filas"].append(
            {
                "fecha": fila.fecha,
                "horizonte_dias": fila.horizonte_dias,
                "valor_diario": float(fila.valor_diario),
                "consumo_acumulado": float(fila.consumo_acumulado),
            }
        )
        bucket["tendencia"] = fila.tendencia
        bucket["producto"] = fila.producto

    filas_reporte = []
    for pid, bucket in por_producto.items():
        producto = bucket["producto"]
        tendencia = bucket["tendencia"]
        proyecciones = bucket["filas"]
        if not producto or not tendencia or not proyecciones:
            continue

        resumen_api = serializar_resumen_proyecciones_api(
            resumen_proyecciones_completo(proyecciones, tendencia.fecha_fin)
        )
        n = min(7, len(proyecciones))
        promedio_diario = sum(f["valor_diario"] for f in proyecciones[:n]) / n if n else 0.0
        meta = evaluar_metadatos_proyeccion_producto(tendencia, resumen_api, producto)
        estado = meta.get("estado_operativo")
        if solo_alerta and estado in ("Suficiente", "Datos insuficientes"):
            continue

        filas_reporte.append(
            {
                "producto_id": pid,
                "sku": producto.sku,
                "nombre": producto.nombre,
                "tendencia_id": tendencia.id,
                "fecha_fin_tendencia": tendencia.fecha_fin,
                "prediccion_siguiente": cantidad_entera(tendencia.prediccion_siguiente),
                "consumo_promedio_diario_proyectado": cantidad_entera(promedio_diario),
                "resumen": resumen_api,
                **meta,
            }
        )

    orden_estado = {
        "Stock crítico": 0,
        "Revisar": 1,
        "Planificar": 2,
        "Suficiente": 3,
        "Datos insuficientes": 4,
    }
    filas_reporte.sort(
        key=lambda r: (
            orden_estado.get(r.get("estado_operativo"), 9),
            r["sku"] or "",
        )
    )
    limite = max(1, min(int(limit or 200), 500))
    corrida_info = {
        "id": corrida.id,
        "fecha_ejecucion": corrida.fecha_ejecucion,
        "proyeccion_horizonte_dias": _horizonte_corrida(corrida),
    }
    return corrida_info, filas_reporte[:limite]


def serializar_resumen_proyecciones_api(resumen: dict):
    """Convierte fechas a ISO y cantidades a enteros redondeados para respuestas JSON."""
    out = dict(resumen)
    for key in _RESUMEN_CANTIDAD_KEYS:
        if out.get(key) is not None:
            out[key] = cantidad_entera(out[key])
    for key in (
        "periodo_semana_desde",
        "periodo_semana_hasta",
        "periodo_mes_desde",
        "periodo_mes_hasta",
        "periodo_trimestre_desde",
        "periodo_trimestre_hasta",
    ):
        val = out.get(key)
        if val is not None:
            out[key] = val.isoformat() if hasattr(val, "isoformat") else str(val)
    return out


def serializar_fila_proyeccion_diaria(fila: dict):
    """Fila diaria de proyección con cantidades enteras."""
    return {
        "fecha": fila["fecha"],
        "horizonte_dias": fila["horizonte_dias"],
        "valor_diario": cantidad_entera(fila.get("valor_diario")),
        "consumo_acumulado": cantidad_entera(fila.get("consumo_acumulado")),
    }
