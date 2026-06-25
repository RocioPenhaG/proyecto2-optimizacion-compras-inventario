import re

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.models import Role, User
from .models import Producto, renumerar_skus_spk_tras_eliminacion, siguiente_sku_spk


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

    def test_funcionario_no_editar_producto(self):
        self.client.force_authenticate(self.func)
        r = self.client.patch(
            f"/api/products/productos/{self.producto.id}/",
            {"nombre": "Cambiado"},
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

    def test_crear_producto_desde_solicitud_registra_stock_inicial(self):
        from apps.inventory.models import MovStock, StockProducto
        from apps.purchases.models import SolicitudInsumo
        from apps.users.models import User

        func = User.objects.create_user(username="f_prod_sol", password="x", role=Role.FUNCIONARIO)
        sol = SolicitudInsumo.objects.create(
            solicitante=func,
            destino="D",
            tipo_destino_compra="INVENTARIO",
        )

        self.client.force_authenticate(self.compras)
        r = self.client.post(
            "/api/products/productos/",
            {
                "nombre": "Insumo nuevo",
                "unidad": "UN",
                "stock_inicial": 12,
                "stock_minimo": 3,
                "solicitud_id": sol.pk,
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        producto_id = r.json()["id"]
        stock = StockProducto.objects.get(producto_id=producto_id)
        self.assertEqual(stock.qty_on_hand, 12)
        mov = MovStock.objects.filter(producto_id=producto_id, tipo="IN").first()
        self.assertIsNotNone(mov)
        self.assertEqual(mov.cantidad, 12)
        self.assertEqual(mov.ref_tipo, "SOLICITUD")
        self.assertEqual(mov.ref_id, sol.pk)
        self.assertEqual(r.json()["stock_minimo"], 3)

    def test_crear_producto_entrega_inmediata_sin_stock_minimo(self):
        from apps.purchases.models import SolicitudInsumo
        from apps.users.models import User

        func = User.objects.create_user(username="f_prod_ent", password="x", role=Role.FUNCIONARIO)
        sol = SolicitudInsumo.objects.create(
            solicitante=func,
            destino="D",
            tipo_destino_compra="ENTREGA_INMEDIATA",
        )
        self.client.force_authenticate(self.compras)
        r = self.client.post(
            "/api/products/productos/",
            {
                "nombre": "Puntual",
                "unidad": "UN",
                "stock_inicial": 5,
                "stock_minimo": 10,
                "solicitud_id": sol.pk,
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.json()["stock_minimo"], 0)

    def test_crear_producto_desde_solicitud_exige_stock_inicial(self):
        self.client.force_authenticate(self.compras)
        r = self.client.post(
            "/api/products/productos/",
            {"nombre": "Sin stock", "unidad": "UN", "solicitud_id": 1, "stock_inicial": 0},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("stock_inicial", r.json())

    def test_compras_puede_editar_producto(self):
        self.client.force_authenticate(self.compras)
        r = self.client.patch(
            f"/api/products/productos/{self.producto.id}/",
            {"nombre": "Actualizado", "stock_minimo": 5},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.nombre, "Actualizado")
        self.assertEqual(self.producto.stock_minimo, 5)

    def test_gerencia_solo_lectura_productos(self):
        gerencia = User.objects.create_user(
            username="ger_prod",
            password="x",
            role=Role.GERENCIA,
        )
        self.client.force_authenticate(gerencia)
        r_list = self.client.get("/api/products/productos/")
        self.assertEqual(r_list.status_code, status.HTTP_200_OK)
        self.assertIn("stock_actual", r_list.json()[0])

        r_create = self.client.post(
            "/api/products/productos/",
            {"sku": "G-1", "nombre": "Nuevo", "unidad": "UN"},
            format="json",
        )
        self.assertEqual(r_create.status_code, status.HTTP_403_FORBIDDEN)

        r_patch = self.client.patch(
            f"/api/products/productos/{self.producto.id}/",
            {"nombre": "Cambiado gerencia"},
            format="json",
        )
        self.assertEqual(r_patch.status_code, status.HTTP_403_FORBIDDEN)

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

    def test_renumerar_skus_tras_eliminacion(self):
        p8 = Producto.objects.create(sku="SPK-0008", nombre="Ocho", unidad="UN")
        p9 = Producto.objects.create(sku="SPK-0009", nombre="Nueve", unidad="UN")
        p10 = Producto.objects.create(sku="SPK-0010", nombre="Diez", unidad="UN")
        p9.delete()
        renumerar_skus_spk_tras_eliminacion(9)
        p8.refresh_from_db()
        p10.refresh_from_db()
        self.assertEqual(p8.sku, "SPK-0008")
        self.assertEqual(p10.sku, "SPK-0009")


class ProductoListadoOrdenBusquedaTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.compras = User.objects.create_user(
            username="c_list",
            password="x",
            role=Role.COMPRAS,
        )
        self.p1 = Producto.objects.create(sku="SPK-0001", nombre="Alfa papel", categoria="Oficina")
        self.p2 = Producto.objects.create(sku="SPK-0003", nombre="Beta tinta", categoria="Insumos")
        self.p3 = Producto.objects.create(sku="SPK-0002", nombre="Gamma clips", categoria="Oficina")

    def test_listado_por_defecto_orden_creacion_asc(self):
        self.client.force_authenticate(self.compras)
        r = self.client.get("/api/products/productos/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        ids = [p["id"] for p in r.json()]
        self.assertEqual(ids, [self.p1.id, self.p2.id, self.p3.id])

    def test_listado_orden_creacion_desc(self):
        self.client.force_authenticate(self.compras)
        r = self.client.get("/api/products/productos/?orden=creacion_desc")
        ids = [p["id"] for p in r.json()]
        self.assertEqual(ids, [self.p3.id, self.p2.id, self.p1.id])

    def test_listado_buscar_por_nombre_o_sku(self):
        self.client.force_authenticate(self.compras)
        r_nombre = self.client.get("/api/products/productos/?buscar=tinta")
        self.assertEqual(len(r_nombre.json()), 1)
        self.assertEqual(r_nombre.json()[0]["sku"], "SPK-0003")

        r_sku = self.client.get("/api/products/productos/?buscar=SPK-0002")
        self.assertEqual(len(r_sku.json()), 1)
        self.assertEqual(r_sku.json()[0]["nombre"], "Gamma clips")


class AdminEliminarProductoTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username="admin_prod",
            email="admin@local",
            password="x",
        )
        self.compras = User.objects.create_user(
            username="comp_del_prod",
            password="x",
            role=Role.COMPRAS,
        )
        self.producto = Producto.objects.create(sku="DEL-1", nombre="A borrar", unidad="UN")

    def test_admin_elimina_producto(self):
        self.client.force_authenticate(self.admin)
        r = self.client.delete(f"/api/products/productos/{self.producto.pk}/")
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Producto.objects.filter(pk=self.producto.pk).exists())

    def test_compras_no_elimina_producto(self):
        self.client.force_authenticate(self.compras)
        r = self.client.delete(f"/api/products/productos/{self.producto.pk}/")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_eliminar_spk_renumera_posteriores(self):
        p8 = Producto.objects.create(sku="SPK-0008", nombre="Ocho", unidad="UN")
        p9 = Producto.objects.create(sku="SPK-0009", nombre="Nueve", unidad="UN")
        p10 = Producto.objects.create(sku="SPK-0010", nombre="Diez", unidad="UN")
        self.client.force_authenticate(self.admin)
        r = self.client.delete(f"/api/products/productos/{p9.pk}/")
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT)
        p8.refresh_from_db()
        p10.refresh_from_db()
        self.assertEqual(p8.sku, "SPK-0008")
        self.assertEqual(p10.sku, "SPK-0009")
