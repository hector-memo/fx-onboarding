"""Fábrica de la aplicación Flask."""
import logging
from datetime import timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask, g, render_template, request, url_for
from flask_wtf.csrf import CSRFError, CSRFProtect

from config import Config

from . import constantes as C
from .utils import folio, formatear_fecha, formatear_fecha_corta, formatear_monto, mostrar, valor_input

csrf = CSRFProtect()


def _configurar_logs(app):
    logger = logging.getLogger("fx")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    for handler in list(logger.handlers):
        if getattr(handler, "_fx", False):
            logger.removeHandler(handler)
            handler.close()
    formato = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    archivo = RotatingFileHandler(app.config["LOG_FILE"], maxBytes=2_000_000, backupCount=5, encoding="utf-8")
    archivo.setFormatter(formato)
    archivo._fx = True
    logger.addHandler(archivo)
    if not app.config.get("TESTING"):
        consola = logging.StreamHandler()
        consola.setFormatter(formato)
        consola._fx = True
        logger.addHandler(consola)


def _lista(valor):
    if isinstance(valor, (list, tuple)):
        return list(valor)
    return [x for x in str(valor or "").split(",") if x]


def create_app(config_override=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if config_override:
        app.config.update(config_override)
    app.config["MAX_CONTENT_LENGTH"] = int(app.config["MAX_UPLOAD_MB"]) * 1024 * 1024
    app.permanent_session_lifetime = timedelta(minutes=int(app.config["SESSION_MINUTES"]))

    for clave in ("BACKUP_DIR", "OUTBOX_DIR", "UPLOAD_DIR"):
        Path(app.config[clave]).mkdir(parents=True, exist_ok=True)
    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    Path(app.config["LOG_FILE"]).parent.mkdir(parents=True, exist_ok=True)
    _configurar_logs(app)
    csrf.init_app(app)

    from . import db as base
    app.teardown_appcontext(base.cerrar_db)
    with app.app_context():
        base.crear_esquema(base.get_db())

    from . import notificaciones
    from .auth import bp as auth_bp, cargar_usuario
    from .respaldo import respaldo_diario
    from .rutas.admin import bp as admin_bp
    from .rutas.api import bp as api_bp
    from .rutas.cartera import bp as cartera_bp
    from .rutas.ejecutivo import bp as ejecutivo_bp
    from .rutas.formularios import bp as formularios_bp
    from .rutas.notificaciones import bp as notificaciones_bp
    from .rutas.padron_admin import bp as padron_admin_bp
    from .rutas.usuarios_admin import bp as usuarios_admin_bp

    app.before_request(respaldo_diario)
    app.before_request(cargar_usuario)
    for blueprint in (auth_bp, ejecutivo_bp, formularios_bp, api_bp, admin_bp, cartera_bp, padron_admin_bp,
                      usuarios_admin_bp, notificaciones_bp):
        app.register_blueprint(blueprint)

    app.jinja_env.filters.update(
        fecha=formatear_fecha, fecha_corta=formatear_fecha_corta, folio=folio, monto=formatear_monto,
        valor_input=valor_input, mostrar=mostrar, lista=_lista,
    )

    def url_con(**cambios):
        """URL de la página actual con parámetros modificados (paginación)."""
        argumentos = {**(request.view_args or {}), **request.args.to_dict(), **cambios}
        return url_for(request.endpoint, **argumentos)

    def url_args(endpoint, **extra):
        """URL de otro endpoint conservando los filtros actuales (exportar)."""
        argumentos = request.args.to_dict()
        argumentos.pop("pagina", None)
        argumentos.update(extra)
        return url_for(endpoint, **argumentos)

    @app.context_processor
    def globales():
        usuario = g.get("usuario")
        sin_leer = notificaciones.no_leidas(base.get_db(), usuario["usuario"]) if usuario is not None else 0
        return {
            "notif_sin_leer": sin_leer,
            "notif_texto": notificaciones.texto_contador(sin_leer),
            "usuario_actual": usuario,
            "es_admin": usuario is not None and usuario["rol"] == C.ROL_ADMIN,
            "url_con": url_con,
            "url_args": url_args,
            "ESTATUS": C.ESTATUS,
            "TIPOS": C.TIPOS,
            "ESTATUS_CORREO": C.ESTATUS_CORREO,
            "ETIQUETAS": C.ETIQUETAS,
            "CAMPOS_PERMISOS": C.CAMPOS_PERMISOS,
        }

    def _error(codigo, titulo, mensaje):
        return render_template("error.html", codigo=codigo, titulo=titulo, mensaje=mensaje), codigo

    app.register_error_handler(403, lambda e: _error(403, "Acceso no permitido",
                                                     "No tienes permiso para ver esta página."))
    app.register_error_handler(404, lambda e: _error(404, "No encontrado",
                                                     "La página o el registro que buscas no existe."))
    app.register_error_handler(413, lambda e: _error(413, "Archivo demasiado grande",
                                                     f"El archivo supera el máximo de {app.config['MAX_UPLOAD_MB']} MB."))
    app.register_error_handler(CSRFError, lambda e: _error(400, "Formulario expirado",
                                                           "El formulario expiró. Recarga la página e inténtalo de nuevo."))
    return app
