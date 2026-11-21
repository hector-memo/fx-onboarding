"""Ayudas compartidas por las rutas."""
from flask import current_app, g, request

from ..constantes import ROL_ADMIN

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def es_admin():
    return g.get("usuario") is not None and g.usuario["rol"] == ROL_ADMIN


def pagina_actual():
    try:
        return max(1, int(request.args.get("pagina", 1)))
    except (TypeError, ValueError):
        return 1


def por_pagina():
    return int(current_app.config["PAGE_SIZE"])


def filtros_de(claves):
    return {clave: (request.args.get(clave) or "").strip() for clave in claves}


def datos_formulario(listas=("divisas",)):
    datos = request.form.to_dict()
    datos.pop("csrf_token", None)
    for clave in listas:
        datos[clave] = request.form.getlist(clave)
    return datos


def ruta_segura(destino, defecto):
    if destino and destino.startswith("/") and not destino.startswith("//") and "\\" not in destino:
        return destino
    return defecto
