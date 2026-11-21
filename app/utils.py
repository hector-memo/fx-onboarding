"""Utilidades de fechas, folios y formato de valores."""
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from flask import current_app, has_app_context

FMT_DB = "%Y-%m-%d %H:%M:%S"
ZONA_DEFECTO = "America/Mexico_City"
RE_FOLIO = re.compile(r"^sol-?0*(\d+)$", re.IGNORECASE)


def _zona():
    nombre = current_app.config.get("TIMEZONE", ZONA_DEFECTO) if has_app_context() else ZONA_DEFECTO
    return ZoneInfo(nombre)


def ahora():
    """Fecha y hora local (zona configurada), sin tzinfo, para guardar en la base."""
    return datetime.now(_zona()).replace(tzinfo=None, microsecond=0)


def ahora_str():
    return ahora().strftime(FMT_DB)


def hoy_str():
    return ahora().strftime("%Y-%m-%d")


def a_datetime(valor):
    if isinstance(valor, datetime):
        return valor
    return datetime.strptime(str(valor)[:19], FMT_DB)


def formatear_fecha(valor):
    """'2026-11-21 14:05:00' -> '21/11/2026 14:05'."""
    if not valor:
        return ""
    texto = str(valor)
    try:
        return datetime.strptime(texto[:19], FMT_DB).strftime("%d/%m/%Y %H:%M")
    except ValueError:
        pass
    try:
        return datetime.strptime(texto[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return texto


def formatear_fecha_corta(valor):
    """'2026-11-21 14:05:00' -> '21/11/2026'."""
    texto = formatear_fecha(valor)
    return texto[:10] if texto else ""


def parse_fecha_alta(texto):
    """Fecha opcional capturada por el admin. Devuelve texto para la base, None si viene vacía o False si es inválida."""
    if not texto:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(str(texto).strip(), fmt).strftime(FMT_DB)
        except ValueError:
            continue
    return False


def folio(sid):
    return f"SOL-{int(sid):06d}"


def parse_folio(texto):
    """'SOL-000012' o 'sol12' -> 12. Devuelve None si el texto no es un folio."""
    m = RE_FOLIO.match((texto or "").strip())
    return int(m.group(1)) if m else None


def dias_habiles_entre(inicio, fin=None):
    """Días hábiles (lunes a viernes) transcurridos desde `inicio` hasta `fin`."""
    inicio = a_datetime(inicio)
    fin = fin or ahora()
    dia, dias = inicio.date(), 0
    while dia < fin.date():
        dia += timedelta(days=1)
        if dia.weekday() < 5:
            dias += 1
    return dias


def formatear_monto(valor):
    if valor is None or valor == "":
        return ""
    try:
        return f"{float(valor):,.2f}"
    except (TypeError, ValueError):
        return str(valor)


def valor_input(valor):
    """Valor para el atributo value de un input HTML."""
    if valor is None:
        return ""
    if isinstance(valor, float):
        return str(int(valor)) if valor.is_integer() else f"{valor:.2f}"
    if isinstance(valor, (list, tuple)):
        return ",".join(str(v) for v in valor)
    return valor


def mostrar(valor, campo=""):
    """Valor legible para pantallas de detalle."""
    if valor is None or valor == "":
        return "—"
    if campo.startswith("limite_"):
        return formatear_monto(valor)
    if campo == "divisas":
        return ", ".join(x for x in str(valor).split(",") if x)
    return str(valor)
