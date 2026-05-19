"""
Depura corridas ETL antiguas y resultados de tendencia asociados.

Los datos operativos originales no se eliminan. Solo se depuran resultados analíticos
derivados y recalculables para evitar crecimiento innecesario de la base de datos.

Uso:
  python manage.py limpiar_datos_analiticos
  python manage.py limpiar_datos_analiticos --dias-retencion 365
  python manage.py limpiar_datos_analiticos --dry-run
"""
from django.core.management.base import BaseCommand, CommandError

from apps.analytics.services.retencion import limpiar_datos_analiticos


class Command(BaseCommand):
    help = (
        "Elimina corridas analíticas antiguas y tendencias/proyecciones asociadas. "
        "No modifica datos operativos ni agregados HechoConsumo/ResumenConsumoMensual."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dias-retencion",
            type=int,
            default=180,
            help="Conservar corridas con fecha_ejecucion >= ahora - N días (default: 180).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simula la limpieza sin borrar registros.",
        )

    def handle(self, *args, **options):
        dias_retencion = options["dias_retencion"]
        dry_run = options["dry_run"]

        if dias_retencion < 1:
            raise CommandError("--dias-retencion debe ser un entero >= 1.")

        try:
            resultado = limpiar_datos_analiticos(
                dias_retencion=dias_retencion,
                dry_run=dry_run,
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(f"Fecha de corte: {resultado.fecha_corte.isoformat()}")
        self.stdout.write(f"Días de retención: {resultado.dias_retencion}")
        self.stdout.write(f"Corridas analíticas antiguas: {resultado.corridas_antiguas}")
        self.stdout.write(f"Tendencias lineales asociadas: {resultado.tendencias_asociadas}")
        self.stdout.write(f"Proyecciones de consumo asociadas: {resultado.proyecciones_asociadas}")

        if dry_run:
            self.stdout.write(self.style.WARNING("Modo simulación: no se eliminaron datos."))
            return

        self.stdout.write(
            self.style.SUCCESS(
                "Limpieza completada: "
                f"{resultado.eliminadas_corridas} corrida(s), "
                f"{resultado.eliminadas_tendencias} tendencia(s), "
                f"{resultado.eliminadas_proyecciones} proyección(es) eliminadas."
            )
        )
