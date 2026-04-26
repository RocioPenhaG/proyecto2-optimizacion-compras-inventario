"""Tests para el módulo analytics (ETL, resumen mensual, API hábitos)."""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.products.models import Producto
from apps.inventory.models import MovStock
from apps.users.models import User, Role

from .models import HechoConsumo, ResumenConsumoMensual, CorridaAnalitica, ResultadoTendenciaLineal
from .etl import ejecutar_etl_analitico, actualizar_resumen_consumo_mensual


class ETLTestCase(TestCase):
    def setUp(self):
        self.p = Producto.objects.create(sku="TST-001", nombre="Test", stock_minimo=0)
        self._crear_mov_stock_con_fecha(
            self.p,
            "IN",
            5000,
            timezone.now() - timedelta(days=30),
        )

    def _crear_mov_stock_con_fecha(self, producto, tipo, cantidad, fecha_dt):
        mov = MovStock.objects.create(producto=producto, tipo=tipo, cantidad=cantidad)
        MovStock.objects.filter(pk=mov.pk).update(fecha=fecha_dt)

    def test_etl_creates_hechos_and_corrida(self):
        MovStock.objects.create(producto=self.p, tipo="IN", cantidad=100)
        MovStock.objects.create(
            producto=self.p,
            fecha=timezone.now(),
            tipo="OUT",
            cantidad=10,
        )
        corrida = ejecutar_etl_analitico()
        self.assertEqual(corrida.estado, CorridaAnalitica.Estado.SUCCESS)
        self.assertIsNotNone(corrida.started_at)
        self.assertIsNotNone(corrida.finished_at)
        self.assertEqual(corrida.error_detalle, "")
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

    def test_resumen_mensual_promedio_diario_usa_solo_out_y_formula(self):
        """
        Valida:
        - cantidad_salidas mensual
        - dias_con_movimiento (solo días con OUT)
        - promedio_diario = cantidad_salidas / dias_con_movimiento
        - redondeo a 2 decimales
        - exclusión de movimientos IN
        """
        ref = date(2026, 6, 20)
        # OUT en 3 días diferentes del mismo mes.
        HechoConsumo.objects.create(producto=self.p, fecha=ref, tipo_movimiento="OUT", cantidad_total=10)
        HechoConsumo.objects.create(
            producto=self.p, fecha=ref - timedelta(days=1), tipo_movimiento="OUT", cantidad_total=10
        )
        HechoConsumo.objects.create(
            producto=self.p, fecha=ref - timedelta(days=2), tipo_movimiento="OUT", cantidad_total=11
        )
        # IN que no debe afectar el resumen de consumo.
        HechoConsumo.objects.create(producto=self.p, fecha=ref, tipo_movimiento="IN", cantidad_total=999)

        actualizar_resumen_consumo_mensual(fecha_desde=ref - timedelta(days=10), fecha_hasta=ref)
        r = ResumenConsumoMensual.objects.get(producto=self.p, anio=ref.year, mes=ref.month)

        self.assertEqual(r.cantidad_salidas, 31)
        self.assertEqual(r.dias_con_movimiento, 3)
        self.assertEqual(r.promedio_diario, Decimal("10.33"))
        self.assertEqual(r.promedio_diario, Decimal(str(round(31 / 3, 2))))

    def test_resumen_mensual_promedio_diario_redondeo_dos_decimales(self):
        """Valida redondeo esperado cuando el promedio es periódico (10/6 = 1.666...)."""
        ref = date(2026, 7, 10)
        cantidades = [1, 1, 2, 2, 2, 2]  # total=10 en 6 días
        for idx, cantidad in enumerate(cantidades):
            HechoConsumo.objects.create(
                producto=self.p,
                fecha=ref - timedelta(days=idx),
                tipo_movimiento="OUT",
                cantidad_total=cantidad,
            )

        actualizar_resumen_consumo_mensual(fecha_desde=ref - timedelta(days=10), fecha_hasta=ref)
        r = ResumenConsumoMensual.objects.get(producto=self.p, anio=ref.year, mes=ref.month)

        self.assertEqual(r.cantidad_salidas, 10)
        self.assertEqual(r.dias_con_movimiento, 6)
        self.assertEqual(r.promedio_diario, Decimal("1.67"))

    def test_tendencia_lineal_se_crea_con_tres_o_mas_puntos_out(self):
        ref = timezone.now()
        self._crear_mov_stock_con_fecha(self.p, "OUT", 10, ref - timedelta(days=2))
        self._crear_mov_stock_con_fecha(self.p, "OUT", 20, ref - timedelta(days=1))
        self._crear_mov_stock_con_fecha(self.p, "OUT", 30, ref)

        corrida = ejecutar_etl_analitico()

        resultado = ResultadoTendenciaLineal.objects.get(corrida=corrida, producto=self.p)
        self.assertEqual(resultado.corrida_id, corrida.id)
        self.assertEqual(resultado.puntos_usados, 3)
        self.assertIsNotNone(resultado.pendiente)
        self.assertIsNotNone(resultado.intercepto)
        self.assertIsNotNone(resultado.prediccion_siguiente)

    def test_tendencia_lineal_no_se_crea_con_menos_de_tres_puntos(self):
        ref = timezone.now()
        self._crear_mov_stock_con_fecha(self.p, "OUT", 10, ref - timedelta(days=1))
        self._crear_mov_stock_con_fecha(self.p, "OUT", 20, ref)

        corrida = ejecutar_etl_analitico()

        self.assertEqual(
            ResultadoTendenciaLineal.objects.filter(corrida=corrida, producto=self.p).count(),
            0,
        )

    def test_tendencia_lineal_solo_considera_movimientos_out(self):
        ref = timezone.now()
        self._crear_mov_stock_con_fecha(self.p, "OUT", 10, ref - timedelta(days=2))
        self._crear_mov_stock_con_fecha(self.p, "OUT", 20, ref - timedelta(days=1))
        self._crear_mov_stock_con_fecha(self.p, "OUT", 30, ref)
        self._crear_mov_stock_con_fecha(self.p, "IN", 500, ref - timedelta(days=2))
        self._crear_mov_stock_con_fecha(self.p, "IN", 700, ref - timedelta(days=1))
        self._crear_mov_stock_con_fecha(self.p, "IN", 900, ref)

        corrida = ejecutar_etl_analitico()

        resultado = ResultadoTendenciaLineal.objects.get(corrida=corrida, producto=self.p)
        self.assertEqual(resultado.variable_objetivo, "consumo_out")
        self.assertEqual(resultado.puntos_usados, 3)
        self.assertAlmostEqual(float(resultado.pendiente), 10.0, places=5)



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
