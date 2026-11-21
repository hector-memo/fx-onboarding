"""Consulta JSON de un contrato en el padrón (autocompletado de formularios).

A un ejecutivo nunca se le devuelven datos de contratos de otra cartera.
"""
from flask import Blueprint, g, jsonify, request

from .. import padron as P
from .. import solicitudes as S
from ..auth import login_requerido
from ..constantes import CAMPOS_EMPRESA, CAMPOS_PERMISOS
from ..db import get_db
from ..utils import folio
from ..validaciones import es_contrato

bp = Blueprint("api", __name__, url_prefix="/api")
CAMPOS_CLIENTE = ("contrato",) + CAMPOS_EMPRESA + CAMPOS_PERMISOS + ("ejecutivo_asignado",)


@bp.route("/contrato/<contrato>")
@login_requerido
def contrato(contrato):
    para_alta = request.args.get("para", "alta") != "cambio"
    if not es_contrato(contrato):
        return jsonify(estado="invalido", mensaje="El contrato debe tener exactamente 11 dígitos numéricos.")

    db = get_db()
    estado, registro = P.estado_contrato(db, contrato, g.usuario)
    if estado == "ajeno":
        return jsonify(estado="ajeno", mensaje=S.MSG_AJENO_ALTA if para_alta else S.MSG_AJENO_CAMBIO)
    if estado == "alta_pendiente":
        mensaje = S.mensaje_alta_pendiente(registro, g.usuario) if para_alta else S.MSG_ALTA_PENDIENTE_CAMBIO
        return jsonify(estado="alta_pendiente", mensaje=mensaje)
    if estado == "nuevo":
        mensaje = "Contrato nuevo: captura todos los datos." if para_alta else S.MSG_NO_EXISTE
        return jsonify(estado="nuevo", mensaje=mensaje)

    cliente = {c: registro[c] for c in CAMPOS_CLIENTE}
    if para_alta:
        return jsonify(estado="propio", cliente=cliente, mensaje=(
            "Usuario nuevo en un contrato existente: los datos de empresa y permisos se toman del padrón. "
            "Para modificarlos usa Cambio de permisos."))
    pendiente = S.cambio_pendiente(db, contrato)
    if pendiente is not None:
        return jsonify(estado="cambio_pendiente", cliente=cliente, mensaje=(
            f"Ya hay un cambio de permisos pendiente para este contrato ({folio(pendiente['id'])})."))
    return jsonify(estado="propio", cliente=cliente, mensaje="Datos vigentes tomados del padrón.")
