"""Amplia el Data Lake en AWS S3 con datos sinteticos volumetricos.

Genera directamente Parquet (sin pasar por MongoDB) particionado por anio/mes
y lo sube a s3://<bucket>/data_lake/scale/.

Uso:
    python scripts/ampliar_lake_s3.py                    # ~1 GB por defecto
    python scripts/ampliar_lake_s3.py --gb 2             # 2 GB
    python scripts/ampliar_lake_s3.py --registros 5000000
    python scripts/ampliar_lake_s3.py --limpiar          # borra scale/ antes
"""
import argparse
import os
import random
import time

import numpy as np
import pandas as pd
import s3fs
from dotenv import load_dotenv

load_dotenv()

BUCKET = os.getenv("AWS_S3_BUCKET", "data-steven")
PREFIJO = f"{BUCKET}/data_lake/scale"
FILA_POR_LOTE = 500_000

METODOS = np.array(["Tarjeta de Credito", "Tarjeta Debito", "Nequi",
                    "DaviPlata", "Efectivo", "PSE"])
ESTADOS = np.array(["Entregado", "Entregado", "Entregado", "En camino",
                    "Pendiente", "Cancelado"])
CIUDADES = np.array(["Bogota", "Medellin", "Cali", "Barranquilla",
                     "Cartagena", "Bucaramanga"])
CATEGORIAS = np.array(["Comida Rapida", "Hogar", "Ropa", "Deportes",
                       "Tecnologia", "Mercado"])


def filesystem_s3():
    return s3fs.S3FileSystem(
        anon=False,
        key=os.getenv("AWS_ACCESS_KEY_ID"),
        secret=os.getenv("AWS_SECRET_ACCESS_KEY"),
    )


def tamano_bucket_gb(fs):
    """Suma bytes de TODOS los objetos bajo data_lake/ (recursivo)."""
    try:
        rutas = [r for r in fs.find(f"{BUCKET}/data_lake")
                 if not r.endswith("/")]
        total = sum(fs.info(r).get("size", 0) or 0 for r in rutas)
        return total / 1024**3, len(rutas)
    except FileNotFoundError:
        return 0.0, 0


def limpiar_escala(fs):
    if fs.exists(PREFIJO):
        fs.rm(PREFIJO, recursive=True)
        print(f"[OK] Prefijo s3://{PREFIJO}/ eliminado.")
    else:
        print("[OK] No habia datos en scale/, nada que limpiar.")


def generar_lote(n_rows, anio, mes, indice):
    rng = np.random.default_rng()
    precio = np.round(rng.uniform(5000, 500000, n_rows), 2)
    cantidad = rng.integers(1, 4, n_rows)
    subtotal = np.round(precio * cantidad, 2)
    delivery = np.round(rng.uniform(3000, 15000, n_rows), 2)
    comision = np.round(subtotal * 0.10, 2)
    total = np.round(subtotal + delivery, 2)

    df = pd.DataFrame({
        "venta_id": [f"SCALE-{anio}{mes:02d}-{i:09d}"
                     for i in range(indice * n_rows, (indice + 1) * n_rows)],
        "fecha_pedido": pd.to_datetime(
            [f"{anio}-{mes:02d}-{d:02d}" for d in rng.integers(1, 28, n_rows)]),
        "anio": anio,
        "mes": mes,
        "cliente_id": [f"CLI-{v:06d}" for v in rng.integers(1, 50_000, n_rows)],
        "producto_id": [f"PROD-{v:05d}" for v in rng.integers(1, 2_000, n_rows)],
        "repartidor_id": [f"REP-{v:04d}" for v in rng.integers(1, 500, n_rows)],
        "cantidad": cantidad,
        "precio_unitario": precio,
        "subtotal_linea": subtotal,
        "total_pedido": total,
        "delivery_fee": delivery,
        "comision_plataforma": comision,
        "ganancia_estimada": np.round(subtotal * 0.15, 2),
        "metodo_pago": rng.choice(METODOS, n_rows),
        "estado": rng.choice(ESTADOS, n_rows),
        "ciudad_entrega": rng.choice(CIUDADES, n_rows),
        "categoria": rng.choice(CATEGORIAS, n_rows),
        "descripcion": [f"Pedido sintetico para prueba de escala volumetrica "
                        f"del data lake {anio}-{mes:02d} lote {indice} registro {i}"
                        for i in range(n_rows)],
    })
    return df


def ampliar(gb_objetivo=None, registros_objetivo=None, limpiar=False):
    fs = filesystem_s3()
    if limpiar:
        limpiar_escala(fs)

    gb_antes, n_antes = tamano_bucket_gb(fs)
    print(f"[ANTES] data_lake en S3: {gb_antes:.3f} GB en {n_antes} objetos\n")

    # ~65 bytes/fila comprimidos con snappy => ~15.4M filas ~ 1 GB
    objetivo_registros = registros_objetivo or int((gb_objetivo or 1) * 15_000_000)
    print(f"Objetivo: {objetivo_registros:,} registros "
          f"(~{gb_objetivo or 1} GB) en s3://{PREFIJO}/\n")

    inicio = time.time()
    escritos = 0
    lote = 0
    fs.makedirs(PREFIJO, exist_ok=True)

    while escritos < objetivo_registros:
        n_rows = min(FILA_POR_LOTE, objetivo_registros - escritos)
        # Distribuye el lote en anio/mes ficticios 2024-2025
        anio = 2024 + (lote % 2)
        mes = (lote % 12) + 1
        df = generar_lote(n_rows, anio, mes, lote)
        ruta = (f"s3://{PREFIJO}/pedidos_anio={anio}/"
                f"mes={mes:02d}/part-{lote:04d}.parquet")
        df.to_parquet(ruta, compression="snappy", index=False)
        escritos += n_rows
        lote += 1
        gb_actual, _ = tamano_bucket_gb(fs)
        print(f"  Lote {lote:03d}: +{n_rows:,} filas -> {ruta.split('/')[-1]}"
              f"   (S3 total: {gb_actual:.3f} GB)")

    duracion = time.time() - inicio
    gb_despues, n_despues = tamano_bucket_gb(fs)
    print("\n" + "=" * 60)
    print("AMPLIACION DEL DATA LAKE COMPLETADA")
    print("=" * 60)
    print(f"Registros subidos : {escritos:,}")
    print(f"Particiones (lotes): {lote}")
    print(f"Tiempo total      : {duracion:.1f} s")
    print(f"ANTES  -> {gb_antes:.3f} GB ({n_antes} objetos)")
    print(f"DESPUES-> {gb_despues:.3f} GB ({n_despues} objetos)")
    print(f"Aumento : {gb_despues - gb_antes:.3f} GB")
    print(f"Ruta    : s3://{PREFIJO}/pedidos_anio=YYYY/mes=MM/part-NNNN.parquet")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Amplia el Data Lake en S3")
    parser.add_argument("--gb", type=float, default=None,
                        help="Volumen objetivo en GB (default 1)")
    parser.add_argument("--registros", type=int, default=None,
                        help="Cantidad exacta de registros (sobrepone --gb)")
    parser.add_argument("--limpiar", action="store_true",
                        help="Elimina s3://.../data_lake/scale/ antes de generar")
    args = parser.parse_args()
    ampliar(gb_objetivo=args.gb, registros_objetivo=args.registros,
            limpiar=args.limpiar)
