"""Solicitudes de alta y cambio de permisos: registro, consultas y duplicados."""
import json
import logging
import re

from . import notificaciones, padron
from . import validaciones as V
from .constantes import (
    CAMPOS_EMPRESA, CAMPOS_PERMISOS, ESTATUS, PENDIENTE, ROL_ADMIN, TIPO_ALTA, TIPO_CAMBIO,
)
from .db import transaccion
from .usuarios import es_ejecutivo_activo
from .utils import ahora_str, folio, parse_folio

log = logging.getLogger("fx")

COLUMNAS = (
    "fecha_solicitud", "tipo", "estatus", "contrato", "nombre_cliente", "rfc", "region", "segmento",
    "zona", "numero_usuario", "nombre_completo", "ejecutivo", "correo_notificaciones", "grupo_spot",
    "multiaprobacion", "multiabono", "divisas", "limite_operacion", "limite_diario",
    "permisos_vigentes", "comentarios", "motivo_cambio",
)
FILTROS_IGUALDAD = ("estatus", "tipo", "region", "segmento", "estatus_correo")
RE_FECHA = re.compile(r"\d{4}-\d{2}-\d{2}")

MSG_AJENO_ALTA = "Este contrato pertenece a otra cartera. Contacta al administrador."
MSG_AJENO_CAMBIO = "Este contrato no está en tu cartera."
MSG_DUP_PADRON = ("Este usuario ya está dado de alta en este contrato. Si necesitas modificar sus "
                  "permisos, usa el formulario de Cambio de permisos.")
MSG_NO_EXISTE = "Este contrato no existe en el padrón. Primero debe solicitarse el alta."
MSG_ALTA_PENDIENTE_CAMBIO = "El alta de este contrato aún está pendiente."
MSG_SIN_CAMBIOS = "Los permisos solicitados son iguales a los vigentes. No hay nada que cambiar."


class ErrorSolicitud(Exception):
    """Errores de captura o de reglas de negocio, por campo."""

    def __init__(self, errores, contexto=None):
        super().__init__("; ".join(f"{k}: {v}" for k, v in errores.items()))
        self.errores = errores
        self.contexto = contexto or {}


# ---------------------------------------------------------------- consultas

def obtener(db, sid, ejecutivo=None):
    """Una solicitud. Con `ejecutivo`, solo si le pertenece."""
    sql, params = "SELECT * FROM solicitudes WHERE id = ?", [sid]
    if ejecutivo is not None:
        sql += " AND ejecutivo = ?"
        params.append(ejecutivo)
    return db.execute(sql, params).fetchone()


def obtener_para(db, sid, actor):
    """El admin ve cualquier solicitud; el ejecutivo solo las suyas."""
    return obtener(db, sid, None if actor["rol"] == ROL_ADMIN else actor["usuario"])


def historial(db, sid):
    return db.execute(
        "SELECT * FROM historial_estatus WHERE solicitud_id = ? ORDER BY id", (sid,)
    ).fetchall()


def historial_de_varias(db, ids):
    filas = []
    ids = list(ids)
    for i in range(0, len(ids), 500):
        bloque = ids[i:i + 500]
        marcas = ", ".join("?" for _ in bloque)
        filas += db.execute(
            f"SELECT * FROM historial_estatus WHERE solicitud_id IN ({marcas}) ORDER BY solicitud_id, id", bloque
        ).fetchall()
    return filas


def alta_pendiente(db, contrato, numero_usuario=None):
    sql = "SELECT * FROM solicitudes WHERE tipo = ? AND estatus = ? AND contrato = ?"
    params = [TIPO_ALTA, PENDIENTE, contrato]
    if numero_usuario is not None:
        sql += " AND numero_usuario = ?"
        params.append(numero_usuario)
    return db.execute(sql + " ORDER BY id LIMIT 1", params).fetchone()


def cambio_pendiente(db, contrato):
    return db.execute(
        "SELECT * FROM solicitudes WHERE tipo = ? AND estatus = ? AND contrato = ? ORDER BY id LIMIT 1",
        (TIPO_CAMBIO, PENDIENTE, contrato),
    ).fetchone()


def buscar_duplicado(db, contrato, numero_usuario):
    """("padron", None) | ("pendiente", solicitud) | None.

    Solo cuentan el padrón y las altas Pendientes; las Rechazadas o Canceladas no.
    """
    if padron.existe_usuario(db, contrato, numero_usuario):
        return "padron", None
    pendiente = alta_pendiente(db, contrato, numero_usuario)
    if pendiente is not None:
        return "pendiente", pendiente
    return None


def _where(filtros, ejecutivo=None):
    condiciones, params = [], []
    filtros = filtros or {}
    if ejecutivo is not None:
        condiciones.append("ejecutivo = ?")
        params.append(ejecutivo)
    elif filtros.get("ejecutivo"):
        condiciones.append("ejecutivo = ?")
        params.append(filtros["ejecutivo"])
    for campo in FILTROS_IGUALDAD:  # nombres de columna fijos, no vienen del usuario
        if filtros.get(campo):
            condiciones.append(f"{campo} = ?")
            params.append(filtros[campo])
    for clave, operador in (("desde", ">="), ("hasta", "<="), ("dia", "=")):
        valor = filtros.get(clave) or ""
        if RE_FECHA.fullmatch(valor):
            condiciones.append(f"substr(fecha_solicitud, 1, 10) {operador} ?")
            params.append(valor)
    texto = (filtros.get("q") or "").strip()
    if texto:
        like = f"%{texto}%"
        opciones = ["contrato LIKE ?", "numero_usuario LIKE ?", "nombre_cliente LIKE ?"]
        params += [like, like, like]
        sid = parse_folio(texto)
        if sid is not None:
            opciones.append("id = ?")
            params.append(sid)
        condiciones.append("(" + " OR ".join(opciones) + ")")
    where = (" WHERE " + " AND ".join(condiciones)) if condiciones else ""
    return where, params


def listar(db, filtros, ejecutivo=None, pagina=1, por_pagina=25):
    where, params = _where(filtros, ejecutivo)
    total = db.execute(f"SELECT COUNT(*) FROM solicitudes{where}", params).fetchone()[0]
    filas = db.execute(
        f"SELECT * FROM solicitudes{where} ORDER BY id DESC LIMIT ? OFFSET ?",
        params + [por_pagina, (pagina - 1) * por_pagina],
    ).fetchall()
    return filas, total


def listar_todas(db, filtros, ejecutivo=None):
    where, params = _where(filtros, ejecutivo)
    return db.execute(f"SELECT * FROM solicitudes{where} ORDER BY id DESC", params).fetchall()


def contadores(db, ejecutivo=None):
    where, params = ("", []) if ejecutivo is None else (" WHERE ejecutivo = ?", [ejecutivo])
    conteo = {e: 0 for e in ESTATUS}
    for fila in db.execute(f"SELECT estatus, COUNT(*) AS n FROM solicitudes{where} GROUP BY estatus", params):
        conteo[fila["estatus"]] = fila["n"]
    conteo["total"] = sum(conteo[e] for e in ESTATUS)
    return conteo


def por_contrato(db, contrato, ejecutivo=None):
    sql, params = "SELECT * FROM solicitudes WHERE contrato = ?", [contrato]
    if ejecutivo is not None:
        sql += " AND ejecutivo = ?"
        params.append(ejecutivo)
    return db.execute(sql + " ORDER BY id DESC", params).fetchall()


def pendientes_de(db, ejecutivo):
    return db.execute(
        "SELECT * FROM solicitudes WHERE ejecutivo = ? AND estatus = ? ORDER BY id", (ejecutivo, PENDIENTE)
    ).fetchall()


def transferir_pendientes(db, de, a, correo_nuevo, usuario, motivo):
    """Pasa las solicitudes Pendientes de un ejecutivo a otro, con su correo de notificaciones.

    Deja constancia en historial_estatus (el estatus no cambia). Quien llama abre la transacción.
    """
    pendientes = pendientes_de(db, de)
    momento = ahora_str()
    for sol in pendientes:
        db.execute("UPDATE solicitudes SET ejecutivo = ?, correo_notificaciones = ? WHERE id = ?",
                   (a, correo_nuevo, sol["id"]))
        db.execute(
            "INSERT INTO historial_estatus (solicitud_id, fecha, usuario, estatus_anterior, estatus_nuevo, comentario) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (sol["id"], momento, usuario, PENDIENTE, PENDIENTE, f"Transferida de {de} a {a}: {motivo}"),
        )
    return len(pendientes)


# ---------------------------------------------------------------- registro

def mensaje_alta_pendiente(sol, actor):
    """Solo muestra el folio a quien puede abrir esa solicitud."""
    if actor["rol"] == ROL_ADMIN or sol["ejecutivo"] == actor["usuario"]:
        return (f"Ya hay un alta pendiente para este contrato ({folio(sol['id'])}). "
                "Espera a que se atienda para agregar más usuarios.")
    return "Ya hay un alta pendiente para este contrato. Espera a que se atienda para agregar más usuarios."


def _resolver_ejecutivo(db, d, actor, errores, defecto=None):
    """El ejecutivo de la solicitud: el de la sesión, o el que elija el admin."""
    if actor["rol"] != ROL_ADMIN:
        return actor["usuario"]
    elegido = (d.get("ejecutivo") or defecto or "").lower()
    if not elegido:
        errores["ejecutivo"] = "Selecciona el ejecutivo solicitante."
        return None
    if not es_ejecutivo_activo(db, elegido):
        errores["ejecutivo"] = "Ejecutivo no válido."
        return None
    return elegido


def _marcar_duplicado(duplicado, contrato, errores, contexto):
    tipo, sol = duplicado
    if tipo == "padron":
        errores["numero_usuario"] = MSG_DUP_PADRON
        contexto["duplicado_contrato"] = contrato
    else:
        errores["numero_usuario"] = (
            f"Ya existe una solicitud de alta pendiente para este contrato y usuario ({folio(sol['id'])})."
        )


def _insertar(db, registro, registrado_por):
    columnas = ", ".join(COLUMNAS)
    marcas = ", ".join("?" for _ in COLUMNAS)
    cur = db.execute(f"INSERT INTO solicitudes ({columnas}) VALUES ({marcas})", [registro.get(c) for c in COLUMNAS])
    sid = cur.lastrowid
    db.execute(
        "INSERT INTO historial_estatus (solicitud_id, fecha, usuario, estatus_anterior, estatus_nuevo, comentario) "
        "VALUES (?, ?, ?, NULL, ?, ?)",
        (sid, registro["fecha_solicitud"], registrado_por["usuario"], PENDIENTE, "Solicitud registrada"),
    )
    notificaciones.por_nueva_solicitud(db, sid, registrado_por)
    return sid


def registrar_alta(db, datos, actor, catalogo):
    """Valida y registra un Alta nueva. Lanza ErrorSolicitud si algo no cumple."""
    d = V.normalizar(datos)
    errores_negocio, contexto = {}, {}
    existente = None

    if V.es_contrato(d.get("contrato", "")):
        estado, registro = padron.estado_contrato(db, d["contrato"], actor)
        if estado == "ajeno":
            errores_negocio["contrato"] = MSG_AJENO_ALTA
        elif estado == "alta_pendiente":
            errores_negocio["contrato"] = mensaje_alta_pendiente(registro, actor)
        elif estado == "propio":
            existente = registro

    errores = {**V.validar_alta(d, catalogo, contrato_existente=existente is not None), **errores_negocio}
    defecto = existente["ejecutivo_asignado"] if existente is not None else None
    ejecutivo = _resolver_ejecutivo(db, d, actor, errores, defecto)

    if "contrato" not in errores and "numero_usuario" not in errores:
        duplicado = buscar_duplicado(db, d["contrato"], d["numero_usuario"])
        if duplicado:
            _marcar_duplicado(duplicado, d["contrato"], errores, contexto)
    if errores:
        raise ErrorSolicitud(errores, contexto)

    registro = dict(d)
    if existente is not None:
        # Usuario nuevo en contrato existente: empresa y permisos vienen del padrón.
        for campo in CAMPOS_EMPRESA + CAMPOS_PERMISOS:
            registro[campo] = existente[campo]
    registro.update(
        fecha_solicitud=ahora_str(), tipo=TIPO_ALTA, estatus=PENDIENTE, ejecutivo=ejecutivo,
        permisos_vigentes=None, motivo_cambio=None, comentarios=d.get("comentarios") or None,
    )

    with transaccion(db):
        # Se vuelve a revisar con el bloqueo de escritura tomado, por si alguien registró lo mismo.
        duplicado = buscar_duplicado(db, d["contrato"], d["numero_usuario"])
        if duplicado:
            errores, contexto = {}, {}
            _marcar_duplicado(duplicado, d["contrato"], errores, contexto)
            raise ErrorSolicitud(errores, contexto)
        sid = _insertar(db, registro, actor)
    log.info("Solicitud %s (alta) registrada por %s para contrato %s", folio(sid), actor["usuario"], d["contrato"])
    return sid


def registrar_cambio(db, datos, actor, catalogo):
    """Valida y registra un Cambio de permisos sobre un contrato del padrón."""
    d = V.normalizar(datos)
    errores = V.validar_cambio(d, catalogo)
    cliente = None

    if "contrato" not in errores:
        estado, registro = padron.estado_contrato(db, d["contrato"], actor)
        if estado == "nuevo":
            errores["contrato"] = MSG_NO_EXISTE
        elif estado == "alta_pendiente":
            errores["contrato"] = MSG_ALTA_PENDIENTE_CAMBIO
        elif estado == "ajeno":
            errores["contrato"] = MSG_AJENO_CAMBIO
        else:
            cliente = registro
            pendiente = cambio_pendiente(db, d["contrato"])
            if pendiente is not None:
                errores["contrato"] = (
                    f"Ya hay un cambio de permisos pendiente para este contrato ({folio(pendiente['id'])})."
                )

    defecto = cliente["ejecutivo_asignado"] if cliente is not None else None
    ejecutivo = _resolver_ejecutivo(db, d, actor, errores, defecto)

    if cliente is not None and not errores:
        if not padron.diferencias(padron.permisos_de(cliente), padron.permisos_de(d)):
            errores["_general"] = MSG_SIN_CAMBIOS
    if errores:
        raise ErrorSolicitud(errores)

    registro = {c: d.get(c) for c in CAMPOS_PERMISOS}
    for campo in CAMPOS_EMPRESA:
        registro[campo] = cliente[campo]
    registro.update(
        contrato=d["contrato"], fecha_solicitud=ahora_str(), tipo=TIPO_CAMBIO, estatus=PENDIENTE,
        ejecutivo=ejecutivo, correo_notificaciones=d["correo_notificaciones"],
        permisos_vigentes=json.dumps(padron.permisos_de(cliente), ensure_ascii=False),
        motivo_cambio=d["motivo_cambio"], numero_usuario=None, nombre_completo=None, comentarios=None,
    )

    with transaccion(db):
        pendiente = cambio_pendiente(db, d["contrato"])
        if pendiente is not None:
            raise ErrorSolicitud({"contrato": (
                f"Ya hay un cambio de permisos pendiente para este contrato ({folio(pendiente['id'])})."
            )})
        sid = _insertar(db, registro, actor)
    log.info("Solicitud %s (cambio) registrada por %s para contrato %s", folio(sid), actor["usuario"], d["contrato"])
    return sid
