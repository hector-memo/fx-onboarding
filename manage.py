"""Comandos de administración.

  python manage.py init                       crea la base y carga datos de ejemplo
  python manage.py init --sin-ejemplos        crea la base solo con el usuario admin
  python manage.py init --forzar              borra la base existente y la vuelve a crear
  python manage.py crear-usuario USUARIO "Nombre" correo@x.com --rol ejecutivo --contrasena Temporal2026!
  python manage.py restablecer-contrasena USUARIO Temporal2026!

En el día a día es más cómodo usar la pantalla Admin › Usuarios. Estos comandos sirven para
crear el primer administrador o recuperar el acceso si ningún administrador puede entrar.
"""
import argparse
import sqlite3
import sys
from pathlib import Path

from config import Config


def _borrar_base(ruta):
    for sufijo in ("", "-wal", "-shm"):
        Path(str(ruta) + sufijo).unlink(missing_ok=True)


def cmd_init(args):
    ruta = Path(Config.DATABASE)
    if ruta.exists():
        if not args.forzar:
            print(f"La base {ruta} ya existe. Usa --forzar para borrarla y crearla de nuevo.")
            return 1
        _borrar_base(ruta)
        print("Base anterior eliminada.")

    from app import create_app
    from app import datos_ejemplo
    from app.db import get_db

    app = create_app()
    with app.app_context():
        db = get_db()
        if args.sin_ejemplos:
            datos_ejemplo.cargar_usuarios(db, solo_admin=True)
            print("Base creada con el usuario admin (contraseña temporal: Admin2026!).")
        else:
            archivo = datos_ejemplo.cargar_todo(db)
            print("Base creada con datos de ejemplo.")
            print("Usuarios (contraseñas temporales, se piden cambiar al entrar):")
            for usuario, nombre, _correo, rol, contrasena in datos_ejemplo.USUARIOS:
                print(f"  {usuario:<10} {rol:<10} {contrasena:<16} {nombre}")
            print(f"Archivo de ejemplo para la carga inicial: {archivo}")
    return 0


def cmd_crear_usuario(args):
    from app import create_app
    from app.db import get_db
    from app.usuarios import ACCION_ALTA, crear_usuario, registrar_historial
    from app.validaciones import validar_contrasena_nueva

    error = validar_contrasena_nueva(args.contrasena)
    if error:
        print(error)
        return 1
    app = create_app()
    with app.app_context():
        try:
            crear_usuario(get_db(), args.usuario, args.nombre, args.correo, args.rol, args.contrasena)
            registrar_historial(get_db(), args.usuario.lower(), "consola", ACCION_ALTA, f"Rol: {args.rol}")
        except sqlite3.IntegrityError:
            print(f"El usuario '{args.usuario}' ya existe.")
            return 1
        except ValueError as e:
            print(e)
            return 1
    print(f"Usuario '{args.usuario.lower()}' creado. Deberá cambiar la contraseña al entrar.")
    return 0


def cmd_restablecer(args):
    from app import create_app
    from app.db import get_db
    from app.usuarios import ACCION_CONTRASENA, registrar_historial, restablecer_contrasena
    from app.validaciones import validar_contrasena_nueva

    error = validar_contrasena_nueva(args.contrasena)
    if error:
        print(error)
        return 1
    app = create_app()
    with app.app_context():
        if not restablecer_contrasena(get_db(), args.usuario, args.contrasena):
            print(f"El usuario '{args.usuario}' no existe.")
            return 1
        registrar_historial(get_db(), args.usuario.lower(), "consola", ACCION_CONTRASENA,
                            "Contraseña temporal; deberá cambiarla al entrar")
    print("Contraseña restablecida. Deberá cambiarla al entrar; el bloqueo por intentos fallidos se reinició.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Administración de FX Onboarding")
    sub = parser.add_subparsers(dest="comando", required=True)

    p_init = sub.add_parser("init", help="Crea la base de datos")
    p_init.add_argument("--sin-ejemplos", action="store_true", help="Solo crea el usuario admin")
    p_init.add_argument("--forzar", action="store_true", help="Borra la base existente")
    p_init.set_defaults(func=cmd_init)

    p_usr = sub.add_parser("crear-usuario", help="Crea un usuario de la app")
    p_usr.add_argument("usuario")
    p_usr.add_argument("nombre")
    p_usr.add_argument("correo")
    p_usr.add_argument("--rol", choices=["admin", "ejecutivo"], default="ejecutivo")
    p_usr.add_argument("--contrasena", required=True, help="Contraseña temporal")
    p_usr.set_defaults(func=cmd_crear_usuario)

    p_rst = sub.add_parser("restablecer-contrasena", help="Pone una contraseña temporal")
    p_rst.add_argument("usuario")
    p_rst.add_argument("contrasena")
    p_rst.set_defaults(func=cmd_restablecer)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
