import re

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.models import Role, User
from .models import Producto, siguiente_sku_spk


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


class ProductoSkuAutogeneradoTests(TestCase):
    def test_autogen_formato_spk_y_secuencia(self):
        p1 = Producto(nombre="A", unidad="UN")
        p1.save()
        self.assertRegex(p1.sku, r"^SPK-\d{4}$")
        p2 = Producto(nombre="B", unidad="UN")
        p2.save()
        self.assertRegex(p2.sku, r"^SPK-\d{4}$")
        n1 = int(re.match(r"^SPK-(\d{4})$", p1.sku).group(1))
        n2 = int(re.match(r"^SPK-(\d{4})$", p2.sku).group(1))
        self.assertEqual(n2, n1 + 1)

    def test_siguiente_sku_ignora_formato_distinto(self):
        Producto.objects.create(sku="LEGACY-99", nombre="L", unidad="UN")
        p = Producto(nombre="Nuevo", unidad="UN")
        p.save()
        self.assertEqual(p.sku, "SPK-0001")

    def test_siguiente_sku_incrementa_max_spk(self):
        Producto.objects.create(sku="SPK-0003", nombre="A", unidad="UN")
        Producto.objects.create(sku="OTRO", nombre="B", unidad="UN")
        p = Producto(nombre="C", unidad="UN")
        p.save()
        self.assertEqual(p.sku, "SPK-0004")

    def test_sku_explicito_no_se_sobrescribe(self):
        p = Producto(sku="MANUAL-1", nombre="M", unidad="UN")
        p.save()
        self.assertEqual(p.sku, "MANUAL-1")

    def test_siguiente_sku_spk_helper(self):
        Producto.objects.create(sku="SPK-0009", nombre="X", unidad="UN")
        self.assertEqual(siguiente_sku_spk(), "SPK-0010")
