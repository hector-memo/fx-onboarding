"""Carga inicial de clientes existentes desde Excel.

Flujo: plantilla -> el admin la llena -> `analizar` valida todo y arma la vista
previa -> el admin confirma -> `importar` guarda solo las filas válidas en una
sola transacción.
"""
import logging
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from . import padron
from . import validaciones as V
from .constantes import ETIQUETAS, NO, ORIGEN_CARGA, ROL_EJECUTIVO, SI
from .db import transaccion
from .utils import ahora_str, parse_fecha_alta

log = logging.getLogger("fx")

HOJA_CLIENTES = "Clientes"
HOJA_USUARIOS = "Usuarios"
FILAS_PLANTILLA = 1000

COLUMNAS_CLIENTES = [
    ("contrato", "Contrato"),
    ("nombre_cliente", "Nombre de cliente"),
    ("rfc", "RFC"),
    ("region", "Región"),
    ("segmento", "Segmento"),
    ("zona", "Zona"),
    ("grupo_spot", "Grupo spot"),
    ("multiaprobacion", "Multiaprobación"),
    ("multiabono", "Multiabono"),
    ("divisas", "Divisas autorizadas"),
    ("limite_operacion", "Límite por operación"),
    ("limite_diario", "Límite diario"),
    ("ejecutivo_asignado", "Ejecutivo asignado"),
    ("fecha_alta", "Fecha de alta en plataforma"),
]
COLUMNAS_USUARIOS = [
    ("contrato", "Contrato"),
    ("numero_usuario", "Número de usuario"),
    ("nombre_completo", "Nombre completo"),
]
COLUMNAS_OPCIONALES = {"fecha_alta"}
DIGITOS = {"contrato": 11, "numero_usuario": 8}


@dataclass
class Resultado:
    clientes: list = field(default_factory=list)  # [(fila, datos)]
    usuarios: list = field(default_factory=list)  # [(fila, datos)]
    errores: list = field(default_factory=list)   # [{hoja, fila, campo, mensaje}]
    omitidos: list = field(default_factory=list)  # [{hoja, fila, motivo}]

    @property
    def filas_validas(self):
        return len(self.clientes) + len(self.usuarios)

    @property
    def filas_con_error(self):
        return len({(e["hoja"], e["fila"]) for e in self.errores})


# ---------------------------------------------------------------- plantilla

def generar_plantilla(catalogo, ejecutivos):
    """Libro con hojas Instrucciones, Clientes, Usuarios y una hoja oculta de listas."""
    libro = Workbook()
    instrucciones = libro.active
    instrucciones.title = "Instrucciones"
    hoja_c = libro.create_sheet(HOJA_CLIENTES)
    hoja_u = libro.create_sheet(HOJA_USUARIOS)
    listas = libro.create_sheet("Listas")

    for hoja, columnas in ((hoja_c, COLUMNAS_CLIENTES), (hoja_u, COLUMNAS_USUARIOS)):
        hoja.append([titulo for _, titulo in columnas])
        for i, celda in enumerate(hoja[1], start=1):
            celda.font = Font(bold=True, color="FFFFFF")
            celda.fill = PatternFill("solid", fgColor="1F4E79")
            hoja.column_dimensions[get_column_letter(i)].width = max(len(celda.value) + 4, 16)
        hoja.freeze_panes = "A2"

    # Columnas de dígitos en formato Texto para que Excel no quite ceros a la izquierda.
    for hoja, columnas in ((hoja_c, COLUMNAS_CLIENTES), (hoja_u, COLUMNAS_USUARIOS)):
        for i, (clave, _) in enumerate(columnas, start=1):
            if clave in DIGITOS:
                for fila in range(2, FILAS_PLANTILLA + 1):
                    hoja.cell(row=fila, column=i).number_format = "@"

    valores_listas = [
        ("Regiones", catalogo["regiones"]),
        ("Segmentos", catalogo["segmentos"]),
        ("Grupos spot", catalogo["grupos_spot"]),
        ("Sí/No", [SI, NO]),
        ("Ejecutivos", list(ejecutivos)),
        ("Divisas", catalogo["divisas"]),
    ]
    rangos = {}
    for col, (titulo, valores) in enumerate(valores_listas, start=1):
        listas.cell(row=1, column=col, value=titulo)
        for fila, valor in enumerate(valores, start=2):
            listas.cell(row=fila, column=col, value=valor)
        letra = get_column_letter(col)
        rangos[titulo] = f"Listas!${letra}$2:${letra}${max(len(valores), 1) + 1}"
    listas.sheet_state = "hidden"

    validaciones = {
        "region": "Regiones", "segmento": "Segmentos", "grupo_spot": "Grupos spot",
        "multiaprobacion": "Sí/No", "multiabono": "Sí/No", "ejecutivo_asignado": "Ejecutivos",
    }
    for i, (clave, _) in enumerate(COLUMNAS_CLIENTES, start=1):
        if clave in validaciones:
            letra = get_column_letter(i)
            dv = DataValidation(type="list", formula1=rangos[validaciones[clave]], allow_blank=True)
            dv.error = "Selecciona un valor de la lista."
            dv.errorTitle = "Valor no válido"
            dv.showErrorMessage = True
            hoja_c.add_data_validation(dv)
            dv.add(f"{letra}2:{letra}{FILAS_PLANTILLA}")

    lineas = [
        "Plantilla de carga inicial de clientes existentes",
        "",
        "1. Hoja 'Clientes': un renglón por contrato, con sus datos de empresa, permisos y ejecutivo asignado. La zona es texto libre.",
        "2. Hoja 'Usuarios': un renglón por usuario. Cada usuario debe pertenecer a un contrato de la hoja Clientes o ya existente en el padrón.",
        "3. Contrato (11 dígitos) y número de usuario (8) ya tienen formato Texto. No cambies ese formato o Excel quitará los ceros a la izquierda.",
        "4. Divisas autorizadas: pares separados por coma, por ejemplo 'USDMXN,EURMXN'. Valores válidos: " + ", ".join(catalogo["divisas"]) + ".",
        "5. Límites en USD: opcionales (deja la celda vacía si no aplica). Si se capturan, mayores a 0; con ambos, el diario debe ser mayor o igual al de operación.",
        "6. Ejecutivo asignado: el usuario de la app (por ejemplo 'mperez'). Sin ejecutivo, la fila no se importa.",
        "7. Fecha de alta en plataforma: opcional, formato DD/MM/AAAA.",
        "8. Un contrato nuevo necesita al menos un usuario válido en la hoja Usuarios.",
        "9. Los contratos y usuarios que ya estén en el padrón se omiten y se reportan.",
        "",
        "Ejemplo (no lo copies a las otras hojas):",
    ]
    for linea in lineas:
        instrucciones.append([linea])
    instrucciones["A1"].font = Font(bold=True, size=14)
    instrucciones.append([titulo for _, titulo in COLUMNAS_CLIENTES])
    instrucciones.append(["01234567890", "Ejemplo Comercial SA de CV", "ECO990101AB1", catalogo["regiones"][0],
                          catalogo["segmentos"][0], "Monterrey Centro", catalogo["grupos_spot"][0], SI, NO,
                          ",".join(catalogo["divisas"][:2]), 250000, 1000000,
                          ejecutivos[0] if ejecutivos else "usuario_ejecutivo", "15/01/2024"])
    instrucciones.column_dimensions["A"].width = 120
    return libro


# ---------------------------------------------------------------- lectura

def _normalizar_encabezado(texto):
    sin_acentos = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return " ".join(sin_acentos.lower().split())


def _valor_celda(valor):
    """(texto, era_numero). Las celdas numéricas se convierten sin '.0'."""
    if valor is None:
        return "", False
    if isinstance(valor, bool):
        return (SI if valor else NO), False
    if isinstance(valor, int):
        return str(valor), True
    if isinstance(valor, float):
        return (str(int(valor)) if valor.is_integer() else str(valor)), True
    if isinstance(valor, datetime):
        return valor.strftime("%d/%m/%Y"), False
    if isinstance(valor, date):
        return valor.strftime("%d/%m/%Y"), False
    return str(valor).strip(), False


def _celda_vacia(valor):
    return valor is None or (isinstance(valor, str) and not valor.strip())


def _leer_hoja(libro, nombre, columnas, resultado):
    if nombre not in libro.sheetnames:
        resultado.errores.append({"hoja": nombre, "fila": "-", "campo": "-", "mensaje": f"Falta la hoja '{nombre}'."})
        return []
    filas = libro[nombre].iter_rows(values_only=True)
    encabezado = next(filas, None)
    if not encabezado:
        resultado.errores.append({"hoja": nombre, "fila": 1, "campo": "-", "mensaje": "La hoja no tiene encabezados."})
        return []
    indice = {_normalizar_encabezado(t): i for i, t in enumerate(encabezado) if t is not None}
    faltan = [t for c, t in columnas if c not in COLUMNAS_OPCIONALES and _normalizar_encabezado(t) not in indice]
    if faltan:
        resultado.errores.append({"hoja": nombre, "fila": 1, "campo": "-",
                                  "mensaje": "Faltan columnas: " + ", ".join(faltan) + ". Usa la plantilla."})
        return []
    salida = []
    for numero, fila in enumerate(filas, start=2):
        if fila is None or all(_celda_vacia(v) for v in fila):
            continue
        datos, numericos = {}, set()
        for clave, titulo in columnas:
            i = indice.get(_normalizar_encabezado(titulo))
            valor = fila[i] if i is not None and i < len(fila) else None
            texto, era_numero = _valor_celda(valor)
            datos[clave] = texto
            if era_numero:
                numericos.add(clave)
        salida.append((numero, datos, numericos))
    return salida


def _revisar_digitos(datos, numericos, errores):
    for campo, esperado in DIGITOS.items():
        valor = datos.get(campo, "")
        if campo in numericos and valor.isdigit() and len(valor) < esperado and campo not in errores:
            errores[campo] = (f"Tiene {len(valor)} dígitos y se esperaban {esperado}. Probablemente Excel quitó los "
                              "ceros a la izquierda: da formato Texto a la columna y vuelve a capturar el valor.")
        elif campo in numericos and valor.isdigit() and len(valor) < esperado:
            errores[campo] += " (Revisa que la columna tenga formato Texto.)"


def _agregar_errores(resultado, hoja, fila, errores):
    for campo, mensaje in errores.items():
        resultado.errores.append({"hoja": hoja, "fila": fila, "campo": ETIQUETAS.get(campo, campo), "mensaje": mensaje})


# ---------------------------------------------------------------- análisis e importación

def analizar(db, ruta, catalogo):
    """Valida el archivo completo sin guardar nada."""
    resultado = Resultado()
    try:
        libro = load_workbook(ruta, read_only=True, data_only=True)
    except Exception:  # archivo dañado o que no es .xlsx
        resultado.errores.append({"hoja": "-", "fila": "-", "campo": "-",
                                  "mensaje": "No se pudo leer el archivo. Verifica que sea un .xlsx válido."})
        return resultado
    try:
        filas_clientes = _leer_hoja(libro, HOJA_CLIENTES, COLUMNAS_CLIENTES, resultado)
        filas_usuarios = _leer_hoja(libro, HOJA_USUARIOS, COLUMNAS_USUARIOS, resultado)
    finally:
        libro.close()

    ejecutivos = {r["usuario"] for r in db.execute(
        "SELECT usuario FROM usuarios WHERE rol = ? AND activo = 1", (ROL_EJECUTIVO,))}
    estado = {}        # contrato -> "valido" | "error" | "padron"
    filas_vistas = {}  # contrato -> fila donde apareció primero
    validos = {}       # contrato -> (fila, datos)

    for fila, crudo, numericos in filas_clientes:
        d = V.normalizar(crudo)
        errores = V.validar_cliente_padron(d, catalogo)
        _revisar_digitos(d, numericos, errores)
        if not d.get("ejecutivo_asignado"):
            errores["ejecutivo_asignado"] = V.OBLIGATORIO
        elif d["ejecutivo_asignado"] not in ejecutivos:
            errores["ejecutivo_asignado"] = f"El ejecutivo '{d['ejecutivo_asignado']}' no existe o no está activo."
        fecha = parse_fecha_alta(d.get("fecha_alta"))
        if fecha is False:
            errores["fecha_alta"] = "Fecha inválida; usa DD/MM/AAAA."
        else:
            d["fecha_alta"] = fecha
        contrato = d.get("contrato", "")
        if contrato and contrato in filas_vistas:
            errores["contrato"] = f"Contrato repetido en el archivo (ya aparece en la fila {filas_vistas[contrato]})."
        elif contrato:
            filas_vistas[contrato] = fila

        if errores:
            _agregar_errores(resultado, HOJA_CLIENTES, fila, errores)
            estado.setdefault(contrato, "error")
        elif padron.obtener_cliente(db, contrato) is not None:
            resultado.omitidos.append({"hoja": HOJA_CLIENTES, "fila": fila, "motivo": "El contrato ya existe en el padrón."})
            estado[contrato] = "padron"
        else:
            validos[contrato] = (fila, d)
            estado[contrato] = "valido"

    usuarios_por_contrato = {}
    vistos = {}
    for fila, crudo, numericos in filas_usuarios:
        d = V.normalizar(crudo)
        errores = V.validar_usuario_padron(d)
        _revisar_digitos(d, numericos, errores)
        contrato, numero = d.get("contrato", ""), d.get("numero_usuario", "")
        situacion = None
        if "contrato" not in errores and "numero_usuario" not in errores:
            if (contrato, numero) in vistos:
                errores["numero_usuario"] = (f"Usuario repetido para este contrato (ya aparece en la fila "
                                             f"{vistos[(contrato, numero)]}).")
            else:
                vistos[(contrato, numero)] = fila
            situacion = estado.get(contrato)
            if situacion is None and padron.obtener_cliente(db, contrato) is not None:
                situacion = "padron"
            if situacion == "error":
                errores["contrato"] = "El contrato tiene errores en la hoja Clientes."
            elif situacion is None:
                errores["contrato"] = "El contrato no está en la hoja Clientes ni en el padrón."

        if errores:
            _agregar_errores(resultado, HOJA_USUARIOS, fila, errores)
        elif situacion == "padron" and padron.existe_usuario(db, contrato, numero):
            resultado.omitidos.append({"hoja": HOJA_USUARIOS, "fila": fila,
                                       "motivo": "El usuario ya existe en este contrato del padrón."})
        else:
            resultado.usuarios.append((fila, d))
            usuarios_por_contrato[contrato] = usuarios_por_contrato.get(contrato, 0) + 1

    for contrato, (fila, d) in validos.items():
        if usuarios_por_contrato.get(contrato):
            resultado.clientes.append((fila, d))
        else:
            _agregar_errores(resultado, HOJA_CLIENTES, fila,
                             {"contrato": "El contrato no tiene usuarios válidos en la hoja Usuarios."})
    return resultado


def importar(db, resultado, usuario, archivo):
    """Guarda las filas válidas de un análisis. Todo o nada."""
    contratos = usuarios = omitidos_extra = 0
    with transaccion(db):
        for _fila, d in resultado.clientes:
            if padron.obtener_cliente(db, d["contrato"]) is not None:
                omitidos_extra += 1  # alguien lo agregó entre la vista previa y la confirmación
                continue
            padron.crear_cliente(db, d, usuario, ORIGEN_CARGA, fecha_alta=d.get("fecha_alta"))
            contratos += 1
        for _fila, d in resultado.usuarios:
            if (padron.obtener_cliente(db, d["contrato"]) is None
                    or padron.existe_usuario(db, d["contrato"], d["numero_usuario"])):
                omitidos_extra += 1
                continue
            padron.agregar_usuario(db, d["contrato"], d["numero_usuario"], d["nombre_completo"], usuario, ORIGEN_CARGA)
            usuarios += 1
        omitidos = len(resultado.omitidos) + omitidos_extra
        db.execute(
            "INSERT INTO cargas (fecha, usuario, archivo, validas, con_error, omitidas) VALUES (?, ?, ?, ?, ?, ?)",
            (ahora_str(), usuario, archivo, contratos + usuarios, resultado.filas_con_error, omitidos),
        )
    log.info("Carga inicial '%s' por %s: %s contratos, %s usuarios, %s omitidos, %s filas con error",
             archivo, usuario, contratos, usuarios, omitidos, resultado.filas_con_error)
    return {"contratos": contratos, "usuarios": usuarios, "omitidos": omitidos, "errores": resultado.filas_con_error}


def cargas_recientes(db, limite=10):
    return db.execute("SELECT * FROM cargas ORDER BY id DESC LIMIT ?", (limite,)).fetchall()
