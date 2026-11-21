"""Pantalla Notificaciones (la campana de la barra superior). Cada usuario ve solo las suyas."""
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from .. import notificaciones as N
from .. import solicitudes as S
from ..auth import login_requerido
from ..db import get_db
from .comun import pagina_actual, por_pagina

bp = Blueprint("notificaciones", __name__, url_prefix="/notificaciones")


def _volver():
    solo = request.form.get("estado") == "no_leidas"
    return redirect(url_for("notificaciones.lista", estado="no_leidas" if solo else None))


@bp.route("/")
@login_requerido
def lista():
    db = get_db()
    usuario = g.usuario["usuario"]
    solo_no_leidas = request.args.get("estado") == "no_leidas"
    pagina = pagina_actual()
    filas, total = N.listar(db, usuario, solo_no_leidas, pagina, por_pagina())
    return render_template(
        "notificaciones.html", filas=filas, total=total, pagina=pagina, por_pagina=por_pagina(),
        solo_no_leidas=solo_no_leidas, sin_leer=N.no_leidas(db, usuario),
    )


@bp.route("/<int:nid>/abrir", methods=["POST"])
@login_requerido
def abrir(nid):
    """Marca la notificación como leída y lleva a la solicitud."""
    db = get_db()
    notif = N.obtener(db, nid, g.usuario["usuario"])
    if notif is None:
        abort(404)
    N.marcar_leida(db, nid, g.usuario["usuario"])
    if notif["solicitud_id"] and S.obtener_para(db, notif["solicitud_id"], g.usuario) is not None:
        return redirect(url_for("ejecutivo.detalle", sid=notif["solicitud_id"]))
    flash("Esta solicitud ya no está en tu cartera.", "aviso")
    return _volver()


@bp.route("/<int:nid>/leida", methods=["POST"])
@login_requerido
def leida(nid):
    if not N.marcar_leida(get_db(), nid, g.usuario["usuario"]):
        abort(404)
    return _volver()


@bp.route("/marcar-todas", methods=["POST"])
@login_requerido
def marcar_todas():
    n = N.marcar_todas(get_db(), g.usuario["usuario"])
    flash(f"{n} notificación(es) marcada(s) como leída(s)." if n else "No había notificaciones sin leer.", "ok")
    return _volver()
