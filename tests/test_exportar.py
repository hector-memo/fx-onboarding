"""Exportaciones a Excel y protección contra inyección de fórmulas."""
from io import BytesIO

import pytest
from openpyxl import load_workbook

from app import solicitudes as S
from app.exportar import sanitizar
from app.utils import folio, hoy_str
from conftest import EJ1, datos_alta, login


@pytest.mark.parametrize("valor,esperado", [
    ("=HYPERLINK(\"http://x\")", "'=HYPERLINK(\"http://x\")"),
    ("+52", "'+52"),
    ("-1", "'-1"),
    ("@SUMA", "'@SUMA"),
    ("\tdato", "'\tdato"),
    ("\rdato", "'\rdato"),
    ("Cliente SA", "Cliente SA"),
    (100.5, 100.5),
    (None, None),
])
def test_sanitizar(valor, esperado):
    assert sanitizar(valor) == esperado


def test_exportacion_conserva_ceros_y_neutraliza_formulas(client, db, cat):
    sid = S.registrar_alta(db, datos_alta(contrato="01234567890", nombre_cliente="=1+1 Comercial"), EJ1, cat)
    login(client, "admin")
    respuesta = client.get("/admin/solicitudes/exportar")
    libro = load_workbook(BytesIO(respuesta.data))
    hoja = libro["Solicitudes"]
    encabezados = [c.value for c in hoja[1]]
    fila = {encabezados[i]: c.value for i, c in enumerate(hoja[2])}
    assert fila["ID de solicitud"] == folio(sid)
    assert fila["Contrato de banca electrónica"] == "01234567890"
    assert fila["Nombre de cliente"] == "'=1+1 Comercial"
    assert "Historial de estatus" in libro.sheetnames
    # El dato guardado no se alteró.
    assert S.obtener(db, sid)["nombre_cliente"] == "=1+1 Comercial"


def test_exportacion_respeta_filtros(client, db, cat):
    S.registrar_alta(db, datos_alta(contrato="40100000001"), EJ1, cat)
    S.registrar_alta(db, datos_alta(contrato="40100000002", region="Sur"), EJ1, cat)
    login(client, "admin")
    libro = load_workbook(BytesIO(client.get("/admin/solicitudes/exportar?region=Sur").data))
    contratos = [f[4] for f in libro["Solicitudes"].iter_rows(min_row=2, values_only=True)]
    assert contratos == ["40100000002"]


def test_exportar_solicitudes_del_dia(client, db, cat):
    S.registrar_alta(db, datos_alta(), EJ1, cat)
    login(client, "admin")
    respuesta = client.get("/admin/solicitudes/exportar-dia")
    assert respuesta.status_code == 200
    assert f"solicitudes_{hoy_str()}.xlsx" in respuesta.headers["Content-Disposition"]
    libro = load_workbook(BytesIO(respuesta.data))
    assert libro["Solicitudes"].max_row == 2
