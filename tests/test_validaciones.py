"""Reglas de validación centralizadas."""
import pytest

from app import validaciones as V
from app.constantes import CAMPOS_PERMISOS
from conftest import datos_alta

CAT = {
    "regiones": ["Norte"], "segmentos": ["Corporativo"], "grupos_spot": ["Spot Básico"],
    "divisas": ["USDMXN", "EURMXN", "EURUSD"],
}


@pytest.mark.parametrize("valor,ok", [
    ("12345678901", True), ("01234567890", True), ("1234567890", False),
    ("123456789012", False), ("1234567890a", False), ("", False),
])
def test_contrato(valor, ok):
    assert V.es_contrato(valor) is ok


@pytest.mark.parametrize("valor,ok", [("12345678", True), ("1234567", False), ("123456789", False), ("1234567a", False)])
def test_numero_usuario(valor, ok):
    assert V.es_numero_usuario(valor) is ok


@pytest.mark.parametrize("valor,ok", [
    ("CPR990101AB1", True),     # persona moral
    ("GODE561231GR8", True),    # persona física
    ("CPR991301AB1", False),    # mes 13
    ("CPR990231AB1", False),    # 31 de febrero
    ("CP990101AB1", False),
    ("CPR990101AB", False),
])
def test_rfc(valor, ok):
    assert V.es_rfc(valor) is ok


@pytest.mark.parametrize("zona", ["Monterrey Centro", "Zona 9", "CDMX - Polanco / Lomas"])
def test_zona_es_texto_libre(zona):
    assert "zona" not in V.validar_alta(V.normalizar(datos_alta(zona=zona)), CAT)


def test_zona_obligatoria_y_con_limite_de_longitud():
    assert V.validar_alta(V.normalizar(datos_alta(zona="  ")), CAT)["zona"] == V.OBLIGATORIO
    assert "zona" in V.validar_alta(V.normalizar(datos_alta(zona="x" * (V.MAX_ZONA + 1))), CAT)


def test_campos_eliminados_no_se_piden():
    errores = V.validar_alta(V.normalizar(datos_alta()), CAT)
    assert "cuenta_liquidacion" not in errores and "estatus_kyc" not in errores


def test_alta_valida_sin_errores():
    assert V.validar_alta(V.normalizar(datos_alta()), CAT) == {}


def test_todos_los_campos_obligatorios():
    vacios = {k: "" for k in datos_alta()}
    errores = V.validar_alta(V.normalizar(vacios), CAT)
    esperados = {"contrato", "numero_usuario", "nombre_completo", "correo_notificaciones", "nombre_cliente", "rfc",
                 "region", "segmento", "zona", "grupo_spot", "multiaprobacion", "multiabono", "divisas"}
    assert esperados == set(errores)  # comentarios y límites son opcionales


@pytest.mark.parametrize("operacion,diario", [("", ""), ("100000", ""), ("", "500000"), (None, None)])
def test_limites_son_opcionales(operacion, diario):
    d = V.normalizar(datos_alta(limite_operacion=operacion, limite_diario=diario))
    errores = V.validar_alta(d, CAT)
    assert "limite_operacion" not in errores and "limite_diario" not in errores
    if not operacion:
        assert d["limite_operacion"] is None  # vacío se guarda como NULL, no como texto


def test_limite_diario_menor_al_de_operacion():
    errores = V.validar_cliente_padron(V.normalizar(datos_alta(limite_operacion="500", limite_diario="100")), CAT)
    assert "limite_diario" in errores


@pytest.mark.parametrize("valor", ["-5", "0", "abc"])
def test_limites_invalidos(valor):
    errores = V.validar_cliente_padron(V.normalizar(datos_alta(limite_operacion=valor)), CAT)
    assert "limite_operacion" in errores


def test_valores_fuera_de_catalogo():
    datos = datos_alta(region="Atlántico", segmento="Otro", grupo_spot="VIP", divisas=["USDMXN", "USD"])
    errores = V.validar_alta(V.normalizar(datos), CAT)
    for campo in ("region", "segmento", "grupo_spot", "divisas"):
        assert campo in errores
    assert errores["divisas"] == "Divisas no válidas: USD."
    assert "Atlántico" in errores["region"]


def test_correo_invalido():
    errores = V.validar_alta(V.normalizar(datos_alta(correo_notificaciones="no-es-correo")), CAT)
    assert "correo_notificaciones" in errores


def test_normalizar():
    d = V.normalizar({"rfc": " cpr990101ab1 ", "multiaprobacion": "si", "multiabono": "NO",
                      "divisas": ["usdmxn", "EURMXN", "usdmxn"], "limite_operacion": "1,000,000.50",
                      "contrato": "401 0000 0001", "nombre_cliente": "  Cliente   SA ", "csrf_token": "x"})
    assert d["rfc"] == "CPR990101AB1"
    assert d["multiaprobacion"] == "Sí" and d["multiabono"] == "No"
    assert d["divisas"] == "EURMXN,USDMXN"
    assert d["limite_operacion"] == 1000000.5
    assert d["contrato"] == "40100000001"
    assert d["nombre_cliente"] == "Cliente SA"
    assert "csrf_token" not in d


def test_alta_en_contrato_existente_no_pide_datos_de_empresa():
    datos = {"contrato": "40100000001", "numero_usuario": "80000002", "nombre_completo": "Nuevo",
             "correo_notificaciones": "ej1@ejemplo.com"}
    assert V.validar_alta(V.normalizar(datos), CAT, contrato_existente=True) == {}


def test_cambio_requiere_motivo():
    campos = CAMPOS_PERMISOS + ("contrato", "correo_notificaciones")
    datos = {k: v for k, v in datos_alta().items() if k in campos}
    assert "motivo_cambio" in V.validar_cambio(V.normalizar(datos), CAT)


def test_contrasena_nueva():
    assert V.validar_contrasena_nueva("corta1")
    assert V.validar_contrasena_nueva("sinnumeros")
    assert V.validar_contrasena_nueva("Valida2026") is None
