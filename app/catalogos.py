"""Lectura del archivo editable de catálogos (catalogos.json).

Se lee en cada uso para que los cambios al archivo se apliquen sin reiniciar.
"""
import json
from pathlib import Path

from flask import current_app

CLAVES = ("regiones", "segmentos", "grupos_spot", "divisas")


def cargar(ruta=None):
    ruta = Path(ruta or current_app.config["CATALOGOS"])
    with open(ruta, encoding="utf-8") as archivo:
        datos = json.load(archivo)
    catalogo = {}
    for clave in CLAVES:
        valores = datos.get(clave) or []
        catalogo[clave] = [str(v).strip() for v in valores if str(v).strip()]
    catalogo["divisas"] = [d.upper() for d in catalogo["divisas"]]
    return catalogo
