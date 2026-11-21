"""Aislamiento entre ejecutivos y control de acceso (pruebas por HTTP)."""
from io import BytesIO

import pytest
from openpyxl import load_workbook

from app import solicitudes as S
from app.constantes import PENDIENTE
from app.usuarios import crear_usuario
from app.utils import folio
from conftest import CONTRASENA, EJ1, EJ2, cliente_padron, datos_alta, datos_cambio, login


@pytest.fixture
def escenario(db, cat):
    cliente_padron(db, "40100000001", "ej1", nombre_cliente="Cliente Uno SA")
    cliente_padron(db, "40200000002", "ej2", nombre_cliente="Cliente Dos SA", usuarios=("80000005",))
    propia = S.registrar_alta(db, datos_alta(contrato="40100000003", nombre_cliente="Solicitud Uno SA"), EJ1, cat)
    ajena = S.registrar_alta(db, datos_alta(contrato="40200000004", nombre_cliente="Solicitud Dos SA",
                                            numero_usuario="80000006", correo_notificaciones="ej2@ejemplo.com"),
                             EJ2, cat)
    return {"propia": propia, "ajena": ajena}


def test_login_requerido(client):
    respuesta = client.get("/mis-solicitudes")
    assert respuesta.status_code == 302 and "/login" in respuesta.headers["Location"]
    assert client.get("/api/contrato/40100000001").status_code == 401


def test_mis_solicitudes_solo_muestra_las_propias(client, escenario):
    login(client, "ej1")
    html = client.get("/mis-solicitudes").get_data(as_text=True)
    assert folio(escenario["propia"]) in html
    assert folio(escenario["ajena"]) not in html and "Solicitud Dos SA" not in html


def test_busqueda_no_expone_solicitudes_ajenas(client, escenario):
    login(client, "ej1")
    html = client.get("/mis-solicitudes?q=40200000004").get_data(as_text=True)
    assert "Solicitud Dos SA" not in html


def test_detalle_de_solicitud_ajena_da_404(client, escenario):
    login(client, "ej1")
    assert client.get(f"/solicitudes/{escenario['propia']}").status_code == 200
    assert client.get(f"/solicitudes/{escenario['ajena']}").status_code == 404


def test_cancelar_solicitud_ajena_da_404(client, db, escenario):
    login(client, "ej1")
    assert client.post(f"/solicitudes/{escenario['ajena']}/cancelar").status_code == 404
    assert S.obtener(db, escenario["ajena"])["estatus"] == PENDIENTE


@pytest.mark.parametrize("url", [
    "/admin/solicitudes", "/admin/solicitudes/exportar", "/admin/solicitudes/exportar-dia",
    "/admin/padron/carga", "/admin/padron/plantilla", "/admin/padron/agregar-cliente",
    "/cartera/40100000001/editar",
])
def test_rutas_de_admin_dan_403_al_ejecutivo(client, escenario, url):
    login(client, "ej1")
    assert client.get(url).status_code == 403


def test_ejecutivo_no_puede_cambiar_estatus(client, db, escenario):
    login(client, "ej1")
    respuesta = client.post(f"/admin/solicitudes/{escenario['propia']}/estatus", data={"nuevo": "Listo para operar"})
    assert respuesta.status_code == 403
    assert S.obtener(db, escenario["propia"])["estatus"] == PENDIENTE


def test_cartera_solo_muestra_contratos_propios(client, escenario):
    login(client, "ej1")
    html = client.get("/cartera/").get_data(as_text=True)
    assert "Cliente Uno SA" in html and "Cliente Dos SA" not in html
    html = client.get("/cartera/?q=80000005").get_data(as_text=True)
    assert "Cliente Dos SA" not in html


def test_detalle_de_contrato_ajeno_da_404(client, escenario):
    login(client, "ej1")
    assert client.get("/cartera/40100000001").status_code == 200
    assert client.get("/cartera/40200000002").status_code == 404
    assert client.get("/cartera/40999999999").status_code == 404  # misma respuesta que si no existiera


def test_exportar_cartera_solo_incluye_lo_propio(client, escenario):
    login(client, "ej1")
    respuesta = client.get("/cartera/exportar")
    libro = load_workbook(BytesIO(respuesta.data))
    contratos = [fila[0] for fila in libro["Contratos"].iter_rows(min_row=2, values_only=True)]
    usuarios = [fila[0] for fila in libro["Usuarios"].iter_rows(min_row=2, values_only=True)]
    assert contratos == ["40100000001"]
    assert set(usuarios) == {"40100000001"}


def test_api_de_contrato_ajeno_no_devuelve_datos(client, escenario):
    login(client, "ej1")
    respuesta = client.get("/api/contrato/40200000002?para=cambio")
    datos = respuesta.get_json()
    assert datos["estado"] == "ajeno" and "cliente" not in datos
    assert "Cliente Dos" not in respuesta.get_data(as_text=True)


def test_api_no_revela_el_folio_de_un_alta_pendiente_ajena(client, escenario):
    login(client, "ej1")
    datos = client.get("/api/contrato/40200000004?para=alta").get_json()
    assert datos["estado"] == "alta_pendiente"
    assert folio(escenario["ajena"]) not in datos["mensaje"]


def test_cambio_sobre_contrato_ajeno_no_se_registra(client, db, escenario):
    login(client, "ej1")
    respuesta = client.post("/solicitudes/cambio-permisos",
                            data=datos_cambio(contrato="40200000002", grupo_spot="Spot Premium"))
    assert respuesta.status_code == 200
    assert S.MSG_AJENO_CAMBIO in respuesta.get_data(as_text=True)
    assert S.por_contrato(db, "40200000002") == []


def test_alta_por_formulario(client, db, escenario):
    login(client, "ej1")
    respuesta = client.post("/solicitudes/alta", data=datos_alta(contrato="40100000009", numero_usuario="80000009"))
    assert respuesta.status_code == 302
    assert len(S.por_contrato(db, "40100000009", "ej1")) == 1


def test_admin_ve_todo(client, escenario):
    login(client, "admin")
    html = client.get("/admin/solicitudes").get_data(as_text=True)
    assert folio(escenario["propia"]) in html and folio(escenario["ajena"]) in html
    assert client.get(f"/solicitudes/{escenario['ajena']}").status_code == 200
    assert client.get("/cartera/40200000002").status_code == 200


def test_bloqueo_por_intentos_fallidos(client, app):
    for _ in range(app.config["MAX_LOGIN_ATTEMPTS"]):
        login(client, "ej1", "incorrecta")
    respuesta = login(client, "ej1")  # contraseña correcta, pero la cuenta está bloqueada
    assert respuesta.status_code == 200
    assert "bloqueada" in respuesta.get_data(as_text=True)


def test_contrasena_temporal_obliga_a_cambiarla(client, db):
    crear_usuario(db, "nuevo", "Usuario Nuevo", "nuevo@ejemplo.com", "ejecutivo", CONTRASENA, debe_cambiar=True)
    login(client, "nuevo")
    respuesta = client.get("/mis-solicitudes")
    assert respuesta.status_code == 302 and "/cambiar-contrasena" in respuesta.headers["Location"]
