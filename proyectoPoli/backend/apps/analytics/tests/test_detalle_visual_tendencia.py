"""Tests backend/API — TC05 (detalle visual, reporte de proyecciones, solicitudes)."""
from datetime import date, timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework.test import APIClient

from apps.products.models import Producto
from apps.purchases.models import SolicitudDetalle, SolicitudInsumo
from apps.users.models import Role, User

from ..etl import ejecutar_etl_analitico, guardar_proyecciones_consumo_futuro
from ..models import CorridaAnalitica, HechoConsumo, ResultadoTendenciaLineal
from ..proyecciones import (
    ALERTA_DATOS_INSUFICIENTES,
    ALERTA_PROYECCION_AJUSTADA,
    CONFIABILIDAD_DATOS_INSUFICIENTES,
    cantidad_entera,
    construir_reporte_proyecciones_futuras,
)

from ._base import BaseAnalyticsETLTestCase


class AnalyticsDetalleVisualTestCase(BaseAnalyticsETLTestCase):
    """TC05 — Detalle visual de tendencia, reporte y campos en solicitudes de compra."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.compras = User.objects.create_user(
            username="tc05_compras",
            password="x",
            role=Role.COMPRAS,
        )
        self.funcionario = User.objects.create_user(
            username="tc05_sol_func",
            password="x",
            role=Role.FUNCIONARIO,
        )

    def test_tc05_1_api_detalle_visual_expone_historico_tendencia_y_prediccion(self):
        """TC05.1 — API de detalle visual devuelve histórico, tendencia y predicción siguiente."""
        ref = date(2027, 6, 10)
        cantidades = [10, 15, 20]
        dias = [ref + timedelta(days=i) for i in range(len(cantidades))]

        self._crear_mov_stock("IN", 1000, dias[0] - timedelta(days=1))
        for dia, cantidad in zip(dias, cantidades):
            self._crear_mov_stock("OUT", cantidad, dia)

        corrida = ejecutar_etl_analitico(fecha_desde=dias[0], fecha_hasta=dias[-1])
        self.assertEqual(corrida.estado, CorridaAnalitica.Estado.SUCCESS)

        tendencia = ResultadoTendenciaLineal.objects.get(corrida=corrida, producto=self.producto)
        self.client.force_authenticate(user=self.compras)
        resp = self.client.get(f"/api/analytics/etl/tendencias/{tendencia.id}/visual/")
        self.assertEqual(resp.status_code, 200)

        body = resp.json()
        hechos_por_fecha = {
            h.fecha: h.cantidad_total
            for h in HechoConsumo.objects.filter(
                producto=self.producto,
                tipo_movimiento="OUT",
                fecha__gte=tendencia.fecha_inicio,
                fecha__lte=tendencia.fecha_fin,
            ).order_by("fecha")
        }

        self.assertEqual(len(body["historico"]), len(hechos_por_fecha))
        intercepto = float(tendencia.intercepto)
        pendiente = float(tendencia.pendiente)
        for idx, punto_tend in enumerate(body["tendencia"]):
            self.assertAlmostEqual(
                punto_tend["valor"],
                intercepto + (pendiente * idx),
                places=4,
            )

        self.assertEqual(
            body["prediccion"]["fecha"],
            (tendencia.fecha_fin + timedelta(days=1)).isoformat(),
        )
        self.assertEqual(
            body["prediccion"]["valor"],
            cantidad_entera(float(tendencia.prediccion_siguiente)),
        )

    @staticmethod
    def _crear_corrida_con_tendencia(
        sku,
        fecha_inicio,
        fecha_fin,
        puntos_usados,
        consumo_diario,
        pendiente,
        intercepto,
        prediccion_siguiente,
        r2="0.850000",
        fecha_ejecucion=None,
    ):
        producto = Producto.objects.create(
            sku=sku,
            nombre=f"Producto {sku}",
            stock_minimo=0,
        )
        for offset in range((fecha_fin - fecha_inicio).days + 1):
            HechoConsumo.objects.create(
                producto=producto,
                fecha=fecha_inicio + timedelta(days=offset),
                tipo_movimiento="OUT",
                cantidad_total=consumo_diario,
            )

        corrida = CorridaAnalitica.objects.create(
            task_id=f"tc05-{sku.lower()}",
            estado=CorridaAnalitica.Estado.SUCCESS,
            metodo=CorridaAnalitica.Metodo.MANUAL,
            fecha_ejecucion=fecha_ejecucion or timezone.now(),
            parametros={"proyeccion_horizonte_dias": 35},
        )
        ResultadoTendenciaLineal.objects.create(
            corrida=corrida,
            producto=producto,
            variable_objetivo="consumo_out",
            periodicidad="DAILY",
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            puntos_usados=puntos_usados,
            pendiente=Decimal(pendiente),
            intercepto=Decimal(intercepto),
            r2=Decimal(r2),
            mae=Decimal("1.000000"),
            rmse=Decimal("1.500000"),
            prediccion_siguiente=Decimal(prediccion_siguiente),
            metadata={},
        )
        guardar_proyecciones_consumo_futuro(corrida, horizonte_dias=35)
        return producto

    def test_tc05_2_reporte_proyecciones_expone_consumo_original_y_ajustado(self):
        """TC05.2 — Reporte expone consumo original, ajustado y marca de proyección ajustada."""
        producto_ajustado = self._crear_corrida_con_tendencia(
            sku="TC05-AJ",
            fecha_inicio=date(2027, 5, 1),
            fecha_fin=date(2027, 5, 7),
            puntos_usados=7,
            consumo_diario=1,
            pendiente="25.000000",
            intercepto="5.000000",
            prediccion_siguiente="180.000000",
        )

        _, filas = construir_reporte_proyecciones_futuras()
        fila_ajustada = next(f for f in filas if f["producto_id"] == producto_ajustado.id)
        self.assertIsNotNone(fila_ajustada.get("consumo_mes_original"))
        self.assertIsNotNone(fila_ajustada.get("consumo_mes_ajustado"))
        self.assertTrue(fila_ajustada["proyeccion_ajustada"])
        self.assertEqual(fila_ajustada["alerta"], ALERTA_PROYECCION_AJUSTADA)

        producto_insuf = self._crear_corrida_con_tendencia(
            sku="TC05-INS",
            fecha_inicio=date(2027, 6, 1),
            fecha_fin=date(2027, 6, 3),
            puntos_usados=3,
            consumo_diario=5,
            pendiente="2.000000",
            intercepto="10.000000",
            prediccion_siguiente="16.000000",
            r2="0.950000",
            fecha_ejecucion=timezone.now() + timedelta(seconds=5),
        )

        _, filas_insuf = construir_reporte_proyecciones_futuras()
        fila_insuf = next(f for f in filas_insuf if f["producto_id"] == producto_insuf.id)
        self.assertIn("proyeccion_ajustada", fila_insuf)
        self.assertIsInstance(fila_insuf["proyeccion_ajustada"], bool)
        self.assertEqual(fila_insuf["confiabilidad"], CONFIABILIDAD_DATOS_INSUFICIENTES)
        self.assertEqual(fila_insuf["alerta"], ALERTA_DATOS_INSUFICIENTES)

    def test_tc05_3_solicitudes_exponen_alerta_por_proyeccion_de_consumo(self):
        """TC05.3 — API de solicitudes expone campos de alerta (regla deshabilitada: False / [])."""
        producto = Producto.objects.create(
            sku="TC05-SOL",
            nombre="Producto solicitud TC05",
            stock_minimo=0,
        )
        fecha_inicio = date(2027, 7, 1)
        fecha_fin = date(2027, 7, 7)
        for offset in range(7):
            HechoConsumo.objects.create(
                producto=producto,
                fecha=fecha_inicio + timedelta(days=offset),
                tipo_movimiento="OUT",
                cantidad_total=3,
            )
        corrida = CorridaAnalitica.objects.create(
            task_id="tc05-sol-proy",
            estado=CorridaAnalitica.Estado.SUCCESS,
            metodo=CorridaAnalitica.Metodo.MANUAL,
            parametros={"proyeccion_horizonte_dias": 30},
        )
        ResultadoTendenciaLineal.objects.create(
            corrida=corrida,
            producto=producto,
            variable_objetivo="consumo_out",
            periodicidad="DAILY",
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            puntos_usados=7,
            pendiente=Decimal("1.000000"),
            intercepto=Decimal("10.000000"),
            r2=Decimal("0.900000"),
            mae=Decimal("0.500000"),
            rmse=Decimal("0.700000"),
            prediccion_siguiente=Decimal("17.000000"),
            metadata={},
        )
        guardar_proyecciones_consumo_futuro(corrida, horizonte_dias=30)

        solicitud = SolicitudInsumo.objects.create(
            solicitante=self.funcionario,
            destino="Depósito TC05",
        )
        SolicitudDetalle.objects.create(solicitud=solicitud, producto=producto, cantidad=10)

        self.client.force_authenticate(user=self.compras)
        resp_lista = self.client.get("/api/purchases/solicitudes/")
        self.assertEqual(resp_lista.status_code, 200)
        body_lista = resp_lista.json()
        items = body_lista["results"] if isinstance(body_lista, dict) and "results" in body_lista else body_lista
        fila_lista = next(item for item in items if item["id"] == solicitud.id)
        self.assertFalse(fila_lista["alerta_proyeccion_consumo"])

        resp_detalle = self.client.get(f"/api/purchases/solicitudes/{solicitud.id}/")
        self.assertEqual(resp_detalle.status_code, 200)
        body = resp_detalle.json()
        self.assertFalse(body["alerta_proyeccion_consumo"])
        self.assertEqual(body["alertas_proyeccion"], [])
