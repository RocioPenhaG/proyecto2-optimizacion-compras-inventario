"""Tests para el módulo analytics (ETL, resumen mensual, API hábitos)."""
from datetime import date, datetime, timedelta, timezone as datetime_timezone
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.products.models import Producto
from apps.inventory.models import MovStock
from apps.users.models import User, Role

from .models import HechoConsumo, ResumenConsumoMensual, CorridaAnalitica, ResultadoTendenciaLineal
from .etl import ejecutar_etl_analitico, actualizar_resumen_consumo_mensual, _fecha_mov_local


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
        corrida.refresh_from_db()
        self.assertEqual(corrida.productos_candidatos_tendencia, 1)

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
        corrida.refresh_from_db()
        self.assertEqual(corrida.productos_candidatos_tendencia, 1)
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

    def test_etl_solo_fecha_desde_no_borra_hechos_anteriores(self):
        """Solo fecha_desde: borrar hechos con fecha >= corte; conservar fechas anteriores."""
        corte = date(2026, 3, 10)
        anterior = corte - timedelta(days=5)
        HechoConsumo.objects.create(
            producto=self.p, fecha=anterior, tipo_movimiento="OUT", cantidad_total=42
        )
        self._crear_mov_stock_con_fecha(
            self.p, "OUT", 5, timezone.make_aware(datetime(2026, 3, 10, 12, 0, 0))
        )
        ejecutar_etl_analitico(fecha_desde=corte, fecha_hasta=None)
        h_ant = HechoConsumo.objects.get(producto=self.p, fecha=anterior, tipo_movimiento="OUT")
        self.assertEqual(h_ant.cantidad_total, 42)
        h_corte = HechoConsumo.objects.get(producto=self.p, fecha=corte, tipo_movimiento="OUT")
        self.assertEqual(h_corte.cantidad_total, 5)

    def test_etl_solo_fecha_hasta_no_borra_hechos_posteriores(self):
        """Solo fecha_hasta: borrar hechos con fecha <= corte; conservar fechas posteriores."""
        corte = date(2026, 4, 10)
        posterior = corte + timedelta(days=5)
        HechoConsumo.objects.create(
            producto=self.p, fecha=posterior, tipo_movimiento="OUT", cantidad_total=99
        )
        self._crear_mov_stock_con_fecha(
            self.p, "OUT", 7, timezone.make_aware(datetime(2026, 4, 8, 10, 0, 0))
        )
        ejecutar_etl_analitico(fecha_desde=None, fecha_hasta=corte)
        h_post = HechoConsumo.objects.get(producto=self.p, fecha=posterior, tipo_movimiento="OUT")
        self.assertEqual(h_post.cantidad_total, 99)
        h_mov = HechoConsumo.objects.get(producto=self.p, fecha=date(2026, 4, 8), tipo_movimiento="OUT")
        self.assertEqual(h_mov.cantidad_total, 7)

    @override_settings(TIME_ZONE="America/Argentina/Buenos_Aires", USE_TZ=True)
    def test_etl_idempotente_mismo_dia_varios_movimientos(self):
        """Reprocesar el mismo rango no debe violar unique ni duplicar filas en HechoConsumo."""
        timezone.activate("America/Argentina/Buenos_Aires")
        d = date(2026, 4, 28)
        for minute in range(10):
            self._crear_mov_stock_con_fecha(
                self.p, "OUT", 1, timezone.make_aware(datetime(2026, 4, 28, 10, minute, 0))
            )
        ejecutar_etl_analitico(fecha_desde=d, fecha_hasta=d)
        outs = HechoConsumo.objects.filter(producto=self.p, tipo_movimiento="OUT", fecha=d)
        self.assertEqual(outs.count(), 1)
        self.assertEqual(outs.get().cantidad_total, 10)
        ejecutar_etl_analitico(fecha_desde=d, fecha_hasta=d)
        outs = HechoConsumo.objects.filter(producto=self.p, tipo_movimiento="OUT", fecha=d)
        self.assertEqual(outs.count(), 1)
        self.assertEqual(outs.get().cantidad_total, 10)

    @override_settings(TIME_ZONE="America/Argentina/Buenos_Aires", USE_TZ=True)
    def test_etl_hecho_fecha_local_sin_desfase_por_utc(self):
        """
        Movimiento en UTC que cae en calendario local 2026-04-28 (ART) debe agruparse en ese día,
        no en 2026-04-29 (evita borrado parcial + insert duplicado en segunda corrida).
        """
        timezone.activate("America/Argentina/Buenos_Aires")
        # 2026-04-29 02:00 UTC == 2026-04-28 23:00 ART → día local 28.
        dt_utc = timezone.make_aware(datetime(2026, 4, 29, 2, 0, 0), datetime_timezone.utc)
        self._crear_mov_stock_con_fecha(self.p, "OUT", 5, dt_utc)
        ejecutar_etl_analitico(fecha_desde=date(2026, 4, 28), fecha_hasta=date(2026, 4, 28))
        h = HechoConsumo.objects.get(producto=self.p, tipo_movimiento="OUT")
        self.assertEqual(h.fecha, date(2026, 4, 28))
        self.assertEqual(h.cantidad_total, 5)
        self.assertFalse(HechoConsumo.objects.filter(producto=self.p, fecha=date(2026, 4, 29)).exists())
        ejecutar_etl_analitico(fecha_desde=date(2026, 4, 28), fecha_hasta=date(2026, 4, 28))
        self.assertEqual(
            HechoConsumo.objects.filter(producto=self.p, tipo_movimiento="OUT", fecha=date(2026, 4, 28)).count(),
            1,
        )

    @override_settings(TIME_ZONE="America/Argentina/Buenos_Aires", USE_TZ=True)
    def test_fecha_mov_local_coherente_con_trunc(self):
        """_fecha_mov_local alinea con el criterio de día local del ETL."""
        timezone.activate("America/Argentina/Buenos_Aires")
        dt_utc = timezone.make_aware(datetime(2026, 4, 29, 2, 0, 0), datetime_timezone.utc)
        self.assertEqual(_fecha_mov_local(dt_utc), date(2026, 4, 28))


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

    def test_resumen_consumo_desde_hecho(self):
        ref = date(2026, 8, 10)
        HechoConsumo.objects.create(producto=self.p, fecha=ref, tipo_movimiento="OUT", cantidad_total=100)
        HechoConsumo.objects.create(
            producto=self.p, fecha=ref - timedelta(days=1), tipo_movimiento="OUT", cantidad_total=50
        )
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(
            "/api/analytics/resumen-consumo/",
            {"desde": "2026-08-01", "hasta": "2026-08-31"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["total_salidas"], 150)
        self.assertEqual(body["productos_distintos"], 1)
        self.assertEqual(body["dias_con_consumo"], 2)

    def test_top_productos_consumidos(self):
        p2 = Producto.objects.create(sku="TST-003", nombre="Otro", stock_minimo=0)
        ref = date(2026, 9, 5)
        HechoConsumo.objects.create(producto=self.p, fecha=ref, tipo_movimiento="OUT", cantidad_total=10)
        HechoConsumo.objects.create(producto=p2, fecha=ref, tipo_movimiento="OUT", cantidad_total=99)
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(
            "/api/analytics/top-productos-consumidos/",
            {"desde": "2026-09-01", "hasta": "2026-09-30", "limit": 5},
        )
        self.assertEqual(resp.status_code, 200)
        top = resp.json()["top_productos"]
        self.assertEqual(len(top), 2)
        self.assertEqual(top[0]["producto_id"], p2.id)
        self.assertEqual(top[0]["cantidad_total"], 99)

    def test_ultima_corrida(self):
        CorridaAnalitica.objects.create(
            estado=CorridaAnalitica.Estado.SUCCESS,
            metodo=CorridaAnalitica.Metodo.MANUAL,
            mensaje="ok",
        )
        self.client.force_authenticate(user=self.user)
        resp = self.client.get("/api/analytics/ultima-corrida/")
        self.assertEqual(resp.status_code, 200)
        self.assertIsNotNone(resp.json()["corrida"])
        self.assertEqual(resp.json()["corrida"]["estado"], CorridaAnalitica.Estado.SUCCESS)
        self.assertIn("metodo", resp.json()["corrida"])


class AnalyticsCorridaETLTestCase(TestCase):
    """Encolado D-1, estado por task_id y permisos de corridas."""

    def setUp(self):
        self.gerencia = User.objects.create_user(username="gerencia", password="x", role=Role.GERENCIA)
        self.compras = User.objects.create_user(username="compras2", password="x", role=Role.COMPRAS)
        self.funcionario = User.objects.create_user(username="func", password="x", role=Role.FUNCIONARIO)
        self.client = APIClient()

    @patch("apps.analytics.views.run_etl_analitico_d1.apply_async")
    def test_run_d1_crea_corrida_queued_antes_de_worker(self, mock_apply):
        self.client.force_authenticate(user=self.gerencia)
        resp = self.client.post("/api/analytics/etl/run-d1/")
        self.assertEqual(resp.status_code, 202)
        body = resp.json()
        task_id = body["task_id"]
        self.assertEqual(body["status"], "QUEUED")
        mock_apply.assert_called_once()
        self.assertEqual(mock_apply.call_args.kwargs.get("task_id"), task_id)
        corrida = CorridaAnalitica.objects.get(task_id=task_id)
        self.assertEqual(corrida.estado, CorridaAnalitica.Estado.QUEUED)
        self.assertEqual(corrida.metodo, CorridaAnalitica.Metodo.API)
        self.assertIsNotNone(corrida.queued_at)

    @patch("apps.analytics.views.run_etl_analitico_d1.apply_async")
    def test_estado_corrida_no_404_mientras_queued(self, _mock_apply):
        self.client.force_authenticate(user=self.gerencia)
        resp = self.client.post("/api/analytics/etl/run-d1/")
        task_id = resp.json()["task_id"]
        st = self.client.get(f"/api/analytics/etl/status/{task_id}/")
        self.assertEqual(st.status_code, 200)
        self.assertEqual(st.json()["estado"], CorridaAnalitica.Estado.QUEUED)
        self.assertEqual(st.json()["task_id"], task_id)

    def test_corridas_endpoints_permisos(self):
        """
        Encolar ETL D-1: solo Gerencia/Administrador (403 Compras y Funcionario).
        Listado y estado de corridas: Compras/Contable/Gerencia/Admin (puede_ver_analytics); Funcionario 403.
        """
        corrida = CorridaAnalitica.objects.create(
            task_id="manual-test-id",
            estado=CorridaAnalitica.Estado.QUEUED,
            metodo=CorridaAnalitica.Metodo.MANUAL,
        )
        self.client.force_authenticate(user=self.funcionario)
        self.assertEqual(self.client.post("/api/analytics/etl/run-d1/").status_code, 403)
        self.assertEqual(
            self.client.get(f"/api/analytics/etl/status/{corrida.task_id}/").status_code,
            403,
        )
        self.assertEqual(self.client.get("/api/analytics/etl/corridas/").status_code, 403)

        self.client.force_authenticate(user=self.compras)
        self.assertEqual(self.client.post("/api/analytics/etl/run-d1/").status_code, 403)
        self.assertEqual(
            self.client.get(f"/api/analytics/etl/status/{corrida.task_id}/").status_code,
            200,
        )
        self.assertEqual(self.client.get("/api/analytics/etl/corridas/").status_code, 200)

    def test_tendencias_corrida_permite_compras(self):
        """Listado de tendencias usa puede_ver_analytics (Compras sí)."""
        corrida = CorridaAnalitica.objects.create(
            task_id="tend-test",
            estado=CorridaAnalitica.Estado.SUCCESS,
            metodo=CorridaAnalitica.Metodo.MANUAL,
        )
        self.client.force_authenticate(user=self.compras)
        r = self.client.get(f"/api/analytics/etl/corridas/{corrida.id}/tendencias/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["corrida_id"], corrida.id)

    def test_tendencias_corrida_funcionario_403(self):
        corrida = CorridaAnalitica.objects.create(
            task_id="tend-func",
            estado=CorridaAnalitica.Estado.SUCCESS,
            metodo=CorridaAnalitica.Metodo.MANUAL,
        )
        self.client.force_authenticate(user=self.funcionario)
        self.assertEqual(
            self.client.get(f"/api/analytics/etl/corridas/{corrida.id}/tendencias/").status_code,
            403,
        )

    def test_detalle_visual_tendencia_ok(self):
        producto = Producto.objects.create(sku="DET-001", nombre="Det", stock_minimo=0)
        corrida = CorridaAnalitica.objects.create(
            task_id="tend-visual",
            estado=CorridaAnalitica.Estado.SUCCESS,
            metodo=CorridaAnalitica.Metodo.MANUAL,
        )
        HechoConsumo.objects.create(
            producto=producto,
            fecha=date(2026, 4, 24),
            tipo_movimiento="OUT",
            cantidad_total=12,
        )
        HechoConsumo.objects.create(
            producto=producto,
            fecha=date(2026, 4, 25),
            tipo_movimiento="OUT",
            cantidad_total=15,
        )
        tendencia = ResultadoTendenciaLineal.objects.create(
            corrida=corrida,
            producto=producto,
            variable_objetivo="consumo_out",
            periodicidad="DAILY",
            fecha_inicio=date(2026, 4, 24),
            fecha_fin=date(2026, 4, 25),
            puntos_usados=2,
            pendiente=Decimal("3.000000"),
            intercepto=Decimal("12.000000"),
            r2=Decimal("1.000000"),
            mae=Decimal("0.000000"),
            rmse=Decimal("0.000000"),
            prediccion_siguiente=Decimal("18.000000"),
            metadata={},
        )
        self.client.force_authenticate(user=self.compras)
        resp = self.client.get(f"/api/analytics/etl/tendencias/{tendencia.id}/visual/")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["producto"], producto.nombre)
        self.assertEqual(body["sku"], producto.sku)
        self.assertEqual(len(body["historico"]), 2)
        self.assertEqual(len(body["tendencia"]), 2)
        self.assertEqual(body["prediccion"]["fecha"], "2026-04-26")
        self.assertEqual(body["prediccion"]["valor"], 18.0)

    def test_detalle_visual_tendencia_funcionario_403(self):
        corrida = CorridaAnalitica.objects.create(
            task_id="tend-visual-403",
            estado=CorridaAnalitica.Estado.SUCCESS,
            metodo=CorridaAnalitica.Metodo.MANUAL,
        )
        producto = Producto.objects.create(sku="DET-002", nombre="Det2", stock_minimo=0)
        tendencia = ResultadoTendenciaLineal.objects.create(
            corrida=corrida,
            producto=producto,
            variable_objetivo="consumo_out",
            periodicidad="DAILY",
            fecha_inicio=date(2026, 4, 24),
            fecha_fin=date(2026, 4, 25),
            puntos_usados=2,
            pendiente=Decimal("1.000000"),
            intercepto=Decimal("10.000000"),
            r2=Decimal("1.000000"),
            mae=Decimal("0.000000"),
            rmse=Decimal("0.000000"),
            prediccion_siguiente=Decimal("12.000000"),
            metadata={},
        )
        self.client.force_authenticate(user=self.funcionario)
        resp = self.client.get(f"/api/analytics/etl/tendencias/{tendencia.id}/visual/")
        self.assertEqual(resp.status_code, 403)

    @patch("apps.analytics.views.run_etl_analitico_d1.apply_async")
    def test_run_d1_permite_administrador(self, _mock_apply):
        admin = User.objects.create_superuser(username="admin_etl", email="a@a.com", password="x")
        self.client.force_authenticate(user=admin)
        self.assertEqual(self.client.post("/api/analytics/etl/run-d1/").status_code, 202)
