# Migración del Data Warehouse: MongoDB → Google BigQuery

## 1. Contexto: qué se hizo antes (versión local)

El Data Warehouse (modelo estrella) se construyó **dentro de la misma base de datos
MongoDB** (`urbanrush_db`), con las colecciones `dim_tiempo`, `dim_cliente`,
`dim_producto` y `fact_ventas`, pobladas desde `pedidos_analiticos` con pipelines
aggregation (`$group` + `$merge`) — ver `scripts/data_warehouse.py`.

**Limitación:** en una arquitectura moderna, la base transaccional y el DW deben
ser **sistemas separados**:

| Sistema | Rol | Optimizado para |
|---|---|---|
| MongoDB Atlas | OLTP (Ingesta) | **Escribir** rápido (transacciones) |
| BigQuery / Snowflake | OLAP (Data Warehouse) | **Leer y analizar** rápido (consultas masivas) |

Mezclar ambas cargas en la misma base compite por recursos y no escala para
analítica de decenas de millones de filas.

## 2. Versión Cloud (Enterprise)

- **Google BigQuery** — Data Warehouse serverless de Google Cloud.
- **BigQuery Sandbox:** modo gratuito **sin tarjeta de crédito**, con límites
  generosos para proyectos académicos (1 TB de consulta/mes, 10 GB de almacenamiento).
- Alternativas: Snowflake (trial 30 días / $400 USD), Amazon Redshift.

## 3. Qué se implementó (ETL Atlas → BigQuery)

**Script:** `scripts/data_warehouse_cloud.py`

Flujo:
1. **Lee** la colección `pedidos_analiticos` desde **MongoDB Atlas** (150.293 líneas).
2. **Construye** el modelo estrella con pandas:
   - `dim_tiempo` (367 filas): fecha_id, anio, mes, dia, trimestre, es_fin_semana.
   - `dim_cliente` (5.001 filas): cliente_id, nombre, ciudad, barrio, segmento, métricas.
   - `dim_producto` (996 filas): producto_id, nombre, categoria, unidades, ingresos.
   - `fact_ventas` (150.293 filas): venta_id, llaves foráneas y medidas.
3. **Crea** el dataset `urbanrush_dw` en BigQuery (region US) si no existe.
4. **Carga** las 4 tablas con `load_table_from_dataframe` (`WRITE_TRUNCATE`).
5. **Ejecuta** consultas OLAP de demostración (lectura analítica en segundos).

**Configuración en `.env`:**
```env
GOOGLE_APPLICATION_CREDENTIALS=orbital-kit-365104-92574c69900d.json
GCP_PROJECT_ID=orbital-kit-365104
```

**Dependencias:** `google-cloud-bigquery`, `db-dtypes`.

**Nota:** el DW local en MongoDB (`data_warehouse.py`) **se mantiene intacto** como
referencia/desarrollo; el cloud es la capa de producción.

## 4. Resultados de la ejecución real

| Tabla | Filas | Tamaño |
|---|---|---|
| dim_tiempo | 367 | 17.2 KB |
| dim_cliente | 5.001 | 507.2 KB |
| dim_producto | 996 | 73.6 KB |
| fact_ventas | 150.293 | 28.0 MB |

- Tiempo de carga total: **~19 segundos**.
- Consultas OLAP de demostración: ingresos por categoría, top ciudades,
  series temporales por mes — todas responden en segundos sobre 150k filas.

## 5. Cómo ejecutarlo

```powershell
python scripts/data_warehouse_cloud.py   # ETL completo + consultas demo
python scripts/verificar_bigquery.py     # verificar tablas y filas
```

## 6. Reproducir la migración (paso a paso)

1. Crear cuenta Google Cloud → `https://console.cloud.google.com/`.
2. Crear proyecto (ej. `orbital-kit-365104`).
3. IAM → Service Accounts → crear cuenta con roles **BigQuery Job User** +
   **BigQuery Data Editor**; descargar clave JSON.
4. Habilitar la **BigQuery API** en el proyecto (si no está habilitada).
5. Pegar en `.env`: `GOOGLE_APPLICATION_CREDENTIALS` y `GCP_PROJECT_ID`.
6. `pip install google-cloud-bigquery db-dtypes`.
7. Ejecutar `python scripts/data_warehouse_cloud.py`.

## 7. Texto para el informe

> **Data Warehouse (de MongoDB a Google BigQuery).** El modelo estrella
> (dim_tiempo, dim_cliente, dim_producto, fact_ventas) se construyó inicialmente
> dentro de MongoDB. Siguiendo la arquitectura moderna, se diseñó un ETL que
> **separa el OLTP del OLAP**: MongoDB Atlas permanece en la capa de
> **ingesta/transaccional (OLTP)**, y el Data Warehouse migró a **Google BigQuery**
> (modo Sandbox, gratuito, sin tarjeta). Un script de Python (`data_warehouse_cloud.py`)
> lee `pedidos_analiticos` desde Atlas, transforma el modelo estrella con pandas y
> lo carga en BigQuery mediante `google-cloud-bigquery`. En el diagrama de
> arquitectura: *MongoDB Atlas (Ingesta/OLTP) → ETL Python → BigQuery (DW/OLAP)*.
> Las consultas analíticas sobre 150.293 hechos responden en segundos, demostrando
> la ventaja del OLAP sobre consultar la base transaccional directamente.
