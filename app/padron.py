"""Padrón de clientes (base maestra).

Todas las escrituras al padrón pasan por este módulo y quedan registradas en
historial_padron. Las funciones que escriben esperan que quien las llama abra
la transacción (`with transaccion(db):`).
"""
import logging

from .constantes import (
    CAMPOS_EMPRESA, CAMPOS_PERMISOS, ETIQUETAS, ORIGEN_EDICION, ORIGEN_ELIMINACION,
    ORIGEN_REASIGNACION, ORIGEN_SOLICITUD, ROL_ADMIN, TIPO_ALTA, TIPO_CAMBIO, PENDIENTE,
)
from .usuarios import es_ejecutivo_activo
from .utils import ahora_str, folio, formatear_monto
from .validaciones import normalizar_divisas

log = logging.getLogger("fx")

CAMPOS_EDITABLES = CAMPOS_EMPRESA + CAMPOS_PERMISOS
COLUMNAS_CLIENTE = ("contrato",) + CAMPOS_EDITABLES + (
    "ejecutivo_asignado", "origen", "solicitud_origen", "fecha_alta",
    "ultima_actualizacion", "actualizado_por",
)
FILTROS_CARTERA = ("region", "segmento", "grupo_spot")


class ErrorPadron(Exception):
    """Regla de negocio del padrón que impide la operación."""


# ---------------------------------------------------------------- consultas

def _get(registro, campo):
    try:
        return registro[campo]
    except (KeyError, IndexError):
        return None


def es_admin(actor):
    return actor["rol"] == ROL_ADMIN


def obtener_cliente(db, contrato):
    return db.execute("SELECT * FROM clientes WHERE contrato = ?", (contrato,)).fetchone()


def usuarios_de(db, contrato):
    return db.execute(
        "SELECT * FROM usuarios_cliente WHERE contrato = ? ORDER BY numero_usuario", (contrato,)
    ).fetchall()


def existe_usuario(db, contrato, numero_usuario):
    fila = db.execute(
        "SELECT 1 FROM usuarios_cliente WHERE contrato = ? AND numero_usuario = ?",
        (contrato, numero_usuario),
    ).fetchone()
    return fila is not None


def puede_ver(cliente, actor):
    return es_admin(actor) or cliente["ejecutivo_asignado"] == actor["usuario"]


def cliente_visible(db, contrato, actor):
    """El cliente si el actor puede verlo; None si no existe o es de otra cartera."""
    cliente = obtener_cliente(db, contrato)
    if cliente is None or not puede_ver(cliente, actor):
        return None
    return cliente


def estado_contrato(db, contrato, actor):
    """Situación de un contrato para el actor.

    Devuelve (estado, registro):
      ("propio", cliente)          en el padrón y en su cartera (el admin ve todos)
      ("ajeno", None)              en el padrón pero en otra cartera (sin datos)
      ("alta_pendiente", sol)      no está en el padrón y tiene un alta Pendiente
      ("nuevo", None)              no existe
    """
    cliente = obtener_cliente(db, contrato)
    if cliente is not None:
        return ("propio", cliente) if puede_ver(cliente, actor) else ("ajeno", None)
    pendiente = db.execute(
        "SELECT * FROM solicitudes WHERE tipo = ? AND estatus = ? AND contrato = ? ORDER BY id LIMIT 1",
        (TIPO_ALTA, PENDIENTE, contrato),
    ).fetchone()
    if pendiente is not None:
        return "alta_pendiente", pendiente
    return "nuevo", None


def valor_normalizado(campo, valor):
    """Normaliza un valor para comparar el padrón contra lo solicitado."""
    if campo in ("limite_operacion", "limite_diario"):
        try:
            return round(float(valor), 2)
        except (TypeError, ValueError):
            return valor
    if campo == "divisas":
        return normalizar_divisas(valor)
    return "" if valor is None else valor


def permisos_de(registro):
    return {c: valor_normalizado(c, _get(registro, c)) for c in CAMPOS_PERMISOS}


def diferencias(actual, nuevo):
    """Campos de `nuevo` cuyo valor difiere de `actual`."""
    cambios = []
    for campo, valor in nuevo.items():
        antes = valor_normalizado(campo, actual.get(campo))
        despues = valor_normalizado(campo, valor)
        if antes != despues:
            cambios.append({"campo": campo, "etiqueta": ETIQUETAS.get(campo, campo),
                            "antes": antes, "despues": despues})
    return cambios


def historial_de(db, contrato):
    return db.execute(
        "SELECT * FROM historial_padron WHERE contrato = ? ORDER BY id DESC", (contrato,)
    ).fetchall()


# ---------------------------------------------------------------- cartera

def _where_cartera(filtros, actor):
    condiciones, params = [], []
    filtros = filtros or {}
    if not es_admin(actor):
        condiciones.append("c.ejecutivo_asignado = ?")
        params.append(actor["usuario"])
    elif filtros.get("ejecutivo"):
        condiciones.append("c.ejecutivo_asignado = ?")
        params.append(filtros["ejecutivo"])
    for campo in FILTROS_CARTERA:  # nombres de columna fijos, no vienen del usuario
        if filtros.get(campo):
            condiciones.append(f"c.{campo} = ?")
            params.append(filtros[campo])
    zona = (filtros.get("zona") or "").strip()
    if zona:  # la zona es texto libre: se busca por coincidencia parcial
        condiciones.append("c.zona LIKE ?")
        params.append(f"%{zona}%")
    texto = (filtros.get("q") or "").strip()
    if texto:
        like = f"%{texto}%"
        condiciones.append(
            "(c.contrato LIKE ? OR c.nombre_cliente LIKE ? OR c.rfc LIKE ? OR EXISTS ("
            "SELECT 1 FROM usuarios_cliente u2 WHERE u2.contrato = c.contrato AND u2.numero_usuario LIKE ?))"
        )
        params += [like, like, like, like]
    where = (" WHERE " + " AND ".join(condiciones)) if condiciones else ""
    return where, params


def listar_cartera(db, filtros, actor, pagina=1, por_pagina=25):
    where, params = _where_cartera(filtros, actor)
    total = db.execute(f"SELECT COUNT(*) FROM clientes c{where}", params).fetchone()[0]
    filas = db.execute(
        "SELECT c.*, (SELECT COUNT(*) FROM usuarios_cliente u WHERE u.contrato = c.contrato) AS num_usuarios "
        f"FROM clientes c{where} ORDER BY c.nombre_cliente, c.contrato LIMIT ? OFFSET ?",
        params + [por_pagina, (pagina - 1) * por_pagina],
    ).fetchall()
    return filas, total


def cartera_completa(db, filtros, actor):
    """Contratos y usuarios de la cartera visible (para exportar)."""
    where, params = _where_cartera(filtros, actor)
    clientes = db.execute(
        "SELECT c.*, (SELECT COUNT(*) FROM usuarios_cliente u WHERE u.contrato = c.contrato) AS num_usuarios "
        f"FROM clientes c{where} ORDER BY c.nombre_cliente, c.contrato",
        params,
    ).fetchall()
    usuarios = db.execute(
        "SELECT u.*, c.nombre_cliente FROM usuarios_cliente u JOIN clientes c ON c.contrato = u.contrato"
        f"{where} ORDER BY u.contrato, u.numero_usuario",
        params,
    ).fetchall()
    return clientes, usuarios


def contadores_cartera(db, actor):
    if es_admin(actor):
        where, params = "", []
    else:
        where, params = " WHERE c.ejecutivo_asignado = ?", [actor["usuario"]]
    contratos = db.execute(f"SELECT COUNT(*) FROM clientes c{where}", params).fetchone()[0]
    usuarios = db.execute(
        f"SELECT COUNT(*) FROM usuarios_cliente u JOIN clientes c ON c.contrato = u.contrato{where}", params
    ).fetchone()[0]
    return {"contratos": contratos, "usuarios": usuarios}


# ---------------------------------------------------------------- escrituras

def _texto(valor):
    if valor is None:
        return None
    if isinstance(valor, float):
        return formatear_monto(valor)
    return str(valor)


def registrar_historial(db, contrato, usuario, origen, campo, antes=None, despues=None,
                        motivo=None, numero_usuario=None):
    db.execute(
        "INSERT INTO historial_padron (contrato, numero_usuario, fecha, usuario, origen, campo, "
        "valor_anterior, valor_nuevo, motivo) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (contrato, numero_usuario, ahora_str(), usuario, origen, campo, _texto(antes), _texto(despues), motivo),
    )


def _tocar(db, contrato, usuario):
    db.execute(
        "UPDATE clientes SET ultima_actualizacion = ?, actualizado_por = ? WHERE contrato = ?",
        (ahora_str(), usuario, contrato),
    )


def crear_cliente(db, datos, usuario, origen, solicitud_id=None, fecha_alta=None):
    """Da de alta un contrato en el padrón. `datos` debe traer ejecutivo_asignado."""
    if obtener_cliente(db, datos["contrato"]) is not None:
        raise ErrorPadron(f"El contrato {datos['contrato']} ya existe en el padrón.")
    momento = ahora_str()
    registro = {c: _get(datos, c) for c in ("contrato",) + CAMPOS_EDITABLES}
    registro["divisas"] = normalizar_divisas(registro["divisas"])
    registro.update(
        ejecutivo_asignado=datos["ejecutivo_asignado"],
        origen=origen,
        solicitud_origen=solicitud_id,
        fecha_alta=fecha_alta or momento,
        ultima_actualizacion=momento,
        actualizado_por=usuario,
    )
    columnas = ", ".join(COLUMNAS_CLIENTE)
    marcas = ", ".join("?" for _ in COLUMNAS_CLIENTE)
    db.execute(f"INSERT INTO clientes ({columnas}) VALUES ({marcas})", [registro[c] for c in COLUMNAS_CLIENTE])
    origen_hist = folio(solicitud_id) if solicitud_id else origen
    registrar_historial(db, registro["contrato"], usuario, origen_hist, "Alta de contrato en padrón",
                        None, registro["nombre_cliente"])
    log.info("Padrón: alta de contrato %s (%s) por %s", registro["contrato"], origen_hist, usuario)


def agregar_usuario(db, contrato, numero_usuario, nombre_completo, usuario, origen,
                    solicitud_id=None, fecha_alta=None):
    if obtener_cliente(db, contrato) is None:
        raise ErrorPadron(f"El contrato {contrato} no existe en el padrón.")
    if existe_usuario(db, contrato, numero_usuario):
        raise ErrorPadron(f"El usuario {numero_usuario} ya existe en el contrato {contrato}.")
    db.execute(
        "INSERT INTO usuarios_cliente (contrato, numero_usuario, nombre_completo, fecha_alta, origen, "
        "solicitud_origen) VALUES (?, ?, ?, ?, ?, ?)",
        (contrato, numero_usuario, nombre_completo, fecha_alta or ahora_str(), origen, solicitud_id),
    )
    origen_hist = folio(solicitud_id) if solicitud_id else origen
    registrar_historial(db, contrato, usuario, origen_hist, "Alta de usuario", None, nombre_completo,
                        numero_usuario=numero_usuario)
    _tocar(db, contrato, usuario)


def _actualizar_campos(db, cliente, nuevos, usuario, origen, motivo=None):
    for campo in nuevos:
        if campo not in CAMPOS_EDITABLES:
            raise ValueError(f"Campo no editable: {campo}")
    actuales = {c: cliente[c] for c in nuevos}
    cambios = diferencias(actuales, nuevos)
    if not cambios:
        return []
    asignaciones = ", ".join(f"{c['campo']} = ?" for c in cambios)
    db.execute(
        f"UPDATE clientes SET {asignaciones}, ultima_actualizacion = ?, actualizado_por = ? WHERE contrato = ?",
        [c["despues"] for c in cambios] + [ahora_str(), usuario, cliente["contrato"]],
    )
    for c in cambios:
        registrar_historial(db, cliente["contrato"], usuario, origen, c["etiqueta"], c["antes"], c["despues"], motivo)
    return cambios


def aplicar_solicitud(db, sol, usuario):
    """Refleja en el padrón una solicitud que pasa a "Listo para operar"."""
    contrato = sol["contrato"]
    if sol["tipo"] == TIPO_ALTA:
        if existe_usuario(db, contrato, sol["numero_usuario"]):
            raise ErrorPadron(
                f"El usuario {sol['numero_usuario']} ya existe en el contrato {contrato} del padrón. "
                "Rechaza la solicitud como duplicada."
            )
        if obtener_cliente(db, contrato) is None:
            datos = dict(sol)
            datos["ejecutivo_asignado"] = sol["ejecutivo"]
            crear_cliente(db, datos, usuario, ORIGEN_SOLICITUD, solicitud_id=sol["id"])
        agregar_usuario(db, contrato, sol["numero_usuario"], sol["nombre_completo"], usuario,
                        ORIGEN_SOLICITUD, solicitud_id=sol["id"])
    elif sol["tipo"] == TIPO_CAMBIO:
        cliente = obtener_cliente(db, contrato)
        if cliente is None:
            raise ErrorPadron(f"El contrato {contrato} ya no existe en el padrón.")
        _actualizar_campos(db, cliente, permisos_de(sol), usuario, folio(sol["id"]), motivo=sol["motivo_cambio"])
    else:
        raise ErrorPadron(f"Tipo de solicitud desconocido: {sol['tipo']}")


def editar_cliente(db, contrato, datos, usuario, motivo):
    if not (motivo or "").strip():
        raise ErrorPadron("El motivo es obligatorio.")
    cliente = obtener_cliente(db, contrato)
    if cliente is None:
        raise ErrorPadron("El contrato no existe en el padrón.")
    nuevos = {c: _get(datos, c) for c in CAMPOS_EDITABLES}
    return _actualizar_campos(db, cliente, nuevos, usuario, ORIGEN_EDICION, motivo.strip())


def reasignar(db, contrato, nuevo_ejecutivo, usuario, motivo):
    if not (motivo or "").strip():
        raise ErrorPadron("El motivo es obligatorio.")
    cliente = obtener_cliente(db, contrato)
    if cliente is None:
        raise ErrorPadron("El contrato no existe en el padrón.")
    nuevo_ejecutivo = (nuevo_ejecutivo or "").lower()
    if not es_ejecutivo_activo(db, nuevo_ejecutivo):
        raise ErrorPadron("Selecciona un ejecutivo activo.")
    if nuevo_ejecutivo == cliente["ejecutivo_asignado"]:
        raise ErrorPadron("El contrato ya está asignado a ese ejecutivo.")
    db.execute(
        "UPDATE clientes SET ejecutivo_asignado = ?, ultima_actualizacion = ?, actualizado_por = ? WHERE contrato = ?",
        (nuevo_ejecutivo, ahora_str(), usuario, contrato),
    )
    registrar_historial(db, contrato, usuario, ORIGEN_REASIGNACION, ETIQUETAS["ejecutivo_asignado"],
                        cliente["ejecutivo_asignado"], nuevo_ejecutivo, motivo.strip())
    log.info("Padrón: contrato %s reasignado de %s a %s por %s", contrato,
             cliente["ejecutivo_asignado"], nuevo_ejecutivo, usuario)


def contratos_asignados(db, ejecutivo):
    return [r["contrato"] for r in db.execute(
        "SELECT contrato FROM clientes WHERE ejecutivo_asignado = ? ORDER BY contrato", (ejecutivo,))]


def transferir_contratos(db, de, a, usuario, motivo):
    """Reasigna todos los contratos de un ejecutivo a otro (cada uno queda en su historial)."""
    contratos = contratos_asignados(db, de)
    for contrato in contratos:
        reasignar(db, contrato, a, usuario, motivo)
    return len(contratos)


def eliminar_usuario(db, contrato, numero_usuario, usuario, motivo):
    """Corrección de errores de captura/carga. No es una baja formal."""
    if not (motivo or "").strip():
        raise ErrorPadron("El motivo es obligatorio.")
    fila = db.execute(
        "SELECT * FROM usuarios_cliente WHERE contrato = ? AND numero_usuario = ?", (contrato, numero_usuario)
    ).fetchone()
    if fila is None:
        raise ErrorPadron("El usuario no existe en este contrato.")
    db.execute("DELETE FROM usuarios_cliente WHERE id = ?", (fila["id"],))
    registrar_historial(db, contrato, usuario, ORIGEN_ELIMINACION, "Eliminación de usuario",
                        fila["nombre_completo"], None, motivo.strip(), numero_usuario=numero_usuario)
    _tocar(db, contrato, usuario)
    log.info("Padrón: usuario %s eliminado del contrato %s por %s", numero_usuario, contrato, usuario)


def eliminar_cliente(db, contrato, usuario, motivo):
    """Corrección de errores de captura/carga. Elimina el contrato y sus usuarios."""
    if not (motivo or "").strip():
        raise ErrorPadron("El motivo es obligatorio.")
    cliente = obtener_cliente(db, contrato)
    if cliente is None:
        raise ErrorPadron("El contrato no existe en el padrón.")
    num = len(usuarios_de(db, contrato))
    db.execute("DELETE FROM clientes WHERE contrato = ?", (contrato,))
    registrar_historial(db, contrato, usuario, ORIGEN_ELIMINACION, "Eliminación de contrato",
                        f"{cliente['nombre_cliente']} ({num} usuario(s))", None, motivo.strip())
    log.info("Padrón: contrato %s eliminado por %s", contrato, usuario)
