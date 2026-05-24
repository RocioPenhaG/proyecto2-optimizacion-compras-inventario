"""Tests backend/API — TC07 (hábitos de consumo e integración ETL → demanda vs consumo)."""
from datetime import date, timedelta
from unittest.mock import patch

from rest_framework.test import APIClient

from apps.inventory.models import StockProducto
from apps.users.models import Role, User

from ..demanda_consumo import habito_detectado
from ..etl import ejecutar_etl_analitico
from ..models import CorridaAnalitica, ResultadoTendenciaLineal

from ._base import BaseAnalyticsETLTestCase


class AnalyticsHabitosTestCase(BaseAnalyticsETLTestCase):
    """TC07.1 y TC07.3 — Hábito detectado desde pendiente ETL (demanda vs consumo)."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.usuario = User.objects.create_user(
            username="tc07_compras",
            password="x",
            role=Role.COMPRAS,
        )

    def _get_demanda_vs_consumo(self, desde, hasta):
        self.client.force_authenticate(user=self.usuario)
        return self.client.get(
            "/api/analytics/demanda-vs-consumo/",
            {"desde": desde.isoformat(), "hasta": hasta.isoformat()},
        )

    def _fila_producto(self, resp):
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        return next(r for r in body["resultados"] if r["producto_id"] == self.producto.id), body

    def _assert_periodo_api_valido(self, body, desde=None, hasta=None):
        for key in ("desde", "hasta", "periodo"):
            self.assertIn(key, body)
        periodo = body["periodo"]
        api_desde = date.fromisoformat(periodo["desde"])
        api_hasta = date.fromisoformat(periodo["hasta"])
        self.assertLessEqual(api_desde, api_hasta)
        self.assertGreaterEqual(periodo["dias"], 1)
        if desde is not None and hasta is not None:
            self.assertEqual(body["desde"], str(desde))
            self.assertEqual(body["hasta"], str(hasta))

    def test_tc07_1_demanda_vs_consumo_clasifica_consumo_creciente_por_pendiente(self):
        """TC07.1 — Serie OUT creciente → pendiente ETL > 0.2 → Consumo creciente en la API."""
        ref = date(2026, 8, 1)
        cantidades = [2, 4, 6, 8]
        dias = self._crear_serie_out_elegible(self.producto, ref, cantidades)
        desde, hasta = dias[0], dias[-1]

        with patch("apps.analytics.date_range._today", return_value=date(2026, 9, 1)):
            corrida = ejecutar_etl_analitico(fecha_desde=desde, fecha_hasta=hasta)
            self.assertEqual(corrida.estado, CorridaAnalitica.Estado.SUCCESS)

            tendencia = ResultadoTendenciaLineal.objects.get(corrida=corrida, producto=self.producto)
            pendiente_etl = float(tendencia.pendiente)
            self.assertGreater(pendiente_etl, 0.2)

            resp = self._get_demanda_vs_consumo(desde, hasta)
            fila, body = self._fila_producto(resp)

            self.assertEqual(fila["habito_detectado"], "Consumo creciente")
            habito_esperado = habito_detectado(
                pendiente_etl,
                fila["cantidad_consumida"],
                len(cantidades),
                body["periodo"]["dias"],
            )
            self.assertEqual(fila["habito_detectado"], habito_esperado)

        self.assertEqual(habito_detectado(0.21, 10, 3, 10), "Consumo creciente")
        self.assertEqual(habito_detectado(-0.21, 10, 3, 10), "Consumo decreciente")
        self.assertEqual(habito_detectado(0.15, 10, 3, 10), "Consumo estable")

    @patch("apps.analytics.date_range._today")
    def test_tc07_3_flujo_etl_persistencia_api_habito_sin_inconsistencia_producto_fechas(
        self, mock_today
    ):
        """TC07.3 — Flujo ETL → tendencia persistida → API coherente con producto y rango."""
        desde = date(2026, 4, 1)
        hasta = date(2026, 4, 6)
        mock_today.return_value = date(2026, 5, 18)
        cantidades = [12, 12, 12, 12, 12, 12]
        dias = self._crear_serie_out_elegible(self.producto, desde, cantidades)

        corrida = ejecutar_etl_analitico(fecha_desde=desde, fecha_hasta=hasta)
        self.assertEqual(corrida.estado, CorridaAnalitica.Estado.SUCCESS)

        tendencia = ResultadoTendenciaLineal.objects.get(corrida=corrida, producto=self.producto)
        self.assertEqual(tendencia.fecha_inicio, desde)
        self.assertEqual(tendencia.fecha_fin, hasta)

        pendiente_etl = float(tendencia.pendiente)
        stock, _ = StockProducto.objects.get_or_create(
            producto=self.producto,
            defaults={"qty_on_hand": 50},
        )
        stock.qty_on_hand = 50
        stock.save(update_fields=["qty_on_hand"])

        resp = self._get_demanda_vs_consumo(desde, hasta)
        body = resp.json()
        self._assert_periodo_api_valido(body, desde=desde, hasta=hasta)

        fila = next(r for r in body["resultados"] if r["producto_id"] == self.producto.id)
        self.assertEqual(fila["cantidad_consumida"], sum(cantidades))
        habito_esperado = habito_detectado(
            pendiente_etl,
            fila["cantidad_consumida"],
            len(cantidades),
            body["periodo"]["dias"],
        )
        self.assertEqual(fila["habito_detectado"], habito_esperado)
        self.assertEqual(fila["habito_detectado"], "Consumo estable")
