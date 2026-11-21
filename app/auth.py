"""Inicio de sesión, cambio de contraseña y control de acceso por rol."""
import logging
import math
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Blueprint, abort, current_app, flash, g, redirect, render_template, request, session, url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from .constantes import ROL_ADMIN
from .db import get_db
from .utils import FMT_DB, ahora
from .validaciones import validar_contrasena_nueva

bp = Blueprint("auth", __name__)
log = logging.getLogger("fx")

ENDPOINTS_SIN_CAMBIO = {"auth.login", "auth.logout", "auth.cambiar_contrasena", "static"}


def cargar_usuario():
    """Antes de cada petición: identifica al usuario y fuerza el cambio de contraseña temporal."""
    g.usuario = None
    nombre = session.get("usuario")
    if nombre:
        usuario = get_db().execute("SELECT * FROM usuarios WHERE usuario = ? AND activo = 1", (nombre,)).fetchone()
        if usuario is None:
            session.clear()
        else:
            g.usuario = usuario
    if g.usuario is not None and g.usuario["debe_cambiar"] and request.endpoint not in ENDPOINTS_SIN_CAMBIO:
        return redirect(url_for("auth.cambiar_contrasena"))
    return None


def login_requerido(vista):
    @wraps(vista)
    def envoltura(*args, **kwargs):
        if g.get("usuario") is None:
            if request.path.startswith("/api/"):
                return {"error": "Sesión expirada"}, 401
            return redirect(url_for("auth.login", next=request.full_path))
        return vista(*args, **kwargs)
    return envoltura


def admin_requerido(vista):
    @login_requerido
    @wraps(vista)
    def envoltura(*args, **kwargs):
        if g.usuario["rol"] != ROL_ADMIN:
            abort(403)
        return vista(*args, **kwargs)
    return envoltura


def _destino_seguro(destino):
    if destino and destino.startswith("/") and not destino.startswith("//") and "\\" not in destino:
        return destino
    return None


@bp.route("/")
@login_requerido
def inicio():
    if g.usuario["rol"] == ROL_ADMIN:
        return redirect(url_for("admin.solicitudes"))
    return redirect(url_for("ejecutivo.mis_solicitudes"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.get("usuario") is not None:
        return redirect(url_for("auth.inicio"))
    error = None
    if request.method == "POST":
        nombre = (request.form.get("usuario") or "").strip().lower()
        contrasena = request.form.get("contrasena") or ""
        db = get_db()
        usuario = db.execute("SELECT * FROM usuarios WHERE usuario = ?", (nombre,)).fetchone()
        error = "Usuario o contraseña incorrectos."
        momento = ahora()
        bloqueado_hasta = None
        if usuario is not None and usuario["bloqueado_hasta"]:
            bloqueado_hasta = datetime.strptime(usuario["bloqueado_hasta"], FMT_DB)

        if bloqueado_hasta is not None and bloqueado_hasta > momento:
            minutos = math.ceil((bloqueado_hasta - momento).total_seconds() / 60)
            error = f"Cuenta bloqueada por intentos fallidos. Intenta de nuevo en {minutos} minuto(s)."
        elif usuario is not None and usuario["activo"] and check_password_hash(usuario["password_hash"], contrasena):
            db.execute("UPDATE usuarios SET intentos_fallidos = 0, bloqueado_hasta = NULL WHERE usuario = ?", (nombre,))
            session.clear()
            session.permanent = True
            session["usuario"] = nombre
            log.info("Inicio de sesión: %s", nombre)
            return redirect(_destino_seguro(request.args.get("next")) or url_for("auth.inicio"))
        elif usuario is not None:
            intentos = usuario["intentos_fallidos"] + 1
            bloqueo = None
            if intentos >= current_app.config["MAX_LOGIN_ATTEMPTS"]:
                bloqueo = (momento + timedelta(minutes=current_app.config["LOCKOUT_MINUTES"])).strftime(FMT_DB)
                intentos = 0
                error = (f"Cuenta bloqueada por intentos fallidos. Intenta de nuevo en "
                         f"{current_app.config['LOCKOUT_MINUTES']} minuto(s).")
                log.warning("Cuenta bloqueada por intentos fallidos: %s", nombre)
            db.execute("UPDATE usuarios SET intentos_fallidos = ?, bloqueado_hasta = ? WHERE usuario = ?",
                       (intentos, bloqueo, nombre))
            log.warning("Intento fallido de inicio de sesión: %s", nombre)
        else:
            log.warning("Intento de inicio de sesión con usuario inexistente: %s", nombre)
    return render_template("login.html", error=error)


@bp.route("/logout", methods=["POST"])
def logout():
    if g.get("usuario") is not None:
        log.info("Cierre de sesión: %s", g.usuario["usuario"])
    session.clear()
    flash("Sesión cerrada.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/cambiar-contrasena", methods=["GET", "POST"])
@login_requerido
def cambiar_contrasena():
    errores = {}
    if request.method == "POST":
        actual = request.form.get("actual") or ""
        nueva = request.form.get("nueva") or ""
        confirmar = request.form.get("confirmar") or ""
        if not check_password_hash(g.usuario["password_hash"], actual):
            errores["actual"] = "La contraseña actual no es correcta."
        mensaje = validar_contrasena_nueva(nueva)
        if mensaje:
            errores["nueva"] = mensaje
        elif nueva != confirmar:
            errores["confirmar"] = "Las contraseñas no coinciden."
        elif check_password_hash(g.usuario["password_hash"], nueva):
            errores["nueva"] = "La nueva contraseña debe ser distinta de la actual."
        if not errores:
            get_db().execute("UPDATE usuarios SET password_hash = ?, debe_cambiar = 0 WHERE usuario = ?",
                             (generate_password_hash(nueva), g.usuario["usuario"]))
            log.info("Cambio de contraseña: %s", g.usuario["usuario"])
            flash("Contraseña actualizada.", "ok")
            return redirect(url_for("auth.inicio"))
    return render_template("cambiar_contrasena.html", errores=errores, forzado=bool(g.usuario["debe_cambiar"]))
