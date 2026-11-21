"""Carga inicial desde Excel y captura manual de clientes existentes (solo admin)."""
import logging
import secrets
from pathlib import Path

from flask import (
    Blueprint, current_app, flash, g, redirect, render_template, request, send_file, session, url_for,
)
from werkzeug.utils import secure_filename

from .. import carga as K
from .. import exportar as X
from .. import padron as P
from .. import validaciones as V
from ..auth import admin_requerido
from ..catalogos import cargar as cargar_catalogos
from ..constantes import ETIQUETAS, ORIGEN_MANUAL
from ..db import get_db, transaccion
from ..respaldo import respaldar
from ..usuarios import ejecutivos_activos, es_ejecutivo_activo, opciones_ejecutivos
from ..utils import parse_fecha_alta
from .comun import XLSX, datos_formulario

bp = Blueprint("padron_admin", __name__, url_prefix="/admin/padron")
log = logging.getLogger("fx")


def _ruta_carga():
    info = session.get("carga")
    if not info or not str(info.get("token", "")).isalnum():
        return None, None
    ruta = Path(current_app.config["UPLOAD_DIR"]) / f"{info['token']}.xlsx"
    return (ruta, info) if ruta.exists() else (None, None)


def _borrar_carga_anterior():
    ruta, _info = _ruta_carga()
    if ruta is not None:
        ruta.unlink(missing_ok=True)
    session.pop("carga", None)


@bp.route("/plantilla")
@admin_requerido
def plantilla():
    ejecutivos = [r["usuario"] for r in ejecutivos_activos(get_db())]
    libro = K.generar_plantilla(cargar_catalogos(), ejecutivos)
    return send_file(X.a_bytes(libro), mimetype=XLSX, as_attachment=True,
                     download_name="plantilla_carga_inicial.xlsx")


@bp.route("/carga", methods=["GET"])
@admin_requerido
def carga():
    return render_template("carga.html", resultado=None, cargas=K.cargas_recientes(get_db()))


@bp.route("/carga", methods=["POST"])
@admin_requerido
def subir():
    archivo = request.files.get("archivo")
    if archivo is None or not archivo.filename or not archivo.filename.lower().endswith(".xlsx"):
        flash("Selecciona un archivo .xlsx.", "error")
        return redirect(url_for("padron_admin.carga"))
    _borrar_carga_anterior()
    token = secrets.token_hex(16)
    ruta = Path(current_app.config["UPLOAD_DIR"]) / f"{token}.xlsx"
    archivo.save(ruta)
    nombre = secure_filename(archivo.filename) or "archivo.xlsx"
    session["carga"] = {"token": token, "archivo": nombre}
    resultado = K.analizar(get_db(), ruta, cargar_catalogos())
    return render_template("carga.html", resultado=resultado, archivo=nombre, cargas=K.cargas_recientes(get_db()))


@bp.route("/carga/confirmar", methods=["POST"])
@admin_requerido
def confirmar():
    ruta, info = _ruta_carga()
    if ruta is None:
        flash("La vista previa expiró. Vuelve a subir el archivo.", "aviso")
        return redirect(url_for("padron_admin.carga"))
    db = get_db()
    resultado = K.analizar(db, ruta, cargar_catalogos())  # se revalida contra el padrón actual
    if not resultado.filas_validas:
        flash("El archivo no tiene filas válidas para importar.", "error")
        return redirect(url_for("padron_admin.carga"))
    respaldar("antes_carga")
    conteo = K.importar(db, resultado, g.usuario["usuario"], info["archivo"])
    _borrar_carga_anterior()
    flash(f"Carga completada: {conteo['contratos']} contrato(s) y {conteo['usuarios']} usuario(s) importados; "
          f"{conteo['omitidos']} omitido(s); {conteo['errores']} fila(s) con error no se importaron.", "ok")
    return redirect(url_for("cartera.lista"))


@bp.route("/carga/errores")
@admin_requerido
def reporte_errores():
    ruta, _info = _ruta_carga()
    if ruta is None:
        flash("La vista previa expiró. Vuelve a subir el archivo.", "aviso")
        return redirect(url_for("padron_admin.carga"))
    resultado = K.analizar(get_db(), ruta, cargar_catalogos())
    return send_file(X.libro_errores_carga(resultado), mimetype=XLSX, as_attachment=True,
                     download_name="reporte_errores_carga.xlsx")


@bp.route("/agregar-cliente", methods=["GET", "POST"])
@admin_requerido
def agregar_cliente():
    db, catalogo = get_db(), cargar_catalogos()
    errores, errores_usuarios = {}, {}
    filas_usuarios = [("", "")] * 3
    datos = {}
    if request.method == "POST":
        datos = datos_formulario(listas=("divisas", "usuario_numero", "usuario_nombre"))
        numeros, nombres = datos.pop("usuario_numero"), datos.pop("usuario_nombre")
        d = V.normalizar(datos)
        errores = V.validar_cliente_padron(d, catalogo)
        if not d.get("ejecutivo_asignado"):
            errores["ejecutivo_asignado"] = V.OBLIGATORIO
        elif not es_ejecutivo_activo(db, d["ejecutivo_asignado"]):
            errores["ejecutivo_asignado"] = "Selecciona un ejecutivo activo."
        fecha = parse_fecha_alta(d.get("fecha_alta"))
        if fecha is False:
            errores["fecha_alta"] = "Fecha inválida."
        if "contrato" not in errores and P.obtener_cliente(db, d["contrato"]) is not None:
            errores["contrato"] = "El contrato ya existe en el padrón. Usa «Agregar usuario existente»."

        filas_usuarios = list(zip(numeros, nombres)) or [("", "")]
        usuarios, vistos = [], set()
        for i, (numero, nombre) in enumerate(filas_usuarios):
            numero, nombre = V.limpiar(numero).replace(" ", ""), V.limpiar(nombre)
            if not numero and not nombre:
                continue
            e = {}
            V.validar_numero_usuario({"numero_usuario": numero}, e)
            V.validar_texto({"nombre_completo": nombre}, "nombre_completo", e)
            if numero in vistos:
                e["numero_usuario"] = "Número de usuario repetido."
            vistos.add(numero)
            if e:
                errores_usuarios[i] = " ".join(f"{ETIQUETAS[k]}: {v}" for k, v in e.items())
            usuarios.append((numero, nombre))
        if not usuarios:
            errores["_usuarios"] = "Captura al menos un usuario."

        if not errores and not errores_usuarios:
            with transaccion(db):
                P.crear_cliente(db, d, g.usuario["usuario"], ORIGEN_MANUAL, fecha_alta=fecha)
                for numero, nombre in usuarios:
                    P.agregar_usuario(db, d["contrato"], numero, nombre, g.usuario["usuario"], ORIGEN_MANUAL)
            flash(f"Contrato {d['contrato']} agregado al padrón con {len(usuarios)} usuario(s).", "ok")
            return redirect(url_for("cartera.detalle", contrato=d["contrato"]))
        flash("El cliente no se guardó. Revisa los campos marcados.", "error")
    return render_template(
        "captura_cliente.html", datos=datos, errores=errores, errores_usuarios=errores_usuarios,
        filas_usuarios=filas_usuarios, cat=catalogo, ejecutivos=opciones_ejecutivos(db),
    )


@bp.route("/agregar-usuario", methods=["GET", "POST"])
@admin_requerido
def agregar_usuario():
    db = get_db()
    errores = {}
    datos = {"contrato": (request.args.get("contrato") or "")[:11]}
    if request.method == "POST":
        datos = datos_formulario(listas=())
        d = V.normalizar(datos)
        errores = V.validar_usuario_padron(d)
        if "contrato" not in errores and P.obtener_cliente(db, d["contrato"]) is None:
            errores["contrato"] = "El contrato no existe en el padrón. Usa «Agregar cliente existente»."
        if not errores and P.existe_usuario(db, d["contrato"], d["numero_usuario"]):
            errores["numero_usuario"] = "Este usuario ya está registrado en este contrato."
        if not errores:
            with transaccion(db):
                P.agregar_usuario(db, d["contrato"], d["numero_usuario"], d["nombre_completo"],
                                  g.usuario["usuario"], ORIGEN_MANUAL)
            flash(f"Usuario {d['numero_usuario']} agregado al contrato {d['contrato']}.", "ok")
            return redirect(url_for("cartera.detalle", contrato=d["contrato"]))
    return render_template("captura_usuario.html", datos=datos, errores=errores)
