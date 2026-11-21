"""Configuración central de la aplicación.

Los valores se leen del archivo .env (ver .env.example). Cada valor tiene un
default razonable para que la app arranque en un equipo de desarrollo.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _bool(nombre, defecto=False):
    valor = os.getenv(nombre)
    if valor is None:
        return defecto
    return valor.strip().lower() in ("1", "true", "si", "sí", "yes", "on")


def _int(nombre, defecto):
    try:
        return int(os.getenv(nombre, defecto))
    except (TypeError, ValueError):
        return defecto


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "cambia-esta-clave")
    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = _int("PORT", 8000)

    # Rutas de archivos
    DATABASE = os.getenv("DATABASE", str(BASE_DIR / "data" / "fx_onboarding.db"))
    CATALOGOS = os.getenv("CATALOGOS", str(BASE_DIR / "catalogos.json"))
    BACKUP_DIR = os.getenv("BACKUP_DIR", str(BASE_DIR / "backups"))
    LOG_FILE = os.getenv("LOG_FILE", str(BASE_DIR / "logs" / "app.log"))
    OUTBOX_DIR = os.getenv("OUTBOX_DIR", str(BASE_DIR / "outbox"))
    UPLOAD_DIR = os.getenv("UPLOAD_DIR", str(BASE_DIR / "data" / "cargas"))
    DATOS_EJEMPLO_DIR = str(BASE_DIR / "datos_ejemplo")

    # Reglas de operación
    TIMEZONE = os.getenv("TIMEZONE", "America/Mexico_City")
    SESSION_MINUTES = _int("SESSION_MINUTES", 30)
    MAX_LOGIN_ATTEMPTS = _int("MAX_LOGIN_ATTEMPTS", 5)
    LOCKOUT_MINUTES = _int("LOCKOUT_MINUTES", 15)
    SLA_DIAS_HABILES = _int("SLA_DIAS_HABILES", 2)
    PAGE_SIZE = _int("PAGE_SIZE", 25)
    BACKUP_KEEP = _int("BACKUP_KEEP", 14)
    MAX_UPLOAD_MB = _int("MAX_UPLOAD_MB", 5)
    RESPALDO_AUTOMATICO = True

    # Correo
    MAIL_ENABLED = _bool("MAIL_ENABLED", False)
    MAIL_HOST = os.getenv("MAIL_HOST", "localhost")
    MAIL_PORT = _int("MAIL_PORT", 587)
    MAIL_USE_TLS = _bool("MAIL_USE_TLS", True)
    MAIL_USE_SSL = _bool("MAIL_USE_SSL", False)
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
    MAIL_FROM = os.getenv("MAIL_FROM", "FX Onboarding <no-responder@localhost>")
    MAIL_TIMEOUT = _int("MAIL_TIMEOUT", 15)

    # Sesión y CSRF
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    WTF_CSRF_TIME_LIMIT = None
