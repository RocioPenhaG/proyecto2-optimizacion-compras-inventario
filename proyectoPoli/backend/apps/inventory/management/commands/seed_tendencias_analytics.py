"""
Seed local: movimientos OUT históricos para probar tendencias lineales en analytics.

Crea entradas IN técnicas (una por producto, día anterior al rango) y salidas OUT
con patrones de cantidad distintos por producto. Solo entorno local.

Uso:
    python manage.py seed_tendencias_analytics
    python manage.py seed_tendencias_analytics --dias 60 --cantidad 20

ETL sugerido (incluir ventana de tendencia >= días del seed para que entren todos los puntos):

    python manage.py run_etl_analitico --desde YYYY-MM-DD --hasta YYYY-MM-DD --ventana-tendencia-dias 60
"""
from datetime import datetime, time, timedelta

from django.core.management.base import BaseCommand
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.inventory.models import MovStock
from apps.products.models import Producto

NOMBRES_PRODUCTO = [
    "trapos de piso",
    "Tinta Epson L1250 Negro",
    "Pilas AA",
    "etiquetas adhesivas",
]

PATRON_ETIQUETA = [3, 9, 2, 12, 6]

OBS_PREP = (
    "SEED tendencias analytics: entrada técnica stock inicial "
    "(pruebas locales; no borrar sin revisar inventario)"
)
OBS_OUT = "SEED tendencias analytics OUT"

DEFAULT_DIAS = 60
DEFAULT_CANTIDAD_OUT = 20


def _noon_on(d):
    return timezone.make_aware(datetime.combine(d, time(12, 0)))


def _fechas_equidistantes(hoy, dias, n):
    """n fechas (date) entre hoy-(dias-1) y hoy inclusive."""
    if n < 1:
        return []
    if n == 1:
        return [hoy - timedelta(days=dias - 1)]
    inicio = hoy - timedelta(days=dias - 1)
    out = []
    for i in range(n):
        delta = round((dias - 1) * i / (n - 1))
        out.append(inicio + timedelta(days=delta))
    return out


def _cantidades_ascendente(n):
    if n == 1:
        return [2]
    return [min(15, max(1, round(2 + i * (8 / (n - 1))))) for i in range(n)]


def _cantidades_descendente(n):
    if n == 1:
        return [10]
    return [min(15, max(1, round(10 - i * (8 / (n - 1))))) for i in range(n)]


def _cantidades_estable(n):
    return [min(15, max(1, 5))] * n


def _cantidades_irregular(n):
    return [PATRON_ETIQUETA[i % len(PATRON_ETIQUETA)] for i in range(n)]


class Command(BaseCommand):
    help = (
        "Crea salidas OUT históricas (y entradas IN técnicas previas) para probar "
        "tendencias en analytics. Productos: trapos de piso, Tinta Epson…, Pilas AA, etiquetas adhesivas."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dias",
            type=int,
            default=DEFAULT_DIAS,
            help=f"Largo del período histórico de salidas OUT, en días inclusivos (default: {DEFAULT_DIAS}).",
        )
        parser.add_argument(
            "--cantidad",
            type=int,
            default=DEFAULT_CANTIDAD_OUT,
            help=f"Total de movimientos OUT a crear (default: {DEFAULT_CANTIDAD_OUT}; debe ser múltiplo de 4).",
        )

    def handle(self, *args, **options):
        dias = options.get("dias") or DEFAULT_DIAS
        cantidad_out = options.get("cantidad") or DEFAULT_CANTIDAD_OUT

        if dias < 5:
            self.stderr.write(self.style.ERROR("--dias debe ser al menos 5 (se necesitan varios puntos en el tiempo)."))
            return
        if cantidad_out < 4 or cantidad_out % 4 != 0:
            self.stderr.write(
                self.style.ERROR("--cantidad debe ser un entero >= 4 y múltiplo de 4 (un bloque por cada uno de los 4 productos).")
            )
            return

        n_por_producto = cantidad_out // 4
        hoy = timezone.localdate()
        fecha_inicio_rango = hoy - timedelta(days=dias - 1)
        fecha_prep = fecha_inicio_rango - timedelta(days=1)
        dt_prep = _noon_on(fecha_prep)

        productos_meta = []
        faltantes = []
        for nombre in NOMBRES_PRODUCTO:
            p = Producto.objects.filter(nombre__iexact=nombre.strip()).first()
            if p is None:
                faltantes.append(nombre)
            else:
                productos_meta.append((p, nombre))

        if len(productos_meta) < 4:
            self.stderr.write(
                self.style.ERROR(
                    "Se requieren los 4 productos por nombre (iexact). Faltan: "
                    + ", ".join(faltantes or NOMBRES_PRODUCTO)
                )
            )
            return

        # (producto, nombre_busqueda, patrón_label, cantidades_out)
        bloques = [
            (
                productos_meta[0][0],
                productos_meta[0][1],
                "ascendente",
                _cantidades_ascendente(n_por_producto),
            ),
            (
                productos_meta[1][0],
                productos_meta[1][1],
                "descendente",
                _cantidades_descendente(n_por_producto),
            ),
            (
                productos_meta[2][0],
                productos_meta[2][1],
                "estable",
                _cantidades_estable(n_por_producto),
            ),
            (
                productos_meta[3][0],
                productos_meta[3][1],
                "irregular",
                _cantidades_irregular(n_por_producto),
            ),
        ]

        fechas_out = _fechas_equidistantes(hoy, dias, n_por_producto)
        filas_resumen = []
        prep_creadas = 0
        out_creadas = 0

        with transaction.atomic():
            for producto, _nombre, patron, cantidades in bloques:
                total_out = sum(cantidades)
                buffer_extra = max(50, total_out // 2)
                qty_in = total_out + buffer_extra

                mov_in = MovStock.objects.create(
                    producto=producto,
                    tipo="IN",
                    cantidad=qty_in,
                    observacion=OBS_PREP,
                )
                MovStock.objects.filter(pk=mov_in.pk).update(fecha=dt_prep)
                prep_creadas += 1

                for fecha_d, cant in zip(fechas_out, cantidades):
                    dt_out = _noon_on(fecha_d)
                    try:
                        mov = MovStock.objects.create(
                            producto=producto,
                            tipo="OUT",
                            cantidad=cant,
                            observacion=OBS_OUT,
                        )
                    except ValidationError as e:
                        self.stderr.write(self.style.ERROR(f"OUT rechazado ({producto.nombre}): {e}"))
                        raise
                    MovStock.objects.filter(pk=mov.pk).update(fecha=dt_out)
                    out_creadas += 1
                    filas_resumen.append(
                        {
                            "producto": producto.nombre,
                            "fecha": fecha_d.isoformat(),
                            "tipo": "OUT",
                            "cantidad": cant,
                            "patron": patron,
                        }
                    )

        self.stdout.write(self.style.SUCCESS("\nDetalle movimientos OUT:\n"))
        for row in sorted(filas_resumen, key=lambda r: (r["fecha"], r["producto"])):
            self.stdout.write(
                f"  {row['producto']} | {row['fecha']} | {row['tipo']} | cant={row['cantidad']} | "
                f"patrón esperado: {row['patron']}"
            )

        fecha_desde_etl = fecha_inicio_rango.isoformat()
        fecha_hasta_etl = hoy.isoformat()

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Seed de tendencias completado."))
        self.stdout.write(f"  Movimientos OUT creados: {out_creadas}")
        self.stdout.write(f"  Entradas técnicas IN creadas: {prep_creadas}")
        self.stdout.write(f"  Rango sugerido para ETL: {fecha_desde_etl} → {fecha_hasta_etl}")
        self.stdout.write(f"  (Entradas técnicas en: {fecha_prep.isoformat()}, fuera del rango OUT)\n")

        self.stdout.write("Procesar analytics (CLI):\n")
        self.stdout.write(
            f'  python manage.py run_etl_analitico --desde {fecha_desde_etl} --hasta {fecha_hasta_etl} '
            f"--ventana-tendencia-dias {dias}\n"
        )
        self.stdout.write(
            "  Use --ventana-tendencia-dias igual o mayor que --dias del seed para que la regresión "
            "use todos los días con salidas del período.\n"
        )

        self.stdout.write("Desde shell Django:\n")
        self.stdout.write("  from datetime import date\n")
        self.stdout.write("  from apps.analytics.etl import ejecutar_etl_analitico\n")
        self.stdout.write(
            f"  ejecutar_etl_analitico(fecha_desde=date.fromisoformat('{fecha_desde_etl}'), "
            f"fecha_hasta=date.fromisoformat('{fecha_hasta_etl}'), tendencia_ventana_dias={dias})\n"
        )

        self.stdout.write("Verificar MovStock (shell):\n")
        self.stdout.write("  from apps.inventory.models import MovStock\n")
        self.stdout.write(f"  MovStock.objects.filter(observacion__startswith='SEED tendencias').count()\n")
        self.stdout.write(
            f"  MovStock.objects.filter(tipo='OUT', fecha__date__gte='{fecha_desde_etl}', "
            f"fecha__date__lte='{fecha_hasta_etl}').values('producto__nombre','fecha','cantidad')\n"
        )

        self.stdout.write("Verificar HechoConsumo tras ETL:\n")
        self.stdout.write("  from apps.analytics.models import HechoConsumo\n")
        self.stdout.write(
            f"  HechoConsumo.objects.filter(tipo_movimiento='OUT', fecha__gte='{fecha_desde_etl}', "
            f"fecha__lte='{fecha_hasta_etl}').order_by('fecha','producto_id')\n"
        )

        self.stdout.write(
            "Dashboard: recargar la vista de analytics/consumo; revisar KPIs, top consumidos y "
            "sección de tendencias (ascendente / descendente / estable / irregular según producto).\n"
        )
