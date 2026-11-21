"""Formularios de Alta de cliente nuevo y Cambio de permisos."""
from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from .. import solicitudes as S
from ..auth import login_requerido
from ..catalogos import cargar as cargar_catalogos
from ..db import get_db
from ..usuarios import opciones_ejecutivos
from ..utils import folio
from .comun import datos_formulario, es_admin

bp = Blueprint("formularios", __name__, url_prefix="/solicitudes")


def _api_base():
    return url_for("api.contrato", contrato="X")[:-1]


def _datos_iniciales():
    return {"contrato": (request.args.get("contrato") or "")[:11], "correo_notificaciones": g.usuario["correo"]}


@bp.route("/alta", methods=["GET", "POST"])
@login_requerido
def alta():
    db, catalogo = get_db(), cargar_catalogos()
    errores, contexto = {}, {}
    if request.method == "POST":
        datos = datos_formulario()
        try:
            sid = S.registrar_alta(db, datos, g.usuario, catalogo)
            flash(f"Solicitud {folio(sid)} registrada con estatus Pendiente.", "ok")
            return redirect(url_for("ejecutivo.detalle", sid=sid))
        except S.ErrorSolicitud as error:
            errores, contexto = error.errores, error.contexto
            flash("La solicitud no se envió. Revisa los campos marcados.", "error")
    else:
        datos = _datos_iniciales()
    return render_template(
        "form_alta.html", datos=datos, errores=errores, contexto=contexto, cat=catalogo,
        ejecutivos=opciones_ejecutivos(db) if es_admin() else [], api_base=_api_base(),
        repost=request.method == "POST",
    )


@bp.route("/cambio-permisos", methods=["GET", "POST"])
@login_requerido
def cambio():
    db, catalogo = get_db(), cargar_catalogos()
    errores = {}
    if request.method == "POST":
        datos = datos_formulario()
        try:
            sid = S.registrar_cambio(db, datos, g.usuario, catalogo)
            flash(f"Solicitud {folio(sid)} registrada con estatus Pendiente.", "ok")
            return redirect(url_for("ejecutivo.detalle", sid=sid))
        except S.ErrorSolicitud as error:
            errores = error.errores
            flash("La solicitud no se envió. Revisa los campos marcados.", "error")
    else:
        datos = _datos_iniciales()
    return render_template(
        "form_cambio.html", datos=datos, errores=errores, cat=catalogo,
        ejecutivos=opciones_ejecutivos(db) if es_admin() else [], api_base=_api_base(),
        repost=request.method == "POST",
    )
