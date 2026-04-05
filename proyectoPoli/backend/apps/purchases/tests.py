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

    def test_gerencia_no_aprueba_si_hay_stock_aunque_producto_caro(self):
        s = self._solicitud_con(self.prod_caro)
        s.estado = EstadoSolicitud.EN_REVISION
        s.save()
        self.client.force_authenticate(self.gerencia)
        r = self.client.patch(
            f"/api/purchases/solicitudes/{s.pk}/",
            {"estado": EstadoSolicitud.COMPRA_ACEPTADA},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_gerencia_no_aprueba_si_no_requiere_gerencia(self):
        s = self._solicitud_con(self.prod_barato)
        s.estado = EstadoSolicitud.EN_REVISION
        s.save()
        self.client.force_authenticate(self.gerencia)
        r = self.client.patch(
            f"/api/purchases/solicitudes/{s.pk}/",
            {"estado": EstadoSolicitud.COMPRA_ACEPTADA},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_gerencia_aprueba_insumo_habitual_sin_stock(self):
        """Sin stock en producto barato: req_g por falta de existencias; Gerencia aprueba (sin movimiento OUT)."""
        StockProducto.objects.filter(producto=self.prod_barato).update(qty_on_hand=0)
        s = self._solicitud_con(self.prod_barato, cantidad=5)
        s.estado = EstadoSolicitud.EN_REVISION
        s.save()
        self.client.force_authenticate(self.gerencia)
        r = self.client.patch(
            f"/api/purchases/solicitudes/{s.pk}/",
            {"estado": EstadoSolicitud.COMPRA_ACEPTADA},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertFalse(MovStock.objects.filter(ref_tipo="SOLICITUD", ref_id=s.pk).exists())

    def test_compras_no_aprueba_sin_stock(self):
        StockProducto.objects.filter(producto=self.prod_barato).update(qty_on_hand=1)
        s = self._solicitud_con(self.prod_barato, cantidad=50)
        s.estado = EstadoSolicitud.EN_REVISION
        s.save()
        self.client.force_authenticate(self.compras)
        r = self.client.patch(
            f"/api/purchases/solicitudes/{s.pk}/",
            {"estado": EstadoSolicitud.COMPRA_ACEPTADA},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

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

    def test_aprobacion_sin_stock_no_crea_movimientos(self):
        """Gerencia puede aprobar sin stock; no se registran salidas."""
        StockProducto.objects.filter(producto=self.prod_caro).update(qty_on_hand=0)
        s = self._solicitud_con(self.prod_caro, cantidad=1)
        s.estado = EstadoSolicitud.EN_REVISION
        s.save()
        self.client.force_authenticate(self.gerencia)
        r = self.client.patch(
            f"/api/purchases/solicitudes/{s.pk}/",
            {"estado": EstadoSolicitud.COMPRA_ACEPTADA},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertFalse(MovStock.objects.filter(ref_tipo="SOLICITUD", ref_id=s.pk).exists())

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
        self.assertGreaterEqual(len(r.json()), 1)

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

    def test_no_aprobar_sin_vincular_todas_las_lineas(self):
        s = SolicitudInsumo.objects.create(solicitante=self.func, destino="D")
        SolicitudDetalle.objects.create(
            solicitud=s,
            producto=None,
            descripcion_insumo_solicitado="Insumo libre",
            cantidad=1,
        )
        s.estado = EstadoSolicitud.EN_REVISION
        s.save()
        self.client.force_authenticate(self.gerencia)
        r = self.client.patch(
            f"/api/purchases/solicitudes/{s.pk}/",
            {"estado": EstadoSolicitud.COMPRA_ACEPTADA},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("catálogo", r.json()["detail"])

    def test_vincular_detalle_y_luego_gerencia_aprueba_sin_stock(self):
        """Tras vincular, sin stock: circuito Gerencia; Gerencia aprueba."""
        StockProducto.objects.filter(producto=self.prod_caro).update(qty_on_hand=0)
        s = SolicitudInsumo.objects.create(solicitante=self.func, destino="D")
        d = SolicitudDetalle.objects.create(
            solicitud=s,
            producto=None,
            descripcion_insumo_solicitado="Equipo especial",
            cantidad=1,
        )
        s.estado = EstadoSolicitud.EN_REVISION
        s.save()
        self.client.force_authenticate(self.compras)
        r_v = self.client.post(
            f"/api/purchases/solicitudes/{s.pk}/vincular-detalle/",
            {"detalle_id": d.pk, "producto_id": self.prod_caro.pk},
            format="json",
        )
        self.assertEqual(r_v.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(r_v.json()["detalles"][0]["producto"])
        self.client.force_authenticate(self.gerencia)
        r = self.client.patch(
            f"/api/purchases/solicitudes/{s.pk}/",
            {"estado": EstadoSolicitud.COMPRA_ACEPTADA},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
