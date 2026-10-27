import os
import pymongo
import pandas as pd
from bson import ObjectId
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")

# -------------------------------------------------------------------
# BLOQUE 2. Definir el Data Lake (zona principal + 3 zonas)
# Soporte dual: carpetas locales (disco C:\) o AWS S3 (la nube).
#   DATA_LAKE_DESTINO=local  -> data_lake/raw...   (por defecto)
#   DATA_LAKE_DESTINO=s3     -> s3://bucket/raw...
# -------------------------------------------------------------------
DATA_LAKE_DESTINO = os.getenv("DATA_LAKE_DESTINO", "local").lower()
BUCKET_S3 = os.getenv("AWS_S3_BUCKET", "data-steven")

if DATA_LAKE_DESTINO == "s3":
    RAIZ = f"s3://{BUCKET_S3}/data_lake"
else:
    RAIZ = "data_lake"

ZONAS = {
    "raw": f"{RAIZ}/raw",
    "processed": f"{RAIZ}/processed",
    "curated": f"{RAIZ}/curated"
}


def es_s3():
    return DATA_LAKE_DESTINO == "s3"


def ruta_completa(zona, nombre_archivo):
    """Ruta final del archivo segun el destino (local o s3)."""
    base = ZONAS[zona]
    return f"{base}/{nombre_archivo}" if es_s3() else os.path.join(base, nombre_archivo)


# -------------------------------------------------------------------
# BLOQUE 3. Crear la estructura del Data Lake
# -------------------------------------------------------------------
def crear_estructura_lake():
    if es_s3():
        import boto3
        print(f"Destino: AWS S3 (bucket '{BUCKET_S3}')")
        s3 = boto3.client(
            "s3",
            region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-2"),
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        )
        # Verificar que el bucket existe (en S3 no hace falta crear carpetas:
        # las 'carpetas' son prefijos que aparecen al subir el primer objeto)
        try:
            s3.head_bucket(Bucket=BUCKET_S3)
            print(f"Bucket '{BUCKET_S3}' verificado.")
        except Exception:
            region = os.getenv("AWS_DEFAULT_REGION", "us-east-2")
            s3.create_bucket(
                Bucket=BUCKET_S3,
                CreateBucketConfiguration={"LocationConstraint": region}
            )
            print(f"Bucket '{BUCKET_S3}' creado en la region {region}.")
        for zona, ruta in ZONAS.items():
            print(f"Zona '{zona}' -> {ruta}/")
    else:
        print(f"Destino: almacenamiento local ({RAIZ})")
        for zona, ruta in ZONAS.items():
            os.makedirs(ruta, exist_ok=True)
            print(f"Zona '{zona}' creada en {ruta}")


def convertir_objectids(valor):
    """Convierte ObjectId a string recursivamente (Parquet no lo entiende)"""
    if isinstance(valor, ObjectId):
        return str(valor)
    if isinstance(valor, list):
        return [convertir_objectids(v) for v in valor]
    if isinstance(valor, dict):
        return {k: convertir_objectids(v) for k, v in valor.items()}
    return valor


# -------------------------------------------------------------------
# BLOQUE 4 y 5. Exportar una coleccion a Parquet
# En S3 usa s3fs (df.to_parquet("s3://...") nativo de pandas)
# -------------------------------------------------------------------
def exportar_a_parquet(coleccion, nombre_archivo, zona):
    print(f"Exportando '{coleccion}' -> {nombre_archivo} ({zona})...")

    client = pymongo.MongoClient(MONGO_URI)
    db = client["urbanrush_db"]

    # Traer todos los documentos de la coleccion
    documentos = list(db[coleccion].find({}))

    # JSON -> DataFrame
    df = pd.json_normalize(documentos)

    # Parquet no entiende ObjectId: los convertimos a string
    df = df.map(convertir_objectids)

    guardar_parquet(df, zona, nombre_archivo)

    client.close()
    return df


def guardar_parquet(df, zona, nombre_archivo):
    """Escribe un DataFrame como Parquet en la zona indicada (local o S3)."""
    ruta = ruta_completa(zona, nombre_archivo)
    df.to_parquet(ruta, compression="snappy",
                  coerce_timestamps="us", allow_truncated_timestamps=True)
    print(f"   OK -> {len(df)} registros guardados en {ruta}")
    return ruta


# -------------------------------------------------------------------
# BLOQUE 6. Construccion completa del Data Lake (ETL)
# -------------------------------------------------------------------
def generar_data_lake_completo():
    print("=" * 60)
    print("GENERANDO DATA LAKE (Fase 2 - Big Data)")
    print(f"Destino: {'AWS S3' if es_s3() else 'almacenamiento local'}")
    print("=" * 60)

    # 1. Crear carpetas / verificar bucket
    crear_estructura_lake()
    print()

    # 2. ETAPA RAW: copia exacta de MongoDB (sin modificar)
    print(">> ETAPA RAW (copia exacta de la base de datos)\n")
    exportar_a_parquet("clientes", "clientes.parquet", "raw")
    exportar_a_parquet("productos", "productos.parquet", "raw")
    exportar_a_parquet("pedidos", "pedidos.parquet", "raw")
    print()

    # 3. ETAPA PROCESSED: transformaciones (filtro + columnas nuevas)
    print(">> ETAPA PROCESSED (datos limpios y transformados)\n")
    client = pymongo.MongoClient(MONGO_URI)
    db = client["urbanrush_db"]

    # Filtro: solo pedidos entregados (equivalente a 'Completada')
    documentos = list(db["pedidos"].find({"estado": "Entregado"}))
    df = pd.json_normalize(documentos)
    df = df.map(convertir_objectids)
    df["fecha_pedido"] = pd.to_datetime(df["fecha_pedido"])

    # Agregar dimensiones de tiempo (simula trabajo de Spark)
    df["anio"] = df["fecha_pedido"].dt.year
    df["mes"] = df["fecha_pedido"].dt.month
    df["fecha_procesamiento"] = datetime.now()

    guardar_parquet(df, "processed", "pedidos_procesados.parquet")
    print()
    client.close()

    # 4. ETAPA CURATED: modelo estrella listo para BI
    print(">> ETAPA CURATED (modelo analitico listo para BI)\n")
    exportar_a_parquet("pedidos_analiticos", "pedidos_analiticos.parquet", "curated")
    print()

    # 5. BLOQUE 7. Resumen del Data Lake
    resumen_del_lake()


# -------------------------------------------------------------------
# BLOQUE 7. Resumen del Data Lake (archivos, tamanos, espacio)
# -------------------------------------------------------------------
def resumen_del_lake():
    print("=" * 60)
    print("RESUMEN DEL DATA LAKE")
    print("=" * 60)

    if es_s3():
        import s3fs
        fs = s3fs.S3FileSystem(
            anon=False,
            key=os.getenv("AWS_ACCESS_KEY_ID"),
            secret=os.getenv("AWS_SECRET_ACCESS_KEY"),
        )
        total_objetos = 0
        total_bytes = 0
        for zona, base in ZONAS.items():
            prefijo = base.replace(f"s3://{BUCKET_S3}/", "")
            rutas = fs.ls(f"{BUCKET_S3}/{prefijo}")
            archivos = [r for r in rutas if not r.endswith("/")]
            tamano = sum(fs.info(r).get("size", 0) for r in archivos)
            total_objetos += len(archivos)
            total_bytes += tamano
            print(f"{zona.upper()}: {len(archivos)} archivo(s) - "
                  f"{tamano/1024:.2f} KB  [{base}]")
        print(f"\nTOTAL S3: {total_objetos} objetos - "
              f"{total_bytes/1024:.2f} KB ({total_bytes/1024/1024:.2f} MB)")
        print(f"Bucket: s3://{BUCKET_S3}/ (Data Lake en la nube)")
    else:
        total_archivos = 0
        total_bytes = 0
        for zona, ruta in ZONAS.items():
            archivos = [f for f in os.listdir(ruta) if os.path.isfile(os.path.join(ruta, f))]
            total_archivos += len(archivos)
            tamano_bytes = sum(os.path.getsize(os.path.join(ruta, f)) for f in archivos)
            total_bytes += tamano_bytes
            print(f"{zona.upper()}: {len(archivos)} archivo(s) - {tamano_bytes/1024:.2f} KB")
        print(f"\nTOTAL: {total_archivos} archivos - {total_bytes/1024:.2f} KB "
              f"({total_bytes/1024/1024:.2f} MB)")
    print("=" * 60)


# -------------------------------------------------------------------
# PUNTO DE ENTRADA
# -------------------------------------------------------------------
if __name__ == "__main__":
    generar_data_lake_completo()
