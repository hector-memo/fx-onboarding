-- Esquema de FX Onboarding (SQLite).
-- Contrato y número de usuario se guardan como TEXT para conservar ceros a la izquierda.
-- Divisas autorizadas: pares separados por coma, p. ej. 'EURMXN,USDMXN'.

CREATE TABLE IF NOT EXISTS usuarios (
    usuario           TEXT PRIMARY KEY,
    nombre            TEXT NOT NULL,
    correo            TEXT NOT NULL,
    rol               TEXT NOT NULL CHECK (rol IN ('admin', 'ejecutivo')),
    password_hash     TEXT NOT NULL,
    activo            INTEGER NOT NULL DEFAULT 1,
    debe_cambiar      INTEGER NOT NULL DEFAULT 1,
    intentos_fallidos INTEGER NOT NULL DEFAULT 0,
    bloqueado_hasta   TEXT
);

CREATE TABLE IF NOT EXISTS solicitudes (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha_solicitud       TEXT NOT NULL,
    tipo                  TEXT NOT NULL CHECK (tipo IN ('Alta nueva', 'Cambio de permisos')),
    estatus               TEXT NOT NULL DEFAULT 'Pendiente'
                          CHECK (estatus IN ('Pendiente', 'Listo para operar', 'Rechazada', 'Cancelada')),
    contrato              TEXT NOT NULL,
    nombre_cliente        TEXT,
    rfc                   TEXT,
    region                TEXT,
    segmento              TEXT,
    zona                  TEXT,
    numero_usuario        TEXT,
    nombre_completo       TEXT,
    ejecutivo             TEXT NOT NULL REFERENCES usuarios(usuario),
    correo_notificaciones TEXT NOT NULL,
    grupo_spot            TEXT,
    multiaprobacion       TEXT,
    multiabono            TEXT,
    divisas               TEXT,
    limite_operacion      REAL,
    limite_diario         REAL,
    permisos_vigentes     TEXT,      -- JSON con los permisos del padrón al momento de solicitar (cambios)
    comentarios           TEXT,
    motivo_cambio         TEXT,
    motivo_resolucion     TEXT,      -- motivo de rechazo o cancelación
    fecha_atencion        TEXT,
    atendido_por          TEXT,
    estatus_correo        TEXT NOT NULL DEFAULT 'No aplica'
                          CHECK (estatus_correo IN ('No aplica', 'Pendiente', 'Enviado', 'Error'))
);
CREATE INDEX IF NOT EXISTS ix_sol_contrato  ON solicitudes(contrato);
CREATE INDEX IF NOT EXISTS ix_sol_usuario   ON solicitudes(numero_usuario);
CREATE INDEX IF NOT EXISTS ix_sol_ejecutivo ON solicitudes(ejecutivo);
CREATE INDEX IF NOT EXISTS ix_sol_estatus   ON solicitudes(estatus);

CREATE TABLE IF NOT EXISTS historial_estatus (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    solicitud_id     INTEGER NOT NULL REFERENCES solicitudes(id),
    fecha            TEXT NOT NULL,
    usuario          TEXT NOT NULL,
    estatus_anterior TEXT,
    estatus_nuevo    TEXT NOT NULL,
    comentario       TEXT
);
CREATE INDEX IF NOT EXISTS ix_hist_sol ON historial_estatus(solicitud_id);

-- Padrón de clientes (base maestra). Datos de empresa y permisos a nivel contrato.
CREATE TABLE IF NOT EXISTS clientes (
    contrato             TEXT PRIMARY KEY,
    nombre_cliente       TEXT NOT NULL,
    rfc                  TEXT NOT NULL,
    region               TEXT NOT NULL,
    segmento             TEXT NOT NULL,
    zona                 TEXT NOT NULL,
    grupo_spot           TEXT NOT NULL,
    multiaprobacion      TEXT NOT NULL,
    multiabono           TEXT NOT NULL,
    divisas              TEXT NOT NULL,
    limite_operacion     REAL,           -- opcional
    limite_diario        REAL,           -- opcional
    ejecutivo_asignado   TEXT NOT NULL REFERENCES usuarios(usuario),
    origen               TEXT NOT NULL,
    solicitud_origen     INTEGER,
    fecha_alta           TEXT NOT NULL,
    ultima_actualizacion TEXT NOT NULL,
    actualizado_por      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_cli_ejecutivo ON clientes(ejecutivo_asignado);

-- Un mismo número de usuario puede estar en varios contratos; la unicidad es la pareja.
CREATE TABLE IF NOT EXISTS usuarios_cliente (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    contrato         TEXT NOT NULL REFERENCES clientes(contrato) ON DELETE CASCADE,
    numero_usuario   TEXT NOT NULL,
    nombre_completo  TEXT NOT NULL,
    fecha_alta       TEXT NOT NULL,
    origen           TEXT NOT NULL,
    solicitud_origen INTEGER,
    UNIQUE (contrato, numero_usuario)
);
CREATE INDEX IF NOT EXISTS ix_ucli_numero ON usuarios_cliente(numero_usuario);

-- Sin llave foránea: el historial se conserva aunque se elimine el contrato.
CREATE TABLE IF NOT EXISTS historial_padron (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    contrato       TEXT NOT NULL,
    numero_usuario TEXT,
    fecha          TEXT NOT NULL,
    usuario        TEXT NOT NULL,
    origen         TEXT NOT NULL,
    campo          TEXT NOT NULL,
    valor_anterior TEXT,
    valor_nuevo    TEXT,
    motivo         TEXT
);
CREATE INDEX IF NOT EXISTS ix_hpad_contrato ON historial_padron(contrato);

-- Bitácora de la administración de usuarios de la app (altas, ediciones, desactivaciones, etc.).
CREATE TABLE IF NOT EXISTS historial_usuarios (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario       TEXT NOT NULL,
    fecha         TEXT NOT NULL,
    realizado_por TEXT NOT NULL,
    accion        TEXT NOT NULL,
    detalle       TEXT
);
CREATE INDEX IF NOT EXISTS ix_husr_usuario ON historial_usuarios(usuario);

-- Campana de notificaciones: una fila por destinatario.
-- Ejecutivo: cambios de estatus de sus solicitudes. Administradores: cada solicitud nueva.
CREATE TABLE IF NOT EXISTS notificaciones (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario      TEXT NOT NULL,              -- destinatario
    fecha        TEXT NOT NULL,
    tipo         TEXT NOT NULL CHECK (tipo IN ('Nueva solicitud', 'Cambio de estatus')),
    solicitud_id INTEGER REFERENCES solicitudes(id),
    estatus      TEXT,                       -- estatus de la solicitud al crear el aviso
    mensaje      TEXT NOT NULL,
    leida        INTEGER NOT NULL DEFAULT 0,
    fecha_leida  TEXT
);
CREATE INDEX IF NOT EXISTS ix_notif_usuario ON notificaciones(usuario, leida);

CREATE TABLE IF NOT EXISTS cargas (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha     TEXT NOT NULL,
    usuario   TEXT NOT NULL,
    archivo   TEXT NOT NULL,
    validas   INTEGER NOT NULL,
    con_error INTEGER NOT NULL,
    omitidas  INTEGER NOT NULL
);
