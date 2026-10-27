# Migración del Data Lake: carpetas locales → AWS S3

## 1. Contexto: qué se hizo antes (versión local)

El Data Lake original se construyó como **carpetas en el disco duro** (`C:\...\data_lake\raw`, `processed`, `curated`) y los archivos `.parquet` se escribían ahí con `df.to_parquet("data_lake/raw/...")`.

**Limitación:** un Data Lake real no es una carpeta en la PC:
- Es un **almacenamiento de objetos infinito** (no dependes del disco local).
- Es **duradero y separado de la computación** (los datos viven independientes del proceso que los genera).
- Permite **escalar a Terabytes** sin cambiar el código.

## 2. Versión Cloud (Enterprise)

- **AWS S3 (Simple Storage Service)** — el estándar de la industria (alternativas: Azure ADLS, Google Cloud Storage).
- **AWS Free Tier:** 5 GB de S3 gratis por 12 meses.

## 3. Qué se implementó (arquitectura dual)

El script `scripts/data_lake.py` quedó en **modo dual**, controlado por la variable de entorno `DATA_LAKE_DESTINO`:

| Variable | Comportamiento |
|---|---|
| `DATA_LAKE_DESTINO=local` (default) | Escribe en `data_lake/` (comportamiento original, no se rompe nada). |
| `DATA_LAKE_DESTINO=s3` | Escribe en `s3://<bucket>/data_lake/{raw,processed,curated}/`. |

**Configuración en `.env`:**
```env
AWS_ACCESS_KEY_ID=<access key>
AWS_SECRET_ACCESS_KEY=<secret key>
AWS_DEFAULT_REGION=us-east-2
AWS_S3_BUCKET=data-steven
DATA_LAKE_DESTINO=s3
```

**Cambios técnicos:**
- Dependencias: `boto3` (gestión/verificación del bucket) + `s3fs` (permite `df.to_parquet("s3://...")` nativo de pandas).
- `crear_estructura_lake()` → en S3 **verifica (o crea) el bucket**; en S3 no existen "carpetas": las rutas son prefijos que aparecen al subir el primer objeto.
- Escritura → misma llamada `df.to_parquet(...)`, solo cambia la ruta (`s3://...` en vez de `data_lake/...`).
- `resumen_del_lake()` → en S3 lista los objetos y tamaños del bucket con `s3fs`.

**ETL (igual que la versión local):**
1. `raw/`: copia exacta de MongoDB (clientes, productos, pedidos).
2. `processed/`: pedidos entregados + columnas derivadas (`anio`, `mes`, `fecha_procesamiento`).
3. `curated/`: `pedidos_analiticos` (modelo analítico listo para BI).

## 4. Cómo ejecutarlo

```powershell
# Modo local (default)
python scripts/data_lake.py

# Modo S3 (sube a la nube)
$env:DATA_LAKE_DESTINO="s3"; python scripts/data_lake.py
```

Verificación en consola AWS: S3 → bucket `data-steven` → `data_lake/raw|processed|curated`.

## 5. Reproducir la migración (paso a paso)

1. Crear cuenta AWS Free Tier: https://aws.amazon.com/free/
2. Crear bucket (ej. `data-steven`, región `us-east-2`).
3. Crear usuario IAM con acceso programático + política `AmazonS3FullAccess`.
4. Copiar Access Key / Secret Key al `.env`.
5. `pip install boto3 s3fs`.
6. Ejecutar `python scripts/data_lake.py` con `DATA_LAKE_DESTINO=s3`.

## 6. Texto para el informe

> **Data Lake (de carpetas locales a AWS S3).** Inicialmente construimos el Data Lake como
> carpetas locales (`data_lake/raw|processed|curated`) con archivos Parquet en el disco.
> Para la capa de producción diseñamos la migración a **Amazon S3**, un almacenamiento de
> objetos infinito, duradero y separado de la computación — es decir, un Data Lake real
> y no una carpeta en el equipo. El script quedó en modo dual (`DATA_LAKE_DESTINO=local|s3`),
> de modo que el mismo ETL puede escribir en disco (desarrollo) o en
> `s3://<bucket>/data_lake/...` (producción), usando `boto3` para la gestión del bucket
> y `s3fs` para la escritura Parquet nativa. Esta arquitectura apuntando a S3 es lo que
> permite escalar a volúmenes de 50 GB o más sin cambiar el código, tal como lo haría
> una empresa real.

## 7. Relación con el ítem #13 (≥ 50 GB)

Tener el Data Lake apuntando a S3 es **exactamente** lo que habilita el volumen solicitado:
el mismo script puede generar datos masivos (`scripts/generar_datos_masivos.py`),
convertirlos a Parquet y subirlos a S3, donde el almacenamiento no está limitado por el
disco local (Free Tier: 5 GB; por encima de eso, costo marginal de S3 ~$0.023 USD/GB-mes).

## 8. Demostración de escala (evidencia real)

**Script:** `scripts/ampliar_lake_s3.py` — genera datos volumétricos sintéticos
**directamente en Parquet** (sin pasar por MongoDB M0, que tiene límite de 512 MB)
y los sube a `s3://data-steven/data_lake/scale/`, particionados por estilo Hive:

```
s3://data-steven/data_lake/scale/pedidos_anio=YYYY/mes=MM/part-NNNN.parquet
```

**Uso:**
```powershell
python scripts/ampliar_lake_s3.py --gb 1            # ~1 GB
python scripts/ampliar_lake_s3.py --gb 5 --limpiar  # 5 GB, reemplaza lo anterior
python scripts/ampliar_lake_s3.py --registros 20000000  # cantidad exacta
```

**Resultado de la corrida real (verificado en el bucket):**

| Métrica | Valor |
|---|---|
| Registros subidos | 15.000.000 |
| Archivos (particiones) | 30 (28,5 MB c/u) |
| Volumen en `scale/` | 0,835 GB |
| Tiempo de subida | 1.246 s (~21 min) |
| Antes (ETL original) | 12,65 MB (5 archivos) |
| Después (+ escala) | 0,847 GB (35 archivos en total) |

Rutas reales (estilo Hive, particionado por año/mes):
```
s3://data-steven/data_lake/scale/pedidos_anio=2024/mes=01/part-0000.parquet
s3://data-steven/data_lake/scale/pedidos_anio=2025/mes=12/part-0029.parquet
... (30 particiones, 24 combinaciones año/mes 2024-2025)
```

Verificación reproducible:
```powershell
python scripts/verificar_s3.py        # lista todos los objetos del bucket
python scripts/verificar_s3_escala.py # desglose data_lake/ y scale/
```

Esto demuestra que **la arquitectura escala**: el mismo pipeline puede llevar el
Data Lake de MBs a GBs sin cambiar una línea de código, y S3 no tiene el techo
del disco local ni del tier M0 de Atlas.
