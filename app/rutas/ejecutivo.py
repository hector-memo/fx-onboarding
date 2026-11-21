"""Panel "Mis solicitudes" y vista de detalle de una solicitud."""
import json

from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, url_for

from .. import estatus as E
from .. import padron as P
from .. import solicitudes as S
from ..auth import login_requerido
from ..constantes import CAMPOS_PERMISOS, CANCELADA, ETIQUETAS, PENDIENTE, TIPO_CAMBIO
from ..db import get_db
from ..utils import dias_habiles_entre, folio
from .comun import es_admin, filtros_de, pagina_actual, por_pagina

bp = Blueprint("ejecutivo", __name__)
FILTROS = ("estatus", "tipo", "desde", "hasta", "q")


@bp.route("/mis-solicitudes")
@login_requerido
def mis_solicitudes():
    if es_admin():
        return redirect(url_for("admin.solicitudes"))
    db = get_db()
    filtros = filtros_de(FILTROS)
    pagina = pagina_actual()
    filas, total = S.listar(db, filtros, g.usuario["usuario"], pagina, por_pagina())
    return render_template(
        "mis_solicitudes.html", filas=filas, total=total, pagina=pagina, por_pagina=por_pagina(),
        filtros=filtros, contadores=S.contadores(db, g.usuario["usuario"]),
    )


@bp.route("/solicitudes/<int:sid>")
@login_requerido
def detalle(sid):
    db = get_db()
    sol = S.obtener_para(db, sid, g.usuario)
    if sol is None:
        abort(404)  # 404 también para solicitudes ajenas: no se revela que existen

    comparacion = None
    if sol["tipo"] == TIPO_CAMBIO and sol["permisos_vigentes"]:
        antes = json.loads(sol["permisos_vigentes"])
        despues = P.permisos_de(sol)
        comparacion = [
            {"campo": c, "etiqueta": ETIQUETAS[c], "antes": antes.get(c), "despues": despues.get(c),
             "cambia": P.valor_normalizado(c, antes.get(c)) != despues.get(c)}
            for c in CAMPOS_PERMISOS
        ]
    antiguedad = dias_habiles_entre(sol["fecha_solicitud"]) if sol["estatus"] == PENDIENTE else None
    return render_template(
        "solicitud_detalle.html", sol=sol, historial=S.historial(db, sid), comparacion=comparacion,
        contrato_visible=P.cliente_visible(db, sol["contrato"], g.usuario) is not None,
        antiguedad=antiguedad, sla=current_app.config["SLA_DIAS_HABILES"],
        puede_cancelar=sol["estatus"] == PENDIENTE and sol["ejecutivo"] == g.usuario["usuario"],
    )


@bp.route("/solicitudes/<int:sid>/cancelar", methods=["POST"])
@login_requerido
def cancelar(sid):
    db = get_db()
    if S.obtener(db, sid, ejecutivo=g.usuario["usuario"]) is None:
        abort(404)  # solo el ejecutivo dueño puede cancelar
    try:
        E.atender(db, sid, CANCELADA, g.usuario, request.form.get("motivo", ""))
        flash(f"Solicitud {folio(sid)} cancelada.", "ok")
    except E.ErrorEstatus as error:
        flash(str(error), "error")
    return redirect(url_for("ejecutivo.detalle", sid=sid))
