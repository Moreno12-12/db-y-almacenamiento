"""ETL: MongoDB Atlas (OLTP) -> Google BigQuery (Data Warehouse en la nube).

Lee la coleccion pedidos_analiticos de Atlas, construye el modelo estrella
(dim_tiempo, dim_cliente, dim_producto, fact_ventas) y lo carga como tablas
en el dataset urbanrush_dw de BigQuery.

Uso:
    python scripts/data_warehouse_cloud.py
"""
import os
import time

import pymongo
from bson import ObjectId
from dotenv import load_dotenv
from google.cloud import bigquery

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")
PROYECTO = os.getenv("GCP_PROJECT_ID", "orbital-kit-365104")
DATASET = "urbanrush_dw"
FUENTE = "pedidos_analiticos"


def convertir_objectids(valor):
    if isinstance(valor, ObjectId):
        return str(valor)
    if isinstance(valor, list):
        return [convertir_objectids(v) for v in valor]
    if isinstance(valor, dict):
        return {k: convertir_objectids(v) for k, v in valor.items()}
    return valor


def leer_pedidos_analiticos():
    client = pymongo.MongoClient(MONGO_URI)
    db = client["urbanrush_db"]
    print(f"Leyendo '{FUENTE}' de MongoDB Atlas...")
    docs = list(db[FUENTE].find({}))
    client.close()
    print(f"  {len(docs):,} lineas de venta leidas.")
    return [convertir_objectids(d) for d in docs]


def construir_modelo(documentos):
    import pandas as pd

    df = pd.json_normalize(documentos)

    # --- dim_tiempo ---
    df_tmp = df.copy()
    df_tmp["fecha"] = pd.to_datetime(df_tmp["fecha_pedido"]).dt.date
    dim_tiempo = (df_tmp
        .drop_duplicates(subset="fecha")
        .assign(fecha_id=lambda d: d["fecha"].astype(str),
                anio=lambda d: pd.to_datetime(d["fecha"]).dt.year,
                mes=lambda d: pd.to_datetime(d["fecha"]).dt.month,
                dia=lambda d: pd.to_datetime(d["fecha"]).dt.day)
        .assign(trimestre=lambda d: ((d["mes"] - 1) // 3) + 1,
                es_fin_semana=lambda d: [
                    "Si" if f.weekday() >= 5 else "No" for f in d["fecha"]])
        [["fecha_id", "anio", "mes", "dia", "trimestre", "es_fin_semana"]])

    # --- dim_cliente ---
    dim_cliente = (df
        .groupby("cliente.id")
        .agg(nombre=("cliente.nombre", "first"),
             ciudad=("cliente.ciudad", "first"),
             barrio=("cliente.barrio", "first"),
             segmento=("cliente.segmento", "first"),
             numero_compras=("total_pedido", "size"),
             total_compras=("total_pedido", "sum"),
             ticket_promedio=("total_pedido", "mean"))
        .reset_index()
        .rename(columns={"cliente.id": "cliente_id"})
        .assign(total_compras=lambda d: d["total_compras"].round(2),
                ticket_promedio=lambda d: d["ticket_promedio"].round(2)))

    # --- dim_producto ---
    dim_producto = (df
        .groupby("producto.id")
        .agg(nombre=("producto.nombre", "first"),
             categoria=("producto.categoria", "first"),
             unidades_vendidas=("cantidad", "sum"),
             ingresos=("subtotal_linea", "sum"))
        .reset_index()
        .rename(columns={"producto.id": "producto_id"})
        .assign(ingresos=lambda d: d["ingresos"].round(2),
                numero_pedidos=df.groupby("producto.id")["numero_pedido"].nunique().values))

    # --- fact_ventas ---
    fact_ventas = pd.DataFrame({
        "venta_id": df["numero_pedido"],
        "fecha_id": pd.to_datetime(df["fecha_pedido"]).dt.strftime("%Y-%m-%d"),
        "cliente_id": df["cliente.id"],
        "producto_id": df["producto.id"],
        "repartidor_id": df["repartidor.id"],
        "cantidad": df["cantidad"],
        "precio_unitario": df["precio_unitario"],
        "subtotal_linea": df["subtotal_linea"],
        "total_pedido": df["total_pedido"],
        "delivery_fee": df["delivery_fee"],
        "comision_plataforma": df["comision_plataforma"],
        "ganancia_estimada": df["ganancia_estimada"],
        "metodo_pago": df["metodo_pago"],
        "estado": df["estado"],
        "ciudad_entrega": df["ciudad_entrega"],
    })

    print(f"  dim_tiempo   : {len(dim_tiempo):>8,} filas")
    print(f"  dim_cliente  : {len(dim_cliente):>8,} filas")
    print(f"  dim_producto : {len(dim_producto):>8,} filas")
    print(f"  fact_ventas  : {len(fact_ventas):>8,} filas")
    return dim_tiempo, dim_cliente, dim_producto, fact_ventas


def cargar_tabla(client, tabla, df, esquema):
    referencia = f"{PROYECTO}.{DATASET}.{tabla}"
    config = bigquery.LoadJobConfig(
        schema=esquema,
        write_disposition="WRITE_TRUNCATE",
    )
    job = client.load_table_from_dataframe(df, referencia, job_config=config)
    job.result()
    destino = client.get_table(referencia)
    print(f"  [OK] {tabla}: {destino.num_rows:,} filas cargadas en BigQuery")


def consultar_olap(client):
    consultas = {
        "Ingresos por categoria":
            f"SELECT categoria, ROUND(SUM(ingresos),2) AS ingresos "
            f"FROM `{PROYECTO}.{DATASET}.dim_producto` "
            f"GROUP BY categoria ORDER BY ingresos DESC",
        "Top 5 ciudades por volumen de hechos":
            f"SELECT ciudad_entrega, COUNT(*) AS lineas, "
            f"ROUND(SUM(subtotal_linea),2) AS ingresos "
            f"FROM `{PROYECTO}.{DATASET}.fact_ventas` "
            f"GROUP BY ciudad_entrega ORDER BY lineas DESC LIMIT 5",
        "Ventas por mes (series temporales)":
            f"SELECT anio, mes, COUNT(*) AS lineas "
            f"FROM `{PROYECTO}.{DATASET}.fact_ventas` f "
            f"JOIN `{PROYECTO}.{DATASET}.dim_tiempo` t USING(fecha_id) "
            f"GROUP BY anio, mes ORDER BY anio, mes",
    }
    for titulo, sql in consultas.items():
        print(f"\n--- {titulo} ---")
        filas = client.query(sql).result()
        for r in filas:
            print("  ", dict(r))


def main():
    print("=" * 60)
    print("ETL CLOUD: MongoDB Atlas -> Google BigQuery")
    print(f"Proyecto: {PROYECTO} | Dataset: {DATASET}")
    print("=" * 60 + "\n")

    client = bigquery.Client(project=PROYECTO)

    # Crear dataset si no existe
    dataset_ref = bigquery.Dataset(f"{PROYECTO}.{DATASET}")
    dataset_ref.location = "US"
    try:
        client.create_dataset(dataset_ref, exists_ok=True)
        print(f"[OK] Dataset '{DATASET}' verificado/creado (region US)\n")
    except Exception as e:
        print(f"[ERROR] No se pudo crear el dataset: {e}")
        print("Habilita la API de BigQuery en la consola de GCP y reintenta.")
        return

    documentos = leer_pedidos_analiticos()
    print("\nConstruyendo modelo estrella (pandas)...")
    dim_tiempo, dim_cliente, dim_producto, fact_ventas = construir_modelo(documentos)

    inicio = time.time()
    print("\nCargando tablas a BigQuery...")
    cargar_tabla(client, "dim_tiempo", dim_tiempo, [
        bigquery.SchemaField("fecha_id", "STRING"),
        bigquery.SchemaField("anio", "INTEGER"),
        bigquery.SchemaField("mes", "INTEGER"),
        bigquery.SchemaField("dia", "INTEGER"),
        bigquery.SchemaField("trimestre", "INTEGER"),
        bigquery.SchemaField("es_fin_semana", "STRING"),
    ])
    cargar_tabla(client, "dim_cliente", dim_cliente, [
        bigquery.SchemaField("cliente_id", "STRING"),
        bigquery.SchemaField("nombre", "STRING"),
        bigquery.SchemaField("ciudad", "STRING"),
        bigquery.SchemaField("barrio", "STRING"),
        bigquery.SchemaField("segmento", "STRING"),
        bigquery.SchemaField("numero_compras", "INTEGER"),
        bigquery.SchemaField("total_compras", "FLOAT"),
        bigquery.SchemaField("ticket_promedio", "FLOAT"),
    ])
    cargar_tabla(client, "dim_producto", dim_producto, [
        bigquery.SchemaField("producto_id", "STRING"),
        bigquery.SchemaField("nombre", "STRING"),
        bigquery.SchemaField("categoria", "STRING"),
        bigquery.SchemaField("unidades_vendidas", "INTEGER"),
        bigquery.SchemaField("ingresos", "FLOAT"),
        bigquery.SchemaField("numero_pedidos", "INTEGER"),
    ])
    cargar_tabla(client, "fact_ventas", fact_ventas, [
        bigquery.SchemaField("venta_id", "STRING"),
        bigquery.SchemaField("fecha_id", "STRING"),
        bigquery.SchemaField("cliente_id", "STRING"),
        bigquery.SchemaField("producto_id", "STRING"),
        bigquery.SchemaField("repartidor_id", "STRING"),
        bigquery.SchemaField("cantidad", "INTEGER"),
        bigquery.SchemaField("precio_unitario", "FLOAT"),
        bigquery.SchemaField("subtotal_linea", "FLOAT"),
        bigquery.SchemaField("total_pedido", "FLOAT"),
        bigquery.SchemaField("delivery_fee", "FLOAT"),
        bigquery.SchemaField("comision_plataforma", "FLOAT"),
        bigquery.SchemaField("ganancia_estimada", "FLOAT"),
        bigquery.SchemaField("metodo_pago", "STRING"),
        bigquery.SchemaField("estado", "STRING"),
        bigquery.SchemaField("ciudad_entrega", "STRING"),
    ])

    print(f"\nTiempo de carga: {time.time() - inicio:.1f} s")
    print("\n" + "=" * 60)
    print("CONSULTAS OLAP DE DEMOSTRACION (lectura rapida en BigQuery)")
    print("=" * 60)
    consultar_olap(client)
    print("\n[OK] Data Warehouse en la nube listo.")
    client.close()


if __name__ == "__main__":
    main()
