"""
Lógica de demanda vs consumo sincronizada con el filtro temporal del dashboard.

El consumo y las solicitudes se calculan sobre el rango ``desde``/``hasta`` de la petición.
Las tendencias lineales provienen del ETL (última por producto); no se recalcula regresión aquí.
"""
from __future__ import annotations

HABITO_CONSUMO_FUERTE = frozenset({"Consumo frecuente", "Consumo creciente"})


def dias_periodo_inclusivo(fecha_desde, fecha_hasta) -> int:
    return max(1, (fecha_hasta - fecha_desde).days + 1)


def clasificar_demanda_vs_consumo(cantidad_solicitada: int, cantidad_consumida: int):
    """
    diferencia = solicitado - consumido.
    Coherente si |diff| <= 1 o |diff| <= 10% del máximo entre solicitado y consumido.
    """
    diff = int(cantidad_solicitada) - int(cantidad_consumida)
    mx = max(int(cantidad_solicitada), int(cantidad_consumida))
    if mx == 0:
        return diff, "coherente", "Demanda coherente"
    umbral_rel = 0.10 * mx
    coherente = abs(diff) <= 1 or abs(diff) <= umbral_rel
    if coherente:
        return diff, "coherente", "Demanda coherente"
    if diff > 0:
        return diff, "solicitado_mayor", "Se solicita más de lo que se consume"
    return diff, "consumo_mayor", "Se consume más de lo solicitado"


def demanda_vs_consumo_texto(solicitado: int, consumido: int):
    diff, estado, lectura = clasificar_demanda_vs_consumo(solicitado, consumido)
    if estado == "consumo_mayor":
        return diff, estado, lectura, "Se consume más de lo solicitado"
    if estado == "solicitado_mayor":
        return diff, estado, lectura, "Se solicita más de lo que se consume"
    return diff, estado, lectura, "Demanda coherente"


def habito_detectado(
    pendiente: float | None,
    consumo_periodo: int,
    dias_con_consumo: int,
    dias_periodo: int,
):
    """
    Hábito: primero tendencia ETL (pendiente); si no hay, frecuencia en el período filtrado.
    """
    if pendiente is not None:
        if pendiente > 0.2:
            return "Consumo creciente"
        if pendiente < -0.2:
            return "Consumo decreciente"
        return "Consumo estable"
    if consumo_periodo <= 0:
        return "Sin consumo reciente"
    frecuencia = dias_con_consumo / dias_periodo if dias_periodo else 0
    if frecuencia >= 0.30:
        return "Consumo frecuente"
    return "Consumo esporádico"


def cobertura_desde_stock(stock_actual: int, consumo_promedio_diario: float):
    if stock_actual <= 0:
        return None, "Sin stock"
    if consumo_promedio_diario > 0:
        dias = int(round(stock_actual / consumo_promedio_diario))
        return dias, f"{dias} días"
    if consumo_promedio_diario == 0:
        return None, "Sin consumo reciente"
    return None, "No disponible"


def riesgo_y_recomendacion_demanda(
    stock_actual: int,
    stock_minimo: int,
    cobertura_dias: int | None,
    habito: str,
    estado: str,
):
    consumo_fuerte = habito in HABITO_CONSUMO_FUERTE
    if (
        (cobertura_dias is not None and cobertura_dias <= 7) or stock_actual <= stock_minimo
    ) and consumo_fuerte:
        riesgo = "Alto"
    elif (cobertura_dias is not None and 8 <= cobertura_dias <= 15) or estado == "consumo_mayor":
        riesgo = "Medio"
    else:
        riesgo = "Bajo"

    if stock_actual <= 0 or cobertura_dias == 0:
        recomendacion = "Reponer urgente"
    elif habito == "Sin consumo reciente":
        recomendacion = "Revisar stock inmovilizado"
    elif estado == "consumo_mayor" and cobertura_dias is not None and cobertura_dias <= 7:
        recomendacion = "Revisar reposición"
    elif estado == "solicitado_mayor":
        recomendacion = "Validar necesidad"
    elif riesgo == "Alto":
        recomendacion = "Reponer pronto"
    elif riesgo == "Medio":
        recomendacion = "Monitorear"
    elif habito in ("Bajo movimiento", "Sin consumo reciente") and stock_actual > max(
        stock_minimo * 2, 0
    ):
        recomendacion = "No priorizar compra"
    else:
        recomendacion = "Sin acción inmediata"
    return riesgo, recomendacion


def periodo_payload(fecha_desde, fecha_hasta) -> dict:
    dias = dias_periodo_inclusivo(fecha_desde, fecha_hasta)
    return {
        "desde": str(fecha_desde),
        "hasta": str(fecha_hasta),
        "dias": dias,
    }
