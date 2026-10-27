import os
from dotenv import load_dotenv
from google.cloud import bigquery

load_dotenv()
proyecto = os.getenv("GCP_PROJECT_ID")
c = bigquery.Client(project=proyecto)

print("TABLAS EN BigQuery (dataset urbanrush_dw):")
for t in ["dim_tiempo", "dim_cliente", "dim_producto", "fact_ventas"]:
    tab = c.get_table(f"{proyecto}.urbanrush_dw.{t}")
    print(f"  {t}: {tab.num_rows:,} filas, {tab.num_bytes/1024:.1f} KB")

print("\n--- Consulta OLAP: ventas por mes ---")
sql = (
    "SELECT anio, mes, COUNT(*) AS lineas "
    f"FROM `{proyecto}.urbanrush_dw.fact_ventas` f "
    f"JOIN `{proyecto}.urbanrush_dw.dim_tiempo` t USING(fecha_id) "
    "GROUP BY anio, mes ORDER BY anio, mes LIMIT 6"
)
for r in c.query(sql).result():
    print(" ", dict(r))
