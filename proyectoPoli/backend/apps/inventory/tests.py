from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.inventory.models import MovStock, StockProducto
from apps.products.models import Producto
from apps.users.models import Role, User


class GerenciaInventarioSoloLecturaTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.gerencia = User.objects.create_user(
            username="ger_inv",
            password="x",
            role=Role.GERENCIA,
        )
        self.producto = Producto.objects.create(sku="SKU-G", nombre="Prod gerencia", unidad="UN")
        StockProducto.objects.create(producto=self.producto, qty_on_hand=3)

    def test_gerencia_puede_listar_movimientos_y_stock(self):
        self.client.force_authenticate(self.gerencia)
        self.assertEqual(self.client.get("/api/inventory/movimientos/").status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get("/api/inventory/stock/").status_code, status.HTTP_200_OK)

    def test_gerencia_no_registra_movimientos(self):
        self.client.force_authenticate(self.gerencia)
        r = self.client.post(
            "/api/inventory/movimientos/",
            {"tipo": "IN", "producto": self.producto.pk, "cantidad": 1},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)


class MovStockSalidaTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.compras = User.objects.create_user(
            username="comp_inv",
            password="x",
            role=Role.COMPRAS,
        )
        self.producto = Producto.objects.create(sku="SKU-Z", nombre="Prod cero", unidad="UN")
        StockProducto.objects.create(producto=self.producto, qty_on_hand=0)

    def test_no_permite_salida_con_stock_cero(self):
        self.client.force_authenticate(self.compras)
        r = self.client.post(
            "/api/inventory/movimientos/",
            {"tipo": "OUT", "producto": self.producto.pk, "cantidad": 1},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("stock", str(r.json()).lower())

    def test_permite_entrada_con_stock_cero(self):
        self.client.force_authenticate(self.compras)
        r = self.client.post(
            "/api/inventory/movimientos/",
            {"tipo": "IN", "producto": self.producto.pk, "cantidad": 5},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.producto.stock.refresh_from_db()
        self.assertEqual(self.producto.stock.qty_on_hand, 5)

    def test_listado_movimiento_incluye_stock_actual_vigente(self):
        StockProducto.objects.filter(producto=self.producto).update(qty_on_hand=12)
        self.client.force_authenticate(self.compras)
        MovStock.objects.create(
            producto=self.producto,
            tipo="IN",
            cantidad=3,
            usuario=self.compras,
        )
        r = self.client.get("/api/inventory/movimientos/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        data = r.json()
        rows = data if isinstance(data, list) else data.get("results", [])
        self.assertGreaterEqual(len(rows), 1)
        self.assertEqual(rows[0]["stock_actual"], 15)


class AdminEliminarMovimientoTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username="admin_mov",
            email="admin@local",
            password="x",
        )
        self.compras = User.objects.create_user(
            username="comp_del_mov",
            password="x",
            role=Role.COMPRAS,
        )
        self.producto = Producto.objects.create(sku="SKU-DEL", nombre="Prod del", unidad="UN")
        StockProducto.objects.create(producto=self.producto, qty_on_hand=10)

    def test_admin_elimina_movimiento_y_revierte_stock(self):
        mov = MovStock.objects.create(
            producto=self.producto,
            tipo="IN",
            cantidad=4,
            usuario=self.compras,
        )
        self.producto.stock.refresh_from_db()
        self.assertEqual(self.producto.stock.qty_on_hand, 14)

        self.client.force_authenticate(self.admin)
        r = self.client.delete(f"/api/inventory/movimientos/{mov.pk}/")
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(MovStock.objects.filter(pk=mov.pk).exists())
        self.producto.stock.refresh_from_db()
        self.assertEqual(self.producto.stock.qty_on_hand, 10)

    def test_compras_no_elimina_movimiento(self):
        mov = MovStock.objects.create(
            producto=self.producto,
            tipo="IN",
            cantidad=2,
            usuario=self.compras,
        )
        self.client.force_authenticate(self.compras)
        r = self.client.delete(f"/api/inventory/movimientos/{mov.pk}/")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
