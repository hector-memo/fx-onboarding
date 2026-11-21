# FX Onboarding

Aplicación web para centralizar las solicitudes de **alta de clientes** y **cambios de permisos** de la plataforma de FX (mesa de cambios), con un **padrón maestro de clientes** y trazabilidad completa.

- Python 3.11+ · Flask · SQLite (un solo archivo, sin servidor) · openpyxl · waitress
- Interfaz en español, responsiva, sin dependencias externas en el navegador.

## Instalación

```bash
cd onbording_app
python -m venv .venv
# Windows:  .venv\Scripts\activate      macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env        # en macOS/Linux: cp .env.example .env
```

Edita `.env` y cambia como mínimo `SECRET_KEY` (texto largo y aleatorio).

## Primer arranque

```bash
python manage.py init        # crea data/fx_onboarding.db con datos de ejemplo
python run.py                # http://127.0.0.1:8000
```

Usuarios de ejemplo (contraseñas **temporales**: la app pide cambiarlas al entrar):

| Usuario | Rol | Contraseña temporal |
|---|---|---|
| `admin` | Administrador | `Admin2026!` |
| `mperez` | Ejecutivo | `Ejecutivo2026!` |
| `jgarcia` | Ejecutivo | `Ejecutivo2026!` |

Para producción usa `python manage.py init --sin-ejemplos` (solo crea `admin`) y da de alta a los demás desde **Admin › Usuarios** (ver más abajo).

Desde la terminal también se puede, útil para el primer administrador o si ningún administrador puede entrar:

```bash
python manage.py crear-usuario lrodriguez "Laura Rodríguez" lrodriguez@tuempresa.com --rol ejecutivo --contrasena Temporal2026!
python manage.py restablecer-contrasena lrodriguez Temporal2026!   # también desbloquea la cuenta
```

`python manage.py init --forzar` borra la base y la vuelve a crear.

## Acceso desde la red interna

En `.env` pon `HOST=0.0.0.0` y el puerto deseado. Los ejecutivos entran con `http://<IP-del-equipo>:8000`. Puede ser necesario abrir el puerto en el firewall de Windows; consúltalo con TI. La app debe correr en un equipo o servidor siempre encendido.

## Correo

- `MAIL_ENABLED=false` (por defecto): los correos se guardan como `.html` en `outbox/`, útil para pruebas.
- `MAIL_ENABLED=true`: usa `MAIL_HOST`, `MAIL_PORT`, `MAIL_USE_TLS`/`MAIL_USE_SSL`, `MAIL_USERNAME`, `MAIL_PASSWORD` y `MAIL_FROM`.
- Se notifica al pasar a **Listo para operar** o **Rechazada**. Si el envío falla, el estatus y el padrón **no** se revierten: la solicitud queda con estatus de correo «Error», se registra en `logs/app.log` y el admin tiene el botón **Reintentar envío**.

## Cómo funciona

### Roles
- **Ejecutivo**: ve en *Mi cartera* solo los contratos que tiene asignados, envía altas y cambios de permisos sobre contratos nuevos o de su cartera, consulta *Mis solicitudes* y puede cancelar las suyas mientras estén Pendientes. La campana le avisa cada vez que cambia el estatus de una de ellas.
- **Administrador**: ve todo, aprueba o rechaza, carga y corrige el padrón, reasigna clientes, exporta, administra los usuarios, recibe un aviso por cada solicitud nueva y puede capturar solicitudes a nombre de un ejecutivo.

### Usuarios (Admin › Usuarios)
- **Lista** con filtros por rol, estado y búsqueda, más los contratos y pendientes de cada ejecutivo.
- **Nuevo usuario**: usuario (3 a 30 caracteres: minúsculas, números, `.`, `-`, `_`; no se puede cambiar después), nombre, correo, rol y contraseña temporal. Al entrar por primera vez se le pide cambiarla.
- **Editar** nombre, correo y rol. **Restablecer contraseña** (temporal, también desbloquea) y **Desbloquear** sin cambiarla.
- **Transferir cartera**: pasa todos los contratos y solicitudes pendientes de un ejecutivo a otro. Cada contrato queda en el historial del padrón y cada solicitud en su historial de estatus; las pendientes toman el correo del nuevo ejecutivo.
- **Desactivar / Reactivar**: un usuario inactivo no puede entrar (si tenía sesión abierta, se cierra) y deja de aparecer en las listas de ejecutivos. Su historial y sus solicitudes se conservan.
- Reglas: nadie puede desactivarse ni cambiarse el rol a sí mismo; siempre queda al menos un administrador activo; un ejecutivo con contratos o pendientes no se desactiva ni cambia de rol sin transferir su cartera.
- Cada acción queda en el **historial del usuario** (fecha, acción, quién la hizo, detalle) y en `logs/app.log`.

### Notificaciones (campana)
La campana de la barra superior lleva a la pantalla **Notificaciones** y muestra un globo rojo con las que no has leído.
- **Ejecutivo**: recibe un aviso cada vez que cambia el estatus de una de sus solicitudes (Listo para operar o Rechazada, con el motivo). Si él mismo cancela la suya, no se genera aviso.
- **Administradores**: cada solicitud nueva (alta o cambio de permisos) genera un aviso para cada administrador activo, salvo para quien la capturó.
- En la pantalla: pestañas *Todas* y *Sin leer*, **Ver solicitud** (la marca como leída y abre la solicitud), **Marcar como leída** y **Marcar todas como leídas**. Cada quien ve solo sus avisos.
- Los avisos se crean en la misma transacción que la solicitud o el cambio de estatus: si algo falla, no queda un aviso falso.
- El contador se actualiza al abrir cualquier página. No se refresca solo para no mantener abiertas las sesiones inactivas.
- Son avisos dentro de la app; los correos siguen igual. Las solicitudes anteriores a esta versión no generan avisos.

### Padrón de clientes
Es la fuente de verdad de quién opera en la plataforma. Datos de empresa y permisos son **a nivel contrato**; un contrato tiene uno o varios usuarios, y un mismo número de usuario puede estar en varios contratos.

Se alimenta de:
1. **Carga inicial** (*Admin › Carga inicial*): descarga la plantilla, llénala, súbela, revisa la vista previa con los errores por hoja, fila y campo, y confirma. Solo se importan las filas válidas; los contratos y usuarios que ya existen se omiten. Antes de importar se hace un respaldo.
2. **Captura manual** (*Admin › Captura manual*): un cliente existente con sus usuarios, o un usuario más en un contrato del padrón.
3. **Solicitudes aprobadas**: al marcar **Listo para operar**, un alta de contrato nuevo crea el cliente (asignado al ejecutivo solicitante), un alta sobre un contrato existente agrega el usuario y un cambio de permisos actualiza el contrato. Todo ocurre en la misma transacción que el cambio de estatus.

Todo cambio al padrón queda en el historial del contrato (campo, valor anterior, valor nuevo, origen, motivo).

### Reglas principales
- **Duplicado**: la pareja (contrato, número de usuario) ya está en el padrón o en otra alta Pendiente. Las Rechazadas y Canceladas no cuentan.
- **Un alta sobre un contrato de otra cartera** se bloquea sin mostrar datos del cliente.
- **Un contrato con un alta Pendiente** no acepta más altas hasta que se atienda.
- **Cambio de permisos**: solo sobre contratos del padrón y de la cartera del ejecutivo. Se bloquea si ya hay otro cambio pendiente o si no cambia nada.
- **Zona**: texto libre (máx. 100 caracteres). En la cartera se filtra por coincidencia parcial.
- **Límites por operación y diario (USD)**: opcionales. Si se capturan deben ser mayores a 0 y, con ambos, el diario ≥ al de operación. Un cambio de permisos puede agregarlos o quitarlos.
- **Divisas autorizadas**: uno o varios pares del catálogo (USDMXN, EURMXN, GBPMXN, CADMXN, CHFMXN, EURUSD, GBPUSD, USDCAD).
- Transiciones: Pendiente → Listo para operar o Rechazada (admin; el rechazo exige motivo) y Pendiente → Cancelada (solo el ejecutivo dueño). Los estatus finales no cambian.

### Catálogos
`catalogos.json` contiene regiones, segmentos, grupos spot y divisas (pares). La zona no tiene catálogo. Reemplaza los valores de ejemplo por los reales; los cambios se aplican sin reiniciar.

### Cambios de estructura (migraciones)
Al arrancar, la app ajusta automáticamente bases creadas con versiones anteriores, sin perder datos (ver `migrar()` en `app/db.py`). Antes de actualizar en producción, guarda una copia de `data/fx_onboarding.db`.

### Respaldos y logs
- Respaldo diario automático del archivo SQLite en `backups/` (se conservan los últimos `BACKUP_KEEP`) y otro antes de cada carga masiva.
- `logs/app.log`: inicios de sesión, cambios de estatus, cambios al padrón, cargas y errores de correo.

## Datos de ejemplo
`manage.py init` carga 8 contratos en el padrón (uno con varios usuarios y un número de usuario repetido en dos contratos), unas 15 solicitudes en todos los estatus y genera `datos_ejemplo/carga_inicial_ejemplo.xlsx`, con filas válidas y errores intencionales para probar la vista previa de la carga inicial.

## Pruebas

```bash
pytest
```

Cubren validaciones, duplicados, autocompletado desde el padrón, transiciones de estatus, actualización del padrón y su rollback, fallo de correo, carga inicial, mantenimiento del padrón, aislamiento entre ejecutivos (solicitudes, cartera, API y exportaciones), acceso a rutas de admin, sanitización de exportaciones, migraciones, la pantalla Usuarios (alta, edición, desactivación con transferencia de cartera, reglas de seguridad) y las notificaciones (quién recibe cada aviso, aislamiento y marcado como leídas).

## Estructura

```
onbording_app/
├── run.py                 arranque con waitress
├── manage.py              init, crear-usuario, restablecer-contrasena
├── config.py              configuración (lee .env)
├── catalogos.json         listas editables
├── app/
│   ├── __init__.py        fábrica de la app, filtros, manejo de errores
│   ├── schema.sql         tablas e índices
│   ├── db.py              conexión y transacciones (BEGIN IMMEDIATE)
│   ├── validaciones.py    TODAS las reglas de validación
│   ├── estatus.py         transiciones de estatus (en un solo lugar)
│   ├── padron.py          TODAS las escrituras al padrón + historial
│   ├── solicitudes.py     registro, consultas y duplicados
│   ├── carga.py           plantilla, análisis e importación de Excel
│   ├── exportar.py        exportaciones .xlsx y sanitización
│   ├── correo.py          notificaciones SMTP / outbox
│   ├── respaldo.py        respaldos de SQLite
│   ├── auth.py            login, bloqueo, cambio de contraseña, roles
│   ├── datos_ejemplo.py   datos para probar el flujo
│   ├── usuarios.py        usuarios de la app y reglas de la pantalla Usuarios
│   ├── notificaciones.py  campana de notificaciones
│   ├── rutas/             blueprints (ejecutivo, formularios, api, admin, cartera, padron_admin, usuarios_admin, notificaciones)
│   ├── templates/         vistas Jinja
│   └── static/            css y js
└── tests/                 pytest
```

## Fuera de alcance por ahora
Bajas formales de clientes (contratos o sus usuarios) en la plataforma de FX.
