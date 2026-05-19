"""
Política de retención para datos analíticos derivados y recalculables.

Los datos operativos originales no se eliminan. Solo se depuran resultados analíticos
derivados y recalculables para evitar crecimiento innecesario de la base de datos.

No afecta: MovStock, StockProducto, Producto, solicitudes, usuarios, HechoConsumo,
ResumenConsumoMensual.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from django.apps import apps
from django.db import transaction
from django.utils import timezone

from apps.analytics.models import CorridaAnalitica, ResultadoTendenciaLineal


@dataclass(frozen=True)
class ResultadoLimpiezaRetencion:
    fecha_corte: datetime
    dias_retencion: int
    dry_run: bool
    corridas_antiguas: int
    tendencias_asociadas: int
    proyecciones_asociadas: int
    eliminadas_corridas: int = 0
    eliminadas_tendencias: int = 0
    eliminadas_proyecciones: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "fecha_corte": self.fecha_corte.isoformat(),
            "dias_retencion": self.dias_retencion,
            "dry_run": self.dry_run,
            "corridas_antiguas": self.corridas_antiguas,
            "tendencias_asociadas": self.tendencias_asociadas,
            "proyecciones_asociadas": self.proyecciones_asociadas,
            "eliminadas_corridas": self.eliminadas_corridas,
            "eliminadas_tendencias": self.eliminadas_tendencias,
            "eliminadas_proyecciones": self.eliminadas_proyecciones,
        }


def _modelo_proyeccion_consumo_futuro():
    """Devuelve el modelo si existe en el proyecto; None si no está migrado."""
    try:
        return apps.get_model("analytics", "ProyeccionConsumoFuturo")
    except LookupError:
        return None


def _corridas_antiguas_queryset(fecha_corte: datetime):
    return CorridaAnalitica.objects.filter(fecha_ejecucion__lt=fecha_corte)


def limpiar_datos_analiticos(dias_retencion: int = 180, dry_run: bool = False) -> ResultadoLimpiezaRetencion:
    """
    Elimina corridas analíticas antiguas y sus derivados (tendencias, proyecciones opcionales).

    Criterio: ``fecha_ejecucion`` de ``CorridaAnalitica`` anterior a
    ``timezone.now() - timedelta(days=dias_retencion)``.
    """
    if dias_retencion < 1:
        raise ValueError("dias_retencion debe ser >= 1.")

    fecha_corte = timezone.now() - timedelta(days=int(dias_retencion))
    corridas_qs = _corridas_antiguas_queryset(fecha_corte)
    corrida_ids = list(corridas_qs.values_list("id", flat=True))

    n_corridas = len(corrida_ids)
    n_tendencias = (
        ResultadoTendenciaLineal.objects.filter(corrida_id__in=corrida_ids).count()
        if corrida_ids
        else 0
    )

    ProyeccionModel = _modelo_proyeccion_consumo_futuro()
    n_proyecciones = 0
    if ProyeccionModel is not None and corrida_ids:
        n_proyecciones = ProyeccionModel.objects.filter(corrida_id__in=corrida_ids).count()

    resultado = ResultadoLimpiezaRetencion(
        fecha_corte=fecha_corte,
        dias_retencion=int(dias_retencion),
        dry_run=bool(dry_run),
        corridas_antiguas=n_corridas,
        tendencias_asociadas=n_tendencias,
        proyecciones_asociadas=n_proyecciones,
    )

    if dry_run or not corrida_ids:
        return resultado

    eliminadas_tendencias = 0
    eliminadas_proyecciones = 0
    eliminadas_corridas = 0

    with transaction.atomic():
        deleted_tend, _ = ResultadoTendenciaLineal.objects.filter(corrida_id__in=corrida_ids).delete()
        eliminadas_tendencias = deleted_tend

        if ProyeccionModel is not None:
            deleted_proy, _ = ProyeccionModel.objects.filter(corrida_id__in=corrida_ids).delete()
            eliminadas_proyecciones = deleted_proy

        deleted_corr, _ = CorridaAnalitica.objects.filter(id__in=corrida_ids).delete()
        eliminadas_corridas = deleted_corr

    return ResultadoLimpiezaRetencion(
        fecha_corte=fecha_corte,
        dias_retencion=int(dias_retencion),
        dry_run=False,
        corridas_antiguas=n_corridas,
        tendencias_asociadas=n_tendencias,
        proyecciones_asociadas=n_proyecciones,
        eliminadas_corridas=eliminadas_corridas,
        eliminadas_tendencias=eliminadas_tendencias,
        eliminadas_proyecciones=eliminadas_proyecciones,
    )
