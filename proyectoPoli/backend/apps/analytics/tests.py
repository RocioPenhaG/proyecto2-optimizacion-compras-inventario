"""Tests para el módulo analytics (ETL, resumen mensual, API hábitos)."""
from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.products.models import Producto
from apps.inventory.models import MovStock
from apps.users.models import User, Role

from .models import HechoConsumo, ResumenConsumoMensual, CorridaAnalitica
from .etl import ejecutar_etl_analitico, actualizar_resumen_consumo_mensual


class ETLTestCase(TestCase):
    def setUp(self):
        self.p = Producto.objects.create(sku="TST-001", nombre="Test", stock_minimo=0)

    def test_etl_creates_hechos_and_corrida(self):
        MovStock.objects.create(producto=self.p, tipo="IN", cantidad=100)
        MovStock.objects.create(
            producto=self.p,
            fecha=timezone.now(),
            tipo="OUT",
            cantidad=10,
        )
        corrida = ejecutar_etl_analitico()
        self.assertEqual(corrida.estado, CorridaAnalitica.Estado.OK)
        self.assertEqual(HechoConsumo.objects.filter(producto=self.p, tipo_movimiento="OUT").count(), 1)
        self.assertEqual(HechoConsumo.objects.get(producto=self.p, tipo_movimiento="OUT").cantidad_total, 10)

    def test_actualizar_resumen_consumo_mensual(self):
        # Fechas fijas en el mismo mes: con date.today() el día 1 del mes fallaba
        # (ayer cae en el mes anterior y el resumen mensual solo sumaba un hecho).
        ref = date(2026, 6, 15)
        HechoConsumo.objects.create(producto=self.p, fecha=ref, tipo_movimiento="OUT", cantidad_total=30)
        HechoConsumo.objects.create(
            producto=self.p, fecha=ref - timedelta(days=1), tipo_movimiento="OUT", cantidad_total=10
        )
        actualizar_resumen_consumo_mensual(fecha_desde=ref - timedelta(days=5), fecha_hasta=ref)
        r = ResumenConsumoMensual.objects.get(producto=self.p, anio=ref.year, mes=ref.month)
        self.assertEqual(r.cantidad_salidas, 40)
        self.assertEqual(r.dias_con_movimiento, 2)


class AnalyticsAPITestCase(TestCase):
    def setUp(self):
        self.p = Producto.objects.create(sku="TST-002", nombre="Test2", stock_minimo=0)
        self.user = User.objects.create_user(username="compras", password="test", role=Role.COMPRAS)
        self.client = APIClient()

    def test_consumo_mensual_requires_auth(self):
        resp = self.client.get("/api/analytics/consumo-mensual/")
        self.assertEqual(resp.status_code, 401)

    def test_consumo_mensual_ok_with_role(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get("/api/analytics/consumo-mensual/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("consumo_mensual", resp.json())
        self.assertIn("filtro_desde", resp.json())
