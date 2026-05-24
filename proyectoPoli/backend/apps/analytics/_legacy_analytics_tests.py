"""Tests para el mÃ³dulo analytics (ETL, resumen mensual, API hÃ¡bitos)."""
from datetime import date, datetime, timedelta, timezone as datetime_timezone
from decimal import Decimal
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.products.models import Producto
from apps.inventory.models import MovStock, StockProducto
from apps.users.models import User, Role
from apps.purchases.models import SolicitudDetalle, SolicitudInsumo

from .models import (
    HechoConsumo,
    ResumenConsumoMensual,
    CorridaAnalitica,
    ProyeccionConsumoFuturo,
    ResultadoTendenciaLineal,
)
from .etl import (
    ejecutar_etl_analitico,
    actualizar_resumen_consumo_mensual,
    generar_proyecciones_consumo,
    guardar_proyecciones_consumo_futuro,
    _fecha_mov_local,
)
from types import SimpleNamespace

from .proyecciones import (
    ALERTA_DATOS_INSUFICIENTES,
    ALERTA_PROYECCION_AJUSTADA,
    ALERTA_STOCK_INSUFICIENTE,
    CONFIABILIDAD_ALTA,
    CONFIABILIDAD_BAJA,
    CONFIABILIDAD_DATOS_INSUFICIENTES,
    CONFIABILIDAD_MEDIA,
    CONFIABILIDAD_TENDENCIA_INESTABLE,
    ajustar_consumo_mensual,
    calcular_campos_vista_operativa,
    cantidad_entera,
    construir_reporte_proyecciones_futuras,
    evaluar_accion_sugerida,
    evaluar_cobertura_estimada_texto,
    evaluar_confiabilidad,
    evaluar_estado_operativo,
    mapa_proyecciones_operativas,
    reposicion_orientativa,
    resumen_proyecciones_completo,
    serializar_resumen_proyecciones_api,
)
from .tasks import run_etl_analitico_d1
from .views import calcular_reposicion_sugerida_tendencia
from .demanda_consumo import riesgo_y_recomendacion_demanda
from .services.retencion import limpiar_datos_analiticos


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
        # Fechas fijas en el mismo mes: con date.today() el dÃ­a 1 del mes fallaba
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
        - dias_con_movimiento (solo dÃ­as con OUT)
        - promedio_diario = cantidad_salidas / dias_con_movimiento
        - redondeo a 2 decimales
        - exclusiÃ³n de movimientos IN
        """
        ref = date(2026, 6, 20)
        # OUT en 3 dÃ­as diferentes del mismo mes.
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
        """Valida redondeo esperado cuando el promedio es periÃ³dico (10/6 = 1.666...)."""
        ref = date(2026, 7, 10)
        cantidades = [1, 1, 2, 2, 2, 2]  # total=10 en 6 dÃ­as
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
        self.assertEqual(
            ProyeccionConsumoFuturo.objects.filter(tendencia=resultado).count(),
            30,
        )
        p1 = ProyeccionConsumoFuturo.objects.get(tendencia=resultado, horizonte_dias=1)
        self.assertAlmostEqual(float(p1.valor_diario), float(resultado.prediccion_siguiente), places=4)

    def test_proyecciones_truncan_valores_negativos(self):
        filas = generar_proyecciones_consumo(
            intercepto=5,
            pendiente=-10,
            puntos_usados=3,
            fecha_fin=date(2026, 5, 1),
            horizonte_dias=3,
        )
        self.assertEqual(len(filas), 3)
        self.assertEqual(filas[0]["valor_diario"], 0.0)

    def test_resumen_proyecciones_periodos_calendario(self):
        fecha_fin = date(2026, 4, 25)  # sÃ¡bado
        filas = generar_proyecciones_consumo(
            intercepto=10,
            pendiente=1,
            puntos_usados=2,
            fecha_fin=fecha_fin,
            horizonte_dias=35,
        )
        resumen = resumen_proyecciones_completo(filas, fecha_fin)
        self.assertIsNotNone(resumen["consumo_proyectado_semana"])
        self.assertIsNotNone(resumen["consumo_proyectado_mes"])
        self.assertIsNotNone(resumen["consumo_proyectado_trimestre"])
        self.assertEqual(resumen["periodo_semana_desde"], date(2026, 4, 27))
        self.assertEqual(resumen["periodo_mes_desde"], date(2026, 5, 1))

    def test_serializar_resumen_proyecciones_enteros(self):
        resumen = serializar_resumen_proyecciones_api(
            {
                "consumo_proyectado_7d": 10.6,
                "consumo_proyectado_semana": 25.4,
                "consumo_proyectado_mes": None,
            }
        )
        self.assertEqual(resumen["consumo_proyectado_7d"], 11)
        self.assertEqual(resumen["consumo_proyectado_semana"], 25)
        self.assertIsNone(resumen["consumo_proyectado_mes"])
        self.assertEqual(cantidad_entera(18.7), 19)

    def test_evaluar_confiabilidad_r2(self):
        class T:
            def __init__(self, puntos, r2):
                self.puntos_usados = puntos
                self.r2 = r2

        self.assertEqual(evaluar_confiabilidad(T(10, Decimal("0.10")), 100, 50), CONFIABILIDAD_BAJA)
        self.assertEqual(evaluar_confiabilidad(T(10, Decimal("0.45")), 100, 50), CONFIABILIDAD_MEDIA)
        self.assertEqual(evaluar_confiabilidad(T(10, Decimal("0.85")), 100, 50), CONFIABILIDAD_ALTA)

    def test_ajustar_consumo_mensual_limite(self):
        orig, adj, flag = ajustar_consumo_mensual(1000, 100)
        self.assertEqual(orig, 1000)
        self.assertEqual(adj, 300)
        self.assertTrue(flag)

    def test_reposicion_orientativa_sin_datos(self):
        self.assertIsNone(reposicion_orientativa(5, 500, 10))

    def test_mapa_proyecciones_operativas(self):
        producto = Producto.objects.create(sku="MAP-001", nombre="Map", stock_minimo=0)
        corrida = CorridaAnalitica.objects.create(
            task_id="map-proy",
            estado=CorridaAnalitica.Estado.SUCCESS,
            metodo=CorridaAnalitica.Metodo.MANUAL,
        )
        ResultadoTendenciaLineal.objects.create(
            corrida=corrida,
            producto=producto,
            variable_objetivo="consumo_out",
            periodicidad="DAILY",
            fecha_inicio=date(2026, 4, 20),
            fecha_fin=date(2026, 4, 22),
            puntos_usados=3,
            pendiente=Decimal("2.000000"),
            intercepto=Decimal("10.000000"),
            r2=Decimal("1.000000"),
            mae=Decimal("0.000000"),
            rmse=Decimal("0.000000"),
            prediccion_siguiente=Decimal("16.000000"),
            metadata={},
        )
        guardar_proyecciones_consumo_futuro(corrida, horizonte_dias=14)
        m = mapa_proyecciones_operativas({producto.id})
        self.assertIn(producto.id, m)
        self.assertGreater(m[producto.id]["consumo_promedio_diario_proyectado"], 0)

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
        Movimiento en UTC que cae en calendario local 2026-04-28 (ART) debe agruparse en ese dÃ­a,
        no en 2026-04-29 (evita borrado parcial + insert duplicado en segunda corrida).
        """
        timezone.activate("America/Argentina/Buenos_Aires")
        # 2026-04-29 02:00 UTC == 2026-04-28 23:00 ART â†’ dÃ­a local 28.
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
        """_fecha_mov_local alinea con el criterio de dÃ­a local del ETL."""
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

    def test_consumo_mensual_respeta_rango_fechas_no_mes_completo(self):
        ref = timezone.localdate() - timedelta(days=2)
        HechoConsumo.objects.create(producto=self.p, fecha=ref, tipo_movimiento="OUT", cantidad_total=100)
        HechoConsumo.objects.create(
            producto=self.p, fecha=ref - timedelta(days=5), tipo_movimiento="OUT", cantidad_total=50
        )
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(
            "/api/analytics/consumo-mensual/",
            {"desde": (ref - timedelta(days=1)).isoformat(), "hasta": ref.isoformat()},
        )
        self.assertEqual(resp.status_code, 200)
        rows = resp.json()["consumo_mensual"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["cantidad_total"], 100)
        self.assertEqual(rows[0]["mes"], ref.month)

    def test_habitos_resumen_consumo_mensual_respeta_filtro(self):
        ref = timezone.localdate() - timedelta(days=1)
        HechoConsumo.objects.create(producto=self.p, fecha=ref, tipo_movimiento="OUT", cantidad_total=30)
        HechoConsumo.objects.create(
            producto=self.p, fecha=ref - timedelta(days=20), tipo_movimiento="OUT", cantidad_total=70
        )
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(
            "/api/analytics/habitos-resumen/",
            {"desde": (ref - timedelta(days=5)).isoformat(), "hasta": ref.isoformat()},
        )
        self.assertEqual(resp.status_code, 200)
        rows = resp.json()["consumo_mensual"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["cantidad_total"], 30)

    def test_resumen_consumo_default_sin_params_ultimos_30_dias(self):
        today = timezone.localdate()
        ref_in = today - timedelta(days=5)
        ref_out = today - timedelta(days=40)
        HechoConsumo.objects.create(
            producto=self.p, fecha=ref_in, tipo_movimiento="OUT", cantidad_total=100
        )
        HechoConsumo.objects.create(
            producto=self.p, fecha=ref_out, tipo_movimiento="OUT", cantidad_total=40
        )
        self.client.force_authenticate(user=self.user)
        resp = self.client.get("/api/analytics/resumen-consumo/")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertFalse(body.get("filtro_historico"))
        self.assertEqual(body["total_salidas"], 100)

    def test_resumen_consumo_solo_desde_calcula_hasta_30_dias(self):
        desde = timezone.localdate() - timedelta(days=10)
        esperado_hasta = min(desde + timedelta(days=30), timezone.localdate())
        self.client.force_authenticate(user=self.user)
        resp = self.client.get("/api/analytics/resumen-consumo/", {"desde": desde.isoformat()})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["filtro_desde"], desde.isoformat())
        self.assertEqual(body["filtro_hasta"], esperado_hasta.isoformat())

    def test_resumen_consumo_acota_rango_mayor_90_dias(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(
            "/api/analytics/resumen-consumo/",
            {"desde": "2026-01-01", "hasta": "2026-12-31"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        desde = date.fromisoformat(body["filtro_desde"])
        hasta = date.fromisoformat(body["filtro_hasta"])
        self.assertLessEqual((hasta - desde).days, 90)

    def test_resumen_consumo_desde_hecho(self):
        ref = timezone.localdate() - timedelta(days=1)
        HechoConsumo.objects.create(producto=self.p, fecha=ref, tipo_movimiento="OUT", cantidad_total=100)
        HechoConsumo.objects.create(
            producto=self.p, fecha=ref - timedelta(days=1), tipo_movimiento="OUT", cantidad_total=50
        )
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(
            "/api/analytics/resumen-consumo/",
            {"desde": (ref - timedelta(days=1)).isoformat(), "hasta": ref.isoformat()},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["total_salidas"], 150)
        self.assertEqual(body["productos_distintos"], 1)
        self.assertEqual(body["dias_con_consumo"], 2)

    def test_top_productos_consumidos(self):
        p2 = Producto.objects.create(sku="TST-003", nombre="Otro", stock_minimo=0)
        ref = timezone.localdate() - timedelta(days=1)
        HechoConsumo.objects.create(producto=self.p, fecha=ref, tipo_movimiento="OUT", cantidad_total=10)
        HechoConsumo.objects.create(producto=p2, fecha=ref, tipo_movimiento="OUT", cantidad_total=99)
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(
            "/api/analytics/top-productos-consumidos/",
            {
                "desde": (ref - timedelta(days=7)).isoformat(),
                "hasta": ref.isoformat(),
                "limit": 5,
            },
        )
        self.assertEqual(resp.status_code, 200)
        top = resp.json()["top_productos"]
        self.assertEqual(len(top), 2)
        self.assertEqual(top[0]["producto_id"], p2.id)
        self.assertEqual(top[0]["cantidad_total"], 99)

    def test_demanda_vs_consumo_sin_auth(self):
        resp = self.client.get("/api/analytics/demanda-vs-consumo/")
        self.assertEqual(resp.status_code, 401)

    def test_demanda_vs_consumo_merge_y_clasificacion(self):
        p_alto = Producto.objects.create(sku="DVC-A", nombre="Alcohol Gel", stock_minimo=0)
        p_bajo = Producto.objects.create(sku="DVC-B", nombre="Mascarillas", stock_minimo=0)
        p_ok = Producto.objects.create(sku="DVC-C", nombre="Guantes", stock_minimo=0)
        ref = timezone.localdate() - timedelta(days=2)
        sol = SolicitudInsumo.objects.create(solicitante=self.user, destino="X")
        sol.creado_en = timezone.make_aware(datetime.combine(ref - timedelta(days=5), datetime.min.time()))
        sol.save(update_fields=["creado_en"])
        SolicitudDetalle.objects.create(solicitud=sol, producto=p_alto, cantidad=160)
        SolicitudDetalle.objects.create(solicitud=sol, producto=p_bajo, cantidad=100)
        SolicitudDetalle.objects.create(solicitud=sol, producto=p_ok, cantidad=90)

        HechoConsumo.objects.create(
            producto=p_alto, fecha=ref, tipo_movimiento="OUT", cantidad_total=140
        )
        HechoConsumo.objects.create(
            producto=p_bajo, fecha=ref, tipo_movimiento="OUT", cantidad_total=115
        )
        HechoConsumo.objects.create(
            producto=p_ok, fecha=ref, tipo_movimiento="OUT", cantidad_total=88
        )

        self.client.force_authenticate(user=self.user)
        desde = (ref - timedelta(days=7)).isoformat()
        hasta = ref.isoformat()
        resp = self.client.get(
            "/api/analytics/demanda-vs-consumo/",
            {"desde": desde, "hasta": hasta, "limit": 20},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["desde"], desde)
        self.assertEqual(body["hasta"], hasta)
        self.assertIn("periodo", body)
        self.assertEqual(body["periodo"]["desde"], desde)
        self.assertEqual(body["periodo"]["hasta"], hasta)
        self.assertGreaterEqual(body["periodo"]["dias"], 1)
        self.assertEqual(body["resumen"]["total_solicitado"], 350)
        self.assertEqual(body["resumen"]["total_consumido"], 343)
        self.assertEqual(body["resumen"]["mayor_solicitud_que_consumo"], 1)
        self.assertEqual(body["resumen"]["mayor_consumo_que_solicitud"], 1)
        self.assertEqual(body["resumen"]["coherentes"], 1)
        self.assertIn("riesgo_alto", body["resumen"])
        self.assertIn("baja_cobertura", body["resumen"])
        self.assertIn("consumo_mayor_solicitud", body["resumen"])
        self.assertIn("demanda_coherente", body["resumen"])

        by_sku = {r["sku"]: r for r in body["resultados"]}
        self.assertEqual(by_sku["DVC-A"]["diferencia"], 20)
        self.assertEqual(by_sku["DVC-A"]["estado"], "solicitado_mayor")
        self.assertEqual(by_sku["DVC-B"]["diferencia"], -15)
        self.assertEqual(by_sku["DVC-B"]["estado"], "consumo_mayor")
        self.assertEqual(by_sku["DVC-C"]["diferencia"], 2)
        self.assertEqual(by_sku["DVC-C"]["estado"], "coherente")
        self.assertIn("demanda_vs_consumo", by_sku["DVC-A"])
        self.assertIn("habito_detectado", by_sku["DVC-A"])
        self.assertIn("cobertura_texto", by_sku["DVC-A"])
        self.assertIn("riesgo", by_sku["DVC-A"])
        self.assertIn("recomendacion", by_sku["DVC-A"])

    def test_demanda_vs_consumo_incluye_producto_con_stock(self):
        p_stock = Producto.objects.create(sku="DVC-STOCK", nombre="Con stock", stock_minimo=2)
        StockProducto.objects.create(producto=p_stock, qty_on_hand=9)
        self.client.force_authenticate(user=self.user)
        ref = timezone.localdate()
        resp = self.client.get(
            "/api/analytics/demanda-vs-consumo/",
            {
                "desde": (ref - timedelta(days=7)).isoformat(),
                "hasta": ref.isoformat(),
                "limit": 50,
            },
        )
        self.assertEqual(resp.status_code, 200)
        by_sku = {r["sku"]: r for r in resp.json()["resultados"]}
        self.assertIn("DVC-STOCK", by_sku)
        self.assertEqual(by_sku["DVC-STOCK"]["cobertura_texto"], "Sin consumo reciente")

    def test_demanda_vs_consumo_solo_consumo(self):
        p = Producto.objects.create(sku="DVC-ONLY-C", nombre="Solo Consumo", stock_minimo=0)
        ref = timezone.localdate() - timedelta(days=1)
        HechoConsumo.objects.create(producto=p, fecha=ref, tipo_movimiento="OUT", cantidad_total=42)
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(
            "/api/analytics/demanda-vs-consumo/",
            {"desde": (ref - timedelta(days=7)).isoformat(), "hasta": ref.isoformat()},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(len(body["resultados"]), 1)
        r0 = body["resultados"][0]
        self.assertEqual(r0["cantidad_solicitada"], 0)
        self.assertEqual(r0["cantidad_consumida"], 42)
        self.assertEqual(r0["estado"], "consumo_mayor")

    def test_demanda_vs_consumo_cobertura_historica(self):
        p = Producto.objects.create(sku="DVC-COB", nombre="Cobertura hist", stock_minimo=5)
        StockProducto.objects.create(producto=p, qty_on_hand=14)
        ref = timezone.localdate() - timedelta(days=1)
        for i in range(7):
            HechoConsumo.objects.create(
                producto=p,
                fecha=ref - timedelta(days=i),
                tipo_movimiento="OUT",
                cantidad_total=2,
            )
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(
            "/api/analytics/demanda-vs-consumo/",
            {"desde": (ref - timedelta(days=6)).isoformat(), "hasta": ref.isoformat()},
        )
        self.assertEqual(resp.status_code, 200)
        row = next(r for r in resp.json()["resultados"] if r["sku"] == "DVC-COB")
        self.assertIn("días", row["cobertura_texto"])
        self.assertNotIn("consumo_proyectado_semana", row)

    @patch("apps.analytics.date_range._today")
    def test_demanda_vs_consumo_sin_fechas_usa_ultimos_30_dias(self, mock_today):
        mock_today.return_value = date(2026, 5, 18)
        self.client.force_authenticate(user=self.user)
        resp = self.client.get("/api/analytics/demanda-vs-consumo/")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["periodo"]["hasta"], "2026-05-18")
        self.assertEqual(body["periodo"]["desde"], "2026-04-18")
        self.assertEqual(body["periodo"]["dias"], 31)

    def test_demanda_vs_consumo_filtra_consumo_y_solicitudes_por_rango(self):
        p = Producto.objects.create(sku="DVC-RNG", nombre="Rango", stock_minimo=0)
        ref = date(2026, 5, 10)
        sol = SolicitudInsumo.objects.create(solicitante=self.user, destino="X")
        sol.creado_en = timezone.make_aware(datetime.combine(ref, datetime.min.time()))
        sol.save(update_fields=["creado_en"])
        SolicitudDetalle.objects.create(solicitud=sol, producto=p, cantidad=50)
        HechoConsumo.objects.create(
            producto=p, fecha=ref, tipo_movimiento="OUT", cantidad_total=40
        )
        HechoConsumo.objects.create(
            producto=p,
            fecha=ref - timedelta(days=60),
            tipo_movimiento="OUT",
            cantidad_total=999,
        )
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(
            "/api/analytics/demanda-vs-consumo/",
            {
                "desde": (ref - timedelta(days=7)).isoformat(),
                "hasta": ref.isoformat(),
            },
        )
        body = resp.json()
        row = body["resultados"][0]
        self.assertEqual(row["cantidad_solicitada"], 50)
        self.assertEqual(row["cantidad_consumida"], 40)

    def test_demanda_vs_consumo_usa_ultima_tendencia_etl(self):
        p = Producto.objects.create(sku="DVC-TREND", nombre="Trend", stock_minimo=0)
        corrida_vieja = CorridaAnalitica.objects.create(
            task_id="dvc-old",
            estado=CorridaAnalitica.Estado.SUCCESS,
            metodo=CorridaAnalitica.Metodo.MANUAL,
            fecha_ejecucion=timezone.now() - timedelta(days=90),
        )
        corrida_nueva = CorridaAnalitica.objects.create(
            task_id="dvc-new",
            estado=CorridaAnalitica.Estado.SUCCESS,
            metodo=CorridaAnalitica.Metodo.MANUAL,
            fecha_ejecucion=timezone.now(),
        )
        ResultadoTendenciaLineal.objects.create(
            corrida=corrida_vieja,
            producto=p,
            variable_objetivo="consumo_out",
            periodicidad="DAILY",
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 1, 10),
            puntos_usados=5,
            pendiente=Decimal("-5.000000"),
            intercepto=Decimal("10.000000"),
            r2=Decimal("0.900000"),
            mae=Decimal("1.000000"),
            rmse=Decimal("1.200000"),
            prediccion_siguiente=Decimal("5.000000"),
            metadata={},
        )
        ResultadoTendenciaLineal.objects.create(
            corrida=corrida_nueva,
            producto=p,
            variable_objetivo="consumo_out",
            periodicidad="DAILY",
            fecha_inicio=date(2026, 4, 1),
            fecha_fin=date(2026, 4, 10),
            puntos_usados=5,
            pendiente=Decimal("3.000000"),
            intercepto=Decimal("10.000000"),
            r2=Decimal("0.900000"),
            mae=Decimal("1.000000"),
            rmse=Decimal("1.200000"),
            prediccion_siguiente=Decimal("15.000000"),
            metadata={},
        )
        ref = timezone.localdate()
        HechoConsumo.objects.create(
            producto=p, fecha=ref, tipo_movimiento="OUT", cantidad_total=10
        )
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(
            "/api/analytics/demanda-vs-consumo/",
            {"desde": (ref - timedelta(days=7)).isoformat(), "hasta": ref.isoformat()},
        )
        row = resp.json()["resultados"][0]
        self.assertEqual(row["habito_detectado"], "Consumo creciente")

    def test_riesgo_alto_exige_consumo_fuerte(self):
        riesgo, _ = riesgo_y_recomendacion_demanda(5, 10, 5, "Consumo esporádico", "coherente")
        self.assertEqual(riesgo, "Medio")
        riesgo_alto, _ = riesgo_y_recomendacion_demanda(5, 10, 5, "Consumo creciente", "coherente")
        self.assertEqual(riesgo_alto, "Alto")

    def test_consumo_mayor_genera_riesgo_medio(self):
        riesgo, _ = riesgo_y_recomendacion_demanda(100, 10, 30, "Consumo esporádico", "consumo_mayor")
        self.assertEqual(riesgo, "Medio")

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


class RunEtlAnaliticoD1MetodoTestCase(TestCase):
    """Origen de corrida: MANUAL por defecto; SCHEDULED solo con kwarg (p. ej. Celery Beat)."""

    @patch("apps.analytics.tasks.ejecutar_etl_analitico", side_effect=lambda **kw: kw["corrida"])
    def test_run_d1_sin_metodo_registra_manual(self, _mock_etl):
        run_etl_analitico_d1.run()
        corrida = CorridaAnalitica.objects.get()
        self.assertEqual(corrida.metodo, CorridaAnalitica.Metodo.MANUAL)

    @patch("apps.analytics.tasks.ejecutar_etl_analitico", side_effect=lambda **kw: kw["corrida"])
    def test_run_d1_metodo_scheduled_como_beat(self, _mock_etl):
        run_etl_analitico_d1.run(metodo=CorridaAnalitica.Metodo.SCHEDULED)
        corrida = CorridaAnalitica.objects.get()
        self.assertEqual(corrida.metodo, CorridaAnalitica.Metodo.SCHEDULED)

    def test_celery_beat_schedule_pasa_metodo_scheduled(self):
        entry = settings.CELERY_BEAT_SCHEDULE["etl-analitico-d1-diario"]
        self.assertEqual(entry["kwargs"], {"metodo": "SCHEDULED"})


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
        self.assertEqual(
            mock_apply.call_args.kwargs.get("kwargs"),
            {"metodo": CorridaAnalitica.Metodo.MANUAL},
        )
        corrida = CorridaAnalitica.objects.get(task_id=task_id)
        self.assertEqual(corrida.estado, CorridaAnalitica.Estado.QUEUED)
        self.assertEqual(corrida.metodo, CorridaAnalitica.Metodo.MANUAL)
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
        """Listado de tendencias usa puede_ver_analytics (Compras sÃ­)."""
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

    def _tendencia_corrida_producto(self, sku, stock_qty, stock_minimo, pendiente, prediccion):
        producto = Producto.objects.create(sku=sku, nombre=f"Prod {sku}", stock_minimo=stock_minimo)
        StockProducto.objects.create(producto=producto, qty_on_hand=stock_qty)
        corrida = CorridaAnalitica.objects.create(
            task_id=f"tend-rep-{sku}",
            estado=CorridaAnalitica.Estado.SUCCESS,
            metodo=CorridaAnalitica.Metodo.MANUAL,
        )
        tendencia = ResultadoTendenciaLineal.objects.create(
            corrida=corrida,
            producto=producto,
            variable_objetivo="consumo_out",
            periodicidad="DAILY",
            fecha_inicio=date(2026, 5, 1),
            fecha_fin=date(2026, 5, 10),
            puntos_usados=5,
            pendiente=Decimal(str(pendiente)),
            intercepto=Decimal("10.000000"),
            r2=Decimal("0.900000"),
            mae=Decimal("1.000000"),
            rmse=Decimal("1.200000"),
            prediccion_siguiente=Decimal(str(prediccion)),
            metadata={},
        )
        return corrida, tendencia

    def test_reposicion_sugerida_stock_bajo_tendencia_creciente(self):
        cantidad, criterio = calcular_reposicion_sugerida_tendencia(20, 30, 2, 5)
        self.assertEqual(cantidad, 15)
        self.assertEqual(criterio, "Stock bajo con tendencia creciente")

    def test_reposicion_sugerida_stock_bajo_sin_crecimiento(self):
        cantidad, criterio = calcular_reposicion_sugerida_tendencia(20, 30, 0, 5)
        self.assertEqual(cantidad, 10)
        self.assertEqual(criterio, "Stock bajo")

        cantidad_neg, criterio_neg = calcular_reposicion_sugerida_tendencia(20, 30, -1, 5)
        self.assertEqual(cantidad_neg, 10)
        self.assertEqual(criterio_neg, "Stock bajo")

    def test_reposicion_sugerida_stock_suficiente(self):
        cantidad, criterio = calcular_reposicion_sugerida_tendencia(35, 30, 2, 5)
        self.assertEqual(cantidad, 0)
        self.assertEqual(criterio, "Stock suficiente")

    def test_tendencias_api_incluye_reposicion_sugerida(self):
        corrida, _ = self._tendencia_corrida_producto(
            "REP-A", stock_qty=20, stock_minimo=30, pendiente=2, prediccion=5
        )
        self.client.force_authenticate(user=self.compras)
        resp = self.client.get(f"/api/analytics/etl/corridas/{corrida.id}/tendencias/")
        self.assertEqual(resp.status_code, 200)
        fila = resp.json()["results"][0]
        self.assertEqual(fila["stock_actual"], 20)
        self.assertEqual(fila["stock_minimo"], 30)
        self.assertEqual(fila["cantidad_sugerida_reposicion"], 15)
        self.assertEqual(fila["criterio_reposicion"], "Stock bajo con tendencia creciente")
        self.assertEqual(fila["pendiente"], 2)
        self.assertEqual(fila["prediccion_siguiente"], 5)

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
        self.assertEqual(body["prediccion"]["valor"], 18)
        self.assertNotIn("proyecciones", body)
        self.assertNotIn("resumen_proyecciones", body)

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


class RetencionDatosAnaliticosTestCase(TestCase):
    """Retención de corridas/tendencias analíticas sin tocar agregados operativos."""

    def setUp(self):
        self.producto = Producto.objects.create(sku="RET-001", nombre="Retención", stock_minimo=0)

    def _corrida_antigua(self, suffix="old"):
        return CorridaAnalitica.objects.create(
            task_id=f"ret-{suffix}",
            estado=CorridaAnalitica.Estado.SUCCESS,
            metodo=CorridaAnalitica.Metodo.MANUAL,
            fecha_ejecucion=timezone.now() - timedelta(days=200),
        )

    def _corrida_reciente(self, suffix="new"):
        return CorridaAnalitica.objects.create(
            task_id=f"ret-{suffix}",
            estado=CorridaAnalitica.Estado.SUCCESS,
            metodo=CorridaAnalitica.Metodo.MANUAL,
            fecha_ejecucion=timezone.now() - timedelta(days=10),
        )

    def _tendencia(self, corrida):
        return ResultadoTendenciaLineal.objects.create(
            corrida=corrida,
            producto=self.producto,
            variable_objetivo="consumo_out",
            periodicidad="DAILY",
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 1, 10),
            puntos_usados=5,
            pendiente=Decimal("1.000000"),
            intercepto=Decimal("10.000000"),
            r2=Decimal("0.900000"),
            mae=Decimal("1.000000"),
            rmse=Decimal("1.200000"),
            prediccion_siguiente=Decimal("12.000000"),
            metadata={},
        )

    def test_dry_run_no_elimina_registros(self):
        corrida = self._corrida_antigua()
        self._tendencia(corrida)
        resultado = limpiar_datos_analiticos(dias_retencion=180, dry_run=True)
        self.assertTrue(resultado.dry_run)
        self.assertEqual(resultado.corridas_antiguas, 1)
        self.assertEqual(resultado.tendencias_asociadas, 1)
        self.assertEqual(CorridaAnalitica.objects.count(), 1)
        self.assertEqual(ResultadoTendenciaLineal.objects.count(), 1)

    def test_elimina_proyecciones_asociadas_a_corrida_antigua(self):
        corrida = self._corrida_antigua("proy")
        self._tendencia(corrida)
        guardar_proyecciones_consumo_futuro(corrida, horizonte_dias=5)
        self.assertGreater(ProyeccionConsumoFuturo.objects.filter(corrida=corrida).count(), 0)

        resultado = limpiar_datos_analiticos(dias_retencion=180, dry_run=False)
        self.assertGreater(resultado.eliminadas_proyecciones, 0)
        self.assertEqual(ProyeccionConsumoFuturo.objects.filter(corrida_id=corrida.id).count(), 0)

    def test_elimina_corridas_antiguas_y_tendencias(self):
        corrida_vieja = self._corrida_antigua()
        tendencia_vieja = self._tendencia(corrida_vieja)
        corrida_nueva = self._corrida_reciente()
        tendencia_nueva = self._tendencia(corrida_nueva)

        resultado = limpiar_datos_analiticos(dias_retencion=180, dry_run=False)
        self.assertFalse(resultado.dry_run)
        self.assertEqual(resultado.eliminadas_corridas, 1)
        self.assertGreaterEqual(resultado.eliminadas_tendencias, 1)

        self.assertFalse(CorridaAnalitica.objects.filter(id=corrida_vieja.id).exists())
        self.assertFalse(ResultadoTendenciaLineal.objects.filter(id=tendencia_vieja.id).exists())
        self.assertTrue(CorridaAnalitica.objects.filter(id=corrida_nueva.id).exists())
        self.assertTrue(ResultadoTendenciaLineal.objects.filter(id=tendencia_nueva.id).exists())

    def test_conserva_hecho_consumo_y_resumen_mensual(self):
        corrida = self._corrida_antigua()
        self._tendencia(corrida)
        HechoConsumo.objects.create(
            producto=self.producto,
            fecha=date(2026, 2, 1),
            tipo_movimiento="OUT",
            cantidad_total=7,
        )
        ResumenConsumoMensual.objects.create(
            producto=self.producto,
            anio=2026,
            mes=2,
            cantidad_salidas=7,
            promedio_diario=Decimal("7.00"),
            dias_con_movimiento=1,
        )

        limpiar_datos_analiticos(dias_retencion=180, dry_run=False)

        self.assertEqual(HechoConsumo.objects.count(), 1)
        self.assertEqual(ResumenConsumoMensual.objects.count(), 1)

    def test_acepta_dias_retencion_personalizado(self):
        corrida = CorridaAnalitica.objects.create(
            task_id="ret-custom",
            estado=CorridaAnalitica.Estado.SUCCESS,
            metodo=CorridaAnalitica.Metodo.MANUAL,
            fecha_ejecucion=timezone.now() - timedelta(days=400),
        )
        self._tendencia(corrida)

        limpiar_datos_analiticos(dias_retencion=365, dry_run=False)
        self.assertFalse(CorridaAnalitica.objects.filter(id=corrida.id).exists())

        corrida_reciente = self._corrida_reciente("custom-ok")
        limpiar_datos_analiticos(dias_retencion=365, dry_run=False)
        self.assertTrue(CorridaAnalitica.objects.filter(id=corrida_reciente.id).exists())

    def test_management_command_dry_run(self):
        from django.core.management import call_command
        from io import StringIO

        self._tendencia(self._corrida_antigua())
        out = StringIO()
        call_command("limpiar_datos_analiticos", "--dry-run", stdout=out)
        self.assertIn("Modo simulación", out.getvalue())
        self.assertEqual(CorridaAnalitica.objects.count(), 1)
