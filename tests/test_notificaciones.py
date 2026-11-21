"""Campana de notificaciones: quién recibe qué, aislamiento y pantalla."""
import pytest

from app import estatus as E
from app import notificaciones as N
from app import solicitudes as S
from app import usuarios as U
from app.constantes import CANCELADA, LISTO, RECHAZADA
from app.usuarios import crear_usuario
from conftest import ADMIN, CONTRASENA, EJ1, EJ2, cliente_padron, datos_alta, login

ADMIN2 = {"usuario": "admin2", "rol": "admin", "correo": "admin2@ejemplo.com", "nombre": "Admin Dos"}


def _de(db, usuario):
    return N.listar(db, usuario, por_pagina=100)[0]


@pytest.fixture
def admin2(db):
    crear_usuario(db, ADMIN2["usuario"], ADMIN2["nombre"], ADMIN2["correo"], "admin", CONTRASENA, debe_cambiar=False)
    return ADMIN2


@pytest.fixture
def sid(db, cat, admin2):
    """Alta enviada por ej1."""
    return S.registrar_alta(db, datos_alta(), EJ1, cat)


# ---------------------------------------------------------------- nuevas solicitudes → administradores

def test_alta_nueva_avisa_a_cada_admin(db, sid):
    for admin in ("admin", "admin2"):
        avisos = _de(db, admin)
        assert len(avisos) == 1
        aviso = avisos[0]
        assert aviso["tipo"] == N.TIPO_NUEVA and aviso["solicitud_id"] == sid and aviso["leida"] == 0
        assert "SOL-" in aviso["mensaje"] and "40100000001" in aviso["mensaje"] and "Ejecutivo Uno" in aviso["mensaje"]
    assert _de(db, "ej1") == [] and _de(db, "ej2") == []


def test_cambio_de_permisos_tambien_avisa(db, cat):
    cliente_padron(db, "40100000001", "ej1")
    from conftest import datos_cambio
    S.registrar_cambio(db, datos_cambio(multiabono="Sí"), EJ1, cat)
    assert _de(db, "admin")[0]["mensaje"].startswith("Nueva solicitud SOL-")
    assert "Cambio de permisos" in _de(db, "admin")[0]["mensaje"]


def test_admin_que_captura_no_se_avisa_a_si_mismo(db, cat, admin2):
    S.registrar_alta(db, datos_alta(ejecutivo="ej1"), ADMIN, cat)
    assert _de(db, "admin") == []
    aviso = _de(db, "admin2")[0]
    assert "capturada por Admin Pruebas a nombre de Ejecutivo Uno" in aviso["mensaje"]


def test_admin_inactivo_no_recibe(db, cat, admin2):
    U.desactivar(db, "admin2", ADMIN, motivo="Baja")
    S.registrar_alta(db, datos_alta(), EJ1, cat)
    assert len(_de(db, "admin")) == 1 and _de(db, "admin2") == []


def test_solicitud_rechazada_por_validacion_no_avisa(db, cat):
    with pytest.raises(S.ErrorSolicitud):
        S.registrar_alta(db, datos_alta(contrato="123"), EJ1, cat)
    assert _de(db, "admin") == []


# ---------------------------------------------------------------- cambios de estatus → ejecutivo

@pytest.mark.parametrize("nuevo,motivo", [(LISTO, ""), (RECHAZADA, "Falta la carta firmada")])
def test_cambio_de_estatus_avisa_al_ejecutivo(db, sid, nuevo, motivo):
    E.atender(db, sid, nuevo, ADMIN, motivo)
    avisos = _de(db, "ej1")
    assert len(avisos) == 1
    aviso = avisos[0]
    assert aviso["tipo"] == N.TIPO_ESTATUS and aviso["estatus"] == nuevo and f"«{nuevo}»" in aviso["mensaje"]
    if motivo:
        assert f"Motivo: {motivo}" in aviso["mensaje"]
    assert _de(db, "ej2") == []
    assert len(_de(db, "admin")) == 1  # solo el aviso de la solicitud nueva


def test_cancelar_la_propia_no_avisa(db, sid):
    E.atender(db, sid, CANCELADA, EJ1)
    assert _de(db, "ej1") == []


def test_aprobacion_multiple_avisa_por_cada_una(db, cat, sid):
    otra = S.registrar_alta(db, datos_alta(contrato="40100000002", numero_usuario="80000002"), EJ2, cat)
    E.atender_varias(db, [sid, otra], ADMIN)
    assert len(_de(db, "ej1")) == 1 and len(_de(db, "ej2")) == 1


def test_cambio_fallido_no_deja_aviso(db, sid):
    with pytest.raises(E.ErrorEstatus):
        E.atender(db, sid, RECHAZADA, ADMIN, "")  # sin motivo
    E.atender(db, sid, LISTO, ADMIN)
    with pytest.raises(E.ErrorEstatus):
        E.atender(db, sid, RECHAZADA, ADMIN, "Tarde")  # ya es final
    assert [a["estatus"] for a in _de(db, "ej1")] == [LISTO]


# ---------------------------------------------------------------- lectura

def test_contador_y_marcar(db, cat, sid):
    S.registrar_alta(db, datos_alta(contrato="40100000002", numero_usuario="80000002"), EJ2, cat)
    assert N.no_leidas(db, "admin") == 2
    primera = _de(db, "admin")[-1]
    assert N.marcar_leida(db, primera["id"], "admin") is True
    assert N.no_leidas(db, "admin") == 1
    assert len(N.listar(db, "admin", solo_no_leidas=True)[0]) == 1
    assert N.marcar_todas(db, "admin") == 1 and N.no_leidas(db, "admin") == 0


def test_no_se_puede_marcar_una_ajena(db, sid):
    ajena = _de(db, "admin")[0]
    assert N.marcar_leida(db, ajena["id"], "ej1") is False
    assert N.no_leidas(db, "admin") == 1


def test_texto_contador():
    assert N.texto_contador(5) == "5" and N.texto_contador(100) == "99+"


# ---------------------------------------------------------------- pantalla y campana

def test_campana_muestra_sin_leer(client, db, sid):
    login(client, "admin")
    html = client.get("/admin/solicitudes").get_data(as_text=True)
    assert 'class="campana' in html and 'class="globo">1<' in html
    client.post("/logout")
    login(client, "ej1")
    html = client.get("/mis-solicitudes").get_data(as_text=True)
    assert 'class="campana' in html and 'class="globo"' not in html


def test_pantalla_lista_solo_las_propias(client, db, sid):
    E.atender(db, sid, LISTO, ADMIN)
    login(client, "ej1")
    html = client.get("/notificaciones/").get_data(as_text=True)
    assert "«Listo para operar»" in html and "Nueva solicitud" not in html
    client.post("/logout")
    login(client, "ej2")
    html = client.get("/notificaciones/").get_data(as_text=True)
    assert "Aún no tienes notificaciones." in html


def test_abrir_marca_leida_y_lleva_a_la_solicitud(client, db, sid):
    aviso = _de(db, "admin")[0]
    login(client, "admin")
    r = client.post(f"/notificaciones/{aviso['id']}/abrir")
    assert r.status_code == 302 and r.headers["Location"].endswith(f"/solicitudes/{sid}")
    assert N.no_leidas(db, "admin") == 0
    html = client.get("/notificaciones/?estado=no_leidas").get_data(as_text=True)
    assert "No tienes notificaciones sin leer." in html


def test_acciones_sobre_ajenas_dan_404(client, db, sid):
    aviso = _de(db, "admin")[0]
    login(client, "ej1")
    assert client.post(f"/notificaciones/{aviso['id']}/abrir").status_code == 404
    assert client.post(f"/notificaciones/{aviso['id']}/leida").status_code == 404
    client.post("/notificaciones/marcar-todas")
    assert N.no_leidas(db, "admin") == 1


def test_abrir_solicitud_transferida(client, db, sid):
    E.atender(db, sid, LISTO, ADMIN)
    aviso = _de(db, "ej1")[0]
    U.transferir_cartera(db, "ej1", "ej2", ADMIN, "Reorganización")
    # El aviso de una solicitud ya atendida sigue abriendo (las finales no se transfieren).
    login(client, "ej1")
    assert client.post(f"/notificaciones/{aviso['id']}/abrir").status_code == 302


def test_marcar_todas_por_pantalla(client, db, sid):
    login(client, "admin")
    r = client.post("/notificaciones/marcar-todas", data={"estado": "no_leidas"})
    assert r.status_code == 302 and "estado=no_leidas" in r.headers["Location"]
    assert N.no_leidas(db, "admin") == 0


def test_requiere_sesion(client):
    assert client.get("/notificaciones/").status_code == 302
