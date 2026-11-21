"""Fixtures y datos de apoyo para las pruebas."""
import pytest

from app import create_app
from app import padron
from app.catalogos import cargar as cargar_catalogos
from app.constantes import ORIGEN_CARGA
from app.db import get_db, transaccion
from app.usuarios import crear_usuario

CONTRASENA = "Prueba2026!"
ADMIN = {"usuario": "admin", "rol": "admin", "correo": "admin@ejemplo.com", "nombre": "Admin Pruebas"}
EJ1 = {"usuario": "ej1", "rol": "ejecutivo", "correo": "ej1@ejemplo.com", "nombre": "Ejecutivo Uno"}
EJ2 = {"usuario": "ej2", "rol": "ejecutivo", "correo": "ej2@ejemplo.com", "nombre": "Ejecutivo Dos"}


def datos_alta(**cambios):
    datos = {
        "contrato": "40100000001", "nombre_cliente": "Cliente Prueba SA", "rfc": "CPR990101AB1",
        "region": "Norte", "segmento": "Corporativo", "zona": "Monterrey Centro",
        "numero_usuario": "80000001", "nombre_completo": "Usuario Prueba",
        "correo_notificaciones": "ej1@ejemplo.com",
        "grupo_spot": "Spot Básico", "multiaprobacion": "No", "multiabono": "No", "divisas": ["USDMXN"],
        "limite_operacion": "100000", "limite_diario": "500000", "comentarios": "",
    }
    datos.update(cambios)
    return datos


def datos_cambio(**cambios):
    """Por defecto, permisos idénticos a los de `cliente_padron` (sin cambios)."""
    datos = {
        "contrato": "40100000001", "grupo_spot": "Spot Básico", "multiaprobacion": "No", "multiabono": "No",
        "divisas": ["USDMXN"], "limite_operacion": "100000", "limite_diario": "500000",
        "motivo_cambio": "Ajuste solicitado por el cliente",
        "correo_notificaciones": "ej1@ejemplo.com",
    }
    datos.update(cambios)
    return datos


def cliente_padron(db, contrato, ejecutivo, usuarios=("80000001",), **cambios):
    datos = {
        "contrato": contrato, "nombre_cliente": f"Cliente {contrato}", "rfc": "CPR990101AB1",
        "region": "Norte", "segmento": "Corporativo", "zona": "Monterrey Centro", "grupo_spot": "Spot Básico",
        "multiaprobacion": "No", "multiabono": "No", "divisas": "USDMXN", "limite_operacion": 100000.0,
        "limite_diario": 500000.0, "ejecutivo_asignado": ejecutivo,
    }
    datos.update(cambios)
    with transaccion(db):
        padron.crear_cliente(db, datos, "admin", ORIGEN_CARGA)
        for numero in usuarios:
            padron.agregar_usuario(db, contrato, numero, f"Usuario {numero}", "admin", ORIGEN_CARGA)
    return padron.obtener_cliente(db, contrato)


@pytest.fixture
def app(tmp_path):
    aplicacion = create_app({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "DATABASE": str(tmp_path / "prueba.db"),
        "BACKUP_DIR": str(tmp_path / "backups"),
        "OUTBOX_DIR": str(tmp_path / "outbox"),
        "UPLOAD_DIR": str(tmp_path / "cargas"),
        "LOG_FILE": str(tmp_path / "app.log"),
        "DATOS_EJEMPLO_DIR": str(tmp_path / "datos_ejemplo"),
        "MAIL_ENABLED": False,
        "RESPALDO_AUTOMATICO": False,
    })
    with aplicacion.app_context():
        db = get_db()
        for u in (ADMIN, EJ1, EJ2):
            crear_usuario(db, u["usuario"], u["nombre"], u["correo"], u["rol"], CONTRASENA, debe_cambiar=False)
    return aplicacion


@pytest.fixture
def db(app):
    with app.app_context():
        yield get_db()


@pytest.fixture
def cat(db):
    return cargar_catalogos()


@pytest.fixture
def client(app):
    return app.test_client()


def login(client, usuario, contrasena=CONTRASENA):
    return client.post("/login", data={"usuario": usuario, "contrasena": contrasena})
