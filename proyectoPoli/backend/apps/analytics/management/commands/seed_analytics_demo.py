"""
Carga datos demo para analytics sin duplicar registros en ejecuciones sucesivas.
Uso: python manage.py seed_analytics_demo
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.inventory.models import MovStock
from apps.products.models import Producto


DEMO_REF_TIPO = "ANALYTICS_DEMO"
DEMO_PRODUCTS = [
    {"sku": "DEMO-AN-001", "nombre": "Demo Guantes Nitrilo"},
    {"sku": "DEMO-AN-002", "nombre": "Demo Mascarillas"},
    {"sku": "DEMO-AN-003", "nombre": "Demo Alcohol Gel"},
]
DAY_OFFSETS = [14, 10, 7, 4, 1]


class Command(BaseCommand):
    help = "Carga productos y movimientos demo para probar analytics (idempotente)."

    def _demo_key(self, sku, tipo, tag):
        return f"DEMO_ANALYTICS_SEED|{sku}|{tipo}|{tag}"

    def _mov_exists(self, producto_id, tipo, observacion):
        return MovStock.objects.filter(
            producto_id=producto_id,
            tipo=tipo,
            ref_tipo=DEMO_REF_TIPO,
            observacion=observacion,
        ).exists()

    def _create_mov_with_fecha(self, producto, tipo, cantidad, fecha_dt, observacion):
        mov = MovStock.objects.create(
            producto=producto,
            tipo=tipo,
            cantidad=cantidad,
            ref_tipo=DEMO_REF_TIPO,
            observacion=observacion,
        )
        # Mantiene validación de negocio en create y luego fija fecha demo.
        MovStock.objects.filter(pk=mov.pk).update(fecha=fecha_dt)

    @transaction.atomic
    def handle(self, *args, **options):
        now = timezone.now()
        productos_creados = 0
        productos_reutilizados = 0
        movimientos_in_creados = 0
        movimientos_out_creados = 0
        fechas_generadas = []

        for idx, data in enumerate(DEMO_PRODUCTS):
            producto, created = Producto.objects.get_or_create(
                sku=data["sku"],
                defaults={
                    "nombre": data["nombre"],
                    "unidad": "UNIDAD",
                    "categoria": "DEMO_ANALYTICS",
                    "stock_minimo": 0,
                    "activo": True,
                },
            )
            if created:
                productos_creados += 1
            else:
                productos_reutilizados += 1

            obs_in = self._demo_key(producto.sku, "IN", "stock_base")
            if not self._mov_exists(producto.id, "IN", obs_in):
                self._create_mov_with_fecha(
                    producto=producto,
                    tipo="IN",
                    cantidad=1000,
                    fecha_dt=now - timedelta(days=21),
                    observacion=obs_in,
                )
                movimientos_in_creados += 1
                fechas_generadas.append((now - timedelta(days=21)).date())

            # OUT en días distintos (>= 3 puntos por producto para tendencias).
            base = 12 + (idx * 5)
            for point_idx, day_offset in enumerate(DAY_OFFSETS):
                fecha_point = now - timedelta(days=day_offset)
                cantidad_out = base + (point_idx * 3)
                tag = fecha_point.date().isoformat()
                obs_out = self._demo_key(producto.sku, "OUT", tag)
                if self._mov_exists(producto.id, "OUT", obs_out):
                    continue
                self._create_mov_with_fecha(
                    producto=producto,
                    tipo="OUT",
                    cantidad=cantidad_out,
                    fecha_dt=fecha_point,
                    observacion=obs_out,
                )
                movimientos_out_creados += 1
                fechas_generadas.append(fecha_point.date())

        if fechas_generadas:
            fecha_min = min(fechas_generadas)
            fecha_max = max(fechas_generadas)
            rango = f"{fecha_min} -> {fecha_max}"
        else:
            rango = "sin cambios (datos demo ya existentes)"

        self.stdout.write(self.style.SUCCESS("Seed analytics demo completado."))
        self.stdout.write(f"- Productos creados: {productos_creados}")
        self.stdout.write(f"- Productos reutilizados: {productos_reutilizados}")
        self.stdout.write(f"- Movimientos IN creados: {movimientos_in_creados}")
        self.stdout.write(f"- Movimientos OUT creados: {movimientos_out_creados}")
        self.stdout.write(f"- Rango de fechas generado: {rango}")
