"""Reglas de validación centralizadas.

Las usan los formularios de solicitudes, la carga inicial, la captura manual y
la edición del padrón. Cada función `validar_*` devuelve (o llena) un dict
{campo: mensaje}; un dict vacío significa que todo es válido.
"""
import math
import re
from datetime import date

from .constantes import NO, SI

RE_CONTRATO = re.compile(r"\d{11}")
RE_NUMERO_USUARIO = re.compile(r"\d{8}")
RE_RFC_MORAL = re.compile(r"[A-ZÑ&]{3}(\d{2})(\d{2})(\d{2})[A-Z0-9]{3}")
RE_RFC_FISICA = re.compile(r"[A-ZÑ&]{4}(\d{2})(\d{2})(\d{2})[A-Z0-9]{3}")
RE_CORREO = re.compile(r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,}")
RE_USUARIO_APP = re.compile(r"[a-z0-9._-]{3,30}")
ROLES_APP = ("admin", "ejecutivo")

MAX_TEXTO = 150
MAX_ZONA = 100
MAX_COMENTARIO = 500
OBLIGATORIO = "Campo obligatorio."


# ---------------------------------------------------------------- normalización

def limpiar(valor):
    """Recorta espacios y colapsa espacios internos repetidos."""
    if valor is None:
        return ""
    if isinstance(valor, str):
        return " ".join(valor.split())
    return valor


def normalizar_si_no(valor):
    texto = str(limpiar(valor)).lower()
    if texto in ("sí", "si", "s", "yes", "y", "true", "1", "verdadero"):
        return SI
    if texto in ("no", "n", "false", "0", "falso"):
        return NO
    return limpiar(valor)


def parse_monto(valor):
    """'1,000,000.50' -> 1000000.5. Devuelve None si no es un número válido."""
    if valor is None or valor == "" or isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        numero = float(valor)
    else:
        texto = str(valor).strip().replace(",", "").replace("$", "").replace(" ", "")
        try:
            numero = float(texto)
        except ValueError:
            return None
    if math.isnan(numero) or math.isinf(numero):
        return None
    return round(numero, 2)


def normalizar_divisas(valor):
    """Lista o texto separado por comas -> 'EURMXN,USDMXN' (mayúsculas, sin repetir, ordenado)."""
    if valor is None:
        partes = []
    elif isinstance(valor, (list, tuple)):
        partes = valor
    else:
        partes = str(valor).replace(";", ",").split(",")
    return ",".join(sorted({str(p).strip().upper() for p in partes if str(p).strip()}))


def normalizar(datos):
    """Limpia y normaliza los datos capturados antes de validarlos o guardarlos."""
    d = {}
    for clave, valor in datos.items():
        if clave == "csrf_token":
            continue
        if clave == "divisas":
            d[clave] = normalizar_divisas(valor)
        elif isinstance(valor, (list, tuple)):
            d[clave] = [limpiar(v) for v in valor]
        else:
            d[clave] = limpiar(valor)
    for clave in ("contrato", "numero_usuario"):
        if isinstance(d.get(clave), str):
            d[clave] = d[clave].replace(" ", "")
    if "rfc" in d:
        d["rfc"] = str(d["rfc"]).upper()
    for clave in ("multiaprobacion", "multiabono"):
        if clave in d:
            d[clave] = normalizar_si_no(d[clave])
    for clave in ("limite_operacion", "limite_diario"):
        if clave in d:
            if d[clave] in ("", None):
                d[clave] = None  # opcional: vacío se guarda como NULL
                continue
            monto = parse_monto(d[clave])
            if monto is not None:
                d[clave] = monto  # si no es número se deja el texto original para reportar el error
    for clave in ("correo_notificaciones", "ejecutivo", "ejecutivo_asignado"):
        if isinstance(d.get(clave), str):
            d[clave] = d[clave].lower()
    return d


# ---------------------------------------------------------------- formatos

def es_contrato(valor):
    return isinstance(valor, str) and RE_CONTRATO.fullmatch(valor) is not None


def es_numero_usuario(valor):
    return isinstance(valor, str) and RE_NUMERO_USUARIO.fullmatch(valor) is not None


def es_correo(valor):
    return isinstance(valor, str) and RE_CORREO.fullmatch(valor) is not None


def es_rfc(valor):
    """RFC de persona moral (12) o física (13) con fecha AAMMDD válida."""
    if not isinstance(valor, str):
        return False
    m = RE_RFC_MORAL.fullmatch(valor) or RE_RFC_FISICA.fullmatch(valor)
    if not m:
        return False
    aa, mm, dd = (int(x) for x in m.groups())
    try:
        date(2000 + aa, mm, dd)
    except ValueError:
        return False
    return True


# ---------------------------------------------------------------- validadores por campo

def _vacio(valor):
    if valor is None:
        return True
    if isinstance(valor, str):
        return valor.strip() == ""
    if isinstance(valor, (list, tuple)):
        return len(valor) == 0
    return False


def _requerido(d, campo, errores):
    if _vacio(d.get(campo)):
        errores[campo] = OBLIGATORIO
        return False
    return True


def validar_contrato(d, errores, campo="contrato"):
    if _requerido(d, campo, errores) and not es_contrato(d[campo]):
        errores[campo] = "El contrato debe tener exactamente 11 dígitos numéricos."


def validar_numero_usuario(d, errores):
    if _requerido(d, "numero_usuario", errores) and not es_numero_usuario(d["numero_usuario"]):
        errores["numero_usuario"] = "El número de usuario debe tener exactamente 8 dígitos numéricos."


def validar_texto(d, campo, errores, maximo=MAX_TEXTO, requerido=True):
    if requerido and not _requerido(d, campo, errores):
        return
    valor = d.get(campo) or ""
    if len(str(valor)) > maximo:
        errores[campo] = f"Máximo {maximo} caracteres."


def validar_catalogo(d, campo, opciones, errores):
    if _requerido(d, campo, errores) and d[campo] not in opciones:
        errores[campo] = f"«{d[campo]}» no es un valor válido; selecciona uno de la lista."


def validar_correo(d, errores, campo="correo_notificaciones"):
    if _requerido(d, campo, errores) and not es_correo(d[campo]):
        errores[campo] = "El correo no tiene un formato válido."


def validar_empresa(d, catalogo, errores):
    validar_texto(d, "nombre_cliente", errores)
    if _requerido(d, "rfc", errores) and not es_rfc(d["rfc"]):
        errores["rfc"] = "RFC inválido: 12 caracteres (persona moral) o 13 (persona física), con fecha válida."
    validar_catalogo(d, "region", catalogo["regiones"], errores)
    validar_catalogo(d, "segmento", catalogo["segmentos"], errores)
    validar_texto(d, "zona", errores, maximo=MAX_ZONA)  # texto libre, sin catálogo


def validar_permisos(d, catalogo, errores):
    validar_catalogo(d, "grupo_spot", catalogo["grupos_spot"], errores)
    for campo in ("multiaprobacion", "multiabono"):
        if _requerido(d, campo, errores) and d[campo] not in (SI, NO):
            errores[campo] = "Selecciona Sí o No."

    if _requerido(d, "divisas", errores):
        invalidas = [x for x in str(d["divisas"]).split(",") if x not in catalogo["divisas"]]
        if invalidas:
            errores["divisas"] = f"Divisas no válidas: {', '.join(invalidas)}."

    # Límites opcionales: si se capturan deben ser números mayores a 0.
    limites = {}
    for campo in ("limite_operacion", "limite_diario"):
        valor = d.get(campo)
        if _vacio(valor):
            continue
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            errores[campo] = "Debe ser un número."
        elif valor <= 0:
            errores[campo] = "Debe ser mayor a 0."
        else:
            limites[campo] = valor
    # Solo se comparan cuando vienen los dos.
    if len(limites) == 2 and limites["limite_diario"] < limites["limite_operacion"]:
        errores["limite_diario"] = "El límite diario debe ser mayor o igual al límite por operación."


# ---------------------------------------------------------------- validadores compuestos

def validar_alta(d, catalogo, contrato_existente=False):
    """Alta nueva. Si el contrato ya está en el padrón, empresa y permisos vienen de ahí."""
    errores = {}
    validar_contrato(d, errores)
    validar_numero_usuario(d, errores)
    validar_texto(d, "nombre_completo", errores)
    validar_correo(d, errores)
    validar_texto(d, "comentarios", errores, maximo=MAX_COMENTARIO, requerido=False)
    if not contrato_existente:
        validar_empresa(d, catalogo, errores)
        validar_permisos(d, catalogo, errores)
    return errores


def validar_cambio(d, catalogo):
    errores = {}
    validar_contrato(d, errores)
    validar_permisos(d, catalogo, errores)
    validar_correo(d, errores)
    validar_texto(d, "motivo_cambio", errores, maximo=MAX_COMENTARIO)
    return errores


def validar_cliente_padron(d, catalogo):
    """Contrato completo del padrón (carga inicial, captura manual, edición)."""
    errores = {}
    validar_contrato(d, errores)
    validar_empresa(d, catalogo, errores)
    validar_permisos(d, catalogo, errores)
    return errores


def validar_usuario_padron(d):
    errores = {}
    validar_contrato(d, errores)
    validar_numero_usuario(d, errores)
    validar_texto(d, "nombre_completo", errores)
    return errores


def validar_usuario_app(d, nuevo=True):
    """Usuario de la aplicación (pantalla Usuarios). En una alta también valida usuario y contraseña."""
    errores = {}
    if nuevo:
        if _requerido(d, "usuario", errores) and not RE_USUARIO_APP.fullmatch(d["usuario"]):
            errores["usuario"] = "Usa de 3 a 30 caracteres: minúsculas, números, punto, guion o guion bajo."
        mensaje = validar_contrasena_nueva(d.get("contrasena") or "")
        if mensaje:
            errores["contrasena"] = mensaje
    validar_texto(d, "nombre", errores)
    validar_correo(d, errores, campo="correo")
    if _requerido(d, "rol", errores) and d["rol"] not in ROLES_APP:
        errores["rol"] = "Selecciona un rol."
    return errores


def validar_contrasena_nueva(contrasena):
    """Devuelve un mensaje de error o None."""
    if len(contrasena or "") < 8:
        return "La contraseña debe tener al menos 8 caracteres."
    if not re.search(r"[A-Za-z]", contrasena) or not re.search(r"\d", contrasena):
        return "La contraseña debe incluir letras y números."
    return None
