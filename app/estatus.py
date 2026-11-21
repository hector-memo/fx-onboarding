"""Flujo de estatus de las solicitudes.

Las transiciones permitidas están definidas en un solo lugar (TRANSICIONES).
Al pasar a "Listo para operar" se actualiza el padrón en la misma transacción;
el correo se envía después de confirmarla, así un fallo de correo nunca
revierte el estatus ni el padrón. El aviso de la campana para el ejecutivo
se crea dentro de la misma transacción.
"""
import logging

from . import correo, notificaciones, padron
from .constantes import (
    CANCELADA, CORREO_NO_APLICA, CORREO_PENDIENTE, ESTATUS, LISTO, PENDIENTE, RECHAZADA, ROL_ADMIN,
)
from .db import transaccion
from .utils import ahora_str, folio

log = logging.getLogger("fx")

DUENO = "dueño"

# (estatus actual, estatus nuevo) -> quién puede hacerlo
TRANSICIONES = {
    (PENDIENTE, LISTO): ROL_ADMIN,
    (PENDIENTE, RECHAZADA): ROL_ADMIN,
    (PENDIENTE, CANCELADA): DUENO,
}
ESTATUS_FINALES = (LISTO, RECHAZADA, CANCELADA)


class ErrorEstatus(Exception):
    """El cambio de estatus no se puede aplicar."""


def validar_transicion(sol, nuevo, actor, motivo=""):
    if nuevo not in ESTATUS:
        raise ErrorEstatus("Estatus no válido.")
    actual = sol["estatus"]
    if actual in ESTATUS_FINALES:
        raise ErrorEstatus(
            f"La solicitud {folio(sol['id'])} ya fue atendida (estatus actual: {actual}); no se puede cambiar."
        )
    regla = TRANSICIONES.get((actual, nuevo))
    if regla is None:
        raise ErrorEstatus(f"No se permite cambiar de {actual} a {nuevo}.")
    if regla == ROL_ADMIN and actor["rol"] != ROL_ADMIN:
        raise ErrorEstatus("Solo un administrador puede realizar este cambio.")
    if regla == DUENO and actor["usuario"] != sol["ejecutivo"]:
        raise ErrorEstatus("Solo el ejecutivo que envió la solicitud puede cancelarla.")
    if nuevo == RECHAZADA and not (motivo or "").strip():
        raise ErrorEstatus("El motivo de rechazo es obligatorio.")


def cambiar_estatus(db, sid, nuevo, actor, motivo=""):
    """Aplica el cambio de estatus (y el padrón, si aplica) de forma atómica."""
    motivo = (motivo or "").strip()
    with transaccion(db):
        sol = db.execute("SELECT * FROM solicitudes WHERE id = ?", (sid,)).fetchone()
        if sol is None:
            raise ErrorEstatus("La solicitud no existe.")
        validar_transicion(sol, nuevo, actor, motivo)

        if nuevo == LISTO:
            try:
                padron.aplicar_solicitud(db, sol, actor["usuario"])
            except padron.ErrorPadron as error:
                raise ErrorEstatus(f"{folio(sid)}: {error}") from error

        momento = ahora_str()
        estado_correo = CORREO_PENDIENTE if nuevo in (LISTO, RECHAZADA) else CORREO_NO_APLICA
        cur = db.execute(
            "UPDATE solicitudes SET estatus = ?, fecha_atencion = ?, atendido_por = ?, motivo_resolucion = ?, "
            "estatus_correo = ? WHERE id = ? AND estatus = ?",
            (nuevo, momento, actor["usuario"], motivo or None, estado_correo, sid, PENDIENTE),
        )
        if cur.rowcount != 1:
            raise ErrorEstatus("La solicitud cambió mientras la atendías. Recarga la página.")
        db.execute(
            "INSERT INTO historial_estatus (solicitud_id, fecha, usuario, estatus_anterior, estatus_nuevo, comentario) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (sid, momento, actor["usuario"], sol["estatus"], nuevo, motivo or None),
        )
        notificaciones.por_cambio_estatus(db, sid, actor)
    log.info("Estatus %s: %s -> %s por %s", folio(sid), sol["estatus"], nuevo, actor["usuario"])
    return db.execute("SELECT * FROM solicitudes WHERE id = ?", (sid,)).fetchone()


def atender(db, sid, nuevo, actor, motivo="", enviar_correo=True):
    """Cambia el estatus y, si corresponde, notifica por correo.

    Devuelve (solicitud, correo_ok) donde correo_ok es True/False, o None si no aplica.
    """
    sol = cambiar_estatus(db, sid, nuevo, actor, motivo)
    correo_ok = None
    if enviar_correo and sol["estatus_correo"] == CORREO_PENDIENTE:
        correo_ok = correo.notificar(db, sid)
    return sol, correo_ok


def atender_varias(db, ids, actor):
    """Marca varias solicitudes como Listo para operar. Las que no cumplen se omiten."""
    listas, fallidas, correos_error = [], [], []
    for sid in ids:
        try:
            _sol, correo_ok = atender(db, sid, LISTO, actor)
        except ErrorEstatus as error:
            fallidas.append((sid, str(error)))
            continue
        listas.append(sid)
        if correo_ok is False:
            correos_error.append(sid)
    return listas, fallidas, correos_error
