"""
Normalización de rangos de fechas para APIs analíticas y dashboard.
"""
from datetime import datetime, timedelta

from django.utils import timezone

DEFAULT_RANGE_DAYS = 30
MAX_CUSTOM_RANGE_DAYS = 30
MAX_QUICK_RANGE_DAYS = 90


def _today():
    return timezone.localdate()


def _parse_ymd(value: str):
    return datetime.strptime(value.strip(), "%Y-%m-%d").date()


def normalize_fecha_range(fecha_desde, fecha_hasta, max_days=MAX_QUICK_RANGE_DAYS):
    """Rango inclusivo [desde, hasta], acotado a hoy y a max_days de diferencia."""
    today = _today()
    if fecha_hasta > today:
        fecha_hasta = today
    if fecha_desde > fecha_hasta:
        fecha_desde, fecha_hasta = fecha_hasta, fecha_desde
    span = (fecha_hasta - fecha_desde).days
    if span > max_days:
        fecha_hasta = fecha_desde + timedelta(days=max_days)
        if fecha_hasta > today:
            fecha_hasta = today
            fecha_desde = fecha_hasta - timedelta(days=max_days)
    return fecha_desde, fecha_hasta


def parse_fechas(request):
    """
    Siempre devuelve (fecha_desde, fecha_hasta) acotadas.

    - Sin params: últimos DEFAULT_RANGE_DAYS hasta hoy.
    - Solo ``desde``: hasta = desde + MAX_CUSTOM_RANGE_DAYS (máx. hoy).
    - Solo ``hasta``: desde = hasta - MAX_CUSTOM_RANGE_DAYS.
    - Ambos: normaliza (máx. MAX_QUICK_RANGE_DAYS entre fechas).

    Lanza ValueError con código ``invalid`` si el formato es inválido.
    """
    desde_qp = (request.query_params.get("desde") or "").strip()
    hasta_qp = (request.query_params.get("hasta") or "").strip()
    today = _today()

    try:
        if not desde_qp and not hasta_qp:
            fecha_hasta = today
            fecha_desde = today - timedelta(days=DEFAULT_RANGE_DAYS)
            return fecha_desde, fecha_hasta

        if desde_qp and not hasta_qp:
            fecha_desde = _parse_ymd(desde_qp)
            fecha_hasta = min(
                fecha_desde + timedelta(days=MAX_CUSTOM_RANGE_DAYS),
                today,
            )
            return normalize_fecha_range(fecha_desde, fecha_hasta, MAX_CUSTOM_RANGE_DAYS)

        if hasta_qp and not desde_qp:
            fecha_hasta = _parse_ymd(hasta_qp)
            if fecha_hasta > today:
                fecha_hasta = today
            fecha_desde = fecha_hasta - timedelta(days=MAX_CUSTOM_RANGE_DAYS)
            return normalize_fecha_range(fecha_desde, fecha_hasta, MAX_CUSTOM_RANGE_DAYS)

        fecha_desde = _parse_ymd(desde_qp)
        fecha_hasta = _parse_ymd(hasta_qp)
        return normalize_fecha_range(fecha_desde, fecha_hasta, MAX_QUICK_RANGE_DAYS)
    except ValueError as exc:
        if "time data" in str(exc) or "does not match" in str(exc):
            raise ValueError("invalid") from exc
        raise
