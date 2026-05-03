"""
Seed local: 20 movimientos de stock (IN/OUT) con fecha de hoy a mediodía (TIME_ZONE).

Solo para pruebas. No modifica ETL ni Celery.

Verificación sugerida (shell):

    from django.utils import timezone
    from apps.inventory.models import MovStock

    hoy = timezone.localdate()
    MovStock.objects.filter(fecha__date=hoy).count()

Para reflejar estos movimientos en tablas analíticas (el Beat D-1 procesa ayer):

    from django.utils import timezone
    from datetime import date
    from apps.analytics.etl import ejecutar_etl_analitico

    hoy = timezone.localdate()
    ejecutar_etl_analitico(fecha_desde=hoy, fecha_hasta=hoy)
"""
from datetime import datetime, time
from random import choice, choices, randint

from django.core.management.base import BaseCommand
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.inventory.models import MovStock, StockProducto
from apps.products.models import Producto

NOMBRES_PRODUCTO = [
    "trapos de piso",
    "Tinta Epson L1250 Negro",
    "Pilas AA",
    "etiquetas adhesivas",
]

TOTAL_MOVIMIENTOS = 20
OBS_SEED = "seed_movimientos_hoy"


class Command(BaseCommand):
    help = "Crea 20 movimientos de stock de prueba para hoy (IN/OUT aleatorios, cantidad 1-15). Solo entorno local."

    def add_arguments(self, parser):
        parser.add_argument(
            "--cantidad",
            type=int,
            default=TOTAL_MOVIMIENTOS,
            help=f"Cantidad de movimientos a crear (default: {TOTAL_MOVIMIENTOS}).",
        )

    def handle(self, *args, **options):
        n_mov = max(1, min(options.get("cantidad") or TOTAL_MOVIMIENTOS, 500))

        hoy = timezone.localdate()
        fecha_movimiento = timezone.make_aware(datetime.combine(hoy, time(12, 0)))

        productos = []
        faltantes = []
        for nombre in NOMBRES_PRODUCTO:
            p = Producto.objects.filter(nombre__iexact=nombre.strip()).first()
            if p is None:
                faltantes.append(nombre)
                self.stderr.write(self.style.WARNING(f"No existe producto con nombre (iexact): «{nombre}»"))
            else:
                productos.append(p)

        if not productos:
            self.stderr.write(
                self.style.ERROR("No hay ninguno de los productos buscados. Cree los productos o ajuste NOMBRES_PRODUCTO.")
            )
            return

        if faltantes:
            self.stdout.write(
                self.style.WARNING(
                    f"Se omiten {len(faltantes)} nombre(s) sin coincidencia. "
                    f"Se usarán {len(productos)} producto(s) para {n_mov} movimiento(s)."
                )
            )

        elegidos = choices(productos, k=n_mov)
        creados = []
        self.stdout.write(f"Fecha movimientos (local): {fecha_movimiento.isoformat()} | día: {hoy}")

        with transaction.atomic():
            for producto in elegidos:
                stock, _ = StockProducto.objects.get_or_create(
                    producto=producto,
                    defaults={"qty_on_hand": 0},
                )
                stock.refresh_from_db()

                qty = randint(1, 15)
                tipo = choice(["IN", "OUT"])

                if tipo == "OUT":
                    if stock.qty_on_hand <= 0:
                        tipo = "IN"
                    elif qty > stock.qty_on_hand:
                        qty = stock.qty_on_hand

                try:
                    mov = MovStock.objects.create(
                        producto=producto,
                        tipo=tipo,
                        cantidad=qty,
                        observacion=OBS_SEED,
                    )
                except ValidationError as e:
                    self.stderr.write(self.style.ERROR(f"Movimiento rechazado ({producto.nombre}): {e}"))
                    continue

                MovStock.objects.filter(pk=mov.pk).update(fecha=fecha_movimiento)
                mov.refresh_from_db()
                stock.refresh_from_db()
                creados.append(
                    {
                        "mov_id": mov.pk,
                        "producto": producto.nombre,
                        "sku": producto.sku,
                        "tipo": tipo,
                        "cantidad": qty,
                        "fecha": mov.fecha,
                        "stock": stock.qty_on_hand,
                    }
                )

        self.stdout.write(self.style.SUCCESS(f"\nMovimientos creados: {len(creados)} / solicitados: {n_mov}\n"))
        for row in creados:
            self.stdout.write(
                f"  id={row['mov_id']} | {row['producto']} ({row['sku']}) | {row['tipo']} | "
                f"cant={row['cantidad']} | fecha={row['fecha']} | stock_actual={row['stock']}"
            )

        self.stdout.write(
            "\nVerificar en shell:\n"
            "  from django.utils import timezone\n"
            "  from apps.inventory.models import MovStock\n"
            "  hoy = timezone.localdate()\n"
            "  MovStock.objects.filter(fecha__date=hoy).count()\n"
        )
        self.stdout.write(
            "ETL analítico para incluir hoy en HechoConsumo (D-1 automático no cubre «hoy»):\n"
            "  from django.utils import timezone\n"
            "  from apps.analytics.etl import ejecutar_etl_analitico\n"
            "  hoy = timezone.localdate()\n"
            "  ejecutar_etl_analitico(fecha_desde=hoy, fecha_hasta=hoy)\n"
        )
