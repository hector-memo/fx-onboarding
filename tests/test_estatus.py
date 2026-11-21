"""Transiciones de estatus y correo."""
from pathlib import Path

import pytest

from app import correo
from app import estatus as E
from app import padron as P
from app import solicitudes as S
from app.constantes import CANCELADA, CORREO_ENVIADO, CORREO_ERROR, LISTO, PENDIENTE, RECHAZADA
from conftest import ADMIN, EJ1, EJ2, cliente_padron, datos_alta, datos_cambio


@pytest.fixture
def pendiente(db, cat):
    return S.registrar_alta(db, datos_alta(), EJ1, cat)


def test_ejecutivo_no_puede_marcar_listo(db, pendiente):
    with pytest.raises(E.ErrorEstatus):
        E.cambiar_estatus(db, pendiente, LISTO, EJ1)


def test_admin_no_puede_cancelar(db, pendiente):
    with pytest.raises(E.ErrorEstatus):
        E.cambiar_estatus(db, pendiente, CANCELADA, ADMIN)


def test_otro_ejecutivo_no_puede_cancelar(db, pendiente):
    with pytest.raises(E.ErrorEstatus):
        E.cambiar_estatus(db, pendiente, CANCELADA, EJ2)


def test_dueno_puede_cancelar_sin_motivo(db, pendiente):
    assert E.cambiar_estatus(db, pendiente, CANCELADA, EJ1)["estatus"] == CANCELADA


def test_rechazo_requiere_motivo(db, pendiente):
    with pytest.raises(E.ErrorEstatus):
        E.cambiar_estatus(db, pendiente, RECHAZADA, ADMIN, motivo="  ")
    sol = E.cambiar_estatus(db, pendiente, RECHAZADA, ADMIN, motivo="CLABE incorrecta")
    assert sol["motivo_resolucion"] == "CLABE incorrecta" and sol["atendido_por"] == "admin"


@pytest.mark.parametrize("siguiente", [LISTO, RECHAZADA, CANCELADA, PENDIENTE])
def test_estatus_finales_no_cambian(db, pendiente, siguiente):
    E.cambiar_estatus(db, pendiente, LISTO, ADMIN)
    with pytest.raises(E.ErrorEstatus):
        E.cambiar_estatus(db, pendiente, siguiente, ADMIN, motivo="x")


def test_listo_en_cambios_y_usuarios_nuevos_de_contrato_existente(db, cat):
    cliente_padron(db, "40100000001", "ej1")
    cambio = S.registrar_cambio(db, datos_cambio(multiabono="Sí"), EJ1, cat)
    usuario = S.registrar_alta(db, datos_alta(numero_usuario="80000002"), EJ1, cat)
    for sid in (cambio, usuario):
        assert E.cambiar_estatus(db, sid, LISTO, ADMIN)["estatus"] == LISTO
    assert P.obtener_cliente(db, "40100000001")["multiabono"] == "Sí"


def test_historial_registra_cada_cambio(db, pendiente):
    E.cambiar_estatus(db, pendiente, RECHAZADA, ADMIN, motivo="Duplicada")
    historial = S.historial(db, pendiente)
    assert [(h["estatus_anterior"], h["estatus_nuevo"]) for h in historial] == [(None, PENDIENTE), (PENDIENTE, RECHAZADA)]
    assert historial[-1]["comentario"] == "Duplicada"


def test_fallo_de_correo_no_revierte_estatus_ni_padron(db, pendiente, monkeypatch):
    def falla(*_args, **_kwargs):
        raise OSError("SMTP caído")

    monkeypatch.setattr(correo, "enviar", falla)
    sol, correo_ok = E.atender(db, pendiente, LISTO, ADMIN)
    assert correo_ok is False
    actual = S.obtener(db, pendiente)
    assert actual["estatus"] == LISTO and actual["estatus_correo"] == CORREO_ERROR
    assert P.obtener_cliente(db, "40100000001") is not None

    monkeypatch.undo()
    assert correo.notificar(db, pendiente) is True
    assert S.obtener(db, pendiente)["estatus_correo"] == CORREO_ENVIADO


def test_correo_desactivado_se_guarda_en_outbox(app, db, pendiente):
    E.atender(db, pendiente, RECHAZADA, ADMIN, motivo="Falta documentación")
    archivos = list(Path(app.config["OUTBOX_DIR"]).glob("*.html"))
    assert len(archivos) == 1
    contenido = archivos[0].read_text(encoding="utf-8")
    assert "Falta documentación" in contenido and "ej1@ejemplo.com" in contenido


def test_aprobacion_masiva_omite_las_que_no_cumplen(db, cat):
    buena = S.registrar_alta(db, datos_alta(), EJ1, cat)
    cancelada = S.registrar_alta(db, datos_alta(contrato="40100000002"), EJ1, cat)
    E.cambiar_estatus(db, cancelada, CANCELADA, EJ1)
    listas, fallidas, _ = E.atender_varias(db, [buena, cancelada], ADMIN)
    assert listas == [buena]
    assert [sid for sid, _ in fallidas] == [cancelada]
