"""Pantalla Usuarios: administración de los usuarios de la app (solo admin)."""
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from .. import usuarios as U
from ..auth import admin_requerido
from ..db import get_db
from .comun import filtros_de

bp = Blueprint("usuarios_admin", __name__, url_prefix="/admin/usuarios")
ROLES = [("ejecutivo", "Ejecutivo"), ("admin", "Administrador")]


def _volver_a(usuario):
    return redirect(url_for("usuarios_admin.detalle", usuario=usuario))


@bp.route("/")
@admin_requerido
def lista():
    db = get_db()
    filtros = filtros_de(("rol", "estado", "q"))
    filas = U.listar(db, filtros)
    return render_template(
        "usuarios.html", filas=filas, filtros=filtros, contadores=U.contadores(db), roles=ROLES,
        bloqueados={f["usuario"] for f in filas if U.esta_bloqueado(f)},
    )


@bp.route("/nuevo", methods=["GET", "POST"])
@admin_requerido
def nuevo():
    errores, datos = {}, {"rol": "ejecutivo"}
    if request.method == "POST":
        datos = request.form.to_dict()
        try:
            usuario = U.registrar_usuario(get_db(), datos, g.usuario)
            flash(f"Usuario «{usuario}» creado. Comparte la contraseña temporal; se le pedirá cambiarla al entrar.", "ok")
            return _volver_a(usuario)
        except U.ErrorUsuario as error:
            errores = error.errores
            flash(str(error), "error")
        datos.pop("contrasena", None)  # nunca se vuelve a mostrar la contraseña
    return render_template("usuario_nuevo.html", datos=datos, errores=errores, roles=ROLES)


@bp.route("/<usuario>", methods=["GET", "POST"])
@admin_requerido
def detalle(usuario):
    db = get_db()
    fila = U.obtener(db, usuario)
    if fila is None:
        abort(404)
    errores, datos = {}, dict(fila)
    if request.method == "POST":
        datos = {**dict(fila), **request.form.to_dict()}
        try:
            cambios = U.actualizar_usuario(db, fila["usuario"], datos, g.usuario)
            flash("Datos actualizados." if cambios else "No hubo cambios.", "ok" if cambios else "info")
            return _volver_a(fila["usuario"])
        except U.ErrorUsuario as error:
            errores = error.errores
            flash(str(error), "error")
    contratos, pendientes = U.carga_de_trabajo(db, fila["usuario"])
    return render_template(
        "usuario_detalle.html", u=fila, datos=datos, errores=errores, roles=ROLES,
        contratos=contratos, pendientes=pendientes, bloqueado=U.esta_bloqueado(fila),
        es_yo=fila["usuario"] == g.usuario["usuario"], historial=U.historial(db, fila["usuario"]),
        destinos=U.opciones_ejecutivos(db, excluir=fila["usuario"]),
    )


def _accion(usuario, funcion, mensaje_ok, *args):
    try:
        funcion(get_db(), usuario, *args)
        flash(mensaje_ok, "ok")
    except U.ErrorUsuario as error:
        flash(str(error), "error")
    return _volver_a(usuario)


@bp.route("/<usuario>/desactivar", methods=["POST"])
@admin_requerido
def desactivar(usuario):
    return _accion(usuario, U.desactivar, f"Usuario «{usuario}» desactivado. Ya no puede iniciar sesión.",
                   g.usuario, request.form.get("transferir_a") or None, request.form.get("motivo", ""))


@bp.route("/<usuario>/reactivar", methods=["POST"])
@admin_requerido
def reactivar(usuario):
    return _accion(usuario, U.reactivar, f"Usuario «{usuario}» reactivado.", g.usuario)


@bp.route("/<usuario>/restablecer", methods=["POST"])
@admin_requerido
def restablecer(usuario):
    return _accion(usuario, U.restablecer,
                   "Contraseña temporal asignada. Se le pedirá cambiarla al entrar; la cuenta quedó desbloqueada.",
                   request.form.get("contrasena", ""), g.usuario)


@bp.route("/<usuario>/desbloquear", methods=["POST"])
@admin_requerido
def desbloquear(usuario):
    return _accion(usuario, U.desbloquear, f"Usuario «{usuario}» desbloqueado.", g.usuario)


@bp.route("/<usuario>/transferir", methods=["POST"])
@admin_requerido
def transferir(usuario):
    try:
        contratos, pendientes = U.transferir_cartera(get_db(), usuario, request.form.get("transferir_a"),
                                                     g.usuario, request.form.get("motivo", ""))
        flash(f"Cartera transferida: {contratos} contrato(s) y {pendientes} solicitud(es) pendiente(s).", "ok")
    except U.ErrorUsuario as error:
        flash(str(error), "error")
    return _volver_a(usuario)
