from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.models import Role, User
from .models import Producto


class FuncionarioCatalogoTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.func = User.objects.create_user(
            username="func_prod",
            password="x",
            role=Role.FUNCIONARIO,
        )
        self.compras = User.objects.create_user(
            username="comp_prod",
            password="x",
            role=Role.COMPRAS,
        )
        self.producto = Producto.objects.create(
            sku="SKU-01",
            nombre="Insumo test",
            unidad="UN",
            categoria="Cat",
        )

    def test_funcionario_list_productos_sin_stock(self):
        self.client.force_authenticate(self.func)
        r = self.client.get("/api/products/productos/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        data = r.json()
        self.assertEqual(len(data), 1)
        self.assertNotIn("stock_actual", data[0])
        self.assertNotIn("stock_minimo", data[0])
        self.assertEqual(data[0]["sku"], "SKU-01")

    def test_funcionario_no_crear_producto(self):
        self.client.force_authenticate(self.func)
        r = self.client.post(
            "/api/products/productos/",
            {"sku": "Nuevo", "nombre": "N", "unidad": "UN"},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_compras_puede_crear_producto(self):
        self.client.force_authenticate(self.compras)
        r = self.client.post(
            "/api/products/productos/",
            {"sku": "Nuevo2", "nombre": "N2", "unidad": "UN"},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)

    def test_funcionario_no_estadisticas_ni_inventario(self):
        self.client.force_authenticate(self.func)
        self.assertEqual(
            self.client.get("/api/products/estadisticas/").status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.client.get("/api/inventory/stock/").status_code,
            status.HTTP_403_FORBIDDEN,
        )
