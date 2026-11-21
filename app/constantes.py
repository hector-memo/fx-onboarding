"""Valores fijos compartidos por toda la aplicación."""

# Estatus de solicitudes
PENDIENTE = "Pendiente"
LISTO = "Listo para operar"
RECHAZADA = "Rechazada"
CANCELADA = "Cancelada"
ESTATUS = (PENDIENTE, LISTO, RECHAZADA, CANCELADA)

# Tipos de solicitud
TIPO_ALTA = "Alta nueva"
TIPO_CAMBIO = "Cambio de permisos"
TIPOS = (TIPO_ALTA, TIPO_CAMBIO)

# Roles
ROL_ADMIN = "admin"
ROL_EJECUTIVO = "ejecutivo"

# Estatus del correo de notificación
CORREO_NO_APLICA = "No aplica"
CORREO_PENDIENTE = "Pendiente"
CORREO_ENVIADO = "Enviado"
CORREO_ERROR = "Error"
ESTATUS_CORREO = (CORREO_NO_APLICA, CORREO_PENDIENTE, CORREO_ENVIADO, CORREO_ERROR)

# Origen de los registros del padrón
ORIGEN_SOLICITUD = "Solicitud"
ORIGEN_CARGA = "Carga inicial"
ORIGEN_MANUAL = "Captura manual"
ORIGEN_EDICION = "Edición manual"
ORIGEN_REASIGNACION = "Reasignación"
ORIGEN_ELIMINACION = "Eliminación"

SI = "Sí"
NO = "No"

# Campos a nivel contrato
CAMPOS_EMPRESA = ("nombre_cliente", "rfc", "region", "segmento", "zona")
CAMPOS_PERMISOS = (
    "grupo_spot",
    "multiaprobacion",
    "multiabono",
    "divisas",
    "limite_operacion",
    "limite_diario",
)

ETIQUETAS = {
    "contrato": "Contrato de banca electrónica",
    "nombre_cliente": "Nombre de cliente",
    "rfc": "RFC",
    "region": "Región",
    "segmento": "Segmento",
    "zona": "Zona",
    "numero_usuario": "Número de usuario",
    "nombre_completo": "Nombre completo",
    "ejecutivo": "Ejecutivo solicitante",
    "correo_notificaciones": "Correo para notificaciones",
    "grupo_spot": "Grupo de parametrización spot",
    "multiaprobacion": "Multiaprobación",
    "multiabono": "Multiabono",
    "divisas": "Divisas autorizadas",
    "limite_operacion": "Límite por operación (USD)",
    "limite_diario": "Límite diario (USD)",
    "comentarios": "Comentarios",
    "motivo_cambio": "Motivo del cambio",
    "ejecutivo_asignado": "Ejecutivo asignado",
    "fecha_alta": "Fecha de alta en plataforma",
    "motivo": "Motivo",
}
