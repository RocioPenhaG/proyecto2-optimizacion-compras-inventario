"""
Notificaciones por correo para el módulo de solicitudes (Release 1).
Se envía un correo al solicitante cuando la solicitud pasa a Aprobada, Rechazada o Finalizada.
"""
import logging

from django.conf import settings
from django.core.mail import send_mail

from .models import EstadoSolicitud, SolicitudInsumo

logger = logging.getLogger(__name__)

ESTADO_LABEL = {
    EstadoSolicitud.COMPRA_ACEPTADA: "Compra aceptada",
    EstadoSolicitud.COMPRA_RECHAZADA: "Compra rechazada",
    EstadoSolicitud.FINALIZADO: "Finalizado",
}


def send_solicitud_estado_email(solicitud: SolicitudInsumo, nuevo_estado: str) -> None:
    """
    Envía un correo al solicitante informando el nuevo estado de su solicitud.
    Solo se envía si el usuario tiene email configurado.
    """
    if nuevo_estado not in (
        EstadoSolicitud.COMPRA_ACEPTADA,
        EstadoSolicitud.COMPRA_RECHAZADA,
        EstadoSolicitud.FINALIZADO,
    ):
        return

    solicitante = solicitud.solicitante
    if not getattr(solicitante, "email", None) or not solicitante.email.strip():
        logger.info(
            "No se envía notificación de solicitud #%s: usuario %s sin email",
            solicitud.pk,
            solicitante.username,
        )
        return

    estado_label = ESTADO_LABEL.get(nuevo_estado, nuevo_estado)
    subject = f"[Segupak] Solicitud #{solicitud.pk} — {estado_label}"

    lineas = [
        f"Hola {solicitante.get_full_name() or solicitante.username},",
        "",
        f"Tu solicitud de compra #{solicitud.pk} ha cambiado de estado a: {estado_label}.",
        "",
        f"Fecha: {solicitud.fecha}",
        f"Destino: {solicitud.destino or '(no indicado)'}",
    ]
    if nuevo_estado == EstadoSolicitud.COMPRA_RECHAZADA and solicitud.motivo_rechazo:
        lineas.append("")
        lineas.append(f"Motivo del rechazo: {solicitud.motivo_rechazo}")
    lineas.extend(["", "Podés consultar el detalle en la aplicación.", ""])
    body = "\n".join(lineas)

    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[solicitud.solicitante.email],
            fail_silently=False,
        )
    except Exception as e:
        logger.exception("Error enviando notificación de solicitud #%s: %s", solicitud.pk, e)
