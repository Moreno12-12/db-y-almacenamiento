import os
import glob
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

# Configuracion especifica para ejecutar Spark en Windows
os.environ['PYSPARK_SUBMIT_ARGS'] = '--master local[*] pyspark-shell'
os.environ['SPARK_LOCAL_HOSTNAME'] = 'localhost'

DATA_LAKE_RAW = "data_lake/raw"
DATA_LAKE_CURATED = "data_lake/curated"


def obtener_archivo_parquet(ruta_carpeta, contiene=None):
    """Devuelve el archivo parquet mas reciente de la carpeta."""
    patron = os.path.join(ruta_carpeta, "*.parquet")
    archivos = glob.glob(patron)
    if contiene:
        archivos = [a for a in archivos if contiene in os.path.basename(a)]
    if not archivos:
        raise FileNotFoundError(f"No hay archivos parquet en {ruta_carpeta}")
    return max(archivos, key=os.path.getctime)


def crear_spark_session():
    return (SparkSession.builder
        .appName("UrbanRush Spark Jobs")
        .master("local[*]")
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.driver.memory", "2g")
        .getOrCreate())


def guardar_resultado(df_pandas, nombre):
    """Guarda un DataFrame de Pandas como un unico parquet en la zona curated."""
    ruta = os.path.join(DATA_LAKE_CURATED, nombre)
    df_pandas.to_parquet(ruta, compression="snappy")
    print(f"  OK -> {len(df_pandas)} registros guardados en {ruta}")
    return ruta


def job1_ventas_por_metodo_pago(spark, ruta):
    print("=" * 60)
    print("SPARK JOB 1 - Ventas por metodo de pago")
    print("=" * 60)
    df = spark.read.parquet(ruta)

    # Explode: convertir la lista de items en una fila por item
    df_items = df.withColumn("item", F.explode("items"))

    resultado = (df_items
        .groupBy("metodo_pago")
        .agg(
            F.count("*").alias("lineas_vendidas"),
            F.countDistinct("numero_pedido").alias("pedidos"),
            F.round(F.sum("item.subtotal"), 2).alias("ingresos"),
            F.round(F.avg("item.subtotal"), 2).alias("ticket_promedio")
        )
        .orderBy(F.desc("ingresos")))

    print("\nQue metodo de pago genera mas ingresos?\n")
    resultado.show(truncate=False)
    guardar_resultado(resultado.toPandas(), "ventas_por_metodo_pago.parquet")


def job2_segmentacion_clientes(spark, ruta):
    print("=" * 60)
    print("SPARK JOB 2 - Segmentacion de clientes")
    print("=" * 60)
    df = spark.read.parquet(ruta)

    resumen = (df
        .groupBy("cliente_id")
        .agg(
            F.count("*").alias("compras"),
            F.round(F.sum("total"), 2).alias("gasto_total"),
            F.round(F.avg("total"), 2).alias("ticket_promedio")
        ))

    segmentos = (resumen
        .withColumn("segmento",
            F.when(F.col("gasto_total") > 50000000, "VIP")
             .when(F.col("gasto_total") > 10000000, "Premium")
             .when(F.col("gasto_total") > 1000000, "Frecuente")
             .otherwise("Regular"))
        .orderBy(F.desc("gasto_total")))

    print("\nQue tipos de clientes tenemos? (top 10 por gasto)\n")
    segmentos.show(10, truncate=False)
    guardar_resultado(segmentos.toPandas(), "segmentacion_clientes.parquet")

    print("\n>>> Resumen por segmento:\n")
    resumen_segmento = (segmentos
        .groupBy("segmento")
        .agg(
            F.count("*").alias("clientes"),
            F.round(F.sum("gasto_total"), 2).alias("ingresos_totales"))
        .orderBy(F.desc("ingresos_totales")))
    resumen_segmento.show(truncate=False)
    guardar_resultado(resumen_segmento.toPandas(), "resumen_segmentos.parquet")


def job3_series_temporales(spark, ruta):
    print("=" * 60)
    print("SPARK JOB 3 - Series temporales (ventas por mes)")
    print("=" * 60)
    df = spark.read.parquet(ruta)

    resultado = (df
        .withColumn("fecha", F.to_date("fecha_pedido"))
        .withColumn("anio", F.year("fecha"))
        .withColumn("mes", F.month("fecha"))
        .groupBy("anio", "mes")
        .agg(
            F.round(F.sum("total"), 2).alias("ingresos"),
            F.count("*").alias("pedidos"))
        .orderBy("anio", "mes"))

    print("\nComo evolucionan las ventas mes a mes?\n")
    resultado.show(30, truncate=False)
    guardar_resultado(resultado.toPandas(), "ventas_por_mes.parquet")


if __name__ == "__main__":
    print("Iniciando Apache Spark (PySpark)...\n")
    spark = crear_spark_session()

    ruta_pedidos = obtener_archivo_parquet(DATA_LAKE_RAW, "pedidos")
    print(f"Archivo fuente: {ruta_pedidos}\n")

    job1_ventas_por_metodo_pago(spark, ruta_pedidos)
    job2_segmentacion_clientes(spark, ruta_pedidos)
    job3_series_temporales(spark, ruta_pedidos)

    spark.stop()
    print("\nSpark finalizado. Resultados guardados en data_lake/curated/")