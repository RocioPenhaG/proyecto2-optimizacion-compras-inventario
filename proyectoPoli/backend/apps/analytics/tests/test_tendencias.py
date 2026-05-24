"""Tests backend/API — TC01, TC02, TC03 (regresión, pendiente, tablas de tendencia)."""
from datetime import date, timedelta

from django.utils import timezone
from rest_framework.test import APIClient

from apps.inventory.models import StockProducto
from apps.products.models import Producto
from apps.users.models import Role, User

from ..etl import ejecutar_etl_analitico
from ..models import CorridaAnalitica, HechoConsumo, ResultadoTendenciaLineal
from ..proyecciones import cantidad_entera
from ..views import calcular_reposicion_sugerida_tendencia

from ._base import BaseAnalyticsETLTestCase


class AnalyticsTendenciasTestCase(BaseAnalyticsETLTestCase):
    """TC01, TC02 y TC03 — ETL de tendencias lineales y API por corrida."""

    def setUp(self):
        super().setUp()
        self.producto.sku = "TEND-TC01"
        self.producto.nombre = "Producto tendencias TC01"
        self.producto.save(update_fields=["sku", "nombre"])

    def _hechos_out_por_dia(self, producto=None):
        producto = producto or self.producto
        return {
            h.fecha: h.cantidad_total
            for h in HechoConsumo.objects.filter(
                producto=producto,
                tipo_movimiento="OUT",
            ).order_by("fecha")
        }

    def test_tc01_1_agrupacion_consumo_antes_de_regresion(self):
        """TC01.1 — El ETL agrega OUT por producto y día antes de calcular la tendencia."""
        ref = date(2026, 9, 10)
        dia_1 = ref - timedelta(days=2)
        dia_2 = ref - timedelta(days=1)
        dia_3 = ref

        self._crear_mov_stock("IN", 1000, dia_1 - timedelta(days=1))
        self._crear_mov_stock("OUT", 10, dia_1)
        self._crear_mov_stock("OUT", 5, dia_1)
        self._crear_mov_stock("OUT", 20, dia_2)
        self._crear_mov_stock("OUT", 30, dia_3)

        corrida = ejecutar_etl_analitico(fecha_desde=dia_1, fecha_hasta=dia_3)
        corrida.refresh_from_db()
        self.assertEqual(corrida.estado, CorridaAnalitica.Estado.SUCCESS)

        resultado = ResultadoTendenciaLineal.objects.get(corrida=corrida, producto=self.producto)
        self.assertEqual(resultado.puntos_usados, 3)

        hechos = self._hechos_out_por_dia()
        self.assertEqual(len(hechos), 3)
        self.assertEqual(hechos[dia_1], 15)
        self.assertEqual(hechos[dia_2], 20)
        self.assertEqual(hechos[dia_3], 30)
        self.assertEqual(resultado.fecha_inicio, dia_1)
        self.assertEqual(resultado.fecha_fin, dia_3)

    def test_tc01_2_metricas_de_ajuste_serie_no_constante(self):
        """TC01.2 — Serie no constante persiste R², MAE y RMSE junto con coeficientes."""
        ref = date(2026, 10, 5)
        cantidades = [5, 8, 12, 15]
        dias = [ref + timedelta(days=i) for i in range(len(cantidades))]

        self._crear_mov_stock("IN", 2000, dias[0] - timedelta(days=1))
        for dia, cantidad in zip(dias, cantidades):
            self._crear_mov_stock("OUT", cantidad, dia)

        corrida = ejecutar_etl_analitico(fecha_desde=dias[0], fecha_hasta=dias[-1])
        corrida.refresh_from_db()
        self.assertEqual(corrida.estado, CorridaAnalitica.Estado.SUCCESS)
        self.assertEqual(corrida.error_detalle, "")

        resultado = ResultadoTendenciaLineal.objects.get(corrida=corrida, producto=self.producto)
        self.assertEqual(resultado.puntos_usados, 4)
        self.assertIsNotNone(resultado.pendiente)
        self.assertIsNotNone(resultado.intercepto)
        self.assertIsNotNone(resultado.r2)
        self.assertIsNotNone(resultado.mae)
        self.assertIsNotNone(resultado.rmse)
        self.assertNotAlmostEqual(float(resultado.pendiente), 0.0, places=6)
        self.assertGreaterEqual(float(resultado.r2), 0.0)
        self.assertGreater(float(resultado.mae), 0.0)
        self.assertGreater(float(resultado.rmse), 0.0)

        hechos = self._hechos_out_por_dia()
        self.assertEqual([hechos[d] for d in dias], cantidades)

    def test_tc02_1_tendencia_creciente_genera_pendiente_positiva_y_prediccion_mayor(self):
        """TC02.1 — Serie creciente: pendiente > 0 y predicción mayor al último consumo."""
        ref = date(2026, 11, 1)
        cantidades = [2, 4, 6, 8]
        dias = [ref + timedelta(days=i) for i in range(len(cantidades))]

        self._crear_mov_stock("IN", 500, dias[0] - timedelta(days=1))
        for dia, cantidad in zip(dias, cantidades):
            self._crear_mov_stock("OUT", cantidad, dia)

        corrida = ejecutar_etl_analitico(fecha_desde=dias[0], fecha_hasta=dias[-1])
        corrida.refresh_from_db()
        self.assertEqual(corrida.estado, CorridaAnalitica.Estado.SUCCESS)

        resultado = ResultadoTendenciaLineal.objects.get(corrida=corrida, producto=self.producto)
        self.assertEqual(resultado.puntos_usados, 4)
        self.assertGreater(float(resultado.pendiente), 0.0)
        self.assertGreater(float(resultado.prediccion_siguiente), float(cantidades[-1]))

    def test_tc02_2_api_expone_pendiente_y_prediccion_siguiente(self):
        """TC02.2 — API de tendencias por corrida expone pendiente y predicción de la BD."""
        ref = date(2026, 11, 10)
        cantidades = [3, 5, 7, 9]
        dias = [ref + timedelta(days=i) for i in range(len(cantidades))]

        self._crear_mov_stock("IN", 500, dias[0] - timedelta(days=1))
        for dia, cantidad in zip(dias, cantidades):
            self._crear_mov_stock("OUT", cantidad, dia)

        corrida = ejecutar_etl_analitico(fecha_desde=dias[0], fecha_hasta=dias[-1])
        resultado = ResultadoTendenciaLineal.objects.get(corrida=corrida, producto=self.producto)

        usuario = User.objects.create_user(username="compras_tc02", password="test", role=Role.COMPRAS)
        client = APIClient()
        client.force_authenticate(user=usuario)

        resp = client.get(f"/api/analytics/etl/corridas/{corrida.id}/tendencias/")
        self.assertEqual(resp.status_code, 200)

        fila = next(r for r in resp.json()["results"] if r["producto_id"] == self.producto.id)
        self.assertEqual(fila["pendiente"], cantidad_entera(resultado.pendiente))
        self.assertEqual(fila["prediccion_siguiente"], cantidad_entera(resultado.prediccion_siguiente))

    def test_tc03_1_corrida_con_multiples_productos_crea_resultados_por_producto_elegible(self):
        """TC03.1 — Varios productos elegibles generan filas en ResultadoTendenciaLineal."""
        ref = date(2026, 12, 1)
        productos = [
            Producto.objects.create(sku="TEND-M01", nombre="Multi 1", stock_minimo=0),
            Producto.objects.create(sku="TEND-M02", nombre="Multi 2", stock_minimo=0),
            Producto.objects.create(sku="TEND-M03", nombre="Multi 3", stock_minimo=0),
        ]
        producto_no_elegible = Producto.objects.create(
            sku="TEND-M04", nombre="Multi 4 no elegible", stock_minimo=0
        )
        dia_ini = ref
        dia_fin = ref + timedelta(days=2)

        for idx, producto in enumerate(productos):
            cantidades = [10 + idx, 12 + idx, 14 + idx]
            self._crear_serie_out_elegible(producto, ref, cantidades)

        self._crear_mov_stock("IN", 500, dia_ini - timedelta(days=1), producto=producto_no_elegible)
        self._crear_mov_stock("OUT", 5, dia_ini, producto=producto_no_elegible)
        self._crear_mov_stock("OUT", 7, dia_ini + timedelta(days=1), producto=producto_no_elegible)

        corrida = ejecutar_etl_analitico(fecha_desde=dia_ini, fecha_hasta=dia_fin)
        corrida.refresh_from_db()
        self.assertEqual(corrida.estado, CorridaAnalitica.Estado.SUCCESS)

        resultados = ResultadoTendenciaLineal.objects.filter(corrida=corrida)
        self.assertGreater(resultados.count(), 0)
        self.assertLessEqual(resultados.count(), corrida.productos_candidatos_tendencia)
        self.assertEqual(resultados.count(), len(productos))

        ids_productos = {p.id for p in productos}
        for resultado in resultados:
            self.assertEqual(resultado.corrida_id, corrida.id)
            self.assertIn(resultado.producto_id, ids_productos)
            self.assertEqual(resultado.periodicidad, "DAILY")
            self.assertGreaterEqual(resultado.puntos_usados, 3)

        self.assertFalse(
            ResultadoTendenciaLineal.objects.filter(
                corrida=corrida, producto=producto_no_elegible
            ).exists()
        )

    def test_tc03_2_api_lista_tendencias_por_corrida_con_columnas_operativas(self):
        """TC03.2 — API de tendencias por corrida expone columnas operativas del dashboard."""
        ref = date(2026, 12, 15)
        cantidades = [4, 6, 8, 10]
        dias = self._crear_serie_out_elegible(self.producto, ref, cantidades)
        self.producto.stock_minimo = 25
        self.producto.save(update_fields=["stock_minimo"])
        stock, _ = StockProducto.objects.get_or_create(
            producto=self.producto,
            defaults={"qty_on_hand": 20},
        )
        stock.qty_on_hand = 20
        stock.save(update_fields=["qty_on_hand"])

        corrida = ejecutar_etl_analitico(fecha_desde=dias[0], fecha_hasta=dias[-1])
        resultado = ResultadoTendenciaLineal.objects.get(corrida=corrida, producto=self.producto)

        usuario = User.objects.create_user(username="compras_tc03", password="test", role=Role.COMPRAS)
        client = APIClient()
        client.force_authenticate(user=usuario)

        resp = client.get(f"/api/analytics/etl/corridas/{corrida.id}/tendencias/")
        self.assertEqual(resp.status_code, 200)

        fila = next(r for r in resp.json()["results"] if r["producto_id"] == self.producto.id)
        self.assertEqual(fila["stock_actual"], 20)
        self.assertEqual(fila["stock_minimo"], 25)
        self.assertEqual(fila["puntos_usados"], resultado.puntos_usados)
        self.assertEqual(fila["pendiente"], cantidad_entera(resultado.pendiente))
        self.assertEqual(fila["prediccion_siguiente"], cantidad_entera(resultado.prediccion_siguiente))
        self.assertEqual(fila["fecha_inicio"], str(resultado.fecha_inicio))
        self.assertEqual(fila["fecha_fin"], str(resultado.fecha_fin))

        cantidad_esperada, criterio_esperado = calcular_reposicion_sugerida_tendencia(
            20,
            25,
            cantidad_entera(resultado.pendiente),
            cantidad_entera(resultado.prediccion_siguiente),
        )
        self.assertEqual(fila["cantidad_sugerida_reposicion"], cantidad_esperada)
        self.assertEqual(fila["criterio_reposicion"], criterio_esperado)
