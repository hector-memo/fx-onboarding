"""Carga inicial de clientes existentes desde Excel."""
import pytest

from app import carga as K
from app import padron as P
from conftest import cliente_padron


def fila_cliente(contrato="40400000001", **cambios):
    datos = {
        "contrato": contrato, "nombre_cliente": f"Cliente {contrato}", "rfc": "GHR130613GG7", "region": "Sur",
        "segmento": "Corporativo", "zona": "Playa del Carmen", "grupo_spot": "Spot Preferente",
        "multiaprobacion": "Sí", "multiabono": "No", "divisas": "USDMXN, eurmxn", "limite_operacion": 750000,
        "limite_diario": 3000000, "ejecutivo_asignado": "ej1", "fecha_alta": "15/03/2021",
    }
    datos.update(cambios)
    return [datos[clave] for clave, _ in K.COLUMNAS_CLIENTES]


@pytest.fixture
def archivo(tmp_path, cat):
    def _crear(clientes, usuarios):
        libro = K.generar_plantilla(cat, ["ej1", "ej2"])
        for hoja, filas in ((libro[K.HOJA_CLIENTES], clientes), (libro[K.HOJA_USUARIOS], usuarios)):
            for i, fila in enumerate(filas, start=2):
                for j, valor in enumerate(fila, start=1):
                    hoja.cell(row=i, column=j, value=valor)
        ruta = tmp_path / "carga.xlsx"
        libro.save(ruta)
        return ruta
    return _crear


def _campos_con_error(resultado):
    return {(e["hoja"], e["fila"], e["campo"]) for e in resultado.errores}


def test_carga_valida_se_importa(db, cat, archivo):
    ruta = archivo([fila_cliente()], [["40400000001", "72000001", "Mariana Solís"], ["40400000001", "72000002", "Héctor Ruiz"]])
    resultado = K.analizar(db, ruta, cat)
    assert resultado.errores == [] and len(resultado.clientes) == 1 and len(resultado.usuarios) == 2
    conteo = K.importar(db, resultado, "admin", "carga.xlsx")
    assert conteo == {"contratos": 1, "usuarios": 2, "omitidos": 0, "errores": 0}
    cliente = P.obtener_cliente(db, "40400000001")
    assert cliente["origen"] == "Carga inicial" and cliente["fecha_alta"].startswith("2021-03-15")
    assert cliente["divisas"] == "EURMXN,USDMXN"
    assert cliente["zona"] == "Playa del Carmen"
    assert len(P.usuarios_de(db, "40400000001")) == 2
    assert db.execute("SELECT COUNT(*) FROM cargas").fetchone()[0] == 1


def test_ceros_perdidos_por_excel(db, cat, archivo):
    ruta = archivo([fila_cliente(contrato=4040000001)], [["04040000001", "72000001", "Mariana Solís"]])
    resultado = K.analizar(db, ruta, cat)
    mensajes = [e["mensaje"] for e in resultado.errores if e["hoja"] == K.HOJA_CLIENTES and e["fila"] == 2]
    assert any("Texto" in m for m in mensajes)
    assert resultado.clientes == []


def test_valores_fuera_de_catalogo_y_ejecutivo_inexistente(db, cat, archivo):
    ruta = archivo([fila_cliente(region="Atlántico", ejecutivo_asignado="plopez")],
                   [["40400000001", "72000001", "Mariana Solís"]])
    errores = _campos_con_error(K.analizar(db, ruta, cat))
    assert (K.HOJA_CLIENTES, 2, "Región") in errores
    assert (K.HOJA_CLIENTES, 2, "Ejecutivo asignado") in errores
    assert (K.HOJA_USUARIOS, 2, "Contrato de banca electrónica") in errores  # su contrato tiene errores


def test_plantilla_sin_columnas_eliminadas(cat):
    libro = K.generar_plantilla(cat, ["ej1"])
    encabezados = [c.value for c in libro[K.HOJA_CLIENTES][1]]
    assert "Zona" in encabezados
    assert not any("CLABE" in e or "KYC" in e for e in encabezados)
    validadas = {str(dv.sqref) for dv in libro[K.HOJA_CLIENTES].data_validations.dataValidation}
    assert not any(r.startswith("F") for r in validadas)  # la zona (columna F) ya no tiene lista desplegable


def test_carga_sin_limites(db, cat, archivo):
    ruta = archivo([fila_cliente(limite_operacion=None, limite_diario=None)],
                   [["40400000001", "72000001", "Mariana Solís"]])
    resultado = K.analizar(db, ruta, cat)
    assert resultado.errores == []
    K.importar(db, resultado, "admin", "carga.xlsx")
    assert P.obtener_cliente(db, "40400000001")["limite_diario"] is None


def test_divisa_que_no_es_par_valido(db, cat, archivo):
    ruta = archivo([fila_cliente(divisas="USDMXN,USD")], [["40400000001", "72000001", "Mariana Solís"]])
    errores = K.analizar(db, ruta, cat).errores
    assert any(e["campo"] == "Divisas autorizadas" and "USD." in e["mensaje"] for e in errores)


def test_contrato_repetido_en_el_archivo(db, cat, archivo):
    ruta = archivo([fila_cliente(), fila_cliente()], [["40400000001", "72000001", "Mariana Solís"]])
    resultado = K.analizar(db, ruta, cat)
    assert (K.HOJA_CLIENTES, 3, "Contrato de banca electrónica") in _campos_con_error(resultado)
    assert len(resultado.clientes) == 1  # la primera aparición sigue siendo válida


def test_contrato_del_padron_se_omite_pero_acepta_usuarios_nuevos(db, cat, archivo):
    cliente_padron(db, "40400000001", "ej1", usuarios=("72000001",))
    ruta = archivo([fila_cliente()], [["40400000001", "72000001", "Ya existe"], ["40400000001", "72000009", "Nuevo"]])
    resultado = K.analizar(db, ruta, cat)
    assert resultado.errores == []
    assert len(resultado.omitidos) == 2  # el contrato y el usuario que ya existían
    assert [d["numero_usuario"] for _, d in resultado.usuarios] == ["72000009"]
    K.importar(db, resultado, "admin", "carga.xlsx")
    assert P.existe_usuario(db, "40400000001", "72000009")


def test_usuarios_invalidos(db, cat, archivo):
    ruta = archivo([fila_cliente()], [
        ["40400000001", "72000001", "Mariana Solís"],
        ["40400000001", "72000001", "Repetido"],
        ["40499999999", "72000002", "Contrato inexistente"],
        ["40400000001", "7200003", "Siete dígitos"],
    ])
    errores = _campos_con_error(K.analizar(db, ruta, cat))
    assert (K.HOJA_USUARIOS, 3, "Número de usuario") in errores
    assert (K.HOJA_USUARIOS, 4, "Contrato de banca electrónica") in errores
    assert (K.HOJA_USUARIOS, 5, "Número de usuario") in errores


def test_contrato_sin_usuarios_es_error(db, cat, archivo):
    resultado = K.analizar(db, archivo([fila_cliente()], []), cat)
    assert resultado.clientes == []
    assert (K.HOJA_CLIENTES, 2, "Contrato de banca electrónica") in _campos_con_error(resultado)


def test_mismo_usuario_en_dos_contratos(db, cat, archivo):
    ruta = archivo([fila_cliente("40400000001"), fila_cliente("40400000002")],
                   [["40400000001", "72000001", "Mariana Solís"], ["40400000002", "72000001", "Mariana Solís"]])
    resultado = K.analizar(db, ruta, cat)
    assert resultado.errores == [] and len(resultado.usuarios) == 2


def test_solo_se_importan_las_filas_validas(db, cat, archivo):
    ruta = archivo([fila_cliente("40400000001"), fila_cliente("40400000002", rfc="XXX")],
                   [["40400000001", "72000001", "Válido"], ["40400000002", "72000002", "Contrato con error"]])
    resultado = K.analizar(db, ruta, cat)
    K.importar(db, resultado, "admin", "carga.xlsx")
    assert P.obtener_cliente(db, "40400000001") is not None
    assert P.obtener_cliente(db, "40400000002") is None


def test_hoja_faltante(db, cat, tmp_path):
    from openpyxl import Workbook
    ruta = tmp_path / "vacio.xlsx"
    Workbook().save(ruta)
    resultado = K.analizar(db, ruta, cat)
    assert any("Falta la hoja" in e["mensaje"] for e in resultado.errores)


def test_archivo_que_no_es_excel(db, cat, tmp_path):
    ruta = tmp_path / "falso.xlsx"
    ruta.write_text("no soy un excel", encoding="utf-8")
    resultado = K.analizar(db, ruta, cat)
    assert resultado.errores and resultado.filas_validas == 0


def test_flujo_web_de_carga(client, db, cat, archivo):
    from conftest import login
    ruta = archivo([fila_cliente()], [["40400000001", "72000001", "Mariana Solís"]])
    login(client, "admin")
    with open(ruta, "rb") as f:
        respuesta = client.post("/admin/padron/carga", data={"archivo": (f, "carga.xlsx")},
                                content_type="multipart/form-data")
    assert respuesta.status_code == 200 and "Vista previa" in respuesta.get_data(as_text=True)
    respuesta = client.post("/admin/padron/carga/confirmar")
    assert respuesta.status_code == 302
    assert P.obtener_cliente(db, "40400000001") is not None
