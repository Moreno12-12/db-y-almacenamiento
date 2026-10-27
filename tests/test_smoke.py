"""Pruebas smoke del pipeline UrbanRush (sin conexion a red).

Verifican que:
1. Todos los scripts Python del proyecto compilan.
2. Funciones puras clave se comportan como se espera.
"""
import importlib.util
import py_compile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SCRIPTS = RAIZ / "scripts"


def cargar_modulo(nombre, ruta):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_compilar_scripts():
    """Todos los .py del proyecto compilan sin errores de sintaxis."""
    archivos = sorted(SCRIPTS.glob("*.py"))
    archivos += [RAIZ / "conexion.py", RAIZ / "iac_setup.py"]
    assert len(archivos) >= 15, f"Solo se encontraron {len(archivos)} scripts"
    for f in archivos:
        py_compile.compile(str(f), doraise=True)


def test_convertir_objectids():
    """ObjectId de MongoDB se convierte recursivamente a string."""
    from bson import ObjectId
    dl = cargar_modulo("data_lake", SCRIPTS / "data_lake.py")
    oid = ObjectId()
    salida = dl.convertir_objectids({
        "_id": oid,
        "items": [{"producto_id": oid}],
        "nested": {"cliente": {"id": oid}},
        "total": 1500.5,
        "activo": True,
    })
    assert salida["_id"] == str(oid)
    assert salida["items"][0]["producto_id"] == str(oid)
    assert salida["nested"]["cliente"]["id"] == str(oid)
    assert salida["total"] == 1500.5
    assert salida["activo"] is True


def test_zonas_dual_local_s3():
    """Las zonas del data lake se construyen segun DATA_LAKE_DESTINO."""
    dl = cargar_modulo("data_lake", SCRIPTS / "data_lake.py")
    if dl.es_s3():
        assert dl.ZONAS["raw"].startswith("s3://")
        assert "data_lake/raw" in dl.ZONAS["raw"]
    else:
        assert dl.ZONAS["raw"].replace("\\", "/").endswith("data_lake/raw")
    assert set(dl.ZONAS) == {"raw", "processed", "curated"}


def test_clasificar_llave():
    """_id es PK; campos *_id y *.id son FK; el resto sin llave."""
    cat = cargar_modulo("generar_catalogo", SCRIPTS / "generar_catalogo.py")
    assert cat.clasificar_llave("_id") == "PK"
    assert cat.clasificar_llave("cliente_id") == "FK"
    assert cat.clasificar_llave("fecha_id") == "FK"
    assert cat.clasificar_llave("cliente.id") == "FK"
    assert cat.clasificar_llave("nombre") == ""
    assert cat.clasificar_llave("total_pedido") == ""


def test_tipo_estandarizado():
    """Tipos BSON/Python -> tipos estandarizados del catalogo."""
    import datetime
    from bson import ObjectId
    cat = cargar_modulo("generar_catalogo", SCRIPTS / "generar_catalogo.py")
    assert cat.tipo_estandarizado("hola") == "String"
    assert cat.tipo_estandarizado(42) == "Integer"
    assert cat.tipo_estandarizado(3.14) == "Float"
    assert cat.tipo_estandarizado(True) == "Boolean"
    assert cat.tipo_estandarizado(ObjectId()) == "ObjectId"
    assert cat.tipo_estandarizado(datetime.datetime.now()) == "Timestamp"
    assert cat.tipo_estandarizado([1, 2]) == "Array"
    assert cat.tipo_estandarizado({"a": 1}) == "Object"
    assert cat.tipo_estandarizado(None) == "Null"
