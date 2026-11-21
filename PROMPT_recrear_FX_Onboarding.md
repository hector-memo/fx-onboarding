# Prompt para recrear "FX Onboarding"

> **Cómo usarlo:** copia todo lo que está debajo de la línea y pégalo en el asistente de IA. Si el asistente corta la respuesta, escribe **"continúa con la siguiente fase"**. Al terminar, sigue el README que genere: instalar dependencias, `python manage.py init`, `python run.py` y `pytest`.

---

Actúa como desarrollador senior full-stack en Python. Vas a construir completa, y lista para ejecutarse, una aplicación web llamada **FX Onboarding**. Centraliza las solicitudes de **alta de clientes** y **cambios de permisos** de una plataforma de FX (mesa de cambios), mantiene un **padrón maestro de clientes** con trazabilidad completa y permite al administrador **gestionar los usuarios** de la app. Hoy los ejecutivos de cuenta envían estas peticiones por correo; la app las reemplaza con formularios en línea.

Sigue esta especificación al pie de la letra. Donde da un texto, un nombre o un mensaje exacto, úsalo tal cual. Si algo no está especificado, elige la opción más simple y coherente con el resto, y menciónalo.

## 0. FORMA DE ENTREGA (OBLIGATORIA)

1. Primero responde en pocas líneas confirmando la arquitectura y el árbol de archivos de la sección 2. No escribas código en ese mensaje.
2. Después entrega el código **por fases**, cada archivo completo en su propio bloque de código con su ruta como título. Nunca uses "…", "resto igual" ni marcadores; cada archivo debe poder copiarse tal cual.
   - Fase 1: `requirements.txt`, `.env.example`, `.gitignore`, `pytest.ini`, `catalogos.json`, `config.py`, `app/schema.sql`, `app/db.py`, `app/constantes.py`, `app/utils.py`, `app/catalogos.py`.
   - Fase 2: `app/validaciones.py`, `app/usuarios.py`, `app/padron.py`, `app/solicitudes.py`, `app/estatus.py`, `app/correo.py`.
   - Fase 3: `app/exportar.py`, `app/carga.py`, `app/respaldo.py`, `app/datos_ejemplo.py`, `app/__init__.py`, `app/auth.py`, `app/rutas/*.py`.
   - Fase 4: todas las plantillas de `app/templates/` y `app/static/`.
   - Fase 5: `run.py`, `manage.py`, `tests/*.py`, `README.md`.
3. Al final de cada fase escribe: "Fase N completa. Escribe *continúa* para la siguiente." Si tu respuesta se corta a la mitad de un archivo, en la siguiente respuesta vuelve a entregar ese archivo completo desde el inicio.

## 1. STACK

- Python 3.11+. Dependencias exactas (`requirements.txt`): `Flask==3.0.3`, `Flask-WTF==1.2.1` (solo para CSRF), `openpyxl==3.1.5`, `python-dotenv==1.0.1`, `waitress==3.0.0`, `tzdata==2024.1`, `pytest==8.3.3`. **No uses pandas ni un ORM**: SQL directo con el módulo `sqlite3`.
- Flask con blueprints; plantillas Jinja2; CSS y JavaScript propios, sin frameworks ni CDNs (debe funcionar sin internet).
- Base de datos: **SQLite**, un solo archivo `data/fx_onboarding.db`, sin servidor. Excel (.xlsx) se usa solo para exportaciones y para la carga inicial de clientes.
- Servidor: `waitress`, escuchando en HOST/PORT de `.env` para que otros equipos de la red interna entren.
- Interfaz 100 % en español, limpia y responsiva (funciona en celular).

## 2. ESTRUCTURA DE ARCHIVOS

```
onbording_app/
├── run.py                 arranque con waitress
├── manage.py              comandos: init, crear-usuario, restablecer-contrasena
├── config.py              clase Config; lee .env con python-dotenv
├── catalogos.json         listas editables
├── requirements.txt, .env.example, .gitignore, pytest.ini, README.md
├── app/
│   ├── __init__.py        create_app(config_override=None): fábrica, filtros Jinja, errores, blueprints
│   ├── schema.sql         tablas e índices (sección 4)
│   ├── db.py              conexión, transacciones, crear_esquema, migraciones
│   ├── constantes.py      estatus, tipos, roles, orígenes, campos, etiquetas
│   ├── utils.py           fechas, folios, formato
│   ├── catalogos.py       lee catalogos.json
│   ├── validaciones.py    TODAS las reglas de validación (un solo módulo)
│   ├── usuarios.py        usuarios de la app y reglas de la pantalla Usuarios (sección 8.1)
│   ├── notificaciones.py  campana de notificaciones (sección 8.2)
│   ├── padron.py          TODAS las escrituras al padrón + historial
│   ├── solicitudes.py     registro de solicitudes, consultas y duplicados
│   ├── estatus.py         transiciones de estatus (definidas en un solo lugar)
│   ├── correo.py          notificaciones SMTP o carpeta outbox/
│   ├── exportar.py        exportaciones .xlsx y sanitización
│   ├── carga.py           plantilla, análisis e importación de la carga inicial
│   ├── respaldo.py        respaldos del archivo SQLite
│   ├── datos_ejemplo.py   datos de prueba
│   ├── auth.py            blueprint auth + decoradores login_requerido / admin_requerido
│   ├── rutas/             __init__.py, comun.py, ejecutivo.py, formularios.py, api.py, admin.py, cartera.py,
│   │                      padron_admin.py, usuarios_admin.py, notificaciones.py
│   ├── templates/         base.html, _macros.html, _campos_empresa.html, _campos_permisos.html,
│   │                      _contadores_solicitudes.html, login.html, cambiar_contrasena.html, error.html,
│   │                      mis_solicitudes.html, admin_solicitudes.html, solicitud_detalle.html,
│   │                      form_alta.html, form_cambio.html, cartera.html, cliente_detalle.html,
│   │                      cliente_editar.html, carga.html, captura_cliente.html, captura_usuario.html,
│   │                      usuarios.html, usuario_nuevo.html, usuario_detalle.html, notificaciones.html,
│   │                      correo/notificacion.html
│   └── static/            css/app.css, js/app.js
└── tests/                 conftest.py, test_validaciones.py, test_duplicados.py, test_padron.py,
                           test_estatus.py, test_aislamiento.py, test_carga.py, test_exportar.py,
                           test_migraciones.py, test_usuarios.py, test_notificaciones.py
```

Carpetas que la app crea sola: `data/`, `data/cargas/`, `backups/`, `logs/`, `outbox/` y `datos_ejemplo/`. Van en `.gitignore`, junto con `.env`, `.venv/`, `__pycache__/`, `.pytest_cache/` y `*.db`.

## 3. CONFIGURACIÓN

`config.py` define `BASE_DIR` (carpeta del archivo) y una clase `Config` con estos valores, leídos de `.env` con default:

| Clave | Default |
|---|---|
| SECRET_KEY | `cambia-esta-clave` |
| HOST / PORT | `127.0.0.1` / `8000` (en `.env.example`: `0.0.0.0`) |
| DATABASE | `data/fx_onboarding.db` |
| CATALOGOS | `catalogos.json` |
| BACKUP_DIR / LOG_FILE / OUTBOX_DIR / UPLOAD_DIR | `backups/` / `logs/app.log` / `outbox/` / `data/cargas/` |
| DATOS_EJEMPLO_DIR | `datos_ejemplo/` |
| TIMEZONE | `America/Mexico_City` |
| SESSION_MINUTES | 30 (expiración por inactividad) |
| MAX_LOGIN_ATTEMPTS / LOCKOUT_MINUTES | 5 / 15 |
| SLA_DIAS_HABILES | 2 |
| PAGE_SIZE | 25 |
| BACKUP_KEEP | 14 |
| MAX_UPLOAD_MB | 5 (se usa para MAX_CONTENT_LENGTH) |
| RESPALDO_AUTOMATICO | True (los tests lo ponen en False) |
| MAIL_ENABLED | false |
| MAIL_HOST, MAIL_PORT (587), MAIL_USE_TLS (true), MAIL_USE_SSL (false), MAIL_USERNAME, MAIL_PASSWORD, MAIL_FROM, MAIL_TIMEOUT (15) | |

Además: `SESSION_COOKIE_HTTPONLY=True`, `SESSION_COOKIE_SAMESITE="Lax"`, `WTF_CSRF_TIME_LIMIT=None`. `.env.example` documenta todas las claves con comentarios en español.

## 4. MODELO DE DATOS (usa este `schema.sql` tal cual)

```sql
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
```

Notas:
- **No existen** campos de CLABE / cuenta de liquidación ni de Estatus KYC/PLD. No los agregues.
- Fechas guardadas como texto `AAAA-MM-DD HH:MM:SS` en hora local (TIMEZONE, vía `zoneinfo`) y mostradas como `DD/MM/AAAA HH:MM`.
- Folio visible de una solicitud: `SOL-` + id con 6 dígitos (`SOL-000012`). En las URL se usa el id numérico. La búsqueda acepta `SOL-000012`, `sol12`, etc.
- El "padrón" son las tablas `clientes` y `usuarios_cliente`.
- `notificaciones` no necesita migración: `CREATE TABLE IF NOT EXISTS` la agrega a bases existentes al arrancar. Los avisos empiezan a generarse desde ese momento (no se crean retroactivos).

### `db.py`
- `conectar(ruta)`: `sqlite3.connect(ruta, timeout=15, isolation_level=None)` (autocommit), `row_factory = sqlite3.Row`, `PRAGMA foreign_keys = ON`, `PRAGMA busy_timeout = 15000`.
- `get_db()`: una conexión por contexto de app, guardada en `g`. `cerrar_db` se registra en `teardown_appcontext`.
- `transaccion(con)`: context manager. Si ya hay transacción abierta, la reutiliza. Si no, `BEGIN IMMEDIATE`, luego `COMMIT`, o `ROLLBACK` ante cualquier excepción. Todas las escrituras de varios pasos lo usan.
- `crear_esquema(con)`: ejecuta `schema.sql` (idempotente), luego `migrar(con)`; si hubo migración, vuelve a ejecutar `schema.sql` para recrear índices. Termina con `PRAGMA journal_mode = WAL`. `create_app` la llama siempre al arrancar.
- `migrar(con)`: si `clientes.limite_operacion` tiene NOT NULL (bases de una versión anterior), reconstruye la tabla con el procedimiento recomendado por SQLite: `foreign_keys OFF` → crear `clientes__nueva` con la definición actual tomada de `schema.sql` → copiar las columnas comunes → `DROP clientes` → renombrar → verificar `PRAGMA foreign_key_check` → `foreign_keys ON`. Todo en una transacción y sin perder datos. Registra "Migración aplicada" en el log.

## 5. CONSTANTES (`constantes.py`)

- Estatus: `Pendiente`, `Listo para operar`, `Rechazada`, `Cancelada`. Tipos: `Alta nueva`, `Cambio de permisos`. Roles: `admin`, `ejecutivo`.
- Estatus de correo: `No aplica`, `Pendiente`, `Enviado`, `Error`.
- Orígenes del padrón: `Solicitud`, `Carga inicial`, `Captura manual`, `Edición manual`, `Reasignación`, `Eliminación`.
- `SI = "Sí"`, `NO = "No"`.
- `CAMPOS_EMPRESA = (nombre_cliente, rfc, region, segmento, zona)`.
- `CAMPOS_PERMISOS = (grupo_spot, multiaprobacion, multiabono, divisas, limite_operacion, limite_diario)`.
- `ETIQUETAS` (campo → texto visible): contrato "Contrato de banca electrónica", nombre_cliente "Nombre de cliente", rfc "RFC", region "Región", segmento "Segmento", zona "Zona", numero_usuario "Número de usuario", nombre_completo "Nombre completo", ejecutivo "Ejecutivo solicitante", correo_notificaciones "Correo para notificaciones", grupo_spot "Grupo de parametrización spot", multiaprobacion "Multiaprobación", multiabono "Multiabono", divisas "Divisas autorizadas", limite_operacion "Límite por operación (USD)", limite_diario "Límite diario (USD)", comentarios "Comentarios", motivo_cambio "Motivo del cambio", ejecutivo_asignado "Ejecutivo asignado", fecha_alta "Fecha de alta en plataforma", motivo "Motivo".

## 6. CATÁLOGOS (`catalogos.json`, editable, se lee en cada uso)

```json
{
  "_instrucciones": "Reemplaza estos valores de ejemplo por los reales. Los cambios se aplican sin reiniciar la app. Si quitas un valor, los registros históricos lo siguen mostrando. La zona es texto libre y no tiene catálogo.",
  "regiones": ["Norte", "Noreste", "Centro", "Bajío", "Occidente", "Sur"],
  "segmentos": ["Corporativo", "Empresarial", "PyME", "Gobierno", "Institucional"],
  "grupos_spot": ["Spot Básico", "Spot Estándar", "Spot Preferente", "Spot Premium"],
  "divisas": ["USDMXN", "EURMXN", "GBPMXN", "CADMXN", "CHFMXN", "EURUSD", "GBPUSD", "USDCAD"]
}
```

`catalogos.cargar()` devuelve un dict con las claves `regiones`, `segmentos`, `grupos_spot` y `divisas` (las divisas en mayúsculas). **La zona no tiene catálogo.**

## 7. VALIDACIONES (`validaciones.py`, el único lugar con reglas)

Normalización (`normalizar(datos)`), antes de validar o guardar:
- Ignora `csrf_token`. Recorta espacios y colapsa espacios internos.
- `contrato` y `numero_usuario`: quita todos los espacios.
- `rfc` en mayúsculas.
- `multiaprobacion` y `multiabono`: "si/sí/s/yes/true/1/verdadero" → `Sí`; "no/n/false/0/falso" → `No`.
- `divisas`: lista o texto separado por comas o punto y coma → mayúsculas, sin repetidos, orden alfabético, unidas con coma (`"EURMXN,USDMXN"`).
- Límites: vacío → `None`. Si no, se convierten a número (acepta `"1,000,000.50"` y `$`), redondeado a 2 decimales. Si no se pueden convertir, se deja el texto para reportar el error.
- `correo_notificaciones`, `ejecutivo` y `ejecutivo_asignado` en minúsculas.

Reglas (cada validador llena un dict `{campo: mensaje}`; si el campo es obligatorio y viene vacío, el mensaje es `"Campo obligatorio."`):
- Contrato: exactamente 11 dígitos → "El contrato debe tener exactamente 11 dígitos numéricos."
- Número de usuario: exactamente 8 dígitos → "El número de usuario debe tener exactamente 8 dígitos numéricos."
- RFC: persona moral `[A-ZÑ&]{3}AAMMDD[A-Z0-9]{3}` (12) o física `[A-ZÑ&]{4}AAMMDD[A-Z0-9]{3}` (13), con fecha válida (prueba `date(2000+AA, MM, DD)`) → "RFC inválido: 12 caracteres (persona moral) o 13 (persona física), con fecha válida."
- Nombre de cliente y nombre completo: obligatorios, máx. 150. Comentarios: opcional, máx. 500. Motivo del cambio: obligatorio, máx. 500.
- **Zona: texto libre, obligatorio, máx. 100** ("Máximo 100 caracteres.").
- Región, Segmento y Grupo spot: solo valores del catálogo → `"«valor» no es un valor válido; selecciona uno de la lista."`
- Multiaprobación y Multiabono: `Sí` o `No` → "Selecciona Sí o No."
- Divisas: al menos una; todas del catálogo → "Divisas no válidas: X, Y."
- **Límites (USD): OPCIONALES.** Si vienen, deben ser número ("Debe ser un número.") y mayores a 0 ("Debe ser mayor a 0."). Solo si vienen los dos: diario ≥ operación → "El límite diario debe ser mayor o igual al límite por operación."
- Correo: formato `algo@dominio.ext` → "El correo no tiene un formato válido."
- Contraseña nueva: mínimo 8 caracteres, con letras y números.
- Usuario de la app (`validar_usuario_app(d, nuevo=True)`): en altas, `usuario` con regex `[a-z0-9._-]{3,30}` ("Usa de 3 a 30 caracteres: minúsculas, números, punto, guion o guion bajo.") y contraseña temporal válida; siempre, nombre obligatorio (máx. 150), correo válido (campo `correo`) y rol `admin` o `ejecutivo` ("Selecciona un rol.").

Validadores compuestos:
- `validar_alta(d, cat, contrato_existente=False)`: contrato, número de usuario, nombre completo, correo y comentarios; si NO es contrato existente, además empresa y permisos.
- `validar_cambio(d, cat)`: contrato, permisos, correo, motivo_cambio.
- `validar_cliente_padron(d, cat)`: contrato, empresa, permisos.
- `validar_usuario_padron(d)`: contrato, número de usuario, nombre completo.

## 8. USUARIOS, ROLES Y SEGURIDAD

- **Ejecutivo**: ve en "Mi cartera" solo los contratos donde es el ejecutivo asignado. Envía altas y cambios solo sobre contratos nuevos o de su cartera. Consulta "Mis solicitudes" y puede cancelar las suyas mientras estén Pendientes.
- **Administrador**: ve todo, aprueba o rechaza, carga y corrige el padrón, reasigna clientes, exporta, **administra los usuarios** (sección 8.1) y puede capturar solicitudes a nombre de un ejecutivo (eligiéndolo de una lista).
- Contraseñas con `werkzeug.security` (hash). Usuarios de ejemplo creados con `debe_cambiar=1`: mientras no cambien su contraseña, cualquier página (salvo login, logout, cambiar contraseña y estáticos) redirige a `/cambiar-contrasena`.
- Login: usuario en minúsculas; mensaje genérico "Usuario o contraseña incorrectos." Después de MAX_LOGIN_ATTEMPTS fallos se bloquea LOCKOUT_MINUTES: "Cuenta bloqueada por intentos fallidos. Intenta de nuevo en N minuto(s)." Un login correcto reinicia el contador. El parámetro `next` solo acepta rutas relativas (`/...`, nunca `//`).
- Sesión permanente con expiración por inactividad (SESSION_MINUTES). CSRF (Flask-WTF `CSRFProtect`) en todos los formularios POST, incluido logout.
- `before_request`: carga `g.usuario` (fila de `usuarios` activa) desde `session["usuario"]`.
- `login_requerido`: sin sesión → redirige a login, o responde `{"error": "Sesión expirada"}` con 401 si la ruta empieza con `/api/`. `admin_requerido`: un ejecutivo recibe 403.
- **Aislamiento:** si un ejecutivo abre, cancela, consulta por API o exporta una solicitud o un contrato que no es suyo, responde **404** (no se revela que existe). Rutas de admin → 403.
- Páginas de error 403, 404, 413 (archivo grande) y CSRF (400, "El formulario expiró…") con una plantilla común `error.html`.

### 8.1 Pantalla Usuarios (solo admin; `usuarios.py` + blueprint `usuarios_admin`, prefijo `/admin/usuarios`)

Funciones de `usuarios.py`. Las de base también las usa `manage.py`: `crear_usuario`, `restablecer_contrasena`, `registrar_historial`, `ejecutivos_activos`, `opciones_ejecutivos(db, excluir=None)` y `es_ejecutivo_activo`. Las de la pantalla lanzan `ErrorUsuario(mensaje, errores_por_campo)`, abren su propia `transaccion` y registran cada acción en `historial_usuarios` y en el log:
- `listar(db, filtros)`: rol, estado (`activo`/`inactivo`) y `q` (usuario, nombre o correo). Incluye `num_contratos` (contratos asignados) y `pendientes` (solicitudes Pendientes). Orden: activos primero, luego por rol y nombre.
- `contadores(db)`: administradores activos, ejecutivos activos e inactivos.
- `registrar_usuario(db, datos, actor)`: normaliza (usuario y correo en minúsculas), valida con `validar_usuario_app`, rechaza usuarios repetidos ("Ese usuario ya existe.") y crea el usuario con `debe_cambiar=1`. Acción "Alta".
- `actualizar_usuario(db, usuario, datos, actor)`: edita nombre, correo y rol (el usuario no se puede cambiar). Reglas para cambiar el rol: nadie cambia su propio rol ("No puedes cambiar tu propio rol."); siempre debe quedar al menos un administrador activo ("Debe quedar al menos un administrador activo."); un ejecutivo con contratos asignados o solicitudes pendientes no cambia de rol ("Tiene N contrato(s) y M solicitud(es) pendiente(s). Transfiere su cartera antes de cambiar su rol."). Acción "Edición" con detalle `campo: antes → después`.
- `transferir_cartera(db, usuario, destino, actor, motivo)`: el destino debe ser **otro** ejecutivo activo y el motivo es obligatorio. Reasigna cada contrato con `padron.reasignar` (vía `padron.transferir_contratos`, cada uno queda en `historial_padron`). Pasa las solicitudes Pendientes con `solicitudes.transferir_pendientes`, que cambia `ejecutivo` y `correo_notificaciones` al del destino y agrega en `historial_estatus` un renglón Pendiente → Pendiente con el comentario "Transferida de X a Y: motivo". Acción "Transferencia de cartera" en ambos usuarios ("Recibió N contrato(s)…" en el destino). Devuelve (contratos, solicitudes).
- `desactivar(db, usuario, actor, transferir_a=None, motivo)`: nadie se desactiva a sí mismo ("No puedes desactivarte a ti mismo."); siempre queda al menos un administrador activo; motivo obligatorio. Si tiene contratos o pendientes y no se eligió `transferir_a` → error "Tiene N contrato(s) y M solicitud(es) pendiente(s). Elige a quién transferir su cartera." Si se eligió, transfiere y desactiva en la misma transacción (si la transferencia falla, no cambia nada). Pone `activo=0`. Acción "Desactivación".
- `reactivar` (pone `activo=1` y quita el bloqueo; acción "Reactivación"), `restablecer(db, usuario, contrasena, actor)` (contraseña temporal validada, `debe_cambiar=1` y desbloqueo; acción "Contraseña restablecida") y `desbloquear` (reinicia intentos y bloqueo sin cambiar la contraseña; acción "Desbloqueo").
- `esta_bloqueado(fila)`, `carga_de_trabajo(db, usuario)` → (contratos, pendientes), `historial(db, usuario)`.

Efectos: un usuario inactivo no puede iniciar sesión ("Usuario o contraseña incorrectos."). Como `before_request` solo carga usuarios activos, si tenía la sesión abierta, su siguiente petición lo manda al login. Además deja de aparecer en todas las listas de ejecutivos. Su historial y sus solicitudes atendidas se conservan.

Rutas (todas con `admin_requerido`; un ejecutivo recibe 403):

| Ruta | Método | Qué hace |
|---|---|---|
| `/admin/usuarios/` | GET | Contadores (administradores activos, ejecutivos activos, inactivos); filtros (rol, estado, búsqueda); tabla: usuario (enlace), nombre ("(tú)" en la cuenta propia), correo, rol, estado (etiquetas Activo verde / Inactivo gris / Bloqueado rojo / Contraseña temporal amarillo), contratos y pendientes (solo ejecutivos; "—" en admins) y botón "Administrar". Botón "Nuevo usuario". |
| `/admin/usuarios/nuevo` | GET/POST | Formulario: usuario (con ayuda del formato; no se cambia después), nombre completo, correo, rol (Ejecutivo/Administrador, por defecto Ejecutivo) y contraseña temporal. Con errores se vuelve a mostrar **sin** la contraseña. Al crear, redirige al detalle con el mensaje para compartir la contraseña temporal. |
| `/admin/usuarios/<usuario>` | GET/POST | Detalle: encabezado con nombre y etiquetas de estado. Tarjeta "Datos" (editar nombre, correo y rol; el rol queda deshabilitado en la cuenta propia, con aviso). Tarjeta "Contraseña y acceso" (restablecer con contraseña temporal; si está bloqueado, botón "Desbloquear sin cambiar contraseña"). Si es ejecutivo, tarjeta "Cartera" con sus números, enlaces a `/cartera/?ejecutivo=…` y a `/admin/solicitudes?ejecutivo=…&estatus=Pendiente`, y, si tiene algo, el formulario "Transferir cartera" (destino + motivo, con confirmación). Si no es la cuenta propia: "Desactivar" (motivo; si tiene cartera, también la lista "Transferir su cartera a"; con confirmación) o "Reactivar". Tabla "Historial" (fecha, acción, realizado por, detalle). 404 si no existe. |
| `/admin/usuarios/<usuario>/desactivar`, `/reactivar`, `/restablecer`, `/desbloquear`, `/transferir` | POST | Acciones; redirigen al detalle con un mensaje de éxito o de error. |

`manage.py crear-usuario` y `restablecer-contrasena` siguen existiendo (para el primer administrador o para recuperar el acceso) y registran en `historial_usuarios` con `realizado_por = "consola"`.

### 8.2 Notificaciones (campana; `notificaciones.py` + blueprint `notificaciones`, prefijo `/notificaciones`)

Avisos dentro de la app (no reemplazan al correo). Una fila por destinatario en la tabla `notificaciones`. Tipos: `"Nueva solicitud"` y `"Cambio de estatus"`.

Quién recibe qué:
- **Administradores → "Nueva solicitud"**: cada vez que se registra un Alta nueva o un Cambio de permisos, un aviso para **cada administrador activo, excepto quien la capturó**. Mensaje: `Nueva solicitud SOL-000012 (Alta nueva · <cliente> · contrato <contrato> · usuario <número>) enviada por <nombre del ejecutivo>.` Si un admin la capturó a nombre de un ejecutivo: `… capturada por <nombre del admin> a nombre de <nombre del ejecutivo>.` (El cambio de permisos no lleva "· usuario …".) La fecha del aviso es la fecha de la solicitud.
- **Ejecutivo → "Cambio de estatus"**: cada vez que cambia el estatus de una de sus solicitudes, un aviso para el ejecutivo dueño (`solicitudes.ejecutivo`), **salvo que él mismo hizo el cambio** (cancelar la propia no genera aviso). Mensaje: `Tu solicitud SOL-000012 (<tipo> · <cliente> · contrato …) cambió a «Listo para operar».` En un rechazo se agrega ` Motivo: <motivo>`. La fecha es la fecha de atención. Cada solicitud de una aprobación masiva genera su propio aviso.
- La columna `estatus` guarda el estatus de la solicitud al crear el aviso (Pendiente en las nuevas), para pintar su etiqueta de color.
- Carga inicial, captura manual, edición del padrón y transferencias de cartera **no** generan avisos.

Reglas técnicas:
- `por_nueva_solicitud(db, sid, actor)` se llama desde `solicitudes._insertar` y `por_cambio_estatus(db, sid, actor)` desde `estatus.cambiar_estatus`, **dentro de la misma transacción**: si el registro o el cambio falla y se revierte, no queda ningún aviso. (Por eso `_insertar` recibe el `actor` completo y no solo su usuario.)
- Consultas, siempre filtradas por el destinatario: `no_leidas(db, usuario)`, `listar(db, usuario, solo_no_leidas=False, pagina, por_pagina)` (del más reciente al más antiguo), `obtener(db, nid, usuario)` (None si no es suya), `marcar_leida(db, nid, usuario)` → True/False (pone `leida=1` y `fecha_leida`), `marcar_todas(db, usuario)` → cuántas marcó, `texto_contador(n)` → `"99+"` si n > 99.
- La campana **no** se refresca sola (sin sondeo con JavaScript): un sondeo periódico renovaría la sesión en cada petición y anularía la expiración por inactividad. El contador se recalcula en cada página que se abre.

Campana en la barra superior (`base.html`, para ambos roles, a la izquierda del nombre del usuario): ícono de campana en SVG en línea, enlace a `/notificaciones/`, con un globo rojo con el número de no leídas (oculto si es 0; "99+" si pasa de 99), `title` y `aria-label` "Notificaciones: N sin leer" / "Notificaciones: ninguna sin leer"; resaltada cuando estás en la pantalla. El context processor de `create_app` expone `notif_sin_leer` y `notif_texto`.

Rutas (todas con `login_requerido`; cada quien solo las suyas):

| Ruta | Método | Qué hace |
|---|---|---|
| `/notificaciones/` | GET | Título "Notificaciones" y una línea que explica qué avisos recibe según su rol. Pestañas "Todas" y "Sin leer (N)" (`?estado=no_leidas`). Botón "Marcar todas como leídas" (solo si hay sin leer). Lista paginada de tarjetas: las no leídas con fondo azul claro, un punto azul y el mensaje en negritas; cada una muestra tipo · fecha, la etiqueta del estatus, el mensaje y los botones "Ver solicitud" y "Marcar como leída" (este solo si no está leída). Vacío: "Aún no tienes notificaciones." / "No tienes notificaciones sin leer." |
| `/notificaciones/<id>/abrir` | POST | Marca leída y redirige a `/solicitudes/<id>`. Si el usuario ya no puede ver esa solicitud, vuelve a la lista con el aviso "Esta solicitud ya no está en tu cartera." 404 si la notificación no es suya. |
| `/notificaciones/<id>/leida` | POST | Marca leída y vuelve a la lista. 404 si no es suya. |
| `/notificaciones/marcar-todas` | POST | Marca todas las del usuario; mensaje "N notificación(es) marcada(s) como leída(s)." o "No había notificaciones sin leer." |

Los POST de esta pantalla mandan un campo oculto `estado` para regresar a la misma pestaña.

## 9. PADRÓN DE CLIENTES (`padron.py`)

Reglas:
- Datos de empresa y permisos son **a nivel contrato**. Un contrato tiene uno o varios usuarios.
- Un número de usuario **puede** estar en varios contratos; la unicidad es (contrato, número de usuario).
- Cada contrato tiene ejecutivo asignado: el solicitante del alta que lo creó, o el indicado en la carga inicial o captura manual. Solo el admin lo reasigna.

Funciones clave:
- `estado_contrato(db, contrato, actor)` → `("propio", cliente)` si está en el padrón y el actor lo puede ver (el admin ve todos); `("ajeno", None)` si es de otra cartera; `("alta_pendiente", solicitud)` si no está en el padrón pero hay un Alta nueva Pendiente con ese contrato; `("nuevo", None)` si no existe.
- `permisos_de(registro)` devuelve los CAMPOS_PERMISOS normalizados (límites redondeados o None, divisas ordenadas). `diferencias(actual, nuevo)` devuelve la lista de `{campo, etiqueta, antes, despues}` de los campos que cambian.
- `crear_cliente`, `agregar_usuario` (error si la pareja ya existe), `editar_cliente(motivo obligatorio)`, `reasignar(motivo obligatorio; error si el ejecutivo no está activo o ya es el asignado)`, `eliminar_usuario` y `eliminar_cliente` (motivo obligatorio; solo para corregir errores de captura; no son bajas formales), `contratos_asignados(db, ejecutivo)` y `transferir_contratos(db, de, a, usuario, motivo)` (llama a `reasignar` por cada contrato).
- **Toda** escritura agrega renglones en `historial_padron` (campo, valor anterior, valor nuevo, origen, motivo). Valores numéricos con formato `1,000,000.00`. Si viene de una solicitud, el origen es su folio (`SOL-000012`).
- Cada escritura actualiza `ultima_actualizacion` y `actualizado_por` del contrato.
- `aplicar_solicitud(db, sol, usuario)`, llamada al pasar a "Listo para operar":
  - Alta nueva: si la pareja ya está en el padrón → error "El usuario X ya existe en el contrato Y del padrón. Rechaza la solicitud como duplicada." Si el contrato no existe, lo crea con los datos de la solicitud y ejecutivo asignado = solicitante. Luego agrega el usuario.
  - Cambio de permisos: actualiza en el contrato solo los permisos que cambian, con el motivo del cambio. Error si el contrato ya no existe.
- Consultas de cartera: `listar_cartera` (paginada, con `num_usuarios`), `cartera_completa` (contratos y usuarios, para exportar), `contadores_cartera` (contratos y usuarios del actor), `historial_de`. Filtros: región, segmento y grupo spot (igualdad); **zona por coincidencia parcial (LIKE)**; ejecutivo (solo admin); `q` busca en contrato, nombre, RFC o número de usuario. Un ejecutivo siempre queda filtrado a su cartera.

## 10. SOLICITUDES (`solicitudes.py`)

`registrar_alta(db, datos, actor, catalogo)`:
1. Normaliza. Si el contrato tiene 11 dígitos, consulta `estado_contrato`:
   - `ajeno` → error en contrato: "Este contrato pertenece a otra cartera. Contacta al administrador."
   - `alta_pendiente` → "Ya hay un alta pendiente para este contrato (SOL-…). Espera a que se atienda para agregar más usuarios." El folio solo se muestra si el actor es admin o dueño de esa solicitud.
   - `propio` → es un **usuario nuevo en un contrato existente**: empresa y permisos no se validan y se copian del padrón.
2. Valida con `validar_alta`. Ejecutivo: el de la sesión; si el actor es admin, el elegido en el formulario o, si no eligió, el asignado al contrato; si el contrato es nuevo y no eligió → "Selecciona el ejecutivo solicitante."
3. **Duplicado** si la pareja (contrato, número de usuario) está en el padrón o en otra Alta nueva Pendiente. Las Rechazadas y Canceladas **no** cuentan.
   - En el padrón → error en número de usuario: "Este usuario ya está dado de alta en este contrato. Si necesitas modificar sus permisos, usa el formulario de Cambio de permisos." En el contexto se devuelve `duplicado_contrato` para mostrar un botón a ese formulario con el contrato precargado.
   - Pendiente → "Ya existe una solicitud de alta pendiente para este contrato y usuario (SOL-…)."
4. Errores → `ErrorSolicitud(errores, contexto)`. Si todo es válido, dentro de `transaccion` vuelve a revisar duplicados e inserta la solicitud con estatus Pendiente, más un renglón de historial_estatus (anterior NULL → Pendiente, "Solicitud registrada").

`registrar_cambio(db, datos, actor, catalogo)`:
- Valida con `validar_cambio`. Según `estado_contrato`: `nuevo` → "Este contrato no existe en el padrón. Primero debe solicitarse el alta."; `alta_pendiente` → "El alta de este contrato aún está pendiente."; `ajeno` → "Este contrato no está en tu cartera."
- Si ya hay un Cambio de permisos Pendiente para el contrato → "Ya hay un cambio de permisos pendiente para este contrato (SOL-…)."
- Si los permisos solicitados son iguales a los vigentes → error general "Los permisos solicitados son iguales a los vigentes. No hay nada que cambiar." Pasar de un límite a vacío, o de vacío a un límite, **sí** es un cambio.
- Guarda los datos de empresa copiados del padrón, los permisos nuevos y `permisos_vigentes` (JSON con los permisos del padrón al solicitar). Usa `transaccion` y vuelve a revisar que no haya otro cambio pendiente.

Consultas: `obtener(db, id, ejecutivo=None)`, `obtener_para(db, id, actor)`, `historial`, `historial_de_varias`, `listar` (paginado, del más reciente al más antiguo), `listar_todas`, `contadores` (total y por estatus), `por_contrato` y `pendientes_de(db, ejecutivo)`. También `transferir_pendientes(db, de, a, correo_nuevo, usuario, motivo)` (sección 8.1). Filtros: estatus, tipo, región, segmento, estatus_correo, ejecutivo, desde, hasta y dia (fechas `AAAA-MM-DD` sobre la fecha de solicitud). `q` busca en contrato, número de usuario, nombre de cliente o folio. Columnas de filtro siempre de una lista fija; SQL siempre parametrizado.

## 11. ESTATUS (`estatus.py`)

Transiciones (en un solo diccionario):

| De | A | Quién | Regla |
|---|---|---|---|
| Pendiente | Listo para operar | admin | actualiza el padrón |
| Pendiente | Rechazada | admin | motivo obligatorio |
| Pendiente | Cancelada | solo el ejecutivo dueño | motivo opcional |

Los estatus finales no cambian ("La solicitud SOL-… ya fue atendida (estatus actual: X); no se puede cambiar."). No existe ninguna regla de KYC.

`cambiar_estatus(db, id, nuevo, actor, motivo)` hace todo en una sola transacción: lee la solicitud, valida la transición, aplica `aplicar_solicitud` si es Listo (un error del padrón cancela todo y no cambia el estatus), y actualiza estatus, fecha_atencion, atendido_por y motivo_resolucion. Si el nuevo estatus es Listo o Rechazada, también pone estatus_correo = Pendiente. El UPDATE lleva `WHERE estatus='Pendiente'`; si no afecta un renglón → "La solicitud cambió mientras la atendías. Recarga la página." Al final agrega el renglón de historial y, en la misma transacción, el aviso de la campana para el ejecutivo dueño (sección 8.2).

`atender(...)` llama a `cambiar_estatus` y **después** de confirmar envía el correo si estatus_correo es Pendiente. Devuelve `(solicitud, correo_ok)`. `atender_varias(ids)` marca Listo varias solicitudes y omite e informa las que fallen.

## 12. CORREO (`correo.py`)

- Al pasar a Listo para operar o Rechazada se envía un correo HTML al correo para notificaciones. Asunto: `[FX Onboarding] SOL-… · estatus · cliente`. El cuerpo (plantilla `correo/notificacion.html`, estilos en línea) incluye ID, tipo, estatus, cliente, contrato, usuario, grupo spot, multiaprobación, multiabono, divisas, límites ("—" si están vacíos), fecha de atención, atendido por y, si es rechazo, el motivo destacado.
- `MAIL_ENABLED=false`: el correo se guarda como `outbox/AAAAMMDD_HHMMSS_SOL-xxxxxx.html` con un comentario `<!-- Para: … | Asunto: … -->`. Con `true` se envía por SMTP (SSL, o STARTTLS si MAIL_USE_TLS, y login si hay usuario).
- `notificar(db, id)` captura cualquier excepción, la registra en el log y guarda estatus_correo `Enviado` o `Error`. Un fallo **nunca** revierte el estatus ni el padrón. El admin tiene "Reintentar envío".
- La carga inicial, la captura manual y la edición del padrón no envían correos.

## 13. RUTAS Y PANTALLAS

| Ruta | Método | Rol | Qué hace |
|---|---|---|---|
| `/` | GET | sesión | Admin → `/admin/solicitudes`; ejecutivo → `/mis-solicitudes` |
| `/login`, `/logout`, `/cambiar-contrasena` | | | sección 8 |
| `/mis-solicitudes` | GET | ejecutivo | Contadores (total, pendientes, listas, rechazadas, canceladas), accesos a los formularios y a Mi cartera, filtros (estatus, tipo, desde, hasta, búsqueda), tabla paginada: ID, fecha de envío, tipo, estatus, contrato, cliente, usuario, fecha de atención. El admin es redirigido a su panel. |
| `/solicitudes/<id>` | GET | dueño o admin | Detalle: datos de empresa; usuario y ejecutivo; permisos (en cambios, tabla "vigente vs. solicitado" con filas resaltadas y el motivo); comentarios; motivo de rechazo o cancelación; historial de estatus; antigüedad en días hábiles si está pendiente; enlace a la cartera si el contrato es visible. Admin: botones Listo, Rechazar (con motivo) y Reintentar envío. Dueño con solicitud pendiente: Cancelar (motivo opcional, con confirmación). |
| `/solicitudes/<id>/cancelar` | POST | dueño | 404 si no es suya |
| `/solicitudes/alta` | GET/POST | sesión | Formulario 1. `?contrato=` precarga. |
| `/solicitudes/cambio-permisos` | GET/POST | sesión | Formulario 2. `?contrato=` precarga. |
| `/api/contrato/<contrato>?para=alta\|cambio` | GET | sesión | JSON (sección 14) |
| `/admin/solicitudes` | GET | admin | Contadores, filtros (desde, hasta, tipo, estatus, ejecutivo, región, segmento, estatus de correo, búsqueda), tabla paginada con casilla para seleccionar pendientes, ID, fecha, **antigüedad en días hábiles (en rojo si supera el SLA)**, tipo, estatus, ejecutivo, contrato, cliente, usuario y estatus de correo; acciones Ver, Listo y Reintentar correo; botón de aprobación múltiple; botones "Exportar a Excel" (filtros actuales) y "Exportar solicitudes del día". |
| `/admin/solicitudes/<id>/estatus` | POST | admin | `nuevo` = Listo para operar o Rechazada, `motivo`, `volver` (ruta relativa segura) |
| `/admin/solicitudes/masivo` | POST | admin | `ids` múltiples |
| `/admin/solicitudes/<id>/reintentar-correo` | POST | admin | |
| `/admin/solicitudes/exportar` | GET | admin | `solicitudes_filtradas_AAAA-MM-DD.xlsx` |
| `/admin/solicitudes/exportar-dia` | GET | admin | `solicitudes_AAAA-MM-DD.xlsx` (solicitudes registradas hoy) |
| `/cartera/` | GET | sesión | "Mi cartera" (ejecutivo) o "Cartera de clientes" (admin). Contadores de contratos y usuarios. Filtros: región, segmento, **zona (texto, contiene)**, grupo spot, ejecutivo (admin), búsqueda. Tabla: contrato, nombre, RFC, región, segmento, zona, núm. de usuarios, grupo spot, divisas, ejecutivo, fecha de alta, última actualización. |
| `/cartera/exportar` | GET | sesión | `cartera_AAAA-MM-DD.xlsx`, hojas Contratos y Usuarios, solo lo visible |
| `/cartera/<contrato>` | GET | dueño o admin | Detalle: datos de empresa, permisos vigentes, usuarios (número, nombre, fecha de alta, origen), solicitudes relacionadas (el ejecutivo solo ve las suyas), historial del padrón. Botones "Agregar usuario" (alta precargada) y "Solicitar cambio de permisos". Admin además: Editar, Agregar usuario existente, Reasignar (ejecutivo + motivo), Eliminar contrato (motivo + confirmación) y Eliminar usuario por fila (motivo). |
| `/cartera/<contrato>/editar` | GET/POST | admin | Empresa y permisos + motivo obligatorio. Valida con `validar_cliente_padron`. |
| `/cartera/<contrato>/reasignar`, `/eliminar`, `/usuarios/<numero>/eliminar` | POST | admin | |
| `/admin/padron/plantilla` | GET | admin | `plantilla_carga_inicial.xlsx` |
| `/admin/padron/carga` | GET/POST | admin | Subir .xlsx → vista previa |
| `/admin/padron/carga/confirmar` | POST | admin | Respaldo + importación |
| `/admin/padron/carga/errores` | GET | admin | `reporte_errores_carga.xlsx` |
| `/admin/padron/agregar-cliente` | GET/POST | admin | Captura manual: contrato, ejecutivo asignado, fecha de alta (opcional), empresa, permisos y una tabla de usuarios (3 filas y botón "+ Agregar fila"). Al menos un usuario; sin repetidos; error si el contrato ya existe. Origen Captura manual. |
| `/admin/padron/agregar-usuario` | GET/POST | admin | Contrato, número y nombre; el contrato debe existir y la pareja no. Origen Captura manual. |
| `/admin/usuarios/…` | | admin | Pantalla Usuarios (sección 8.1) |
| `/notificaciones/…` | | sesión | Campana y pantalla Notificaciones, solo las propias (sección 8.2) |

### Formulario 1: Alta de cliente nuevo
Secciones (cada una un `fieldset`):
1. **Contrato**: contrato de banca electrónica (11 dígitos), con un aviso dinámico debajo.
2. **Datos de la empresa** (`id="seccion-empresa"`): nombre de cliente, RFC, región (lista), segmento (lista), **zona (texto libre)**.
3. **Datos del usuario**: número de usuario (8 dígitos), nombre completo.
4. **Datos del ejecutivo**: ejecutivo solicitante (solo lectura con el nombre de la sesión; el admin ve una lista con la opción vacía "El asignado al contrato") y correo para notificaciones (precargado con el correo del usuario de la sesión).
5. **Permisos y condiciones** (`id="seccion-permisos"`): grupo de parametrización spot (lista), multiaprobación (Sí/No), multiabono (Sí/No), **límite por operación (USD) y límite diario (USD), ambos opcionales con la ayuda "Opcional"**, y divisas autorizadas como casillas con los 8 pares.
6. **Comentarios** (opcional).

**No** hay sección de Cumplimiento/KYC ni campo de CLABE. Si la solicitud tiene errores, se vuelve a mostrar con lo capturado y el error junto a cada campo; si es duplicado, se muestra el aviso con el botón "Ir a Cambio de permisos".

### Formulario 2: Cambio de permisos
Contrato y aviso; un panel de solo lectura "Datos vigentes en el padrón" (empresa y permisos), oculto hasta consultar; un fieldset "Permisos solicitados" (`id="seccion-nuevos"`, deshabilitado hasta consultar un contrato válido) con los mismos campos de permisos; una tabla "Comparación: actual vs. solicitado"; el motivo del cambio (obligatorio); el ejecutivo (solo admin) y el correo para notificaciones.

### Comportamiento en el navegador (`static/js/app.js`, sin librerías)
- Campo contrato: solo dígitos, máximo 11. Al llegar a 11 consulta la API (con 250 ms de espera).
- Alta: estado `propio` → llena empresa y permisos con los datos del padrón y deshabilita `seccion-empresa` y `seccion-permisos` (los campos deshabilitados no se envían; el servidor los toma del padrón); `nuevo` → habilita y limpia lo que se había rellenado; cualquier otro estado → muestra el mensaje en rojo y deshabilita el botón de enviar.
- Cambio: si la API devuelve `cliente`, llena el panel vigente, habilita los permisos y los precarga con los vigentes (salvo en el primer reintento después de un POST con errores, para no borrar lo capturado). Recalcula la tabla de diferencias en cada cambio, comparando límites con 2 decimales y vacío contra vacío. Si no hay diferencias o el estado no es `propio`, deshabilita el envío.
- Formularios con `data-confirmar`: piden confirmación. Casilla "seleccionar todas" en el panel de admin. Botón "+ Agregar fila" en la captura manual.

### Diseño
Barra superior azul marino (`#1f4e79`) con navegación según el rol (admin: Solicitudes, Cartera de clientes, Carga inicial, Captura manual, Usuarios, Nueva alta, Cambio de permisos; ejecutivo: Mis solicitudes, Mi cartera, Nueva alta, Cambio de permisos), la campana de notificaciones con su globo de no leídas (sección 8.2), el nombre del usuario, el enlace "Contraseña" y "Salir". Tarjetas blancas, contadores con un borde de color, tablas con scroll horizontal en celular y etiquetas de estatus: **amarillo = Pendiente, verde = Listo para operar, rojo = Rechazada, gris = Cancelada**. Estatus de correo: verde Enviado, rojo Error, amarillo Pendiente. Mensajes flash en las categorías ok, error, aviso e info. Las macros de Jinja (`_macros.html`) cubren: badge, texto, área, selección, divisas (casillas) y paginación. Filtros Jinja: `fecha`, `fecha_corta`, `folio`, `monto`, `valor_input` y `mostrar` ("—" si está vacío; montos con formato).

## 14. API JSON `/api/contrato/<contrato>?para=alta|cambio`

- Contrato no válido → `{"estado": "invalido", "mensaje": …}`.
- `ajeno` → solo `{"estado": "ajeno", "mensaje": …}`. **Nunca** se incluyen datos del cliente.
- `alta_pendiente` → mensaje (en alta, el folio solo si es suyo o si es admin).
- `nuevo` → alta: "Contrato nuevo: captura todos los datos."; cambio: el mensaje de "Primero debe solicitarse el alta".
- `propio` → `{"estado": "propio", "mensaje": …, "cliente": {contrato, campos de empresa, campos de permisos, ejecutivo_asignado}}`. En alta, el mensaje explica que es un usuario nuevo en un contrato existente. En cambio, si ya hay un cambio pendiente: `estado = "cambio_pendiente"`, con `cliente` y el mensaje con el folio.

## 15. CARGA INICIAL (`carga.py`)

**Plantilla** (`generar_plantilla(catalogo, ejecutivos)`):
- Hoja "Instrucciones" con los pasos y una fila de ejemplo (el ejemplo **no** va en las otras hojas, para que nunca se importe).
- Hoja "Clientes" con estas columnas, en este orden: Contrato, Nombre de cliente, RFC, Región, Segmento, Zona, Grupo spot, Multiaprobación, Multiabono, Divisas autorizadas, Límite por operación, Límite diario, Ejecutivo asignado, Fecha de alta en plataforma.
- Hoja "Usuarios": Contrato, Número de usuario, Nombre completo.
- Hoja oculta "Listas" con las listas para la validación de datos de Región, Segmento, Grupo spot, Sí/No (multiaprobación y multiabono) y Ejecutivo asignado (filas 2 a 1000; `formula1` como `Listas!$A$2:$A$N`, sin "="). La zona y las divisas no tienen lista desplegable.
- Contrato y número de usuario con formato Texto (`@`) en las filas 2 a 1000. Encabezados en negrita, blanco sobre azul.

**Análisis** (`analizar(db, ruta, catalogo)` → objeto `Resultado` con `clientes`, `usuarios`, `errores` (hoja, fila, campo, mensaje) y `omitidos` (hoja, fila, motivo)):
- Lee con openpyxl `read_only=True, data_only=True`. Si el archivo no se puede abrir → error "No se pudo leer el archivo…". Si falta una hoja → "Falta la hoja 'X'.". Si faltan columnas → "Faltan columnas: …". Los encabezados se comparan sin acentos ni mayúsculas; la fecha de alta es opcional. Las filas vacías se ignoran.
- Las celdas se convierten a texto (números enteros sin ".0"; fechas en DD/MM/AAAA). Si contrato o número de usuario llega como celda **numérica** con menos dígitos de los esperados → mensaje que explica que Excel quitó los ceros a la izquierda y que hay que dar formato Texto a la columna.
- Clientes: `validar_cliente_padron`; ejecutivo asignado obligatorio y activo ("El ejecutivo 'x' no existe o no está activo."); fecha opcional (DD/MM/AAAA, AAAA-MM-DD o DD-MM-AAAA); contrato repetido en el archivo → error en la segunda aparición; contrato ya en el padrón → omitido.
- Usuarios: `validar_usuario_padron`; pareja repetida en el archivo → error; contrato con errores en Clientes → error; contrato que no está ni en Clientes ni en el padrón → error; pareja ya en el padrón → omitido. Un usuario nuevo sobre un contrato que ya está en el padrón es válido.
- Un contrato nuevo sin ningún usuario válido pasa a error ("El contrato no tiene usuarios válidos en la hoja Usuarios.").
- Los límites pueden venir vacíos.

**Flujo web:** el archivo subido se guarda en `UPLOAD_DIR/<token>.xlsx` y el token va en la sesión. La vista previa muestra contadores (contratos válidos, usuarios válidos, filas con error, omitidas), las tablas de errores, omitidas y lo que se importará, el botón "Descargar reporte de errores" y el botón "Confirmar e importar N fila(s) válidas". Al confirmar: se vuelve a analizar contra el padrón actual, se hace un respaldo "antes_carga", se importan **solo las filas válidas** en una transacción (origen Carga inicial, sin correos), se registra en `cargas` y en el log, y se borra el archivo temporal. La página muestra también las cargas recientes.

## 16. EXPORTACIONES (`exportar.py`)

- Encabezados en negrita, blanco sobre azul `1F4E79`, autofiltro, primera fila fija y ancho de columna automático (máx. 50). Contrato y número de usuario como texto (`@`). Fechas en DD/MM/AAAA HH:MM.
- **Inyección de fórmulas:** al exportar, todo texto que empiece con `=`, `+`, `-`, `@`, tabulador o retorno de carro se antepone con `'`. **No** se alteran los datos guardados.
- Solicitudes: hoja "Solicitudes" (ID de solicitud, fecha y hora, tipo, estatus, contrato, nombre de cliente, RFC, región, segmento, zona, número de usuario, nombre completo, ejecutivo solicitante, correo para notificaciones, grupo spot, multiaprobación, multiabono, divisas, límite por operación, límite diario, comentarios, motivo del cambio, motivo de rechazo/cancelación, fecha de atención, atendido por, estatus de correo) y hoja "Historial de estatus".
- Cartera: hoja "Contratos" (contrato, nombre, RFC, región, segmento, zona, núm. de usuarios, grupo spot, multiaprobación, multiabono, divisas, límites, ejecutivo asignado, origen, fecha de alta, última actualización) y hoja "Usuarios" (contrato, nombre de cliente, número de usuario, nombre completo, fecha de alta, origen).
- Reporte de errores de carga: hojas "Errores" y "Omitidas".

## 17. RESPALDOS, LOGS Y ARRANQUE

- `respaldo.respaldar(etiqueta)`: copia consistente con `sqlite3.Connection.backup` a `backups/fx_onboarding_<etiqueta>_AAAAMMDD_HHMMSS.db`, conservando los últimos BACKUP_KEEP por etiqueta. `respaldo_diario()` corre en `before_request` y al arrancar; crea el respaldo del día una sola vez y nunca rompe la petición.
- Log `logs/app.log` (RotatingFileHandler 2 MB × 5, UTF-8, más consola fuera de tests): inicios de sesión, intentos fallidos, bloqueos, solicitudes registradas, cambios de estatus, cambios al padrón, cargas, correos, errores y migraciones.
- `run.py`: `create_app()`, respaldo del día, mensaje con la URL y `waitress.serve(app, host, port, threads=8)`.
- `manage.py`:
  - `init [--sin-ejemplos] [--forzar]`: crea la base. Sin bandera carga los datos de ejemplo; `--sin-ejemplos` solo crea `admin`; `--forzar` borra la base, incluidos `-wal` y `-shm`. Si la base existe y no se pasa `--forzar`, avisa y no hace nada.
  - `crear-usuario USUARIO "Nombre" correo --rol ejecutivo|admin --contrasena X` (registra en historial_usuarios como "consola").
  - `restablecer-contrasena USUARIO X`: pone una contraseña temporal, obliga a cambiarla y quita el bloqueo (también se registra).
  - El docstring explica que en el día a día se usa la pantalla Usuarios y que estos comandos sirven para el primer administrador o para recuperar el acceso.

## 18. DATOS DE EJEMPLO (`datos_ejemplo.py`, cargados con `manage.py init`)

- Usuarios con contraseña temporal: `admin` / `Admin2026!` (Administrador FX), `mperez` / `Ejecutivo2026!` (María Pérez), `jgarcia` / `Ejecutivo2026!` (Juan García). Correos `@ejemplo.com`. Su alta queda en historial_usuarios con `realizado_por = "init"`.
- Padrón con 8 contratos de 11 dígitos, origen Carga inicial y fecha de alta 2023-06-01, repartidos entre los dos ejecutivos. Uno tiene 3 usuarios; el número de usuario 70000001 aparece en dos contratos distintos; uno no tiene límites. Usa zonas de texto libre (por ejemplo "Monterrey Centro", "Saltillo", "CDMX Polanco"), RFC válidos y pares de divisas del catálogo.
- 15 solicitudes en todos los estatus, con fechas movidas hacia atrás para que se vea la antigüedad: altas de contrato nuevo aprobadas (crean el cliente), un usuario nuevo en contrato existente aprobado, un cambio de permisos aplicado, altas pendientes (una con más días que el SLA y otra sin límites), un alta rechazada con motivo, una cancelada por su ejecutivo, un cambio pendiente, un cambio rechazado, un usuario con número ya registrado en otro contrato y una solicitud capturada por el admin a nombre de un ejecutivo. Si el correo está desactivado, las aprobaciones y rechazos generan sus correos en `outbox/`. Como se registran con las funciones normales, también generan sus notificaciones (la función que mueve la fecha de la solicitud mueve también la de su aviso "Nueva solicitud").
- Archivo `datos_ejemplo/carga_inicial_ejemplo.xlsx`, generado con la plantilla, con filas válidas y errores intencionales: RFC inválido, región fuera del catálogo, divisa "USD" (no es par), ejecutivo inexistente, contrato que ya está en el padrón (omitido), contrato numérico al que Excel le quitó el cero, usuario repetido, contrato inexistente, número de usuario de 7 dígitos y un usuario nuevo en un contrato del padrón.

## 19. PRUEBAS (pytest; `pytest.ini` con `pythonpath = .` y `testpaths = tests`)

`conftest.py`: fixture `app` con base temporal (`tmp_path`), `WTF_CSRF_ENABLED=False`, `MAIL_ENABLED=False`, `RESPALDO_AUTOMATICO=False`, carpetas temporales y los usuarios `admin`, `ej1` y `ej2` con `debe_cambiar=0`. Fixtures `db` (dentro de app_context), `cat` y `client`. Helpers `datos_alta(**cambios)`, `datos_cambio(**cambios)` (por defecto iguales a los del cliente de prueba), `cliente_padron(db, contrato, ejecutivo, usuarios=(...), **cambios)` y `login(client, usuario)`.

Casos mínimos:
- **Validaciones:** contrato, número de usuario y RFC (moral, física, fecha inválida); obligatorios exactos (los límites y los comentarios no lo son); límites opcionales (vacío se guarda como None; uno sin el otro es válido); diario < operación; límites negativos, cero o texto; zona libre, obligatoria y máx. 100; valores fuera de catálogo (incluida una divisa que no es par); correo; normalización; alta en contrato existente sin datos de empresa; el cambio exige motivo; contraseña.
- **Duplicados:** en el padrón; usuario nuevo en contrato existente (copia los datos del padrón); mismo usuario en otro contrato (permitido); alta pendiente que bloquea el contrato; duplicado pendiente; Rechazadas y Canceladas no cuentan; contrato de otra cartera; admin captura a nombre del asignado; admin debe elegir ejecutivo en un contrato nuevo.
- **Padrón:** Listo crea el cliente con su usuario y su historial; Listo en contrato existente solo agrega el usuario; el cambio actualiza el padrón y registra exactamente los campos que cambian; Rechazo o Cancelación no tocan el padrón; alta sin límites llega al padrón sin límites; un cambio agrega o quita límites; rollback si falla el padrón (el estatus sigue Pendiente); `permisos_vigentes` guardado; "sin cambios" bloqueado; cambio pendiente bloquea otro; contrato inexistente o con alta pendiente; autocompletado vía API; edición, reasignación y eliminación quedan en el historial con motivo; el mantenimiento exige motivo.
- **Estatus:** el ejecutivo no puede aprobar; el admin no puede cancelar; otro ejecutivo no puede cancelar; el dueño cancela sin motivo; el rechazo exige motivo; los estatus finales no cambian; el historial registra cada paso; un fallo de correo (con `monkeypatch` sobre `correo.enviar`) no revierte nada y el reintento funciona; outbox; la aprobación masiva omite las que no proceden.
- **Aislamiento (HTTP):** login requerido (302 o 401 en la API); "Mis solicitudes" y la búsqueda solo muestran lo propio; detalle y cancelación ajenos → 404; rutas de admin → 403 (incluido el POST de estatus); la cartera, su búsqueda, su detalle (404) y su exportación solo incluyen lo propio; la API no devuelve datos de contratos ajenos ni el folio de altas ajenas; un cambio sobre un contrato ajeno no se registra; alta por formulario (302); el admin ve todo; bloqueo por intentos fallidos; la contraseña temporal obliga a cambiarla.
- **Carga:** carga válida (divisas normalizadas, zona libre, fecha); ceros perdidos; catálogo y ejecutivo inexistente; plantilla sin columnas eliminadas y sin lista en la zona; divisa no válida; carga sin límites; contrato repetido; contrato del padrón omitido con usuarios nuevos aceptados; usuarios inválidos; contrato sin usuarios; mismo usuario en dos contratos; solo se importan filas válidas; hoja faltante; archivo que no es Excel; flujo web completo.
- **Exportar:** `sanitizar` (parametrizado); conserva ceros y neutraliza fórmulas sin alterar los datos guardados; respeta filtros; nombre del archivo del día.
- **Migraciones:** una base con `clientes.limite_*` NOT NULL se migra sin perder datos, conserva la llave foránea con cascada y recrea los índices; correr el esquema dos veces no vuelve a migrar.
- **Usuarios:** solo admin (403 al ejecutivo en GET y POST); las pantallas se muestran (404 si el usuario no existe); alta por pantalla (correo en minúsculas, `debe_cambiar=1`, historial) y el nuevo usuario debe cambiar la contraseña al entrar; validación parametrizada de la alta (usuario repetido, formato, corto, contraseña corta o sin números, correo, nombre vacío, rol inválido); con error no se devuelve la contraseña; editar nombre, correo y rol (detalle en el historial); no puede cambiar su propio rol; un ejecutivo con cartera no cambia de rol; siempre queda un administrador; no puede desactivarse a sí mismo; desactivar exige motivo; desactivar con cartera exige transferir; desactivar transfiere contratos y pendientes (ejecutivo, correo, historiales, deja de aparecer en las listas); una transferencia inválida no cambia nada; transferir cartera sin desactivar; un usuario desactivado pierde la sesión abierta y no puede entrar; reactivar; restablecer desbloquea y obliga a cambiar; desbloquear sin cambiar la contraseña.
- **Notificaciones:** un alta nueva avisa a cada admin activo (mensaje con folio, contrato y nombre del ejecutivo) y a ningún ejecutivo; un cambio de permisos también avisa; el admin que captura a nombre de un ejecutivo no se avisa a sí mismo y el mensaje dice "capturada por … a nombre de …"; un admin inactivo no recibe; una solicitud con errores de validación no avisa; Listo y Rechazada (parametrizado) avisan al ejecutivo dueño y a nadie más, y el rechazo incluye el motivo; cancelar la propia no avisa; la aprobación múltiple avisa por cada una; un cambio de estatus fallido no deja aviso; contador, marcar una y marcar todas; no se puede marcar una ajena; `texto_contador` ("99+"); la campana muestra el globo solo con no leídas; la pantalla lista solo las propias; abrir marca leída y redirige a la solicitud; abrir o marcar avisos ajenos da 404 y "marcar todas" no los toca; marcar todas conserva la pestaña; requiere sesión. Para cambiar de usuario en el cliente de pruebas, primero `POST /logout`.

## 20. README.md (en español)

Debe incluir: descripción; instalación (venv, `pip install -r requirements.txt`, copiar `.env.example` a `.env` y cambiar `SECRET_KEY`); primer arranque (`python manage.py init`, `python run.py`, tabla de usuarios de ejemplo); uso en producción (`init --sin-ejemplos`, luego dar de alta usuarios desde Admin › Usuarios; `crear-usuario` y `restablecer-contrasena` como respaldo); acceso desde la red interna (`HOST=0.0.0.0`, firewall); correo; cómo funciona (roles, pantalla Usuarios y sus reglas, notificaciones, padrón, reglas principales); catálogos; migraciones; respaldos y logs; datos de ejemplo; pruebas; estructura; fuera de alcance.

## 21. FUERA DE ALCANCE

Bajas formales de clientes (contratos o sus usuarios) en la plataforma de FX; CLABE / cuenta de liquidación; Estatus KYC/PLD.

## 22. CRITERIOS DE ACEPTACIÓN

- `pip install -r requirements.txt`, `python manage.py init` y `python run.py` funcionan sin errores; `pytest` pasa completo.
- Un ejecutivo nunca ve ni modifica datos de otro ejecutivo, por ninguna ruta, API ni exportación.
- El administrador da de alta, edita, desactiva y reactiva usuarios desde la pantalla Usuarios; nunca queda la app sin administrador activo ni clientes asignados a un ejecutivo inactivo.
- Aprobar una solicitud actualiza el padrón en la misma transacción; un fallo de correo no revierte nada.
- La campana avisa al ejecutivo de cada cambio de estatus de sus solicitudes y a los administradores de cada solicitud nueva; nadie ve las notificaciones de otro.
- Zona es texto libre; límites opcionales; divisas = los 8 pares; no existen CLABE ni KYC en ninguna pantalla, tabla, exportación, correo ni plantilla.
- Todo el texto visible está en español.
