"""
Comando para ejecutar el proceso ETL analítico (Release 1 — ejecución manual).
Uso: python manage.py run_etl_analitico [--desde YYYY-MM-DD] [--hasta YYYY-MM-DD] [--ventana-tendencia-dias 30]
"""
from datetime import datetime

from django.core.management.base import BaseCommand

from apps.analytics.etl import ejecutar_etl_analitico


class Command(BaseCommand):
    help = "Ejecuta el ETL analítico: extrae de MovStock y carga HechoConsumo. Registra la corrida."

    def add_arguments(self, parser):
        parser.add_argument("--desde", type=str, default=None, help="Fecha desde (YYYY-MM-DD)")
        parser.add_argument("--hasta", type=str, default=None, help="Fecha hasta (YYYY-MM-DD)")
        parser.add_argument(
            "--ventana-tendencia-dias",
            type=int,
            default=30,
            help="Ventana histórica para cálculo de tendencias (default: 30 días).",
        )

    def handle(self, *args, **options):
        desde = options.get("desde")
        hasta = options.get("hasta")
        ventana_tendencia_dias = options.get("ventana_tendencia_dias")
        if desde:
            try:
                desde = datetime.strptime(desde, "%Y-%m-%d").date()
            except ValueError:
                self.stderr.write(self.style.ERROR("Formato --desde inválido. Use YYYY-MM-DD."))
                return
        if hasta:
            try:
                hasta = datetime.strptime(hasta, "%Y-%m-%d").date()
            except ValueError:
                self.stderr.write(self.style.ERROR("Formato --hasta inválido. Use YYYY-MM-DD."))
                return
        if desde and hasta and desde > hasta:
            self.stderr.write(self.style.ERROR("--desde no puede ser mayor que --hasta."))
            return
        if ventana_tendencia_dias is not None and ventana_tendencia_dias < 1:
            self.stderr.write(self.style.ERROR("--ventana-tendencia-dias debe ser >= 1."))
            return

        try:
            corrida = ejecutar_etl_analitico(
                fecha_desde=desde,
                fecha_hasta=hasta,
                tendencia_ventana_dias=ventana_tendencia_dias,
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"ETL finalizado: {corrida.estado}, {corrida.registros_procesados} registros. {corrida.mensaje}"
                )
            )
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"ETL falló: {e}"))
