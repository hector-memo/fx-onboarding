"""Acceso a SQLite: conexión por petición, transacciones, esquema y migraciones."""
import logging
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from flask import current_app, g


def conectar(ruta):
    """Abre una conexión en modo autocommit; las escrituras agrupadas usan `transaccion`."""
    con = sqlite3.connect(ruta, timeout=15, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA busy_timeout = 15000")
    return con


def get_db():
    if "db" not in g:
        g.db = conectar(current_app.config["DATABASE"])
    return g.db


def cerrar_db(_error=None):
    con = g.pop("db", None)
    if con is not None:
        con.close()


@contextmanager
def transaccion(con):
    """Agrupa escrituras en una transacción atómica.

    BEGIN IMMEDIATE toma el bloqueo de escritura desde el inicio, así dos
    usuarios que guardan al mismo tiempo se atienden en orden y nunca se pisan.
    Si ya hay una transacción abierta, se reutiliza.
    """
    if con.in_transaction:
        yield con
        return
    con.execute("BEGIN IMMEDIATE")
    try:
        yield con
    except BaseException:
        con.execute("ROLLBACK")
        raise
    else:
        con.execute("COMMIT")


RUTA_ESQUEMA = Path(__file__).parent / "schema.sql"
log = logging.getLogger("fx")


def crear_esquema(con):
    """Crea las tablas que falten y aplica las migraciones pendientes. Se puede llamar siempre."""
    sql = RUTA_ESQUEMA.read_text(encoding="utf-8")
    con.executescript(sql)
    if migrar(con):
        con.executescript(sql)  # recrea los índices de las tablas reconstruidas
    con.execute("PRAGMA journal_mode = WAL")


def _columnas(con, tabla):
    return {r["name"]: r for r in con.execute(f"PRAGMA table_info({tabla})")}


def _reconstruir_tabla(con, tabla):
    """Reconstruye una tabla con la definición actual de schema.sql conservando sus datos.

    Es el procedimiento que recomienda SQLite para cambios que ALTER TABLE no soporta
    (por ejemplo, quitar un NOT NULL): crear la tabla nueva, copiar, borrar y renombrar.
    """
    sql = RUTA_ESQUEMA.read_text(encoding="utf-8")
    definicion = re.search(rf"CREATE TABLE IF NOT EXISTS {tabla} \(.*?\n\);", sql, re.DOTALL).group(0)
    temporal = f"{tabla}__nueva"
    actuales = _columnas(con, tabla)
    con.execute("PRAGMA foreign_keys = OFF")
    try:
        con.execute("BEGIN IMMEDIATE")
        con.execute(definicion.replace(f"IF NOT EXISTS {tabla} (", f"{temporal} (", 1))
        comunes = ", ".join(c for c in _columnas(con, temporal) if c in actuales)
        con.execute(f"INSERT INTO {temporal} ({comunes}) SELECT {comunes} FROM {tabla}")
        con.execute(f"DROP TABLE {tabla}")
        con.execute(f"ALTER TABLE {temporal} RENAME TO {tabla}")
        if con.execute("PRAGMA foreign_key_check").fetchall():
            raise sqlite3.IntegrityError(f"La migración de {tabla} rompió llaves foráneas.")
        con.execute("COMMIT")
    except BaseException:
        con.execute("ROLLBACK")
        raise
    finally:
        con.execute("PRAGMA foreign_keys = ON")
    log.info("Migración aplicada: tabla %s reconstruida", tabla)


def migrar(con):
    """Aplica cambios de estructura a bases creadas con versiones anteriores. Devuelve True si cambió algo."""
    cambios = False
    # Los límites del padrón pasaron a ser opcionales (antes NOT NULL).
    if _columnas(con, "clientes")["limite_operacion"]["notnull"]:
        _reconstruir_tabla(con, "clientes")
        cambios = True
    return cambios
