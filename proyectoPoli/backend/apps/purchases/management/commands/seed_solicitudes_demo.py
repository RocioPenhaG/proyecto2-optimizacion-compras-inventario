"""
Carga solicitudes de insumos demo sin duplicar en ejecuciones sucesivas.
Uso: python manage.py seed_solicitudes_demo
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.products.models import Producto
from apps.users.models import Role, User
from apps.purchases.models import EstadoSolicitud, SolicitudDetalle, SolicitudInsumo


SEED_KEY = "SEED_SOLICITUDES_DEMO"
PRODUCTOS_BASE = [
    {"nombre": "Tinta Epson L1250 Negro", "categoria": "Consumibles", "unidad": "Unidades", "stock_minimo": 4},
    {"nombre": "Etiquetas Adhesivas", "categoria": "Consumibles", "unidad": "Rollos", "stock_minimo": 3},
    {"nombre": "Boligrafos Negros", "categoria": "Articulos de oficina", "unidad": "Unidades", "stock_minimo": 10},
    {"nombre": "Pilas AA", "categoria": "Consumibles", "unidad": "Paquetes", "stock_minimo": 2},
]

SOLICITUDES_DEMO = [
    {
        "slug": "funcionario-cocina",
        "destino": "Cocina central",
        "estado": EstadoSolicitud.SOLICITADO,
        "detalles": [
            {"producto_nombre": "Tinta Epson L1250 Negro", "cantidad": 2, "observacion": "Impresiones de guias"},
            {"producto_nombre": "Etiquetas Adhesivas", "cantidad": 3, "observacion": "Etiquetado semanal"},
        ],
    },
    {
        "slug": "funcionario-deposito",
        "destino": "Deposito principal",
        "estado": EstadoSolicitud.EN_REVISION,
        "detalles": [
            {"producto_nombre": "Boligrafos Negros", "cantidad": 15, "observacion": "Reposicion trimestral"},
        ],
    },
    {
        "slug": "funcionario-mantenimiento",
        "destino": "Mantenimiento",
        "estado": EstadoSolicitud.COMPRA_ACEPTADA,
        "detalles": [
            {"producto_nombre": "Pilas AA", "cantidad": 4, "observacion": "Controles remotos y sensores"},
        ],
    },
    {
        "slug": "funcionario-fuera-catalogo",
        "destino": "Recepcion",
        "estado": EstadoSolicitud.SOLICITADO,
        "detalles": [
            {
                "descripcion_insumo_solicitado": "Porta credenciales plastico transparente",
                "cantidad": 20,
                "observacion": "Evento institucional",
            },
        ],
    },
]


class Command(BaseCommand):
    help = "Genera solicitudes de insumos demo (idempotente)."

    def _get_or_create_usuario_funcionario(self):
        user = User.objects.filter(role=Role.FUNCIONARIO).order_by("id").first()
        if user:
            return user, False
        user = User.objects.create_user(
            username="funcionario_seed",
            password="seed1234",
            role=Role.FUNCIONARIO,
            first_name="Funcionario",
            last_name="Seed",
            email="funcionario.seed@local.test",
        )
        return user, True

    def _ensure_productos_base(self):
        productos = {}
        creados = 0
        for p in PRODUCTOS_BASE:
            producto = Producto.objects.filter(nombre__iexact=p["nombre"]).first()
            if producto is None:
                producto = Producto.objects.create(
                    sku="",
                    nombre=p["nombre"],
                    categoria=p["categoria"],
                    unidad=p["unidad"],
                    stock_minimo=p["stock_minimo"],
                )
                creados += 1
            productos[p["nombre"]] = producto
        return productos, creados

    @transaction.atomic
    def handle(self, *args, **options):
        solicitante, user_created = self._get_or_create_usuario_funcionario()
        productos_map, productos_creados = self._ensure_productos_base()

        solicitudes_creadas = 0
        solicitudes_reutilizadas = 0
        detalles_creados = 0

        for row in SOLICITUDES_DEMO:
            marker = f"{SEED_KEY}|{row['slug']}"
            solicitud = SolicitudInsumo.objects.filter(
                solicitante=solicitante,
                observacion=marker,
            ).first()
            if solicitud is None:
                solicitud = SolicitudInsumo.objects.create(
                    solicitante=solicitante,
                    destino=row["destino"],
                    estado=row["estado"],
                    observacion=marker,
                )
                solicitudes_creadas += 1
            else:
                solicitudes_reutilizadas += 1
                cambios = []
                if solicitud.destino != row["destino"]:
                    solicitud.destino = row["destino"]
                    cambios.append("destino")
                if solicitud.estado != row["estado"]:
                    solicitud.estado = row["estado"]
                    cambios.append("estado")
                if cambios:
                    solicitud.save(update_fields=cambios)

            for idx, det in enumerate(row["detalles"], start=1):
                det_marker = f"{marker}|DET|{idx}"
                existing = SolicitudDetalle.objects.filter(
                    solicitud=solicitud,
                    observacion=det_marker,
                ).first()
                if existing:
                    continue

                producto = None
                descripcion = det.get("descripcion_insumo_solicitado", "")
                if "producto_nombre" in det:
                    producto = productos_map.get(det["producto_nombre"])
                    if producto is None:
                        raise CommandError(
                            f"No se encontro producto base para detalle: {det['producto_nombre']}"
                        )
                    descripcion = ""

                SolicitudDetalle.objects.create(
                    solicitud=solicitud,
                    producto=producto,
                    descripcion_insumo_solicitado=descripcion,
                    cantidad=int(det["cantidad"]),
                    observacion=det_marker,
                )
                detalles_creados += 1

        self.stdout.write(self.style.SUCCESS("Seed de solicitudes demo completado."))
        self.stdout.write(f"- Usuario funcionario creado: {'si' if user_created else 'no'}")
        self.stdout.write(f"- Productos base creados: {productos_creados}")
        self.stdout.write(f"- Solicitudes creadas: {solicitudes_creadas}")
        self.stdout.write(f"- Solicitudes reutilizadas: {solicitudes_reutilizadas}")
        self.stdout.write(f"- Detalles creados: {detalles_creados}")
