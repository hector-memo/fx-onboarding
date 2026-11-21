"""Exportaciones a Excel (.xlsx).

Los datos se guardan tal cual en la base; solo al exportar se neutralizan los
valores que Excel podría interpretar como fórmula.
"""
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from .utils import folio, formatear_fecha

PREFIJOS_PELIGROSOS = ("=", "+", "-", "@", "\t", "\r")
COLUMNAS_TEXTO = {"folio", "contrato", "numero_usuario"}
COLUMNAS_FECHA = {"fecha_solicitud", "fecha_atencion", "fecha", "fecha_alta", "ultima_actualizacion"}
ENCABEZADO_FUENTE = Font(bold=True, color="FFFFFF")
ENCABEZADO_FONDO = PatternFill("solid", fgColor="1F4E79")

COLUMNAS_SOLICITUD = [
    ("folio", "ID de solicitud"),
    ("fecha_solicitud", "Fecha y hora de solicitud"),
    ("tipo", "Tipo"),
    ("estatus", "Estatus"),
    ("contrato", "Contrato de banca electrónica"),
    ("nombre_cliente", "Nombre de cliente"),
    ("rfc", "RFC"),
    ("region", "Región"),
    ("segmento", "Segmento"),
    ("zona", "Zona"),
    ("numero_usuario", "Número de usuario"),
    ("nombre_completo", "Nombre completo"),
    ("ejecutivo", "Ejecutivo solicitante"),
    ("correo_notificaciones", "Correo para notificaciones"),
    ("grupo_spot", "Grupo de parametrización spot"),
    ("multiaprobacion", "Multiaprobación"),
    ("multiabono", "Multiabono"),
    ("divisas", "Divisas autorizadas"),
    ("limite_operacion", "Límite por operación (USD)"),
    ("limite_diario", "Límite diario (USD)"),
    ("comentarios", "Comentarios"),
    ("motivo_cambio", "Motivo del cambio"),
    ("motivo_resolucion", "Motivo de rechazo/cancelación"),
    ("fecha_atencion", "Fecha de atención"),
    ("atendido_por", "Atendido por"),
    ("estatus_correo", "Estatus de correo"),
]
COLUMNAS_HISTORIAL = [
    ("folio", "ID de solicitud"),
    ("fecha", "Fecha"),
    ("usuario", "Usuario"),
    ("estatus_anterior", "Estatus anterior"),
    ("estatus_nuevo", "Estatus nuevo"),
    ("comentario", "Comentario"),
]
COLUMNAS_CONTRATOS = [
    ("contrato", "Contrato"),
    ("nombre_cliente", "Nombre de cliente"),
    ("rfc", "RFC"),
    ("region", "Región"),
    ("segmento", "Segmento"),
    ("zona", "Zona"),
    ("num_usuarios", "Núm. de usuarios"),
    ("grupo_spot", "Grupo de parametrización spot"),
    ("multiaprobacion", "Multiaprobación"),
    ("multiabono", "Multiabono"),
    ("divisas", "Divisas autorizadas"),
    ("limite_operacion", "Límite por operación (USD)"),
    ("limite_diario", "Límite diario (USD)"),
    ("ejecutivo_asignado", "Ejecutivo asignado"),
    ("origen", "Origen"),
    ("fecha_alta", "Fecha de alta"),
    ("ultima_actualizacion", "Última actualización"),
]
COLUMNAS_USUARIOS = [
    ("contrato", "Contrato"),
    ("nombre_cliente", "Nombre de cliente"),
    ("numero_usuario", "Número de usuario"),
    ("nombre_completo", "Nombre completo"),
    ("fecha_alta", "Fecha de alta"),
    ("origen", "Origen"),
]


def sanitizar(valor):
    """Antepone un apóstrofo a textos que Excel podría ejecutar como fórmula."""
    if isinstance(valor, str) and valor.startswith(PREFIJOS_PELIGROSOS):
        return "'" + valor
    return valor


def _valor(registro, clave):
    if clave == "folio":
        return folio(registro["solicitud_id"] if "solicitud_id" in registro.keys() else registro["id"])
    valor = registro[clave]
    if clave in COLUMNAS_FECHA:
        return formatear_fecha(valor)
    return valor


def escribir_hoja(hoja, columnas, filas):
    hoja.append([titulo for _, titulo in columnas])
    for celda in hoja[1]:
        celda.font = ENCABEZADO_FUENTE
        celda.fill = ENCABEZADO_FONDO
    anchos = [len(titulo) for _, titulo in columnas]
    for fila in filas:
        valores = [sanitizar(v) for v in fila]
        hoja.append(valores)
        for i, v in enumerate(valores):
            anchos[i] = max(anchos[i], len(str(v)) if v is not None else 0)
    for i, (clave, _) in enumerate(columnas, start=1):
        if clave in COLUMNAS_TEXTO:
            for (celda,) in hoja.iter_rows(min_row=2, min_col=i, max_col=i):
                celda.number_format = "@"
        hoja.column_dimensions[get_column_letter(i)].width = min(anchos[i - 1] + 2, 50)
    hoja.auto_filter.ref = hoja.dimensions
    hoja.freeze_panes = "A2"


def _filas(registros, columnas):
    return [[_valor(r, clave) for clave, _ in columnas] for r in registros]


def a_bytes(libro):
    buffer = BytesIO()
    libro.save(buffer)
    buffer.seek(0)
    return buffer


def libro_solicitudes(solicitudes, historial):
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Solicitudes"
    escribir_hoja(hoja, COLUMNAS_SOLICITUD, _filas(solicitudes, COLUMNAS_SOLICITUD))
    escribir_hoja(libro.create_sheet("Historial de estatus"), COLUMNAS_HISTORIAL, _filas(historial, COLUMNAS_HISTORIAL))
    return a_bytes(libro)


def libro_cartera(clientes, usuarios):
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Contratos"
    escribir_hoja(hoja, COLUMNAS_CONTRATOS, _filas(clientes, COLUMNAS_CONTRATOS))
    escribir_hoja(libro.create_sheet("Usuarios"), COLUMNAS_USUARIOS, _filas(usuarios, COLUMNAS_USUARIOS))
    return a_bytes(libro)


def libro_errores_carga(resultado):
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Errores"
    escribir_hoja(hoja, [("hoja", "Hoja"), ("fila", "Fila"), ("campo", "Campo"), ("mensaje", "Mensaje")],
                  [[e["hoja"], e["fila"], e["campo"], e["mensaje"]] for e in resultado.errores])
    escribir_hoja(libro.create_sheet("Omitidas"), [("hoja", "Hoja"), ("fila", "Fila"), ("motivo", "Motivo")],
                  [[o["hoja"], o["fila"], o["motivo"]] for o in resultado.omitidos])
    return a_bytes(libro)
