"""Usuarios de la aplicación (administradores y ejecutivos).

Reglas de la pantalla Usuarios (solo admin):
- Nadie puede desactivarse ni cambiarse el rol a sí mismo.
- Siempre debe quedar al menos un administrador activo.
- Un ejecutivo con contratos asignados o solicitudes pendientes no se desactiva ni cambia de rol
  sin transferir antes su cartera a otro ejecutivo activo.
Cada acción queda en historial_usuarios y en logs/app.log.
"""
import logging
from datetime import datetime

from werkzeug.security import generate_password_hash

from .constantes import PENDIENTE, ROL_ADMIN, ROL_EJECUTIVO
from .db import transaccion
from .utils import FMT_DB, ahora, ahora_str

log = logging.getLogger("fx")

ACCION_ALTA = "Alta"
ACCION_EDICION = "Edición"
ACCION_DESACTIVACION = "Desactivación"
ACCION_REACTIVACION = "Reactivación"
ACCION_CONTRASENA = "Contraseña restablecida"
ACCION_DESBLOQUEO = "Desbloqueo"
ACCION_TRANSFERENCIA = "Transferencia de cartera"
ETIQUETA_ROL = {ROL_ADMIN: "Administrador", ROL_EJECUTIVO: "Ejecutivo"}


class ErrorUsuario(Exception):
    """Operación no permitida. `errores` trae los errores por campo, si los hay."""

    def __init__(self, mensaje, errores=None):
        super().__init__(mensaje)
        self.errores = errores or {}


# ---------------------------------------------------------------- operaciones básicas (también las usa manage.py)

def crear_usuario(db, usuario, nombre, correo, rol, contrasena, debe_cambiar=True):
    if rol not in (ROL_ADMIN, ROL_EJECUTIVO):
        raise ValueError("Rol no válido: usa 'admin' o 'ejecutivo'.")
    db.execute(
        "INSERT INTO usuarios (usuario, nombre, correo, rol, password_hash, activo, debe_cambiar) "
        "VALUES (?, ?, ?, ?, ?, 1, ?)",
        (usuario.strip().lower(), nombre.strip(), correo.strip().lower(), rol,
         generate_password_hash(contrasena), 1 if debe_cambiar else 0),
    )


def restablecer_contrasena(db, usuario, contrasena):
    """Pone una contraseña temporal y obliga a cambiarla en el siguiente inicio de sesión."""
    cur = db.execute(
        "UPDATE usuarios SET password_hash = ?, debe_cambiar = 1, intentos_fallidos = 0, "
        "bloqueado_hasta = NULL WHERE usuario = ?",
        (generate_password_hash(contrasena), usuario.strip().lower()),
    )
    return cur.rowcount == 1


def registrar_historial(db, usuario, realizado_por, accion, detalle=None):
    db.execute(
        "INSERT INTO historial_usuarios (usuario, fecha, realizado_por, accion, detalle) VALUES (?, ?, ?, ?, ?)",
        (usuario, ahora_str(), realizado_por, accion, detalle),
    )


# ---------------------------------------------------------------- consultas

def ejecutivos_activos(db):
    return db.execute(
        "SELECT usuario, nombre FROM usuarios WHERE rol = ? AND activo = 1 ORDER BY nombre",
        (ROL_EJECUTIVO,),
    ).fetchall()


def opciones_ejecutivos(db, excluir=None):
    """[(usuario, nombre)] para listas desplegables."""
    return [(r["usuario"], r["nombre"]) for r in ejecutivos_activos(db) if r["usuario"] != excluir]


def es_ejecutivo_activo(db, usuario):
    fila = db.execute(
        "SELECT 1 FROM usuarios WHERE usuario = ? AND rol = ? AND activo = 1",
        ((usuario or "").lower(), ROL_EJECUTIVO),
    ).fetchone()
    return fila is not None


def obtener(db, usuario):
    return db.execute("SELECT * FROM usuarios WHERE usuario = ?", ((usuario or "").lower(),)).fetchone()


def esta_bloqueado(fila):
    if not fila["bloqueado_hasta"]:
        return False
    return datetime.strptime(fila["bloqueado_hasta"], FMT_DB) > ahora()


def admins_activos(db):
    return db.execute("SELECT COUNT(*) FROM usuarios WHERE rol = ? AND activo = 1", (ROL_ADMIN,)).fetchone()[0]


def carga_de_trabajo(db, usuario):
    """(contratos asignados, solicitudes pendientes) de un usuario."""
    contratos = db.execute("SELECT COUNT(*) FROM clientes WHERE ejecutivo_asignado = ?", (usuario,)).fetchone()[0]
    pendientes = db.execute(
        "SELECT COUNT(*) FROM solicitudes WHERE ejecutivo = ? AND estatus = ?", (usuario, PENDIENTE)
    ).fetchone()[0]
    return contratos, pendientes


def listar(db, filtros=None):
    filtros = filtros or {}
    condiciones, params = [], []
    if filtros.get("rol") in (ROL_ADMIN, ROL_EJECUTIVO):
        condiciones.append("u.rol = ?")
        params.append(filtros["rol"])
    if filtros.get("estado") == "activo":
        condiciones.append("u.activo = 1")
    elif filtros.get("estado") == "inactivo":
        condiciones.append("u.activo = 0")
    texto = (filtros.get("q") or "").strip()
    if texto:
        condiciones.append("(u.usuario LIKE ? OR u.nombre LIKE ? OR u.correo LIKE ?)")
        params += [f"%{texto}%"] * 3
    where = (" WHERE " + " AND ".join(condiciones)) if condiciones else ""
    return db.execute(
        "SELECT u.*, "
        "(SELECT COUNT(*) FROM clientes c WHERE c.ejecutivo_asignado = u.usuario) AS num_contratos, "
        "(SELECT COUNT(*) FROM solicitudes s WHERE s.ejecutivo = u.usuario AND s.estatus = 'Pendiente') AS pendientes "
        f"FROM usuarios u{where} ORDER BY u.activo DESC, u.rol, u.nombre",
        params,
    ).fetchall()


def contadores(db):
    fila = db.execute(
        "SELECT COUNT(*) AS total, "
        "SUM(CASE WHEN activo = 1 AND rol = 'admin' THEN 1 ELSE 0 END) AS admins, "
        "SUM(CASE WHEN activo = 1 AND rol = 'ejecutivo' THEN 1 ELSE 0 END) AS ejecutivos, "
        "SUM(CASE WHEN activo = 0 THEN 1 ELSE 0 END) AS inactivos FROM usuarios"
    ).fetchone()
    return {k: fila[k] or 0 for k in ("total", "admins", "ejecutivos", "inactivos")}


def historial(db, usuario):
    return db.execute(
        "SELECT * FROM historial_usuarios WHERE usuario = ? ORDER BY id DESC", (usuario,)
    ).fetchall()


# ---------------------------------------------------------------- pantalla Usuarios

def _normalizar(datos):
    return {
        "usuario": (datos.get("usuario") or "").strip().lower(),
        "nombre": " ".join((datos.get("nombre") or "").split()),
        "correo": (datos.get("correo") or "").strip().lower(),
        "rol": (datos.get("rol") or "").strip(),
        "contrasena": datos.get("contrasena") or "",
    }


def _requerir(db, usuario):
    fila = obtener(db, usuario)
    if fila is None:
        raise ErrorUsuario("El usuario no existe.")
    return fila


def registrar_usuario(db, datos, actor):
    """Alta desde la pantalla Usuarios. El usuario deberá cambiar la contraseña temporal al entrar."""
    from .validaciones import validar_usuario_app

    d = _normalizar(datos)
    errores = validar_usuario_app(d, nuevo=True)
    if "usuario" not in errores and obtener(db, d["usuario"]) is not None:
        errores["usuario"] = "Ese usuario ya existe."
    if errores:
        raise ErrorUsuario("Revisa los campos marcados.", errores)
    with transaccion(db):
        crear_usuario(db, d["usuario"], d["nombre"], d["correo"], d["rol"], d["contrasena"], debe_cambiar=True)
        registrar_historial(db, d["usuario"], actor["usuario"], ACCION_ALTA,
                            f"{ETIQUETA_ROL[d['rol']]} · {d['nombre']} · {d['correo']}")
    log.info("Usuarios: alta de %s (%s) por %s", d["usuario"], d["rol"], actor["usuario"])
    return d["usuario"]


def actualizar_usuario(db, usuario, datos, actor):
    """Edita nombre, correo y rol. Devuelve la lista de cambios aplicados."""
    from .validaciones import validar_usuario_app

    actual = _requerir(db, usuario)
    d = _normalizar(datos)
    errores = validar_usuario_app(d, nuevo=False)
    if errores:
        raise ErrorUsuario("Revisa los campos marcados.", errores)

    if d["rol"] != actual["rol"]:
        if actual["usuario"] == actor["usuario"]:
            raise ErrorUsuario("No puedes cambiar tu propio rol.", {"rol": "No puedes cambiar tu propio rol."})
        if actual["rol"] == ROL_ADMIN and actual["activo"] and admins_activos(db) <= 1:
            raise ErrorUsuario("Debe quedar al menos un administrador activo.",
                               {"rol": "Debe quedar al menos un administrador activo."})
        contratos, pendientes = carga_de_trabajo(db, actual["usuario"])
        if actual["rol"] == ROL_EJECUTIVO and (contratos or pendientes):
            mensaje = (f"Tiene {contratos} contrato(s) y {pendientes} solicitud(es) pendiente(s). "
                       "Transfiere su cartera antes de cambiar su rol.")
            raise ErrorUsuario(mensaje, {"rol": mensaje})

    cambios = [(campo, actual[campo], d[campo]) for campo in ("nombre", "correo", "rol") if actual[campo] != d[campo]]
    if not cambios:
        return []
    with transaccion(db):
        db.execute("UPDATE usuarios SET nombre = ?, correo = ?, rol = ? WHERE usuario = ?",
                   (d["nombre"], d["correo"], d["rol"], actual["usuario"]))
        detalle = "; ".join(f"{campo}: {antes} → {despues}" for campo, antes, despues in cambios)
        registrar_historial(db, actual["usuario"], actor["usuario"], ACCION_EDICION, detalle)
    log.info("Usuarios: %s editado por %s (%s)", actual["usuario"], actor["usuario"], detalle)
    return cambios


def transferir_cartera(db, usuario, destino, actor, motivo):
    """Pasa contratos asignados y solicitudes pendientes de un ejecutivo a otro. Devuelve (contratos, solicitudes)."""
    from . import padron
    from . import solicitudes

    origen = _requerir(db, usuario)
    destino = (destino or "").lower()
    motivo = (motivo or "").strip()
    if not motivo:
        raise ErrorUsuario("El motivo es obligatorio.", {"motivo": "Campo obligatorio."})
    if destino == origen["usuario"] or not es_ejecutivo_activo(db, destino):
        raise ErrorUsuario("Elige otro ejecutivo activo para recibir la cartera.",
                           {"transferir_a": "Elige otro ejecutivo activo."})
    correo_destino = obtener(db, destino)["correo"]
    with transaccion(db):
        contratos = padron.transferir_contratos(db, origen["usuario"], destino, actor["usuario"], motivo)
        pendientes = solicitudes.transferir_pendientes(db, origen["usuario"], destino, correo_destino,
                                                       actor["usuario"], motivo)
        detalle = f"{contratos} contrato(s) y {pendientes} solicitud(es) pendiente(s) a {destino}: {motivo}"
        registrar_historial(db, origen["usuario"], actor["usuario"], ACCION_TRANSFERENCIA, detalle)
        registrar_historial(db, destino, actor["usuario"], ACCION_TRANSFERENCIA,
                            f"Recibió {contratos} contrato(s) y {pendientes} solicitud(es) de {origen['usuario']}")
    log.info("Usuarios: cartera de %s transferida a %s por %s (%s contratos, %s pendientes)",
             origen["usuario"], destino, actor["usuario"], contratos, pendientes)
    return contratos, pendientes


def desactivar(db, usuario, actor, transferir_a=None, motivo=""):
    """Desactiva un usuario (ya no puede entrar). Si tiene cartera, la transfiere en la misma operación."""
    actual = _requerir(db, usuario)
    motivo = (motivo or "").strip()
    if actual["usuario"] == actor["usuario"]:
        raise ErrorUsuario("No puedes desactivarte a ti mismo.")
    if not actual["activo"]:
        raise ErrorUsuario("El usuario ya está inactivo.")
    if actual["rol"] == ROL_ADMIN and admins_activos(db) <= 1:
        raise ErrorUsuario("Debe quedar al menos un administrador activo.")
    if not motivo:
        raise ErrorUsuario("El motivo es obligatorio.", {"motivo": "Campo obligatorio."})
    contratos, pendientes = carga_de_trabajo(db, actual["usuario"])
    if (contratos or pendientes) and not transferir_a:
        raise ErrorUsuario(
            f"Tiene {contratos} contrato(s) y {pendientes} solicitud(es) pendiente(s). "
            "Elige a quién transferir su cartera.", {"transferir_a": "Elige a quién transferir su cartera."})
    with transaccion(db):
        if contratos or pendientes:
            transferir_cartera(db, actual["usuario"], transferir_a, actor, motivo)
        db.execute("UPDATE usuarios SET activo = 0 WHERE usuario = ?", (actual["usuario"],))
        registrar_historial(db, actual["usuario"], actor["usuario"], ACCION_DESACTIVACION, motivo)
    log.info("Usuarios: %s desactivado por %s", actual["usuario"], actor["usuario"])


def reactivar(db, usuario, actor):
    actual = _requerir(db, usuario)
    if actual["activo"]:
        raise ErrorUsuario("El usuario ya está activo.")
    with transaccion(db):
        db.execute("UPDATE usuarios SET activo = 1, intentos_fallidos = 0, bloqueado_hasta = NULL WHERE usuario = ?",
                   (actual["usuario"],))
        registrar_historial(db, actual["usuario"], actor["usuario"], ACCION_REACTIVACION)
    log.info("Usuarios: %s reactivado por %s", actual["usuario"], actor["usuario"])


def restablecer(db, usuario, contrasena, actor):
    """Contraseña temporal desde la pantalla Usuarios (también quita el bloqueo)."""
    from .validaciones import validar_contrasena_nueva

    actual = _requerir(db, usuario)
    mensaje = validar_contrasena_nueva(contrasena or "")
    if mensaje:
        raise ErrorUsuario(mensaje, {"contrasena": mensaje})
    with transaccion(db):
        restablecer_contrasena(db, actual["usuario"], contrasena)
        registrar_historial(db, actual["usuario"], actor["usuario"], ACCION_CONTRASENA,
                            "Contraseña temporal; deberá cambiarla al entrar")
    log.info("Usuarios: contraseña de %s restablecida por %s", actual["usuario"], actor["usuario"])


def desbloquear(db, usuario, actor):
    actual = _requerir(db, usuario)
    with transaccion(db):
        db.execute("UPDATE usuarios SET intentos_fallidos = 0, bloqueado_hasta = NULL WHERE usuario = ?",
                   (actual["usuario"],))
        registrar_historial(db, actual["usuario"], actor["usuario"], ACCION_DESBLOQUEO)
    log.info("Usuarios: %s desbloqueado por %s", actual["usuario"], actor["usuario"])
