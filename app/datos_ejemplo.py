"""Datos de ejemplo para probar todo el flujo (se cargan con `python manage.py init`)."""
from datetime import timedelta
from pathlib import Path

from flask import current_app

from . import carga, estatus, padron
from . import solicitudes as S
from .catalogos import cargar as cargar_catalogos
from .constantes import CANCELADA, LISTO, ORIGEN_CARGA, RECHAZADA, ROL_ADMIN, ROL_EJECUTIVO
from .db import transaccion
from .usuarios import ACCION_ALTA, crear_usuario, registrar_historial
from .utils import FMT_DB, ahora

USUARIOS = [
    ("admin", "Administrador FX", "admin@ejemplo.com", ROL_ADMIN, "Admin2026!"),
    ("mperez", "María Pérez", "mperez@ejemplo.com", ROL_EJECUTIVO, "Ejecutivo2026!"),
    ("jgarcia", "Juan García", "jgarcia@ejemplo.com", ROL_EJECUTIVO, "Ejecutivo2026!"),
]

# contrato, nombre, rfc, región, segmento, zona (texto libre), grupo spot, multiaprobación, multiabono,
# divisas, límite por operación, límite diario, ejecutivo, [(número de usuario, nombre)]
PADRON = [
    ("40112345678", "Comercializadora del Mar SA de CV", "CMA990215AB3", "Norte", "Corporativo", "Monterrey Centro",
     "Spot Premium", "Sí", "Sí", "EURMXN,USDMXN", 500000, 2000000, "mperez",
     [("70000001", "Laura Ríos Méndez"), ("70000002", "Carlos Méndez Soto"), ("70000003", "Ana Torres Vega")]),
    ("40112345679", "Distribuidora Industrial del Norte SA", "DIN050630KT2", "Noreste", "Empresarial", "Saltillo",
     "Spot Estándar", "No", "Sí", "USDMXN", 250000, 1000000, "mperez",
     [("70000004", "Jorge Salinas Ruiz")]),
    # Mismo número de usuario (70000001) que en el primer contrato: está permitido.
    ("40198765432", "Transportes y Logística Occidente SA de CV", "TLO120101HJ7", "Occidente", "Empresarial",
     "Guadalajara Sur", "Spot Básico", "No", "No", "USDMXN", 100000, 300000, "mperez",
     [("70000001", "Laura Ríos Méndez")]),
    ("40155500011", "Ferretera El Bajío SA de CV", "FER830412PP1", "Bajío", "PyME", "León",
     "Spot Básico", "No", "No", "USDMXN", 50000, 150000, "mperez",
     [("70000005", "Rosa Hernández Lara")]),
    ("40233311122", "Gasolineras del Sur SA de CV", "GAS101010QW4", "Sur", "Empresarial", "Mérida",
     "Spot Estándar", "Sí", "No", "USDCAD,USDMXN", 300000, 900000, "jgarcia",
     [("70000006", "Miguel Ángel Cruz"), ("70000007", "Patricia Luna Ortiz")]),
    ("40233311123", "Importaciones del Centro SA de CV", "IMP070707ZX9", "Centro", "Corporativo", "CDMX Polanco",
     "Spot Preferente", "Sí", "Sí", "EURMXN,EURUSD,GBPMXN,USDMXN", 1000000, 5000000, "jgarcia",
     [("70000008", "Fernando Ibarra Gil")]),
    ("40244422233", "Logística Integral Metropolitana SA", "LOG150320MN5", "Centro", "Institucional", "CDMX Santa Fe",
     "Spot Premium", "Sí", "Sí", "CHFMXN,EURMXN,USDMXN", 2000000, 8000000, "jgarcia",
     [("70000009", "Sofía Delgado Paz")]),
    # Sin límites capturados (son opcionales).
    ("40255533344", "Servicios Agrícolas del Norte SC", "SER991231TT0", "Norte", "PyME", "Chihuahua",
     "Spot Básico", "No", "No", "USDMXN", None, None, "jgarcia",
     [("70000010", "Raúl Castillo Núñez")]),
]


def _actor(db, usuario):
    return db.execute("SELECT * FROM usuarios WHERE usuario = ?", (usuario,)).fetchone()


def _alta(contrato, nombre, rfc, region, segmento, zona, numero, persona, correo,
          grupo="Spot Estándar", divisas=("USDMXN",), limites=(200000, 800000), **extra):
    datos = {
        "contrato": contrato, "nombre_cliente": nombre, "rfc": rfc, "region": region, "segmento": segmento,
        "zona": zona, "numero_usuario": numero, "nombre_completo": persona, "correo_notificaciones": correo,
        "grupo_spot": grupo, "multiaprobacion": "No", "multiabono": "No", "divisas": list(divisas),
        "limite_operacion": str(limites[0]) if limites else "", "limite_diario": str(limites[1]) if limites else "",
        "comentarios": "",
    }
    datos.update(extra)
    return datos


def _usuario_nuevo(contrato, numero, persona, correo, **extra):
    datos = {"contrato": contrato, "numero_usuario": numero, "nombre_completo": persona,
             "correo_notificaciones": correo, "comentarios": ""}
    datos.update(extra)
    return datos


def _cambio(db, contrato, correo, motivo, **cambios):
    cliente = padron.obtener_cliente(db, contrato)
    datos = {c: cliente[c] for c in ("grupo_spot", "multiaprobacion", "multiabono", "divisas",
                                     "limite_operacion", "limite_diario")}
    datos.update(contrato=contrato, correo_notificaciones=correo, motivo_cambio=motivo)
    datos.update(cambios)
    return datos


def _fechar(db, sid, dias_atras):
    """Mueve la fecha de una solicitud hacia atrás para que el panel muestre antigüedad."""
    fecha = (ahora() - timedelta(days=dias_atras)).strftime(FMT_DB)
    db.execute("UPDATE solicitudes SET fecha_solicitud = ? WHERE id = ?", (fecha, sid))
    db.execute(
        "UPDATE historial_estatus SET fecha = ? WHERE solicitud_id = ? AND estatus_anterior IS NULL", (fecha, sid)
    )
    db.execute("UPDATE notificaciones SET fecha = ? WHERE solicitud_id = ? AND tipo = 'Nueva solicitud'", (fecha, sid))


def cargar_usuarios(db, solo_admin=False):
    for usuario, nombre, correo, rol, contrasena in USUARIOS:
        if solo_admin and rol != ROL_ADMIN:
            continue
        crear_usuario(db, usuario, nombre, correo, rol, contrasena, debe_cambiar=True)
        registrar_historial(db, usuario, "init", ACCION_ALTA, f"Rol: {rol} (datos de ejemplo)")


def cargar_padron(db):
    for (contrato, nombre, rfc, region, segmento, zona, grupo, multiap, multiab, divisas, lim_op, lim_dia,
         ejecutivo, usuarios) in PADRON:
        with transaccion(db):
            padron.crear_cliente(db, {
                "contrato": contrato, "nombre_cliente": nombre, "rfc": rfc, "region": region,
                "segmento": segmento, "zona": zona, "grupo_spot": grupo, "multiaprobacion": multiap,
                "multiabono": multiab, "divisas": divisas,
                "limite_operacion": float(lim_op) if lim_op is not None else None,
                "limite_diario": float(lim_dia) if lim_dia is not None else None, "ejecutivo_asignado": ejecutivo,
            }, "admin", ORIGEN_CARGA, fecha_alta="2023-06-01 00:00:00")
            for numero, persona in usuarios:
                padron.agregar_usuario(db, contrato, numero, persona, "admin", ORIGEN_CARGA,
                                       fecha_alta="2023-06-01 00:00:00")


def cargar_solicitudes(db):
    cat = cargar_catalogos()
    admin, maria, juan = _actor(db, "admin"), _actor(db, "mperez"), _actor(db, "jgarcia")
    m_correo, j_correo = "mperez@ejemplo.com", "jgarcia@ejemplo.com"

    def alta(actor, datos, dias):
        sid = S.registrar_alta(db, datos, actor, cat)
        _fechar(db, sid, dias)
        return sid

    def cambio(actor, datos, dias):
        sid = S.registrar_cambio(db, datos, actor, cat)
        _fechar(db, sid, dias)
        return sid

    # Con el correo desactivado, las notificaciones de ejemplo quedan en outbox/.
    # Con SMTP real no se envía nada a las direcciones de ejemplo.
    enviar = not current_app.config["MAIL_ENABLED"]

    def resolver(sid, nuevo, actor, motivo=""):
        estatus.atender(db, sid, nuevo, actor, motivo, enviar_correo=enviar)

    # 1. Contrato nuevo aprobado: crea el cliente en el padrón.
    s = alta(maria, _alta("40311122233", "Alimentos Selectos de Jalisco SA de CV", "ASJ180505LM3", "Occidente",
                          "Empresarial", "Zapopan", "71000001", "Verónica Pineda Ríos", m_correo), 9)
    resolver(s, LISTO, admin)
    # 2. Usuario nuevo en contrato existente, aprobado.
    s = alta(maria, _usuario_nuevo("40112345678", "71000002", "Daniel Vázquez Mora", m_correo), 8)
    resolver(s, LISTO, admin)
    # 3. Cambio de permisos aplicado al padrón.
    s = cambio(maria, _cambio(db, "40112345679", m_correo, "El cliente aumentó su volumen de operación.",
                              grupo_spot="Spot Preferente", limite_operacion="400000", limite_diario="1500000"), 7)
    resolver(s, LISTO, admin)
    # 4. Contrato nuevo pendiente con antigüedad mayor al SLA.
    alta(maria, _alta("40322233344", "Textiles Finos de Puebla SA", "TFP200101AA1", "Centro", "PyME", "Puebla",
                      "71000005", "Gerardo Olvera Paz", m_correo, grupo="Spot Básico"), 5)
    # 5. Contrato nuevo pendiente, sin límites (son opcionales).
    alta(juan, _alta("40333344455", "Constructora Peninsular SA de CV", "CPE160815BB2", "Sur", "Corporativo",
                     "Cancún", "71000006", "Lucía Cervantes Mora", j_correo, divisas=("USDMXN", "EURUSD"),
                     limites=None), 3)
    # 6. Alta rechazada.
    s = alta(juan, _alta("40344455566", "Minera Sierra Madre SA", "MSM101112CC3", "Norte", "Corporativo",
                         "Hermosillo", "71000007", "Ricardo Aguilar Ponce", j_correo), 6)
    resolver(s, RECHAZADA, admin, "El RFC no corresponde al titular del contrato.")
    # 7. Alta cancelada por el ejecutivo.
    s = alta(maria, _alta("40355566677", "Papelería Universal SA", "PUN090909DD4", "Centro", "PyME", "Toluca",
                          "71000008", "Isabel Reyes Campos", m_correo), 4)
    resolver(s, CANCELADA, maria, "El cliente decidió posponer la apertura.")
    # 8. Cambio de permisos pendiente.
    cambio(juan, _cambio(db, "40233311122", j_correo, "El cliente necesita abonar a varias cuentas.",
                         multiabono="Sí"), 1)
    # 9. Usuario nuevo en contrato existente, pendiente.
    alta(juan, _usuario_nuevo("40233311123", "71000003", "Elena Ramos Fuentes", j_correo), 2)
    # 10. Número de usuario ya registrado en otro contrato: se permite.
    alta(maria, _usuario_nuevo("40198765432", "70000002", "Carlos Méndez Soto", m_correo), 1)
    # 11. Contrato nuevo aprobado.
    s = alta(juan, _alta("40366677788", "Exportadora Hortícola del Pacífico SA", "EHP140303EE5", "Occidente",
                         "Empresarial", "Culiacán", "71000009", "Andrés Navarro Gil", j_correo,
                         divisas=("USDMXN", "EURMXN")), 6)
    resolver(s, LISTO, admin)
    # 12. Cambio de permisos rechazado.
    s = cambio(maria, _cambio(db, "40198765432", m_correo, "Operará también en euros.",
                              divisas=["USDMXN", "EURMXN"]), 3)
    resolver(s, RECHAZADA, admin, "Falta la carta firmada del representante legal.")
    # 13. Capturada por el administrador a nombre de un ejecutivo.
    alta(admin, _usuario_nuevo("40244422233", "71000004", "Iván Morales Paredes", j_correo, ejecutivo="jgarcia"), 0)
    # 14. Cambio de permisos pendiente sobre un contrato al que ya se le agregó un usuario.
    cambio(maria, _cambio(db, "40112345678", m_correo, "Ampliación de límites por temporada alta.",
                          limite_operacion="750000", limite_diario="3000000"), 0)
    # 15. Contrato nuevo aprobado.
    s = alta(juan, _alta("40377788899", "Farmacéutica del Golfo SA de CV", "FGO111111FF6", "Sur", "Institucional",
                         "Veracruz Puerto", "71000010", "Mónica Esquivel Lara", j_correo, grupo="Spot Premium",
                         divisas=("USDMXN", "EURMXN", "CHFMXN")), 2)
    resolver(s, LISTO, admin)


def generar_archivo_carga(ruta=None):
    """Archivo de ejemplo con filas válidas y errores intencionales para la vista previa."""
    ruta = Path(ruta or Path(current_app.config["DATOS_EJEMPLO_DIR"]) / "carga_inicial_ejemplo.xlsx")
    ruta.parent.mkdir(parents=True, exist_ok=True)
    libro = carga.generar_plantilla(cargar_catalogos(), ["mperez", "jgarcia"])
    clientes = [
        ["40400000001", "Grupo Hotelero Riviera SA de CV", "GHR130613GG7", "Sur", "Corporativo", "Playa del Carmen",
         "Spot Preferente", "Sí", "Sí", "USDMXN,EURMXN", 750000, 3000000, "mperez", "15/03/2021"],
        ["40400000002", "Autopartes Monterrey SA", "AMO080808HH8", "Noreste", "Empresarial", "Apodaca",
         "Spot Estándar", "No", "Sí", "USDMXN,USDCAD", 150000, 600000, "jgarcia", ""],
        # Error: RFC inválido, región fuera de catálogo y divisa que no es un par válido.
        ["40400000003", "Café de Altura SA", "XXX123", "Atlántico", "PyME", "Coatepec",
         "Spot Básico", "No", "No", "USD", 50000, 100000, "mperez", ""],
        # Error: ejecutivo inexistente.
        ["40400000004", "Cerámica Talavera SA", "CTA050505JJ9", "Centro", "PyME", "Puebla",
         "Spot Básico", "No", "No", "USDMXN", 50000, 100000, "plopez", ""],
        # Omitido: ya existe en el padrón.
        ["40112345678", "Comercializadora del Mar SA de CV", "CMA990215AB3", "Norte", "Corporativo", "Monterrey Centro",
         "Spot Premium", "Sí", "Sí", "EURMXN,USDMXN", 500000, 2000000, "mperez", ""],
        # Error: Excel quitó el cero inicial (celda numérica de 10 dígitos).
        [4040000005, "Lácteos del Valle SA", "LVA100101KK1", "Bajío", "PyME", "Lagos de Moreno",
         "Spot Básico", "No", "No", "USDMXN", 50000, 100000, "jgarcia", ""],
    ]
    usuarios = [
        ["40400000001", "72000001", "Mariana Solís Ortega"],
        ["40400000001", "72000002", "Héctor Ruiz Campos"],
        ["40400000002", "72000003", "Gabriela Fuentes Rey"],
        ["40400000002", "72000003", "Gabriela Fuentes Rey"],      # repetido en el archivo
        ["40400000003", "72000004", "Pablo Ortega León"],         # su contrato tiene errores
        ["40499999999", "72000005", "Teresa Gómez Villa"],        # contrato inexistente
        ["40112345678", "70000001", "Laura Ríos Méndez"],         # ya existe en el padrón: se omite
        ["40112345678", "72000006", "Alberto Durán Solís"],       # usuario nuevo en contrato del padrón
        ["40400000002", "7200007", "Nadia Herrera Paz"],          # 7 dígitos
    ]
    for hoja, filas in ((libro[carga.HOJA_CLIENTES], clientes), (libro[carga.HOJA_USUARIOS], usuarios)):
        for i, fila in enumerate(filas, start=2):
            for j, valor in enumerate(fila, start=1):
                hoja.cell(row=i, column=j, value=valor)
    libro.save(ruta)
    return ruta


def cargar_todo(db):
    cargar_usuarios(db)
    cargar_padron(db)
    cargar_solicitudes(db)
    return generar_archivo_carga()
