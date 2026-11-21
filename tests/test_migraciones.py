"""Migraciones de estructura sobre bases creadas con versiones anteriores."""
from app.db import conectar, crear_esquema

# Tabla clientes tal como existía antes de que los límites fueran opcionales.
CLIENTES_ANTERIOR = """
CREATE TABLE clientes (
    contrato TEXT PRIMARY KEY, nombre_cliente TEXT NOT NULL, rfc TEXT NOT NULL, region TEXT NOT NULL,
    segmento TEXT NOT NULL, zona TEXT NOT NULL, grupo_spot TEXT NOT NULL, multiaprobacion TEXT NOT NULL,
    multiabono TEXT NOT NULL, divisas TEXT NOT NULL, limite_operacion REAL NOT NULL, limite_diario REAL NOT NULL,
    ejecutivo_asignado TEXT NOT NULL REFERENCES usuarios(usuario), origen TEXT NOT NULL, solicitud_origen INTEGER,
    fecha_alta TEXT NOT NULL, ultima_actualizacion TEXT NOT NULL, actualizado_por TEXT NOT NULL
);
CREATE TABLE usuarios_cliente (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contrato TEXT NOT NULL REFERENCES clientes(contrato) ON DELETE CASCADE,
    numero_usuario TEXT NOT NULL, nombre_completo TEXT NOT NULL, fecha_alta TEXT NOT NULL, origen TEXT NOT NULL,
    solicitud_origen INTEGER, UNIQUE (contrato, numero_usuario)
);
CREATE TABLE usuarios (
    usuario TEXT PRIMARY KEY, nombre TEXT NOT NULL, correo TEXT NOT NULL, rol TEXT NOT NULL,
    password_hash TEXT NOT NULL, activo INTEGER NOT NULL DEFAULT 1, debe_cambiar INTEGER NOT NULL DEFAULT 1,
    intentos_fallidos INTEGER NOT NULL DEFAULT 0, bloqueado_hasta TEXT
);
INSERT INTO usuarios (usuario, nombre, correo, rol, password_hash) VALUES ('ej1', 'Ej', 'e@x.com', 'ejecutivo', 'x');
INSERT INTO clientes VALUES ('40100000001', 'Cliente SA', 'CPR990101AB1', 'Norte', 'Corporativo', 'Zona 1',
    'Spot Básico', 'No', 'No', 'USDMXN', 100000, 500000, 'ej1', 'Carga inicial', NULL,
    '2023-06-01 00:00:00', '2023-06-01 00:00:00', 'admin');
INSERT INTO usuarios_cliente (contrato, numero_usuario, nombre_completo, fecha_alta, origen)
    VALUES ('40100000001', '80000001', 'Usuario', '2023-06-01 00:00:00', 'Carga inicial');
"""


def test_limites_del_padron_pasan_a_opcionales_sin_perder_datos(tmp_path):
    con = conectar(tmp_path / "anterior.db")
    con.executescript(CLIENTES_ANTERIOR)

    crear_esquema(con)

    columnas = {r["name"]: r for r in con.execute("PRAGMA table_info(clientes)")}
    assert columnas["limite_operacion"]["notnull"] == 0 and columnas["limite_diario"]["notnull"] == 0
    fila = con.execute("SELECT nombre_cliente, limite_operacion FROM clientes").fetchone()
    assert tuple(fila) == ("Cliente SA", 100000)
    # La llave foránea de usuarios_cliente sigue apuntando al padrón.
    con.execute("DELETE FROM clientes WHERE contrato = '40100000001'")
    assert con.execute("SELECT COUNT(*) FROM usuarios_cliente").fetchone()[0] == 0
    # Ahora se aceptan clientes sin límites, y los índices se recrearon.
    indices = {r["name"] for r in con.execute("PRAGMA index_list(clientes)")}
    assert "ix_cli_ejecutivo" in indices
    # Correr el esquema otra vez no vuelve a migrar.
    crear_esquema(con)
    con.close()
