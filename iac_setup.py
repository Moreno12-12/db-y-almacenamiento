import os
import sys
import subprocess

PROYECTO = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(PROYECTO, ".venv")
if os.name == "nt":
    VENV_PYTHON = os.path.join(VENV_DIR, "Scripts", "python.exe")
else:
    VENV_PYTHON = os.path.join(VENV_DIR, "bin", "python")
REQUIREMENTS = os.path.join(PROYECTO, "requirements.txt")
ENV_FILE = os.path.join(PROYECTO, ".env")
PYTHON_MIN = (3, 10)

DATA_LAKE = os.path.join(PROYECTO, "data_lake")
ZONAS = ["raw", "processed", "curated"]

PASOS_PIPELINE = [
    ("crear_estructura", os.path.join("scripts", "crear_estructura.py")),
    ("generar_datos_masivos", os.path.join("scripts", "generar_datos_masivos.py")),
    ("etl_olap", os.path.join("scripts", "transformar_oltp_a_olap.py")),
    ("benchmark", os.path.join("scripts", "benchmark.py")),
    ("data_lake", os.path.join("scripts", "data_lake.py")),
    ("spark_jobs", os.path.join("scripts", "spark_jobs.py")),
    ("data_warehouse", os.path.join("scripts", "data_warehouse.py")),
    ("dashboard", os.path.join("scripts", "dashboard_monitoreo.py")),
]

RESULTADOS = []
SOLO_SETUP = "--solo-setup" in sys.argv


def log(mensaje):
    print(mensaje, flush=True)


def separador():
    print("=" * 70, flush=True)


def ejecutar_comando(comando):
    log(f">> {comando[0]} {' '.join(comando[1:])}")
    resultado = subprocess.run(comando, cwd=PROYECTO)
    return resultado.returncode


def validar_python():
    separador()
    log("PASO 1: Validacion del entorno (Python)")
    log(f"  Python detectado: {sys.version.split()[0]} | {sys.executable}")
    if sys.version_info < PYTHON_MIN:
        log(f"[FALLO] Se requiere Python {PYTHON_MIN[0]}.{PYTHON_MIN[1]} o superior")
        sys.exit(1)
    log(f"[OK] Version de Python valida (>= {PYTHON_MIN[0]}.{PYTHON_MIN[1]})")


def preparar_venv():
    separador()
    log("PASO 2: Aislamiento (entorno virtual .venv)")
    en_venv = os.path.realpath(sys.executable) == os.path.realpath(VENV_PYTHON)
    if not en_venv:
        if not os.path.exists(VENV_PYTHON):
            log("  Creando entorno virtual .venv ...")
            codigo = ejecutar_comando([sys.executable, "-m", "venv", VENV_DIR])
            if codigo != 0:
                log("[FALLO] No se pudo crear el entorno virtual")
                sys.exit(1)
        log("  Re-ejecutando el script dentro del entorno virtual...")
        sys.exit(ejecutar_comando([VENV_PYTHON, os.path.abspath(__file__)] + sys.argv[1:]))
    log("[OK] Ejecutando dentro de .venv")


def instalar_dependencias():
    separador()
    log("PASO 3: Gestion de dependencias (requirements.txt)")
    log("  Nota: pyspark es una descarga pesada (~300 MB), puede tardar unos minutos.")
    codigo = ejecutar_comando([sys.executable, "-m", "pip", "install", "-r", REQUIREMENTS])
    if codigo != 0:
        log("[FALLO] Instalacion de dependencias")
        sys.exit(1)
    log("[OK] Dependencias instaladas")


def crear_data_lake():
    separador()
    log("PASO 4: Provisionamiento local (Data Lake)")
    for zona in ZONAS:
        ruta = os.path.join(DATA_LAKE, zona)
        os.makedirs(ruta, exist_ok=True)
        log(f"  [OK] Carpeta lista: {os.path.relpath(ruta, PROYECTO)}")


def health_check():
    separador()
    log("PASO 5: Health Check (.env + conexion MongoDB Atlas)")
    if not os.path.exists(ENV_FILE):
        log("[FALLO] No existe el archivo .env")
        log("  Crea un .env con: MONGODB_URI=mongodb+srv://<usuario>:<password>@<cluster>.mongodb.net")
        sys.exit(1)
    log("  [OK] Archivo .env encontrado")

    from dotenv import load_dotenv
    import pymongo

    load_dotenv(ENV_FILE)
    uri = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")
    if not uri:
        log("[FALLO] No se encontro MONGO_URI/MONGODB_URI en el .env")
        sys.exit(1)

    intentos = 3
    for intento in range(1, intentos + 1):
        try:
            client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=20000)
            client.admin.command("ping")
            client.close()
            log("[OK] Conexion a MongoDB Atlas verificada (ping exitoso)")
            return
        except Exception as e:
            if intento < intentos:
                log(f"  Intento {intento}/{intentos} fallo, reintentando... ({str(e)[:100]})")
            else:
                log(f"[FALLO] No se pudo conectar a MongoDB Atlas: {e}")
                sys.exit(1)
    log("[OK] Conexion a MongoDB Atlas verificada (ping exitoso)")


def ejecutar_pipeline():
    separador()
    log("PASO 6: Pipeline completo (Data -> ETL -> Benchmark -> Spark -> DW -> Dashboard)")
    for nombre, script in PASOS_PIPELINE:
        log(f"\n>>> Ejecutando: {nombre} ({script})")
        codigo = ejecutar_comando([sys.executable, script])
        RESULTADOS.append((nombre, codigo))
    separador()
    log("RESUMEN DEL PIPELINE")
    for nombre, codigo in RESULTADOS:
        estado = "OK" if codigo == 0 else "FALLO"
        log(f"  {nombre:<22} {estado}")
    fallos = sum(1 for _, c in RESULTADOS if c != 0)
    if fallos > 0:
        log(f"[ATENCION] {fallos} paso(s) con fallo")
        sys.exit(1)


def main():
    log("iac_setup.py - Infraestructura/Configuracion como Codigo (UrbanRush)")
    validar_python()
    preparar_venv()
    instalar_dependencias()
    crear_data_lake()
    health_check()
    if SOLO_SETUP:
        separador()
        log("[OK] Setup del entorno completado (--solo-setup: pipeline omitido)")
    else:
        ejecutar_pipeline()
        separador()
        log("[OK] Entorno e infraestructura listos.")
        log(f"  Usa el python del venv para comandos manuales: {VENV_PYTHON}")
        log("  O automatiza con: scripts/automatizar_pipeline.ps1")


if __name__ == "__main__":
    main()