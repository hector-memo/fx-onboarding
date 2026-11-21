"""Arranque de la aplicación con waitress (servidor apto para la red interna).

Uso:  python run.py
"""
from waitress import serve

from app import create_app
from app.respaldo import respaldo_diario

app = create_app()

if __name__ == "__main__":
    host, port = app.config["HOST"], app.config["PORT"]
    with app.app_context():
        respaldo_diario()
    print(f"FX Onboarding escuchando en http://{host}:{port}  (Ctrl+C para detener)")
    if host == "0.0.0.0":
        print("Desde otros equipos de la red usa http://<IP-de-este-equipo>:" + str(port))
    serve(app, host=host, port=port, threads=8)
