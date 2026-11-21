"""Padrón de clientes: actualización automática, autocompletado y mantenimiento."""
import json

import pytest

from app import estatus as E
from app import padron as P
from app import solicitudes as S
from app.constantes import CANCELADA, ETIQUETAS, LISTO, ORIGEN_CARGA, ORIGEN_SOLICITUD, PENDIENTE, RECHAZADA
from app.db import transaccion
from app.utils import folio
from conftest import ADMIN, EJ1, cliente_padron, datos_alta, datos_cambio, login


def test_listo_en_alta_de_contrato_nuevo_crea_el_cliente(db, cat):
    sid = S.registrar_alta(db, datos_alta(), EJ1, cat)
    E.cambiar_estatus(db, sid, LISTO, ADMIN)
    cliente = P.obtener_cliente(db, "40100000001")
    assert cliente["ejecutivo_asignado"] == "ej1"
    assert cliente["origen"] == ORIGEN_SOLICITUD and cliente["solicitud_origen"] == sid
    assert P.existe_usuario(db, "40100000001", "80000001")
    assert any(h["origen"] == folio(sid) for h in P.historial_de(db, "40100000001"))


def test_listo_en_contrato_existente_solo_agrega_el_usuario(db, cat):
    cliente_padron(db, "40100000001", "ej1", usuarios=("80000001",), grupo_spot="Spot Premium")
    sid = S.registrar_alta(db, datos_alta(numero_usuario="80000002"), EJ1, cat)
    E.cambiar_estatus(db, sid, LISTO, ADMIN)
    assert P.obtener_cliente(db, "40100000001")["grupo_spot"] == "Spot Premium"
    assert [u["numero_usuario"] for u in P.usuarios_de(db, "40100000001")] == ["80000001", "80000002"]


def test_listo_en_cambio_de_permisos_actualiza_el_padron(db, cat):
    cliente_padron(db, "40100000001", "ej1")
    sid = S.registrar_cambio(db, datos_cambio(grupo_spot="Spot Premium", limite_diario="900000"), EJ1, cat)
    E.cambiar_estatus(db, sid, LISTO, ADMIN)
    cliente = P.obtener_cliente(db, "40100000001")
    assert cliente["grupo_spot"] == "Spot Premium"
    assert cliente["limite_diario"] == 900000
    campos = {h["campo"] for h in P.historial_de(db, "40100000001") if h["origen"] == folio(sid)}
    assert campos == {ETIQUETAS["grupo_spot"], ETIQUETAS["limite_diario"]}


@pytest.mark.parametrize("final", [RECHAZADA, CANCELADA])
def test_rechazo_o_cancelacion_no_modifica_el_padron(db, cat, final):
    cliente_padron(db, "40100000001", "ej1")
    sid = S.registrar_cambio(db, datos_cambio(grupo_spot="Spot Premium"), EJ1, cat)
    E.cambiar_estatus(db, sid, final, ADMIN if final == RECHAZADA else EJ1, motivo="No procede")
    assert P.obtener_cliente(db, "40100000001")["grupo_spot"] == "Spot Básico"


def test_alta_sin_limites_llega_al_padron_sin_limites(db, cat):
    sid = S.registrar_alta(db, datos_alta(limite_operacion="", limite_diario=""), EJ1, cat)
    assert S.obtener(db, sid)["limite_operacion"] is None
    E.cambiar_estatus(db, sid, LISTO, ADMIN)
    cliente = P.obtener_cliente(db, "40100000001")
    assert cliente["limite_operacion"] is None and cliente["limite_diario"] is None


def test_cambio_que_agrega_o_quita_limites(db, cat):
    cliente_padron(db, "40100000001", "ej1", limite_operacion=None, limite_diario=None)
    sid = S.registrar_cambio(db, datos_cambio(limite_operacion="250000", limite_diario=""), EJ1, cat)
    E.cambiar_estatus(db, sid, LISTO, ADMIN)
    cliente = P.obtener_cliente(db, "40100000001")
    assert cliente["limite_operacion"] == 250000 and cliente["limite_diario"] is None
    # Quitar el límite también es un cambio válido.
    sid = S.registrar_cambio(db, datos_cambio(limite_operacion="", limite_diario=""), EJ1, cat)
    E.cambiar_estatus(db, sid, LISTO, ADMIN)
    assert P.obtener_cliente(db, "40100000001")["limite_operacion"] is None
    # Sin límites en ambos lados no hay nada que cambiar.
    with pytest.raises(S.ErrorSolicitud):
        S.registrar_cambio(db, datos_cambio(limite_operacion="", limite_diario=""), EJ1, cat)


def test_rollback_si_falla_la_actualizacion_del_padron(db, cat):
    cliente_padron(db, "40100000001", "ej1", usuarios=("80000001",))
    sid = S.registrar_alta(db, datos_alta(numero_usuario="80000002"), EJ1, cat)
    # Mientras tanto, una carga inicial agrega el mismo usuario al padrón.
    with transaccion(db):
        P.agregar_usuario(db, "40100000001", "80000002", "Usuario cargado", "admin", ORIGEN_CARGA)
    with pytest.raises(E.ErrorEstatus):
        E.cambiar_estatus(db, sid, LISTO, ADMIN)
    assert S.obtener(db, sid)["estatus"] == PENDIENTE
    assert len(S.historial(db, sid)) == 1  # solo el registro de creación


def test_cambio_guarda_los_permisos_vigentes(db, cat):
    cliente = cliente_padron(db, "40100000001", "ej1")
    sid = S.registrar_cambio(db, datos_cambio(multiabono="Sí"), EJ1, cat)
    assert json.loads(S.obtener(db, sid)["permisos_vigentes"]) == P.permisos_de(cliente)


def test_cambio_sin_diferencias_se_bloquea(db, cat):
    cliente_padron(db, "40100000001", "ej1")
    with pytest.raises(S.ErrorSolicitud) as error:
        S.registrar_cambio(db, datos_cambio(), EJ1, cat)
    assert error.value.errores["_general"] == S.MSG_SIN_CAMBIOS


def test_cambio_pendiente_bloquea_otro_cambio(db, cat):
    cliente_padron(db, "40100000001", "ej1")
    sid = S.registrar_cambio(db, datos_cambio(multiabono="Sí"), EJ1, cat)
    with pytest.raises(S.ErrorSolicitud) as error:
        S.registrar_cambio(db, datos_cambio(multiaprobacion="Sí"), EJ1, cat)
    assert folio(sid) in error.value.errores["contrato"]


def test_cambio_sobre_contrato_inexistente(db, cat):
    with pytest.raises(S.ErrorSolicitud) as error:
        S.registrar_cambio(db, datos_cambio(multiabono="Sí"), EJ1, cat)
    assert error.value.errores["contrato"] == S.MSG_NO_EXISTE


def test_cambio_con_alta_pendiente(db, cat):
    S.registrar_alta(db, datos_alta(), EJ1, cat)
    with pytest.raises(S.ErrorSolicitud) as error:
        S.registrar_cambio(db, datos_cambio(multiabono="Sí"), EJ1, cat)
    assert error.value.errores["contrato"] == S.MSG_ALTA_PENDIENTE_CAMBIO


def test_autocompletado_desde_el_padron(client, db):
    cliente = cliente_padron(db, "40100000001", "ej1")
    login(client, "ej1")
    respuesta = client.get("/api/contrato/40100000001?para=cambio").get_json()
    assert respuesta["estado"] == "propio"
    assert respuesta["cliente"]["nombre_cliente"] == cliente["nombre_cliente"]
    assert respuesta["cliente"]["grupo_spot"] == "Spot Básico"
    alta = client.get("/api/contrato/40100000001?para=alta").get_json()
    assert alta["estado"] == "propio" and alta["cliente"]["rfc"] == cliente["rfc"]
    nuevo = client.get("/api/contrato/40199999999?para=alta").get_json()
    assert nuevo["estado"] == "nuevo" and "cliente" not in nuevo


def test_edicion_reasignacion_y_eliminacion_quedan_en_historial(db):
    cliente = cliente_padron(db, "40100000001", "ej1", usuarios=("80000001", "80000002"))
    with transaccion(db):
        cambios = P.editar_cliente(db, "40100000001", {**dict(cliente), "zona": "Zona 2"}, "admin", "Corrección")
    assert [c["campo"] for c in cambios] == ["zona"]
    with transaccion(db):
        P.reasignar(db, "40100000001", "ej2", "admin", "Cambio de cartera")
    assert P.obtener_cliente(db, "40100000001")["ejecutivo_asignado"] == "ej2"
    with transaccion(db):
        P.eliminar_usuario(db, "40100000001", "80000002", "admin", "Capturado por error")
    assert not P.existe_usuario(db, "40100000001", "80000002")

    historial = P.historial_de(db, "40100000001")
    origenes = {h["origen"] for h in historial}
    assert {"Edición manual", "Reasignación", "Eliminación"} <= origenes
    assert all(h["motivo"] for h in historial if h["origen"] != ORIGEN_CARGA)

    with transaccion(db):
        P.eliminar_cliente(db, "40100000001", "admin", "Contrato duplicado")
    assert P.obtener_cliente(db, "40100000001") is None
    assert P.usuarios_de(db, "40100000001") == []
    assert P.historial_de(db, "40100000001")[0]["campo"] == "Eliminación de contrato"


def test_mantenimiento_exige_motivo(db):
    cliente_padron(db, "40100000001", "ej1")
    with pytest.raises(P.ErrorPadron):
        P.reasignar(db, "40100000001", "ej2", "admin", "")
    with pytest.raises(P.ErrorPadron):
        P.eliminar_cliente(db, "40100000001", "admin", "  ")
