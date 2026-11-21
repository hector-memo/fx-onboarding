"""Cartera de clientes (padrón): consulta para todos y mantenimiento para el admin."""
from flask import Blueprint, abort, flash, g, redirect, render_template, request, send_file, url_for

from .. import exportar as X
from .. import padron as P
from .. import solicitudes as S
from .. import validaciones as V
from ..auth import admin_requerido, login_requerido
from ..catalogos import cargar as cargar_catalogos
from ..db import get_db, transaccion
from ..usuarios import opciones_ejecutivos
from ..utils import hoy_str
from .comun import XLSX, datos_formulario, es_admin, filtros_de, pagina_actual, por_pagina

bp = Blueprint("cartera", __name__, url_prefix="/cartera")
FILTROS = ("region", "segmento", "zona", "grupo_spot", "ejecutivo", "q")


@bp.route("/")
@login_requerido
def lista():
    db = get_db()
    filtros = filtros_de(FILTROS)
    pagina = pagina_actual()
    filas, total = P.listar_cartera(db, filtros, g.usuario, pagina, por_pagina())
    return render_template(
        "cartera.html", filas=filas, total=total, pagina=pagina, por_pagina=por_pagina(), filtros=filtros,
        contadores=P.contadores_cartera(db, g.usuario), cat=cargar_catalogos(),
        ejecutivos=opciones_ejecutivos(db) if es_admin() else [],
    )


@bp.route("/exportar")
@login_requerido
def exportar():
    clientes, usuarios = P.cartera_completa(get_db(), filtros_de(FILTROS), g.usuario)
    return send_file(X.libro_cartera(clientes, usuarios), mimetype=XLSX, as_attachment=True,
                     download_name=f"cartera_{hoy_str()}.xlsx")


@bp.route("/<contrato>")
@login_requerido
def detalle(contrato):
    db = get_db()
    cliente = P.cliente_visible(db, contrato, g.usuario)
    if cliente is None:
        abort(404)  # no se revela si el contrato existe en otra cartera
    return render_template(
        "cliente_detalle.html", cliente=cliente, usuarios=P.usuarios_de(db, contrato),
        historial=P.historial_de(db, contrato),
        solicitudes=S.por_contrato(db, contrato, None if es_admin() else g.usuario["usuario"]),
        ejecutivos=opciones_ejecutivos(db) if es_admin() else [],
    )


@bp.route("/<contrato>/editar", methods=["GET", "POST"])
@admin_requerido
def editar(contrato):
    db, catalogo = get_db(), cargar_catalogos()
    cliente = P.obtener_cliente(db, contrato)
    if cliente is None:
        abort(404)
    errores = {}
    if request.method == "POST":
        datos = datos_formulario()
        d = V.normalizar({**datos, "contrato": contrato})
        errores = V.validar_cliente_padron(d, catalogo)
        motivo = (d.get("motivo") or "").strip()
        if not motivo:
            errores["motivo"] = V.OBLIGATORIO
        if not errores:
            with transaccion(db):
                cambios = P.editar_cliente(db, contrato, d, g.usuario["usuario"], motivo)
            if cambios:
                flash(f"Contrato actualizado: {len(cambios)} campo(s) modificados.", "ok")
            else:
                flash("No hubo cambios.", "info")
            return redirect(url_for("cartera.detalle", contrato=contrato))
    else:
        datos = dict(cliente)
    return render_template("cliente_editar.html", cliente=cliente, datos=datos, errores=errores, cat=catalogo)


@bp.route("/<contrato>/reasignar", methods=["POST"])
@admin_requerido
def reasignar(contrato):
    db = get_db()
    try:
        with transaccion(db):
            P.reasignar(db, contrato, request.form.get("ejecutivo"), g.usuario["usuario"], request.form.get("motivo"))
        flash("Contrato reasignado.", "ok")
    except P.ErrorPadron as error:
        flash(str(error), "error")
    return redirect(url_for("cartera.detalle", contrato=contrato))


@bp.route("/<contrato>/eliminar", methods=["POST"])
@admin_requerido
def eliminar(contrato):
    db = get_db()
    try:
        with transaccion(db):
            P.eliminar_cliente(db, contrato, g.usuario["usuario"], request.form.get("motivo"))
        flash(f"Contrato {contrato} eliminado del padrón.", "ok")
        return redirect(url_for("cartera.lista"))
    except P.ErrorPadron as error:
        flash(str(error), "error")
        return redirect(url_for("cartera.detalle", contrato=contrato))


@bp.route("/<contrato>/usuarios/<numero>/eliminar", methods=["POST"])
@admin_requerido
def eliminar_usuario(contrato, numero):
    db = get_db()
    try:
        with transaccion(db):
            P.eliminar_usuario(db, contrato, numero, g.usuario["usuario"], request.form.get("motivo"))
        flash(f"Usuario {numero} eliminado del contrato.", "ok")
    except P.ErrorPadron as error:
        flash(str(error), "error")
    return redirect(url_for("cartera.detalle", contrato=contrato))
