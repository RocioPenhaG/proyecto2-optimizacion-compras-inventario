from decimal import Decimal

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.inventory.models import MovStock, StockProducto
from apps.products.models import Producto
from apps.users.models import Role, User

from .models import EstadoSolicitud, SolicitudDetalle, SolicitudInsumo


class SolicitudesAprobacionRulesTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.compras = User.objects.create_user(
            username="c_apr",
            password="x",
            role=Role.COMPRAS,
        )
        self.gerencia = User.objects.create_user(
            username="g_apr",
            password="x",
            role=Role.GERENCIA,
        )
        self.func = User.objects.create_user(
            username="f_apr",
            password="x",
            role=Role.FUNCIONARIO,
        )
        self.prod_barato = Producto.objects.create(
            sku="B-1",
            nombre="Barato",
            costo_promedio=Decimal("5.00"),
        )
        self.prod_caro = Producto.objects.create(
            sku="C-1",
            nombre="Caro",
            costo_promedio=Decimal("50000.00"),
        )
        StockProducto.objects.create(producto=self.prod_barato, qty_on_hand=100)
        StockProducto.objects.create(producto=self.prod_caro, qty_on_hand=100)

    def _solicitud_con(self, producto, cantidad=3):
        s = SolicitudInsumo.objects.create(
            solicitante=self.func,
            destino="Test",
        )
        SolicitudDetalle.objects.create(solicitud=s, producto=producto, cantidad=cantidad)
        return s

    def test_compras_aprueba_aunque_producto_tenga_flag_requiere_gerencia(self):
        """El flag en catálogo no activa Gerencia; solo importa el stock."""
        p = Producto.objects.create(
            sku="FLAG-1",
            nombre="Marcado",
            costo_promedio=Decimal("1.00"),
            requiere_aprobacion_gerencia=True,
        )
        StockProducto.objects.create(producto=p, qty_on_hand=50)
        s = self._solicitud_con(p, cantidad=2)
        s.estado = EstadoSolicitud.EN_REVISION
        s.save()
        self.client.force_authenticate(self.compras)
        r = self.client.patch(
            f"/api/purchases/solicitudes/{s.pk}/",
            {"estado": EstadoSolicitud.COMPRA_ACEPTADA},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_compras_aprueba_con_stock_sin_gerencia(self):
        s = self._solicitud_con(self.prod_barato)
        s.estado = EstadoSolicitud.EN_REVISION
        s.save()
        self.client.force_authenticate(self.compras)
        r = self.client.patch(
            f"/api/purchases/solicitudes/{s.pk}/",
            {"estado": EstadoSolicitud.COMPRA_ACEPTADA},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_compras_aprueba_producto_caro_si_hay_stock(self):
        """El costo del producto no activa Gerencia; con stock Compras aprueba."""
        s = self._solicitud_con(self.prod_caro)
        s.estado = EstadoSolicitud.EN_REVISION
        s.save()
        self.client.force_authenticate(self.compras)
        r = self.client.patch(
            f"/api/purchases/solicitudes/{s.pk}/",
            {"estado": EstadoSolicitud.COMPRA_ACEPTADA},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_gerencia_no_ve_fuera_catalogo_en_solicitado(self):
        s = self._solicitud_con_item_fuera_catalogo(EstadoSolicitud.SOLICITADO)
        self.client.force_authenticate(self.compras)
        self.assertEqual(self.client.get("/api/purchases/solicitudes/").status_code, status.HTTP_200_OK)
        compras_ids = [
            x["id"]
            for x in (
                self.client.get("/api/purchases/solicitudes/").json().get("results")
                or self.client.get("/api/purchases/solicitudes/").json()
            )
        ]
        self.assertIn(s.pk, compras_ids)

        self.client.force_authenticate(self.gerencia)
        r_list = self.client.get("/api/purchases/solicitudes/")
        self.assertEqual(r_list.status_code, status.HTTP_200_OK)
        body = r_list.json()
        items = body["results"] if isinstance(body, dict) else body
        self.assertNotIn(s.pk, [x["id"] for x in items])

        r_detail = self.client.get(f"/api/purchases/solicitudes/{s.pk}/")
        self.assertEqual(r_detail.status_code, status.HTTP_404_NOT_FOUND)

    def test_gerencia_ve_fuera_catalogo_tras_solicitar_aprobacion(self):
        s = self._solicitud_con_item_fuera_catalogo(EstadoSolicitud.SOLICITADO)
        self.client.force_authenticate(self.compras)
        r_rev = self.client.patch(
            f"/api/purchases/solicitudes/{s.pk}/",
            {
                "estado": EstadoSolicitud.EN_REVISION,
                "accion": "SOLICITAR_GERENCIA",
                "tipo_destino_compra": "INVENTARIO",
            },
            format="json",
        )
        self.assertEqual(r_rev.status_code, status.HTTP_200_OK)

        self.client.force_authenticate(self.gerencia)
        r_list = self.client.get("/api/purchases/solicitudes/")
        items = r_list.json()["results"] if isinstance(r_list.json(), dict) else r_list.json()
        self.assertIn(s.pk, [x["id"] for x in items])
        self.assertEqual(
            self.client.get(f"/api/purchases/solicitudes/{s.pk}/").status_code,
            status.HTTP_200_OK,
        )

    def test_gerencia_no_aprueba_solicitud_catalogo(self):
        s = self._solicitud_con(self.prod_barato)
        s.estado = EstadoSolicitud.EN_REVISION
        s.save()
        self.client.force_authenticate(self.gerencia)
        r = self.client.patch(
            f"/api/purchases/solicitudes/{s.pk}/",
            {"estado": EstadoSolicitud.COMPRA_ACEPTADA},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("catálogo", r.json()["detail"].lower())

    def test_compras_no_aprueba_catalogo_sin_stock(self):
        StockProducto.objects.filter(producto=self.prod_barato).update(qty_on_hand=2)
        s = self._solicitud_con(self.prod_barato, cantidad=5)
        s.estado = EstadoSolicitud.EN_REVISION
        s.save()
        self.client.force_authenticate(self.compras)
        r = self.client.patch(
            f"/api/purchases/solicitudes/{s.pk}/",
            {"estado": EstadoSolicitud.COMPRA_ACEPTADA},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("stock inferior", r.json()["detail"].lower())
        self.assertFalse(MovStock.objects.filter(ref_tipo="SOLICITUD", ref_id=s.pk).exists())

    def test_compras_aprueba_catalogo_tras_reponer_stock(self):
        StockProducto.objects.filter(producto=self.prod_barato).update(qty_on_hand=2)
        s = self._solicitud_con(self.prod_barato, cantidad=5)
        s.estado = EstadoSolicitud.EN_REVISION
        s.save()
        self.client.force_authenticate(self.compras)
        r_bloqueado = self.client.patch(
            f"/api/purchases/solicitudes/{s.pk}/",
            {"estado": EstadoSolicitud.COMPRA_ACEPTADA},
            format="json",
        )
        self.assertEqual(r_bloqueado.status_code, status.HTTP_400_BAD_REQUEST)

        StockProducto.objects.filter(producto=self.prod_barato).update(qty_on_hand=10)
        r_ok = self.client.patch(
            f"/api/purchases/solicitudes/{s.pk}/",
            {"estado": EstadoSolicitud.COMPRA_ACEPTADA},
            format="json",
        )
        self.assertEqual(r_ok.status_code, status.HTTP_200_OK)
        self.assertTrue(
            MovStock.objects.filter(ref_tipo="SOLICITUD", ref_id=s.pk, tipo="OUT").exists()
        )

    def test_aprobacion_registra_salidas_y_descuenta_stock(self):
        s = self._solicitud_con(self.prod_barato, cantidad=7)
        s.estado = EstadoSolicitud.EN_REVISION
        s.save()
        antes = StockProducto.objects.get(producto=self.prod_barato).qty_on_hand
        self.client.force_authenticate(self.compras)
        r = self.client.patch(
            f"/api/purchases/solicitudes/{s.pk}/",
            {"estado": EstadoSolicitud.COMPRA_ACEPTADA},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        despues = StockProducto.objects.get(producto=self.prod_barato).qty_on_hand
        self.assertEqual(despues, antes - 7)
        movs = MovStock.objects.filter(ref_tipo="SOLICITUD", ref_id=s.pk, tipo="OUT")
        self.assertEqual(movs.count(), 1)
        self.assertEqual(movs.get().cantidad, 7)

    def test_no_finalizar_catalogo_sin_stock_suficiente(self):
        StockProducto.objects.filter(producto=self.prod_barato).update(qty_on_hand=2)
        s = self._solicitud_con(self.prod_barato, cantidad=5)
        s.estado = EstadoSolicitud.COMPRA_ACEPTADA
        s.save()
        self.client.force_authenticate(self.compras)
        r = self.client.patch(
            f"/api/purchases/solicitudes/{s.pk}/",
            {"estado": EstadoSolicitud.FINALIZADO},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("stock inferior", r.json()["detail"].lower())
        self.assertFalse(MovStock.objects.filter(ref_tipo="SOLICITUD", ref_id=s.pk).exists())

    def test_finalizar_catalogo_con_stock_registra_salidas(self):
        s = self._solicitud_con(self.prod_barato, cantidad=3)
        s.estado = EstadoSolicitud.COMPRA_ACEPTADA
        s.save()
        antes = StockProducto.objects.get(producto=self.prod_barato).qty_on_hand
        self.client.force_authenticate(self.compras)
        r = self.client.patch(
            f"/api/purchases/solicitudes/{s.pk}/",
            {"estado": EstadoSolicitud.FINALIZADO},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.json()["estado"], EstadoSolicitud.FINALIZADO)
        despues = StockProducto.objects.get(producto=self.prod_barato).qty_on_hand
        self.assertEqual(despues, antes - 3)
        self.assertEqual(
            MovStock.objects.filter(ref_tipo="SOLICITUD", ref_id=s.pk, tipo="OUT").count(),
            1,
        )

    def test_compras_rechaza_solicitud_catalogo(self):
        s = self._solicitud_con(self.prod_barato)
        s.estado = EstadoSolicitud.EN_REVISION
        s.save()
        self.client.force_authenticate(self.compras)
        r = self.client.patch(
            f"/api/purchases/solicitudes/{s.pk}/",
            {"estado": EstadoSolicitud.COMPRA_RECHAZADA, "motivo_rechazo": "No procede"},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.json()["estado"], EstadoSolicitud.COMPRA_RECHAZADA)

    def test_contable_ve_todas_las_solicitudes(self):
        self._solicitud_con(self.prod_barato)
        contable = User.objects.create_user(
            username="cont_list",
            password="x",
            role=Role.CONTABLE,
        )
        self.client.force_authenticate(contable)
        r = self.client.get("/api/purchases/solicitudes/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        body = r.json()
        items = body["results"] if isinstance(body, dict) else body
        self.assertGreaterEqual(len(items), 1)

    def test_contable_puede_crear_solicitud(self):
        contable = User.objects.create_user(
            username="cont_crea",
            password="x",
            role=Role.CONTABLE,
        )
        self.client.force_authenticate(contable)
        r = self.client.post(
            "/api/purchases/solicitudes/",
            {
                "destino": "Contabilidad",
                "observacion": "",
                "detalles": [
                    {"producto": self.prod_barato.pk, "cantidad": 1, "observacion": ""},
                ],
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.json()["solicitante"], contable.pk)

    def test_compras_puede_crear_solicitud(self):
        self.client.force_authenticate(self.compras)
        r = self.client.post(
            "/api/purchases/solicitudes/",
            {
                "destino": "Depósito",
                "observacion": "",
                "detalles": [
                    {"producto": self.prod_barato.pk, "cantidad": 2, "observacion": ""},
                ],
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.json()["solicitante"], self.compras.pk)

    def test_funcionario_crea_solicitud_fuera_catalogo(self):
        self.client.force_authenticate(self.func)
        r = self.client.post(
            "/api/purchases/solicitudes/",
            {
                "destino": "Obra norte",
                "observacion": "",
                "detalles": [
                    {
                        "cantidad": 2,
                        "descripcion_insumo_solicitado": "Tornillo M8 no listado",
                        "observacion": "",
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        body = r.json()
        self.assertEqual(len(body["detalles"]), 1)
        self.assertIsNone(body["detalles"][0]["producto"])
        self.assertEqual(body["detalles"][0]["descripcion_insumo_solicitado"], "Tornillo M8 no listado")

    def _solicitud_con_item_fuera_catalogo(self, estado=EstadoSolicitud.SOLICITADO):
        s = SolicitudInsumo.objects.create(
            solicitante=self.func,
            destino="D",
            estado=estado,
            contiene_fuera_catalogo=True,
        )
        SolicitudDetalle.objects.create(
            solicitud=s,
            producto=None,
            descripcion_insumo_solicitado="Insumo libre",
            cantidad=1,
        )
        return s

    def test_flujo_fuera_catalogo_pasar_revision_y_rechazo_solo_gerencia(self):
        s = self._solicitud_con_item_fuera_catalogo(EstadoSolicitud.SOLICITADO)
        self.client.force_authenticate(self.compras)
        r_revision = self.client.patch(
            f"/api/purchases/solicitudes/{s.pk}/",
            {
                "estado": EstadoSolicitud.EN_REVISION,
                "accion": "SOLICITAR_GERENCIA",
                "tipo_destino_compra": "ENTREGA_INMEDIATA",
            },
            format="json",
        )
        self.assertEqual(r_revision.status_code, status.HTTP_200_OK)
        self.assertEqual(r_revision.json()["estado"], EstadoSolicitud.EN_REVISION)

        r_rechazar_compras = self.client.patch(
            f"/api/purchases/solicitudes/{s.pk}/",
            {"estado": EstadoSolicitud.COMPRA_RECHAZADA, "motivo_rechazo": "No corresponde"},
            format="json",
        )
        self.assertEqual(r_rechazar_compras.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Gerencia", r_rechazar_compras.json()["detail"])

        r_aprobar_sin_vincular = self.client.patch(
            f"/api/purchases/solicitudes/{s.pk}/",
            {"estado": EstadoSolicitud.COMPRA_ACEPTADA},
            format="json",
        )
        self.assertEqual(r_aprobar_sin_vincular.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("gerencia", r_aprobar_sin_vincular.json()["detail"].lower())

        self.client.force_authenticate(self.gerencia)
        r_aprobar_gerencia = self.client.patch(
            f"/api/purchases/solicitudes/{s.pk}/",
            {"estado": EstadoSolicitud.COMPRA_ACEPTADA, "comentario_decision": "Autorizado"},
            format="json",
        )
        self.assertEqual(r_aprobar_gerencia.status_code, status.HTTP_200_OK)
        self.assertEqual(r_aprobar_gerencia.json()["estado"], EstadoSolicitud.COMPRA_ACEPTADA)

        s2 = self._solicitud_con_item_fuera_catalogo(EstadoSolicitud.EN_REVISION)
        s2.tipo_destino_compra = "INVENTARIO"
        s2.save(update_fields=["tipo_destino_compra"])
        r_rechazar_gerencia = self.client.patch(
            f"/api/purchases/solicitudes/{s2.pk}/",
            {"estado": EstadoSolicitud.COMPRA_RECHAZADA, "comentario_decision": "No corresponde"},
            format="json",
        )
        self.assertEqual(r_rechazar_gerencia.status_code, status.HTTP_200_OK)

    def test_tomar_solicitud_solo_catalogo(self):
        s = SolicitudInsumo.objects.create(
            solicitante=self.func,
            destino="D",
            contiene_fuera_catalogo=False,
        )
        SolicitudDetalle.objects.create(solicitud=s, producto=self.prod_caro, cantidad=1)
        self.client.force_authenticate(self.compras)
        r_mala = self.client.patch(
            f"/api/purchases/solicitudes/{s.pk}/",
            {"estado": EstadoSolicitud.EN_REVISION, "accion": "SOLICITAR_GERENCIA"},
            format="json",
        )
        self.assertEqual(r_mala.status_code, status.HTTP_400_BAD_REQUEST)
        r_ok = self.client.patch(
            f"/api/purchases/solicitudes/{s.pk}/",
            {
                "estado": EstadoSolicitud.EN_REVISION,
                "accion": "TOMAR_SOLICITUD",
            },
            format="json",
        )
        self.assertEqual(r_ok.status_code, status.HTTP_200_OK)
        self.assertEqual(r_ok.json()["estado"], EstadoSolicitud.EN_REVISION)
        self.assertIsNone(r_ok.json()["tipo_destino_compra"])

    def test_fuera_catalogo_rechaza_tomar_solicitud(self):
        s = self._solicitud_con_item_fuera_catalogo()
        self.client.force_authenticate(self.compras)
        r = self.client.patch(
            f"/api/purchases/solicitudes/{s.pk}/",
            {
                "estado": EstadoSolicitud.EN_REVISION,
                "accion": "TOMAR_SOLICITUD",
                "tipo_destino_compra": "INVENTARIO",
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Gerencia", r.json()["detail"])

    def test_gerencia_no_puede_vincular_detalle(self):
        s = self._solicitud_con_item_fuera_catalogo(EstadoSolicitud.EN_REVISION)
        d = s.detalles.first()
        self.client.force_authenticate(self.gerencia)
        r = self.client.post(
            f"/api/purchases/solicitudes/{s.pk}/vincular-detalle/",
            {"detalle_id": d.pk, "producto_id": self.prod_caro.pk},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_vincular_detalle_solo_despues_aceptacion_gerencia(self):
        """Fuera de catálogo: Gerencia aprueba primero; Compras vincula después."""
        StockProducto.objects.filter(producto=self.prod_caro).update(qty_on_hand=0)
        s = SolicitudInsumo.objects.create(
            solicitante=self.func,
            destino="D",
            contiene_fuera_catalogo=True,
            tipo_destino_compra="ENTREGA_INMEDIATA",
        )
        d = SolicitudDetalle.objects.create(
            solicitud=s,
            producto=None,
            descripcion_insumo_solicitado="Equipo especial",
            cantidad=1,
        )
        s.estado = EstadoSolicitud.EN_REVISION
        s.save()
        self.client.force_authenticate(self.compras)
        r_v_antes = self.client.post(
            f"/api/purchases/solicitudes/{s.pk}/vincular-detalle/",
            {"detalle_id": d.pk, "producto_id": self.prod_caro.pk},
            format="json",
        )
        self.assertEqual(r_v_antes.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("gerencia", r_v_antes.json()["detail"].lower())

        self.client.force_authenticate(self.gerencia)
        r_aprobar = self.client.patch(
            f"/api/purchases/solicitudes/{s.pk}/",
            {"estado": EstadoSolicitud.COMPRA_ACEPTADA},
            format="json",
        )
        self.assertEqual(r_aprobar.status_code, status.HTTP_200_OK)

        self.client.force_authenticate(self.compras)
        r_v = self.client.post(
            f"/api/purchases/solicitudes/{s.pk}/vincular-detalle/",
            {"detalle_id": d.pk, "producto_id": self.prod_caro.pk},
            format="json",
        )
        self.assertEqual(r_v.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(r_v.json()["detalles"][0]["producto"])

    def test_compras_actualiza_cantidad_fuera_catalogo_inventario(self):
        s = SolicitudInsumo.objects.create(
            solicitante=self.func,
            destino="Depósito",
            contiene_fuera_catalogo=True,
            tipo_destino_compra="INVENTARIO",
            estado=EstadoSolicitud.SOLICITADO,
        )
        d = SolicitudDetalle.objects.create(
            solicitud=s,
            producto=None,
            descripcion_insumo_solicitado="Insumo nuevo",
            cantidad=2,
        )
        self.client.force_authenticate(self.compras)
        r = self.client.post(
            f"/api/purchases/solicitudes/{s.pk}/actualizar-cantidad-detalle/",
            {"detalle_id": d.pk, "cantidad": 8},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.json()["detalles"][0]["cantidad"], 8)
        d.refresh_from_db()
        self.assertEqual(d.cantidad, 8)

    def test_no_actualizar_cantidad_entrega_inmediata(self):
        s = SolicitudInsumo.objects.create(
            solicitante=self.func,
            destino="Obra",
            contiene_fuera_catalogo=True,
            tipo_destino_compra="ENTREGA_INMEDIATA",
            estado=EstadoSolicitud.EN_REVISION,
        )
        d = SolicitudDetalle.objects.create(
            solicitud=s,
            producto=None,
            descripcion_insumo_solicitado="Puntual",
            cantidad=1,
        )
        self.client.force_authenticate(self.compras)
        r = self.client.post(
            f"/api/purchases/solicitudes/{s.pk}/actualizar-cantidad-detalle/",
            {"detalle_id": d.pk, "cantidad": 5},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_gerencia_actualiza_cantidad_detalle_inventario(self):
        s = self._solicitud_con_item_fuera_catalogo(EstadoSolicitud.EN_REVISION)
        s.tipo_destino_compra = "INVENTARIO"
        s.save(update_fields=["tipo_destino_compra"])
        d = s.detalles.first()
        self.client.force_authenticate(self.gerencia)
        r = self.client.post(
            f"/api/purchases/solicitudes/{s.pk}/actualizar-cantidad-detalle/",
            {"detalle_id": d.pk, "cantidad": 4},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.json()["detalles"][0]["cantidad"], 4)
        self.assertEqual(r.json()["detalles"][0]["cantidad_inicial"], d.cantidad_inicial)

    def test_no_actualizar_cantidad_menor_a_inicial(self):
        s = SolicitudInsumo.objects.create(
            solicitante=self.func,
            destino="Depósito",
            contiene_fuera_catalogo=True,
            tipo_destino_compra="INVENTARIO",
            estado=EstadoSolicitud.SOLICITADO,
        )
        d = SolicitudDetalle.objects.create(
            solicitud=s,
            producto=None,
            descripcion_insumo_solicitado="Insumo",
            cantidad=3,
        )
        self.client.force_authenticate(self.compras)
        r = self.client.post(
            f"/api/purchases/solicitudes/{s.pk}/actualizar-cantidad-detalle/",
            {"detalle_id": d.pk, "cantidad": 2},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_finalizar_inventario_entrega_solo_cantidad_inicial(self):
        from apps.inventory.models import MovStock, StockProducto

        StockProducto.objects.filter(producto=self.prod_caro).update(qty_on_hand=0)
        s = SolicitudInsumo.objects.create(
            solicitante=self.func,
            destino="Depósito",
            contiene_fuera_catalogo=True,
            tipo_destino_compra="INVENTARIO",
            estado=EstadoSolicitud.COMPRA_ACEPTADA,
        )
        d = SolicitudDetalle.objects.create(
            solicitud=s,
            producto=None,
            descripcion_insumo_solicitado="Repuesto",
            cantidad=10,
        )
        d.cantidad_inicial = 2
        d.cantidad = 10
        d.save(update_fields=["cantidad_inicial", "cantidad"])

        self.client.force_authenticate(self.compras)
        r_v = self.client.post(
            f"/api/purchases/solicitudes/{s.pk}/vincular-detalle/",
            {"detalle_id": d.pk, "producto_id": self.prod_caro.pk},
            format="json",
        )
        self.assertEqual(r_v.status_code, status.HTTP_200_OK)
        self.assertEqual(StockProducto.objects.get(producto=self.prod_caro).qty_on_hand, 10)

        r_fin = self.client.patch(
            f"/api/purchases/solicitudes/{s.pk}/",
            {"estado": EstadoSolicitud.FINALIZADO},
            format="json",
        )
        self.assertEqual(r_fin.status_code, status.HTTP_200_OK)
        self.assertEqual(StockProducto.objects.get(producto=self.prod_caro).qty_on_hand, 8)
        out_fin = MovStock.objects.filter(
            ref_tipo="SOLICITUD",
            ref_id=s.pk,
            producto=self.prod_caro,
            tipo="OUT",
            cantidad=2,
        )
        self.assertTrue(out_fin.exists())

    def test_vincular_detalle_inventario_tras_aprobacion_gerencia(self):
        s = SolicitudInsumo.objects.create(
            solicitante=self.func,
            destino="Depósito",
            contiene_fuera_catalogo=True,
            tipo_destino_compra="INVENTARIO",
            estado=EstadoSolicitud.EN_REVISION,
        )
        d = SolicitudDetalle.objects.create(
            solicitud=s,
            producto=None,
            descripcion_insumo_solicitado="Insumo nuevo inventario",
            cantidad=3,
        )
        self.client.force_authenticate(self.gerencia)
        r_aprobar = self.client.patch(
            f"/api/purchases/solicitudes/{s.pk}/",
            {"estado": EstadoSolicitud.COMPRA_ACEPTADA},
            format="json",
        )
        self.assertEqual(r_aprobar.status_code, status.HTTP_200_OK)

        self.client.force_authenticate(self.compras)
        r_v = self.client.post(
            f"/api/purchases/solicitudes/{s.pk}/vincular-detalle/",
            {"detalle_id": d.pk, "producto_id": self.prod_caro.pk},
            format="json",
        )
        self.assertEqual(r_v.status_code, status.HTTP_200_OK)
        body = r_v.json()
        self.assertEqual(body["tipo_destino_compra"], "INVENTARIO")
        self.assertIsNotNone(body["detalles"][0]["producto"])

    def test_vincular_inventario_registra_entrada_si_no_existe(self):
        from apps.inventory.models import MovStock, StockProducto

        StockProducto.objects.filter(producto=self.prod_caro).update(qty_on_hand=0)
        s = SolicitudInsumo.objects.create(
            solicitante=self.func,
            destino="Depósito",
            contiene_fuera_catalogo=True,
            tipo_destino_compra="INVENTARIO",
            estado=EstadoSolicitud.COMPRA_ACEPTADA,
        )
        d = SolicitudDetalle.objects.create(
            solicitud=s,
            producto=None,
            descripcion_insumo_solicitado="Repuesto",
            cantidad=4,
        )
        self.client.force_authenticate(self.compras)
        r_v = self.client.post(
            f"/api/purchases/solicitudes/{s.pk}/vincular-detalle/",
            {"detalle_id": d.pk, "producto_id": self.prod_caro.pk},
            format="json",
        )
        self.assertEqual(r_v.status_code, status.HTTP_200_OK)
        mov_in = MovStock.objects.filter(
            ref_tipo="SOLICITUD", ref_id=s.pk, producto=self.prod_caro, tipo="IN"
        )
        self.assertTrue(mov_in.filter(cantidad=4).exists())
        self.assertEqual(StockProducto.objects.get(producto=self.prod_caro).qty_on_hand, 4)

    def test_finalizar_entrega_inmediata_tras_vincular(self):
        """Al vincular se registran IN/OUT; finalizar acepta reenvío del mismo destino."""
        from apps.inventory.models import MovStock

        StockProducto.objects.filter(producto=self.prod_caro).update(qty_on_hand=0)
        s = SolicitudInsumo.objects.create(
            solicitante=self.func,
            destino="D",
            contiene_fuera_catalogo=True,
            tipo_destino_compra="ENTREGA_INMEDIATA",
            estado=EstadoSolicitud.COMPRA_ACEPTADA,
        )
        d = SolicitudDetalle.objects.create(
            solicitud=s,
            producto=None,
            descripcion_insumo_solicitado="Equipo",
            cantidad=2,
        )
        self.client.force_authenticate(self.compras)
        r_v = self.client.post(
            f"/api/purchases/solicitudes/{s.pk}/vincular-detalle/",
            {"detalle_id": d.pk, "producto_id": self.prod_caro.pk},
            format="json",
        )
        self.assertEqual(r_v.status_code, status.HTTP_200_OK)
        movs = MovStock.objects.filter(
            ref_tipo="SOLICITUD", ref_id=s.pk, producto=self.prod_caro
        )
        self.assertEqual(movs.count(), 2)
        self.assertTrue(movs.filter(tipo="IN", cantidad=2).exists())
        self.assertTrue(movs.filter(tipo="OUT", cantidad=2).exists())
        self.assertEqual(StockProducto.objects.get(producto=self.prod_caro).qty_on_hand, 0)

        r_fin = self.client.patch(
            f"/api/purchases/solicitudes/{s.pk}/",
            {
                "estado": EstadoSolicitud.FINALIZADO,
                "tipo_destino_compra": "ENTREGA_INMEDIATA",
            },
            format="json",
        )
        self.assertEqual(r_fin.status_code, status.HTTP_200_OK)
        self.assertEqual(r_fin.json()["estado"], EstadoSolicitud.FINALIZADO)


class SolicitudListadoPaginacionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.func = User.objects.create_user(
            username="f_pag",
            password="x",
            role=Role.FUNCIONARIO,
        )
        self.otro = User.objects.create_user(
            username="f_otro",
            password="x",
            role=Role.FUNCIONARIO,
        )

    def test_funcionario_ve_solo_sus_solicitudes_paginadas(self):
        for i in range(12):
            SolicitudInsumo.objects.create(solicitante=self.func, destino=f"Destino {i}")
        SolicitudInsumo.objects.create(solicitante=self.otro, destino="Ajena")

        self.client.force_authenticate(self.func)
        r1 = self.client.get("/api/purchases/solicitudes/?page=1")
        self.assertEqual(r1.status_code, status.HTTP_200_OK)
        body1 = r1.json()
        self.assertEqual(body1["count"], 12)
        self.assertEqual(len(body1["results"]), 10)

        r2 = self.client.get("/api/purchases/solicitudes/?page=2")
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        body2 = r2.json()
        self.assertEqual(body2["count"], 12)
        self.assertEqual(len(body2["results"]), 2)
        self.assertIsNone(body2["next"])
        self.assertIsNotNone(body2["previous"])


class TipoDestinoCompraTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.func = User.objects.create_user(
            username="f_dest",
            password="x",
            role=Role.FUNCIONARIO,
        )
        self.compras = User.objects.create_user(
            username="c_dest",
            password="x",
            role=Role.COMPRAS,
        )
        self.prod = Producto.objects.create(
            sku="D-1",
            nombre="Insumo destino",
            costo_promedio=Decimal("10.00"),
            stock_minimo=5,
        )
        StockProducto.objects.create(producto=self.prod, qty_on_hand=0)

    def test_funcionario_no_define_destino_al_crear(self):
        self.client.force_authenticate(self.func)
        r = self.client.post(
            "/api/purchases/solicitudes/",
            {
                "destino": "Oficina",
                "tipo_destino_compra": "ENTREGA_INMEDIATA",
                "observacion": "",
                "detalles": [
                    {"producto": self.prod.pk, "cantidad": 2, "observacion": ""},
                ],
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(r.json()["tipo_destino_compra"])

    def test_catalogo_rechaza_definir_destino_compra(self):
        s = SolicitudInsumo.objects.create(
            solicitante=self.func,
            destino="D",
            contiene_fuera_catalogo=False,
        )
        SolicitudDetalle.objects.create(solicitud=s, producto=self.prod, cantidad=1)
        self.client.force_authenticate(self.compras)
        r = self.client.patch(
            f"/api/purchases/solicitudes/{s.pk}/",
            {"tipo_destino_compra": "INVENTARIO"},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("fuera de catálogo", r.json()["detail"].lower())

    def test_compras_define_destino_antes_de_gerencia(self):
        s = SolicitudInsumo.objects.create(
            solicitante=self.func,
            destino="D",
            contiene_fuera_catalogo=True,
        )
        SolicitudDetalle.objects.create(
            solicitud=s,
            producto=None,
            descripcion_insumo_solicitado="Fuera",
            cantidad=1,
        )
        self.client.force_authenticate(self.compras)
        r_dest = self.client.patch(
            f"/api/purchases/solicitudes/{s.pk}/",
            {"tipo_destino_compra": "ENTREGA_INMEDIATA"},
            format="json",
        )
        self.assertEqual(r_dest.status_code, status.HTTP_200_OK)
        self.assertEqual(r_dest.json()["tipo_destino_compra"], "ENTREGA_INMEDIATA")

        r_sin_dest = self.client.patch(
            f"/api/purchases/solicitudes/{s.pk}/",
            {"estado": EstadoSolicitud.EN_REVISION, "accion": "SOLICITAR_GERENCIA"},
            format="json",
        )
        self.assertEqual(r_sin_dest.status_code, status.HTTP_200_OK)

    def test_compras_define_destino_inventario_antes_de_gerencia(self):
        s = SolicitudInsumo.objects.create(
            solicitante=self.func,
            destino="D",
            contiene_fuera_catalogo=True,
        )
        SolicitudDetalle.objects.create(
            solicitud=s,
            producto=None,
            descripcion_insumo_solicitado="Repuesto",
            cantidad=2,
        )
        self.client.force_authenticate(self.compras)
        r_dest = self.client.patch(
            f"/api/purchases/solicitudes/{s.pk}/",
            {"tipo_destino_compra": "INVENTARIO"},
            format="json",
        )
        self.assertEqual(r_dest.status_code, status.HTTP_200_OK)
        self.assertEqual(r_dest.json()["tipo_destino_compra"], "INVENTARIO")

        r_envio = self.client.patch(
            f"/api/purchases/solicitudes/{s.pk}/",
            {"estado": EstadoSolicitud.EN_REVISION, "accion": "SOLICITAR_GERENCIA"},
            format="json",
        )
        self.assertEqual(r_envio.status_code, status.HTTP_200_OK)

    def test_gerencia_sin_destino_previo_falla(self):
        s = SolicitudInsumo.objects.create(
            solicitante=self.func,
            destino="D",
            contiene_fuera_catalogo=True,
        )
        SolicitudDetalle.objects.create(
            solicitud=s,
            producto=None,
            descripcion_insumo_solicitado="Fuera",
            cantidad=1,
        )
        self.client.force_authenticate(self.compras)
        r = self.client.patch(
            f"/api/purchases/solicitudes/{s.pk}/",
            {"estado": EstadoSolicitud.EN_REVISION, "accion": "SOLICITAR_GERENCIA"},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("destino", r.json()["detail"].lower())

    def test_entrega_inmediata_excluye_alerta_stock_cero(self):
        from apps.purchases.stock_alerts import excluir_de_alerta_stock_critico

        s = SolicitudInsumo.objects.create(
            solicitante=self.func,
            destino="Puntual",
            tipo_destino_compra="ENTREGA_INMEDIATA",
            estado=EstadoSolicitud.FINALIZADO,
        )
        SolicitudDetalle.objects.create(solicitud=s, producto=self.prod, cantidad=2)
        self.assertTrue(excluir_de_alerta_stock_critico(self.prod.pk, 0))

    def test_inventario_mantiene_alerta_stock_cero(self):
        from apps.purchases.stock_alerts import excluir_de_alerta_stock_critico

        s = SolicitudInsumo.objects.create(
            solicitante=self.func,
            destino="Depósito",
            tipo_destino_compra="INVENTARIO",
            estado=EstadoSolicitud.FINALIZADO,
        )
        SolicitudDetalle.objects.create(solicitud=s, producto=self.prod, cantidad=2)
        self.assertFalse(excluir_de_alerta_stock_critico(self.prod.pk, 0))

    def test_producto_mixto_no_excluye_alerta(self):
        from apps.purchases.stock_alerts import excluir_de_alerta_stock_critico

        s1 = SolicitudInsumo.objects.create(
            solicitante=self.func,
            destino="Puntual",
            tipo_destino_compra="ENTREGA_INMEDIATA",
            estado=EstadoSolicitud.FINALIZADO,
        )
        SolicitudDetalle.objects.create(solicitud=s1, producto=self.prod, cantidad=1)
        s2 = SolicitudInsumo.objects.create(
            solicitante=self.func,
            destino="Depósito",
            tipo_destino_compra="INVENTARIO",
            estado=EstadoSolicitud.FINALIZADO,
        )
        SolicitudDetalle.objects.create(solicitud=s2, producto=self.prod, cantidad=1)
        self.assertFalse(excluir_de_alerta_stock_critico(self.prod.pk, 0))


class AdminEliminarSolicitudTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username="admin_sol",
            email="admin@local",
            password="x",
        )
        self.func = User.objects.create_user(
            username="f_del_sol",
            password="x",
            role=Role.FUNCIONARIO,
        )
        self.prod = Producto.objects.create(sku="DEL-S", nombre="Prod sol", unidad="UN")

    def test_admin_elimina_solicitud_finalizada(self):
        s = SolicitudInsumo.objects.create(
            solicitante=self.func,
            destino="Depósito",
            estado=EstadoSolicitud.FINALIZADO,
        )
        SolicitudDetalle.objects.create(solicitud=s, producto=self.prod, cantidad=1)
        self.client.force_authenticate(self.admin)
        r = self.client.delete(f"/api/purchases/solicitudes/{s.pk}/")
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(SolicitudInsumo.objects.filter(pk=s.pk).exists())

    def test_funcionario_no_elimina_solicitud_finalizada(self):
        s = SolicitudInsumo.objects.create(
            solicitante=self.func,
            destino="Depósito",
            estado=EstadoSolicitud.FINALIZADO,
        )
        SolicitudDetalle.objects.create(solicitud=s, producto=self.prod, cantidad=1)
        self.client.force_authenticate(self.func)
        r = self.client.delete(f"/api/purchases/solicitudes/{s.pk}/")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)


class SolicitudNumeroCorrelativoTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username="admin_num_sol",
            email="admin@local",
            password="x",
        )
        self.func = User.objects.create_user(
            username="func_num_sol",
            password="x",
            role=Role.FUNCIONARIO,
        )
        self.prod = Producto.objects.create(sku="NUM-S", nombre="Prod", unidad="UN")

    def test_nueva_solicitud_asigna_numero_secuencial(self):
        s1 = SolicitudInsumo.objects.create(solicitante=self.func, destino="A")
        s2 = SolicitudInsumo.objects.create(solicitante=self.func, destino="B")
        self.assertEqual(s1.numero + 1, s2.numero)

    def test_eliminar_renumera_solicitudes_posteriores(self):
        s1 = SolicitudInsumo.objects.create(solicitante=self.func, destino="A")
        s2 = SolicitudInsumo.objects.create(solicitante=self.func, destino="B")
        s3 = SolicitudInsumo.objects.create(solicitante=self.func, destino="C")
        n1, n2, n3 = s1.numero, s2.numero, s3.numero
        self.assertEqual(n2, n1 + 1)
        self.assertEqual(n3, n2 + 1)

        self.client.force_authenticate(self.admin)
        r = self.client.delete(f"/api/purchases/solicitudes/{s2.pk}/")
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT)

        s1.refresh_from_db()
        s3.refresh_from_db()
        self.assertEqual(s1.numero, n1)
        self.assertEqual(s3.numero, n2)
        self.assertFalse(SolicitudInsumo.objects.filter(pk=s2.pk).exists())
