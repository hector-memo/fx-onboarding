"""Notificaciones por correo.

Con MAIL_ENABLED=false los correos se guardan como .html en la carpeta outbox/
para probar el flujo sin servidor SMTP.
"""
import logging
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

from flask import current_app, render_template

from .constantes import CORREO_ENVIADO, CORREO_ERROR
from .utils import ahora, folio

log = logging.getLogger("fx")


def construir(sol):
    asunto = f"[FX Onboarding] {folio(sol['id'])} · {sol['estatus']} · {sol['nombre_cliente']}"
    html = render_template("correo/notificacion.html", sol=sol)
    return asunto, html


def enviar(destino, asunto, html, sid):
    """Envía (o guarda en outbox/) un correo. Lanza excepción si falla."""
    cfg = current_app.config
    if not cfg["MAIL_ENABLED"]:
        carpeta = Path(cfg["OUTBOX_DIR"])
        carpeta.mkdir(parents=True, exist_ok=True)
        nombre = f"{ahora().strftime('%Y%m%d_%H%M%S')}_{folio(sid)}.html"
        (carpeta / nombre).write_text(f"<!-- Para: {destino} | Asunto: {asunto} -->\n{html}", encoding="utf-8")
        return

    mensaje = EmailMessage()
    mensaje["Subject"] = asunto
    mensaje["From"] = cfg["MAIL_FROM"]
    mensaje["To"] = destino
    mensaje.set_content("Este mensaje requiere un cliente de correo con soporte HTML.")
    mensaje.add_alternative(html, subtype="html")

    contexto = ssl.create_default_context()
    if cfg["MAIL_USE_SSL"]:
        servidor = smtplib.SMTP_SSL(cfg["MAIL_HOST"], cfg["MAIL_PORT"], timeout=cfg["MAIL_TIMEOUT"], context=contexto)
    else:
        servidor = smtplib.SMTP(cfg["MAIL_HOST"], cfg["MAIL_PORT"], timeout=cfg["MAIL_TIMEOUT"])
    with servidor:
        if not cfg["MAIL_USE_SSL"] and cfg["MAIL_USE_TLS"]:
            servidor.starttls(context=contexto)
        if cfg["MAIL_USERNAME"]:
            servidor.login(cfg["MAIL_USERNAME"], cfg["MAIL_PASSWORD"])
        servidor.send_message(mensaje)


def notificar(db, sid):
    """Envía el correo de una solicitud y guarda el resultado en estatus_correo."""
    sol = db.execute("SELECT * FROM solicitudes WHERE id = ?", (sid,)).fetchone()
    if sol is None:
        return False
    try:
        asunto, html = construir(sol)
        enviar(sol["correo_notificaciones"], asunto, html, sid)
        estado, ok = CORREO_ENVIADO, True
        log.info("Correo de %s enviado a %s", folio(sid), sol["correo_notificaciones"])
    except Exception:  # cualquier fallo de SMTP, red o plantilla se registra y se reporta
        log.exception("Error al enviar el correo de %s a %s", folio(sid), sol["correo_notificaciones"])
        estado, ok = CORREO_ERROR, False
    db.execute("UPDATE solicitudes SET estatus_correo = ? WHERE id = ?", (estado, sid))
    return ok
