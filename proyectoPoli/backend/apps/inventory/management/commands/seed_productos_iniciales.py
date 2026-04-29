from django.core.management.base import BaseCommand
from django.db import transaction

from apps.inventory.models import MovStock, StockProducto
from apps.products.models import Producto


PRODUCTOS_INICIALES = [
    {
        "nombre": "Tinta Epson L1250 Negro",
        "categoria": "Consumibles",
        "unidad": "Unidades",
        "stock_actual": 10,
        "stock_minimo": 4,
    },
    {
        "nombre": "Etiquetas Adhesivas",
        "categoria": "Consumibles",
        "unidad": "Rollos",
        "stock_actual": 10,
        "stock_minimo": 3,
    },
    {
        "nombre": "Boligrafos Negros",
        "categoria": "Articulos de oficina",
        "unidad": "Unidades",
        "stock_actual": 20,
        "stock_minimo": 10,
    },
    {
        "nombre": "Pilas AA",
        "categoria": "Consumibles",
        "unidad": "Paquetes",
        "stock_actual": 6,
        "stock_minimo": 2,
    },
]


class Command(BaseCommand):
    help = "Carga productos iniciales (idempotente) y ajusta stock con movimientos."

    @transaction.atomic
    def handle(self, *args, **options):
        creados = 0
        actualizados = 0
        sin_cambios = 0
        movimientos = 0

        for item in PRODUCTOS_INICIALES:
            nombre = item["nombre"].strip()
            categoria = item["categoria"].strip()
            unidad = item["unidad"].strip()
            stock_minimo = int(item["stock_minimo"])
            stock_objetivo = int(item["stock_actual"])

            producto = Producto.objects.filter(nombre__iexact=nombre).first()
            if producto is None:
                # SKU vacío -> el modelo Producto autogenera SPK-#### al guardar.
                producto = Producto.objects.create(
                    sku="",
                    nombre=nombre,
                    categoria=categoria,
                    unidad=unidad,
                    stock_minimo=stock_minimo,
                )
                creados += 1
                self.stdout.write(self.style.SUCCESS(f"Creado producto: {producto.nombre} ({producto.sku})"))
            else:
                cambios = []
                if producto.categoria != categoria:
                    producto.categoria = categoria
                    cambios.append("categoria")
                if producto.unidad != unidad:
                    producto.unidad = unidad
                    cambios.append("unidad")
                if producto.stock_minimo != stock_minimo:
                    producto.stock_minimo = stock_minimo
                    cambios.append("stock_minimo")

                if cambios:
                    producto.save(update_fields=cambios)
                    actualizados += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"Actualizado producto: {producto.nombre} ({', '.join(cambios)})"
                        )
                    )
                else:
                    sin_cambios += 1

            stock, _ = StockProducto.objects.get_or_create(producto=producto, defaults={"qty_on_hand": 0})
            stock_actual = stock.qty_on_hand
            delta = stock_objetivo - stock_actual
            if delta != 0:
                tipo = "IN" if delta > 0 else "ADJ"
                cantidad = abs(delta) if tipo == "IN" else delta
                MovStock.objects.create(
                    tipo=tipo,
                    producto=producto,
                    cantidad=cantidad,
                    ref_tipo="SEED_INICIAL",
                    observacion=f"Seed inicial de inventario. Stock objetivo={stock_objetivo}.",
                )
                movimientos += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Stock ajustado para {producto.nombre}: {stock_actual} -> {stock_objetivo} ({tipo} {cantidad})"
                    )
                )
            else:
                self.stdout.write(f"Stock sin cambios para {producto.nombre}: {stock_actual}")

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "Seed completado | "
                f"creados={creados}, actualizados={actualizados}, "
                f"sin_cambios={sin_cambios}, movimientos={movimientos}"
            )
        )
