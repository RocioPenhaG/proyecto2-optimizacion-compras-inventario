"""Tests backend/API — TC04 (proyecciones de consumo futuro)."""
from datetime import date, timedelta
from decimal import Decimal

from ..etl import (
    ejecutar_etl_analitico,
    generar_proyecciones_consumo,
    guardar_proyecciones_consumo_futuro,
)
from ..models import CorridaAnalitica, ProyeccionConsumoFuturo, ResultadoTendenciaLineal
from ..proyecciones import resumen_proyecciones_completo

from ._base import BaseAnalyticsETLTestCase


class AnalyticsProyeccionesTestCase(BaseAnalyticsETLTestCase):
    """TC04 — Persistencia, truncado y resumen de proyecciones."""

    HORIZONTE_PRUEBA = 14

    def setUp(self):
        super().setUp()
        self.producto.sku = "PROY-TC04"
        self.producto.nombre = "Producto proyecciones TC04"
        self.producto.save(update_fields=["sku", "nombre"])

    def _ejecutar_etl_y_persistir_proyecciones(self, dias, horizonte=None):
        horizonte = horizonte or self.HORIZONTE_PRUEBA
        corrida = ejecutar_etl_analitico(
            fecha_desde=dias[0],
            fecha_hasta=dias[-1],
            proyeccion_horizonte_dias=horizonte,
        )
        guardar_proyecciones_consumo_futuro(corrida, horizonte_dias=horizonte)
        tendencia = ResultadoTendenciaLineal.objects.get(corrida=corrida, producto=self.producto)
        return corrida, tendencia

    def test_tc04_1_etl_persiste_proyecciones_diarias_por_tendencia(self):
        """TC04.1 — Tras corrida con tendencia válida, se persisten H proyecciones diarias."""
        ref = date(2027, 1, 10)
        cantidades = [6, 8, 10, 12]
        dias = self._crear_serie_out_elegible(self.producto, ref, cantidades)
        horizonte = self.HORIZONTE_PRUEBA

        corrida, tendencia = self._ejecutar_etl_y_persistir_proyecciones(dias, horizonte=horizonte)
        self.assertEqual(corrida.estado, CorridaAnalitica.Estado.SUCCESS)
        self.assertEqual(corrida.parametros.get("proyeccion_horizonte_dias"), horizonte)

        proyecciones = ProyeccionConsumoFuturo.objects.filter(tendencia=tendencia).order_by("horizonte_dias")
        self.assertEqual(proyecciones.count(), horizonte)
        self.assertEqual(
            list(proyecciones.values_list("horizonte_dias", flat=True)),
            list(range(1, horizonte + 1)),
        )
        for proy in proyecciones:
            self.assertEqual(proy.tendencia_id, tendencia.id)
            self.assertEqual(proy.corrida_id, corrida.id)
            self.assertEqual(proy.producto_id, self.producto.id)
            self.assertGreater(proy.fecha, tendencia.fecha_fin)

    def test_tc04_2_proyecciones_negativas_se_truncan_a_cero(self):
        """TC04.2 — Valores proyectados negativos se truncan a 0."""
        filas = generar_proyecciones_consumo(
            intercepto=5,
            pendiente=-10,
            puntos_usados=3,
            fecha_fin=date(2027, 2, 1),
            horizonte_dias=5,
        )
        for fila in filas:
            self.assertGreaterEqual(fila["valor_diario"], 0.0)

        corrida = CorridaAnalitica.objects.create(
            task_id="proy-trunc",
            estado=CorridaAnalitica.Estado.SUCCESS,
            metodo=CorridaAnalitica.Metodo.MANUAL,
        )
        tendencia = ResultadoTendenciaLineal.objects.create(
            corrida=corrida,
            producto=self.producto,
            variable_objetivo="consumo_out",
            periodicidad="DAILY",
            fecha_inicio=date(2027, 1, 29),
            fecha_fin=date(2027, 2, 1),
            puntos_usados=3,
            pendiente=Decimal("-10.000000"),
            intercepto=Decimal("5.000000"),
            r2=Decimal("0.500000"),
            mae=Decimal("1.000000"),
            rmse=Decimal("1.200000"),
            prediccion_siguiente=Decimal("0.000000"),
            metadata={},
        )
        guardar_proyecciones_consumo_futuro(corrida, horizonte_dias=5)
        for proy in ProyeccionConsumoFuturo.objects.filter(tendencia=tendencia):
            self.assertGreaterEqual(float(proy.valor_diario), 0.0)

        ref = date(2027, 3, 1)
        cantidades = [20, 15, 10, 5]
        dias = self._crear_serie_out_elegible(self.producto, ref, cantidades)
        _, tendencia_etl = self._ejecutar_etl_y_persistir_proyecciones(dias, horizonte=7)
        for proy in ProyeccionConsumoFuturo.objects.filter(tendencia=tendencia_etl):
            self.assertGreaterEqual(float(proy.valor_diario), 0.0)

    def test_tc04_3_resumen_de_proyecciones_por_periodo(self):
        """TC04.3 — Resumen por ventanas calendario y lista vacía sin error."""
        fecha_fin = date(2027, 4, 25)
        horizonte = 35
        filas = generar_proyecciones_consumo(
            intercepto=10,
            pendiente=1,
            puntos_usados=2,
            fecha_fin=fecha_fin,
            horizonte_dias=horizonte,
        )

        resumen = resumen_proyecciones_completo(filas, fecha_fin)
        self.assertIsNotNone(resumen["consumo_proyectado_semana"])
        self.assertIsNotNone(resumen["consumo_proyectado_mes"])
        self.assertEqual(resumen["periodo_semana_desde"], date(2027, 4, 26))
        self.assertEqual(resumen["periodo_mes_desde"], date(2027, 5, 1))

        por_fecha = {f["fecha"]: f["valor_diario"] for f in filas}

        def suma_rango(desde, hasta):
            total = 0.0
            d = desde
            while d <= hasta:
                total += float(por_fecha.get(d, 0))
                d += timedelta(days=1)
            return total

        self.assertAlmostEqual(
            resumen["consumo_proyectado_semana"],
            suma_rango(resumen["periodo_semana_desde"], resumen["periodo_semana_hasta"]),
            places=4,
        )

        resumen_vacio = resumen_proyecciones_completo([], fecha_fin)
        self.assertIsNone(resumen_vacio["consumo_proyectado_semana"])
        self.assertIsNone(resumen_vacio["periodo_semana_desde"])
