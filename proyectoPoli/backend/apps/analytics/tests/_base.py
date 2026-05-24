"""Helpers compartidos para tests backend/API del módulo analytics (TC01–TC07)."""
from datetime import date, datetime, timedelta

from django.test import TestCase
from django.utils import timezone

from apps.inventory.models import MovStock
from apps.products.models import Producto


class BaseAnalyticsETLTestCase(TestCase):
    """Movimientos OUT, serie elegible y utilidades de fecha para corridas ETL."""

    def setUp(self):
        self.producto = Producto.objects.create(
            sku="ANAL-ETL-BASE",
            nombre="Producto base analytics tests",
            stock_minimo=0,
        )

    @staticmethod
    def _fecha_mov(dia):
        return timezone.make_aware(datetime.combine(dia, datetime.min.time().replace(hour=12)))

    def _crear_mov_stock(self, tipo, cantidad, dia, producto=None):
        producto = producto or self.producto
        mov = MovStock.objects.create(producto=producto, tipo=tipo, cantidad=cantidad)
        MovStock.objects.filter(pk=mov.pk).update(fecha=self._fecha_mov(dia))
        return mov

    def _crear_serie_out_elegible(self, producto, ref, cantidades):
        dias = [ref + timedelta(days=i) for i in range(len(cantidades))]
        self._crear_mov_stock("IN", 1000, dias[0] - timedelta(days=1), producto=producto)
        for dia, cantidad in zip(dias, cantidades):
            self._crear_mov_stock("OUT", cantidad, dia, producto=producto)
        return dias
