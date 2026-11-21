"""Detección de duplicados en altas (contra el padrón y contra altas pendientes)."""
import pytest

from app import estatus as E
from app import solicitudes as S
from app.constantes import CANCELADA, RECHAZADA
from app.utils import folio
from conftest import ADMIN, EJ1, cliente_padron, datos_alta


def test_duplicado_en_padron(db, cat):
    cliente_padron(db, "40100000001", "ej1", usuarios=("80000001",))
    with pytest.raises(S.ErrorSolicitud) as error:
        S.registrar_alta(db, datos_alta(), EJ1, cat)
    assert "ya está dado de alta" in error.value.errores["numero_usuario"]
    assert error.value.contexto["duplicado_contrato"] == "40100000001"


def test_usuario_nuevo_en_contrato_existente_se_permite_y_copia_el_padron(db, cat):
    cliente = cliente_padron(db, "40100000001", "ej1", usuarios=("80000001",), grupo_spot="Spot Premium")
    sid = S.registrar_alta(db, datos_alta(numero_usuario="80000002", nombre_cliente="Otro nombre",
                                          grupo_spot="Spot Básico"), EJ1, cat)
    sol = S.obtener(db, sid)
    assert sol["nombre_cliente"] == cliente["nombre_cliente"]
    assert sol["grupo_spot"] == "Spot Premium"


def test_mismo_usuario_en_otro_contrato_se_permite(db, cat):
    cliente_padron(db, "40100000001", "ej1", usuarios=("80000001",))
    sid = S.registrar_alta(db, datos_alta(contrato="40100000002", numero_usuario="80000001"), EJ1, cat)
    assert S.obtener(db, sid)["numero_usuario"] == "80000001"


def test_alta_pendiente_bloquea_otra_alta_del_mismo_contrato_nuevo(db, cat):
    sid = S.registrar_alta(db, datos_alta(), EJ1, cat)
    with pytest.raises(S.ErrorSolicitud) as error:
        S.registrar_alta(db, datos_alta(numero_usuario="80000009"), EJ1, cat)
    assert folio(sid) in error.value.errores["contrato"]


def test_duplicado_pendiente_en_contrato_existente(db, cat):
    cliente_padron(db, "40100000001", "ej1", usuarios=("80000001",))
    sid = S.registrar_alta(db, datos_alta(numero_usuario="80000002"), EJ1, cat)
    with pytest.raises(S.ErrorSolicitud) as error:
        S.registrar_alta(db, datos_alta(numero_usuario="80000002"), EJ1, cat)
    assert folio(sid) in error.value.errores["numero_usuario"]


@pytest.mark.parametrize("final", [RECHAZADA, CANCELADA])
def test_rechazadas_y_canceladas_no_cuentan(db, cat, final):
    sid = S.registrar_alta(db, datos_alta(), EJ1, cat)
    E.cambiar_estatus(db, sid, final, ADMIN if final == RECHAZADA else EJ1, motivo="Datos incorrectos")
    nuevo = S.registrar_alta(db, datos_alta(), EJ1, cat)
    assert nuevo != sid


def test_contrato_de_otra_cartera_bloqueado(db, cat):
    cliente_padron(db, "40100000001", "ej2")
    with pytest.raises(S.ErrorSolicitud) as error:
        S.registrar_alta(db, datos_alta(numero_usuario="80000009"), EJ1, cat)
    assert error.value.errores["contrato"] == S.MSG_AJENO_ALTA


def test_admin_captura_en_cualquier_contrato_a_nombre_del_asignado(db, cat):
    cliente_padron(db, "40100000001", "ej2")
    sid = S.registrar_alta(db, datos_alta(numero_usuario="80000009"), ADMIN, cat)
    assert S.obtener(db, sid)["ejecutivo"] == "ej2"


def test_admin_debe_elegir_ejecutivo_en_contrato_nuevo(db, cat):
    with pytest.raises(S.ErrorSolicitud) as error:
        S.registrar_alta(db, datos_alta(), ADMIN, cat)
    assert "ejecutivo" in error.value.errores
    sid = S.registrar_alta(db, datos_alta(ejecutivo="ej1"), ADMIN, cat)
    assert S.obtener(db, sid)["ejecutivo"] == "ej1"
