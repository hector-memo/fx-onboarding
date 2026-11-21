"""Campana de notificaciones dentro de la app.

- Ejecutivo: un aviso cada vez que cambia el estatus de una de sus solicitudes
  (salvo cuando él mismo la cancela).
- Administradores: un aviso por cada solicitud nueva (a todos los administradores
  activos, excepto a quien la capturó).

Los avisos se crean dentro de la transacción del cambio que los origina: si el
cambio se revierte, el aviso también. Cada usuario solo ve y marca los suyos.
"""
from .constantes import RECHAZADA, ROL_ADMIN
from .utils import ahora_str, folio

TIPO_NUEVA = "Nueva solicitud"
TIPO_ESTATUS = "Cambio de estatus"
TIPOS = (TIPO_NUEVA, TIPO_ESTATUS)
MAX_EN_CAMPANA = 99  # la campana muestra "99+" a partir de aquí


def _crear(db, usuario, tipo, sol, mensaje, momento):
    db.execute(
        "INSERT INTO notificaciones (usuario, fecha, tipo, solicitud_id, estatus, mensaje) VALUES (?, ?, ?, ?, ?, ?)",
        (usuario, momento, tipo, sol["id"], sol["estatus"], mensaje),
    )


def _describir(sol):
    cliente = sol["nombre_cliente"] or "cliente"
    detalle = f"{sol['tipo']} · {cliente} · contrato {sol['contrato']}"
    if sol["numero_usuario"]:
        detalle += f" · usuario {sol['numero_usuario']}"
    return f"{folio(sol['id'])} ({detalle})"


def por_nueva_solicitud(db, sid, actor):
    """Avisa a los administradores activos (menos a quien la capturó). Quien llama abre la transacción."""
    sol = db.execute(
        "SELECT s.*, u.nombre AS nombre_ejecutivo FROM solicitudes s "
        "LEFT JOIN usuarios u ON u.usuario = s.ejecutivo WHERE s.id = ?", (sid,)
    ).fetchone()
    ejecutivo = sol["nombre_ejecutivo"] or sol["ejecutivo"]
    mensaje = f"Nueva solicitud {_describir(sol)} enviada por {ejecutivo}."
    if actor["usuario"] != sol["ejecutivo"]:
        mensaje = f"Nueva solicitud {_describir(sol)} capturada por {actor['nombre']} a nombre de {ejecutivo}."
    admins = db.execute(
        "SELECT usuario FROM usuarios WHERE rol = ? AND activo = 1 AND usuario != ? ORDER BY usuario",
        (ROL_ADMIN, actor["usuario"]),
    ).fetchall()
    momento = sol["fecha_solicitud"]
    for admin in admins:
        _crear(db, admin["usuario"], TIPO_NUEVA, sol, mensaje, momento)
    return len(admins)


def por_cambio_estatus(db, sid, actor):
    """Avisa al ejecutivo dueño del nuevo estatus, si no fue él quien lo cambió. Quien llama abre la transacción."""
    sol = db.execute("SELECT * FROM solicitudes WHERE id = ?", (sid,)).fetchone()
    if sol["ejecutivo"] == actor["usuario"]:
        return 0
    mensaje = f"Tu solicitud {_describir(sol)} cambió a «{sol['estatus']}»."
    if sol["estatus"] == RECHAZADA and sol["motivo_resolucion"]:
        mensaje += f" Motivo: {sol['motivo_resolucion']}"
    _crear(db, sol["ejecutivo"], TIPO_ESTATUS, sol, mensaje, sol["fecha_atencion"] or ahora_str())
    return 1


# ---------------------------------------------------------------- consultas del destinatario

def no_leidas(db, usuario):
    return db.execute(
        "SELECT COUNT(*) FROM notificaciones WHERE usuario = ? AND leida = 0", (usuario,)
    ).fetchone()[0]


def texto_contador(n):
    return f"{MAX_EN_CAMPANA}+" if n > MAX_EN_CAMPANA else str(n)


def listar(db, usuario, solo_no_leidas=False, pagina=1, por_pagina=25):
    where, params = "WHERE usuario = ?", [usuario]
    if solo_no_leidas:
        where += " AND leida = 0"
    total = db.execute(f"SELECT COUNT(*) FROM notificaciones {where}", params).fetchone()[0]
    filas = db.execute(
        f"SELECT * FROM notificaciones {where} ORDER BY id DESC LIMIT ? OFFSET ?",
        params + [por_pagina, (pagina - 1) * por_pagina],
    ).fetchall()
    return filas, total


def obtener(db, nid, usuario):
    """Solo devuelve la notificación si es del usuario."""
    return db.execute("SELECT * FROM notificaciones WHERE id = ? AND usuario = ?", (nid, usuario)).fetchone()


def marcar_leida(db, nid, usuario):
    """True si existía y era del usuario."""
    if obtener(db, nid, usuario) is None:
        return False
    db.execute(
        "UPDATE notificaciones SET leida = 1, fecha_leida = ? WHERE id = ? AND usuario = ? AND leida = 0",
        (ahora_str(), nid, usuario),
    )
    return True


def marcar_todas(db, usuario):
    cur = db.execute(
        "UPDATE notificaciones SET leida = 1, fecha_leida = ? WHERE usuario = ? AND leida = 0",
        (ahora_str(), usuario),
    )
    return cur.rowcount
