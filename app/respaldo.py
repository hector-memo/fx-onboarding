"""Respaldos del archivo SQLite (diario automático y antes de cada carga masiva)."""
import logging
import sqlite3
from pathlib import Path

from flask import current_app

from .utils import ahora, hoy_str

log = logging.getLogger("fx")
_ultimo_dia = {"valor": None}


def respaldar(etiqueta="manual"):
    """Copia consistente de la base usando la API de respaldo de SQLite."""
    cfg = current_app.config
    origen = Path(cfg["DATABASE"])
    if not origen.exists():
        return None
    carpeta = Path(cfg["BACKUP_DIR"])
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / f"fx_onboarding_{etiqueta}_{ahora().strftime('%Y%m%d_%H%M%S')}.db"
    fuente = sqlite3.connect(origen)
    copia = sqlite3.connect(destino)
    try:
        fuente.backup(copia)
    finally:
        copia.close()
        fuente.close()
    existentes = sorted(carpeta.glob(f"fx_onboarding_{etiqueta}_*.db"))
    for viejo in existentes[:-max(int(cfg["BACKUP_KEEP"]), 1)]:
        viejo.unlink(missing_ok=True)
    log.info("Respaldo creado: %s", destino.name)
    return destino


def respaldo_diario():
    """Crea el respaldo del día si todavía no existe. Nunca interrumpe la petición."""
    if not current_app.config.get("RESPALDO_AUTOMATICO", True):
        return
    hoy = hoy_str()
    if _ultimo_dia["valor"] == hoy:
        return
    try:
        carpeta = Path(current_app.config["BACKUP_DIR"])
        if not any(carpeta.glob(f"fx_onboarding_diario_{hoy.replace('-', '')}_*.db")):
            respaldar("diario")
        _ultimo_dia["valor"] = hoy
    except Exception:  # un respaldo fallido se registra, pero la app sigue funcionando
        log.exception("No se pudo crear el respaldo diario")
