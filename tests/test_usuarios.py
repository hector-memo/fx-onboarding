"""Pantalla Usuarios: administración de usuarios de la app (solo admin)."""
import pytest

from app import padron as P
from app import solicitudes as S
from app import usuarios as U
from app.constantes import PENDIENTE
from conftest import ADMIN, CONTRASENA, EJ1, cliente_padron, datos_alta, login

NUEVO = {"usuario": "lrodriguez", "nombre": "Laura Rodríguez", "correo": "LRodriguez@Ejemplo.com",
         "rol": "ejecutivo", "contrasena": "Temporal2026"}


# ---------------------------------------------------------------- acceso

@pytest.mark.parametrize("url", ["/admin/usuarios/", "/admin/usuarios/nuevo", "/admin/usuarios/ej2"])
def test_solo_admin(client, url):
    login(client, "ej1")
    assert client.get(url).status_code == 403
    assert client.post("/admin/usuarios/ej2/desactivar", data={"motivo": "x"}).status_code == 403


def test_pantallas_se_muestran(client):
    login(client, "admin")
    html = client.get("/admin/usuarios/").get_data(as_text=True)
    assert "ej1" in html and "ej2" in html and "Administradores activos" in html
    assert client.get("/admin/usuarios/nuevo").status_code == 200
    assert client.get("/admin/usuarios/ej1").status_code == 200
    assert client.get("/admin/usuarios/no-existe").status_code == 404


# ---------------------------------------------------------------- alta

def test_alta_por_pantalla_y_primer_ingreso(client, db):
    login(client, "admin")
    respuesta = client.post("/admin/usuarios/nuevo", data=NUEVO)
    assert respuesta.status_code == 302
    nuevo = U.obtener(db, "lrodriguez")
    assert nuevo["correo"] == "lrodriguez@ejemplo.com" and nuevo["rol"] == "ejecutivo" and nuevo["debe_cambiar"] == 1
    assert U.historial(db, "lrodriguez")[0]["accion"] == U.ACCION_ALTA
    # El nuevo usuario entra y se le obliga a cambiar la contraseña temporal.
    client.post("/logout")
    login(client, "lrodriguez", "Temporal2026")
    assert "/cambiar-contrasena" in client.get("/mis-solicitudes").headers["Location"]


@pytest.mark.parametrize("cambio,campo", [
    ({"usuario": "ej1"}, "usuario"),                 # repetido
    ({"usuario": "Con Espacios"}, "usuario"),        # formato
    ({"usuario": "ab"}, "usuario"),                  # muy corto
    ({"contrasena": "corta1"}, "contrasena"),
    ({"contrasena": "sinnumeros"}, "contrasena"),
    ({"correo": "no-es-correo"}, "correo"),
    ({"nombre": ""}, "nombre"),
    ({"rol": "superadmin"}, "rol"),
])
def test_alta_valida_campos(db, cambio, campo):
    with pytest.raises(U.ErrorUsuario) as error:
        U.registrar_usuario(db, {**NUEVO, **cambio}, ADMIN)
    assert campo in error.value.errores


def test_alta_con_error_no_devuelve_la_contrasena(client):
    login(client, "admin")
    html = client.post("/admin/usuarios/nuevo", data={**NUEVO, "usuario": "ej1"}).get_data(as_text=True)
    assert "Ese usuario ya existe." in html and "Temporal2026" not in html


# ---------------------------------------------------------------- edición

def test_editar_nombre_correo_y_rol(db):
    cambios = U.actualizar_usuario(db, "ej2", {"nombre": "Ejecutivo Dos Editado", "correo": "nuevo@ejemplo.com",
                                               "rol": "admin"}, ADMIN)
    assert {c[0] for c in cambios} == {"nombre", "correo", "rol"}
    fila = U.obtener(db, "ej2")
    assert fila["rol"] == "admin" and fila["correo"] == "nuevo@ejemplo.com"
    assert "rol: ejecutivo → admin" in U.historial(db, "ej2")[0]["detalle"]


def test_no_puede_cambiar_su_propio_rol(db):
    with pytest.raises(U.ErrorUsuario, match="propio rol"):
        U.actualizar_usuario(db, "admin", {"nombre": "Admin", "correo": "admin@ejemplo.com", "rol": "ejecutivo"}, ADMIN)


def test_ejecutivo_con_cartera_no_cambia_de_rol(db):
    cliente_padron(db, "40100000001", "ej1")
    with pytest.raises(U.ErrorUsuario, match="Transfiere su cartera"):
        U.actualizar_usuario(db, "ej1", {"nombre": "Ej", "correo": "ej1@ejemplo.com", "rol": "admin"}, ADMIN)


def test_siempre_queda_un_administrador(db):
    U.registrar_usuario(db, {**NUEVO, "usuario": "admin2", "rol": "admin"}, ADMIN)
    otro_admin = {"usuario": "admin2", "rol": "admin"}
    U.desactivar(db, "admin", otro_admin, motivo="Cambio de puesto")
    # admin2 es ahora el único administrador activo: nadie puede quitarle el rol ni desactivarlo.
    with pytest.raises(U.ErrorUsuario, match="al menos un administrador"):
        U.actualizar_usuario(db, "admin2", {"nombre": "A2", "correo": "a2@ejemplo.com", "rol": "ejecutivo"},
                             {"usuario": "otro", "rol": "admin"})
    with pytest.raises(U.ErrorUsuario, match="al menos un administrador"):
        U.desactivar(db, "admin2", {"usuario": "otro", "rol": "admin"}, motivo="x")


# ---------------------------------------------------------------- desactivación y transferencia

def test_no_puede_desactivarse_a_si_mismo(db):
    with pytest.raises(U.ErrorUsuario, match="ti mismo"):
        U.desactivar(db, "admin", ADMIN, motivo="x")


def test_desactivar_exige_motivo(db):
    with pytest.raises(U.ErrorUsuario, match="motivo"):
        U.desactivar(db, "ej2", ADMIN, motivo=" ")


def test_desactivar_con_cartera_exige_transferir(db, cat):
    cliente_padron(db, "40100000001", "ej1")
    with pytest.raises(U.ErrorUsuario, match="transferir su cartera"):
        U.desactivar(db, "ej1", ADMIN, motivo="Deja el equipo")
    assert U.obtener(db, "ej1")["activo"] == 1


def test_desactivar_transfiere_contratos_y_pendientes(db, cat):
    cliente_padron(db, "40100000001", "ej1")
    sid = S.registrar_alta(db, datos_alta(contrato="40100000005", numero_usuario="80000005"), EJ1, cat)
    U.desactivar(db, "ej1", ADMIN, transferir_a="ej2", motivo="Deja el equipo")

    assert U.obtener(db, "ej1")["activo"] == 0
    assert P.obtener_cliente(db, "40100000001")["ejecutivo_asignado"] == "ej2"
    sol = S.obtener(db, sid)
    assert sol["ejecutivo"] == "ej2" and sol["correo_notificaciones"] == "ej2@ejemplo.com"
    assert sol["estatus"] == PENDIENTE
    assert "Transferida de ej1 a ej2" in S.historial(db, sid)[-1]["comentario"]
    assert any(h["origen"] == "Reasignación" for h in P.historial_de(db, "40100000001"))
    acciones = [h["accion"] for h in U.historial(db, "ej1")]
    assert U.ACCION_DESACTIVACION in acciones and U.ACCION_TRANSFERENCIA in acciones
    assert [r[0] for r in U.opciones_ejecutivos(db)] == ["ej2"]  # ya no aparece en las listas


def test_transferencia_invalida_no_cambia_nada(db, cat):
    cliente_padron(db, "40100000001", "ej1")
    with pytest.raises(U.ErrorUsuario):
        U.desactivar(db, "ej1", ADMIN, transferir_a="ej1", motivo="x")      # a sí mismo
    with pytest.raises(U.ErrorUsuario):
        U.desactivar(db, "ej1", ADMIN, transferir_a="admin", motivo="x")    # no es ejecutivo
    assert U.obtener(db, "ej1")["activo"] == 1
    assert P.obtener_cliente(db, "40100000001")["ejecutivo_asignado"] == "ej1"


def test_transferir_cartera_sin_desactivar(client, db):
    cliente_padron(db, "40100000001", "ej1")
    cliente_padron(db, "40100000002", "ej1", usuarios=("80000002",))
    login(client, "admin")
    client.post("/admin/usuarios/ej1/transferir", data={"transferir_a": "ej2", "motivo": "Cambio de cartera"})
    assert P.contratos_asignados(db, "ej1") == []
    assert P.contratos_asignados(db, "ej2") == ["40100000001", "40100000002"]
    assert U.obtener(db, "ej1")["activo"] == 1


def test_usuario_desactivado_pierde_la_sesion_y_no_entra(app, db):
    sesion_ej2 = app.test_client()
    login(sesion_ej2, "ej2")
    assert sesion_ej2.get("/mis-solicitudes").status_code == 200
    U.desactivar(db, "ej2", ADMIN, motivo="Baja")
    assert "/login" in sesion_ej2.get("/mis-solicitudes").headers["Location"]  # la sesión abierta se corta
    nueva = app.test_client()
    assert "incorrectos" in login(nueva, "ej2").get_data(as_text=True)


def test_reactivar(client, db):
    U.desactivar(db, "ej2", ADMIN, motivo="Licencia")
    U.reactivar(db, "ej2", ADMIN)
    assert U.obtener(db, "ej2")["activo"] == 1
    assert login(client, "ej2").status_code == 302


# ---------------------------------------------------------------- contraseña y bloqueo

def test_restablecer_desbloquea_y_obliga_a_cambiar(client, app, db):
    for _ in range(app.config["MAX_LOGIN_ATTEMPTS"]):
        login(client, "ej1", "incorrecta")
    assert U.esta_bloqueado(U.obtener(db, "ej1"))
    with pytest.raises(U.ErrorUsuario):
        U.restablecer(db, "ej1", "corta", ADMIN)
    U.restablecer(db, "ej1", "Nueva2026", ADMIN)
    fila = U.obtener(db, "ej1")
    assert not U.esta_bloqueado(fila) and fila["debe_cambiar"] == 1
    assert login(client, "ej1", "Nueva2026").status_code == 302


def test_desbloquear_sin_cambiar_contrasena(client, app, db):
    for _ in range(app.config["MAX_LOGIN_ATTEMPTS"]):
        login(client, "ej1", "incorrecta")
    login(client, "admin")
    client.post("/admin/usuarios/ej1/desbloquear")
    client.post("/logout")
    assert login(client, "ej1", CONTRASENA).status_code == 302
