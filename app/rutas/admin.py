"""Panel de administrador: solicitudes, cambio de estatus y exportaciones."""
from flask import (
    Blueprint, abort, current_app, flash, g, redirect, render_template, request, send_file, url_for,
)

from .. import correo
from .. import estatus as E
from .. import exportar as X
from .. import solicitudes as S
from ..auth import admin_requerido
from ..catalogos import cargar as cargar_catalogos
from ..constantes import CORREO_ERROR, CORREO_PENDIENTE, LISTO, PENDIENTE, RECHAZADA
from ..db import get_db
from ..usuarios import opciones_ejecutivos
from ..utils import dias_habiles_entre, folio, hoy_str
from .comun import XLSX, filtros_de, pagina_actual, por_pagina, ruta_segura

bp = Blueprint("admin", __name__, url_prefix="/admin")
FILTROS = ("desde", "hasta", "tipo", "estatus", "ejecutivo", "region", "segmento", "estatus_correo", "q")


def _volver(sid=None):
    defecto = url_for("ejecutivo.detalle", sid=sid) if sid else url_for("admin.solicitudes")
    return redirect(ruta_segura(request.form.get("volver"), defecto))


@bp.route("/solicitudes")
@admin_requerido
def solicitudes():
    db = get_db()
    filtros = filtros_de(FILTROS)
    pagina = pagina_actual()
    filas, total = S.listar(db, filtros, None, pagina, por_pagina())
    antiguedad = {f["id"]: dias_habiles_entre(f["fecha_solicitud"]) for f in filas if f["estatus"] == PENDIENTE}
    return render_template(
        "admin_solicitudes.html", filas=filas, total=total, pagina=pagina, por_pagina=por_pagina(),
        filtros=filtros, contadores=S.contadores(db), ejecutivos=opciones_ejecutivos(db),
        cat=cargar_catalogos(), antiguedad=antiguedad, sla=current_app.config["SLA_DIAS_HABILES"],
    )


@bp.route("/solicitudes/<int:sid>/estatus", methods=["POST"])
@admin_requerido
def cambiar_estatus(sid):
    nuevo = request.form.get("nuevo")
    if nuevo not in (LISTO, RECHAZADA):
        abort(400)
    try:
        _sol, correo_ok = E.atender(get_db(), sid, nuevo, g.usuario, request.form.get("motivo", ""))
        flash(f"{folio(sid)} marcada como {nuevo}.", "ok")
        if correo_ok is False:
            flash(f"El estatus de {folio(sid)} se guardó, pero el correo no se pudo enviar. "
                  "Revisa logs/app.log y usa «Reintentar envío».", "aviso")
    except E.ErrorEstatus as error:
        flash(str(error), "error")
    return _volver(sid)


@bp.route("/solicitudes/masivo", methods=["POST"])
@admin_requerido
def masivo():
    ids = [int(x) for x in request.form.getlist("ids") if x.isdigit()]
    if not ids:
        flash("Selecciona al menos una solicitud pendiente.", "aviso")
        return _volver()
    listas, fallidas, correos_error = E.atender_varias(get_db(), ids, g.usuario)
    if listas:
        flash(f"{len(listas)} solicitud(es) marcadas como Listo para operar.", "ok")
    for _sid, mensaje in fallidas:
        flash(f"Omitida: {mensaje}", "error")
    if correos_error:
        flash("No se pudo enviar el correo de: " + ", ".join(folio(s) for s in correos_error)
              + ". Usa «Reintentar envío».", "aviso")
    return _volver()


@bp.route("/solicitudes/<int:sid>/reintentar-correo", methods=["POST"])
@admin_requerido
def reintentar_correo(sid):
    db = get_db()
    sol = S.obtener(db, sid)
    if sol is None:
        abort(404)
    if sol["estatus_correo"] not in (CORREO_ERROR, CORREO_PENDIENTE):
        flash("Esta solicitud no tiene un correo pendiente de envío.", "aviso")
    elif correo.notificar(db, sid):
        flash(f"Correo de {folio(sid)} enviado.", "ok")
    else:
        flash(f"El correo de {folio(sid)} volvió a fallar. Revisa logs/app.log.", "error")
    return _volver(sid)


@bp.route("/solicitudes/exportar")
@admin_requerido
def exportar():
    db = get_db()
    filas = S.listar_todas(db, filtros_de(FILTROS))
    archivo = X.libro_solicitudes(filas, S.historial_de_varias(db, [f["id"] for f in filas]))
    return send_file(archivo, mimetype=XLSX, as_attachment=True,
                     download_name=f"solicitudes_filtradas_{hoy_str()}.xlsx")


@bp.route("/solicitudes/exportar-dia")
@admin_requerido
def exportar_dia():
    db = get_db()
    hoy = hoy_str()
    filas = S.listar_todas(db, {"dia": hoy})
    archivo = X.libro_solicitudes(filas, S.historial_de_varias(db, [f["id"] for f in filas]))
    return send_file(archivo, mimetype=XLSX, as_attachment=True, download_name=f"solicitudes_{hoy}.xlsx")
