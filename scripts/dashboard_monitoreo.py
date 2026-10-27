import os
import time
import pymongo
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from dotenv import load_dotenv

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")

BASE_DE_DATOS = "urbanrush_db"
COLLECCIONES = [
    "clientes", "productos", "repartidores", "pedidos",
    "pedidos_analiticos", "dim_tiempo", "dim_cliente", "dim_producto", "fact_ventas"
]
ARCHIVO_PNG = "dashboard_arquitectura.png"


def conectar_bd():
    client = pymongo.MongoClient(MONGO_URI)
    return client, client[BASE_DE_DATOS]


def estadisticas_del_sistema(db):
    print("=" * 70)
    print("ESTADISTICAS DEL SISTEMA (MongoDB Atlas)")
    print("=" * 70)

    stats = db.command("dbStats")
    print(f"  Bases de datos del cluster   : -")
    print(f"  Colecciones en {BASE_DE_DATOS}: {stats.get('collections')}")
    print(f"  Documentos totales           : {stats.get('objects')}")
    print(f"  DataSize                     : {stats.get('dataSize') / 1024 / 1024:.2f} MB")
    print(f"  StorageSize                  : {stats.get('storageSize') / 1024 / 1024:.2f} MB")

    registros = []
    for nombre in COLLECCIONES:
        conteo = db[nombre].estimated_document_count()
        coll = db.command("collStats", nombre)
        registros.append({
            "coleccion": nombre,
            "documentos": conteo,
            "dataSize_MB": round(coll.get("size", 0) / 1024 / 1024, 2),
            "storageSize_MB": round(coll.get("storageSize", 0) / 1024 / 1024, 2)
        })
        print(f"  {nombre:<22} {conteo:>8,} docs  {coll.get('size', 0) / 1024 / 1024:>8.2f} MB")

    return registros


def metricas_analiticas(db):
    print("\n" + "=" * 70)
    print("METRICAS ANALITICAS (Data Warehouse / OLAP)")
    print("=" * 70)

    coleccion = db["pedidos_analiticos"]

    total_ingresos = sum(d["ingresos_totales"] for d in coleccion.aggregate([
        {"$group": {"_id": None, "ingresos_totales": {"$sum": "$total_pedido"}}}
    ], allowDiskUse=True))
    total_pedidos = coleccion.count_documents({})
    clientes_unicos = len(coleccion.distinct("cliente.id"))
    ticket_promedio = total_ingresos / total_pedidos if total_pedidos else 0

    kpis = {
        "Ingresos totales (COP)": total_ingresos,
        "Lineas de venta": total_pedidos,
        "Clientes unicos": clientes_unicos,
        "Ticket promedio (COP)": ticket_promedio
    }
    print("  KPIs:")
    for k, v in kpis.items():
        print(f"    {k:<26} {v:,.2f}")

    def a_dataframe(pipeline):
        return pd.DataFrame(list(coleccion.aggregate(pipeline, allowDiskUse=True)))

    # 1. Ventas por metodo de pago
    ventas_metodo = a_dataframe([
        {"$group": {"_id": "$metodo_pago", "ingresos": {"$sum": "$total_pedido"}}},
        {"$project": {"_id": 0, "metodo_pago": "$_id", "ingresos": 1}},
        {"$sort": {"ingresos": -1}}
    ])
    print(f"\n  Ventas por metodo de pago: {len(ventas_metodo)} metodos")

    # 2. Ventas mensuales (serie temporal)
    ventas_mensuales = a_dataframe([
        {"$group": {"_id": {"anio": "$anio", "mes": "$mes"},
                    "ingresos": {"$sum": "$total_pedido"}}},
        {"$project": {"_id": 0, "anio": "$_id.anio", "mes": "$_id.mes", "ingresos": 1}},
        {"$sort": {"anio": 1, "mes": 1}}
    ])
    ventas_mensuales["periodo"] = ventas_mensuales["anio"].astype(str) + "-" + ventas_mensuales["mes"].astype(str).str.zfill(2)
    print(f"  Ventas mensuales: {len(ventas_mensuales)} periodos")

    # 3. Top 10 productos por ingresos
    top_productos = a_dataframe([
        {"$group": {"_id": "$producto.nombre", "ingresos": {"$sum": "$subtotal_linea"},
                    "unidades": {"$sum": "$cantidad"}}},
        {"$project": {"_id": 0, "producto": "$_id", "ingresos": 1, "unidades": 1}},
        {"$sort": {"ingresos": -1}},
        {"$limit": 10}
    ])
    print(f"  Top 10 productos por ingresos")

    # 4. Distribucion por segmento
    segmentos = a_dataframe([
        {"$group": {"_id": "$cliente.segmento", "lineas": {"$sum": 1}}},
        {"$project": {"_id": 0, "segmento": "$_id", "lineas": 1}},
        {"$sort": {"lineas": -1}}
    ])
    print(f"  Segmentos de clientes: {len(segmentos)}")

    return kpis, ventas_metodo, ventas_mensuales, top_productos, segmentos


def generar_imagen(registros, kpis, ventas_metodo, ventas_mensuales, top_productos, segmentos):
    print("\n" + "=" * 70)
    print("GENERANDO IMAGEN DEL DASHBOARD...")
    print("=" * 70)

    plt.rcParams["figure.facecolor"] = "white"
    fig, ejes = plt.subplots(2, 3, figsize=(18, 10))
    fig.suptitle("Dashboard de Arquitectura de Datos - UrbanRush\n"
                 "MongoDB Atlas -> Data Lake -> Spark -> Data Warehouse (OLAP)",
                 fontsize=16, fontweight="bold")

    # Panel 1: Tamano de colecciones (documentos)
    ejes[0, 0].barh([r["coleccion"] for r in registros], [r["documentos"] for r in registros], color="#3498db")
    ejes[0, 0].set_title("Documentos por coleccion")
    ejes[0, 0].set_xlabel("Documentos")
    ejes[0, 0].grid(axis="x", linestyle="--", alpha=0.5)

    # Panel 2: Ventas por metodo de pago
    ejes[0, 1].bar(ventas_metodo["metodo_pago"], ventas_metodo["ingresos"] / 1e6, color="#2ecc71")
    ejes[0, 1].set_title("Ingresos por metodo de pago (COP millones)")
    ejes[0, 1].tick_params(axis="x", rotation=20)
    ejes[0, 1].grid(axis="y", linestyle="--", alpha=0.5)

    # Panel 3: Ventas mensuales (serie temporal)
    ejes[0, 2].plot(ventas_mensuales["periodo"], ventas_mensuales["ingresos"] / 1e6, marker="o", color="#e74c3c")
    ejes[0, 2].set_title("Evolucion de ventas mensuales (COP millones)")
    ejes[0, 2].tick_params(axis="x", rotation=45)
    ejes[0, 2].grid(axis="y", linestyle="--", alpha=0.5)

    # Panel 4: Top 10 productos
    ejes[1, 0].barh(top_productos["producto"], top_productos["ingresos"] / 1e6, color="#9b59b6")
    ejes[1, 0].set_title("Top 10 productos por ingresos (COP millones)")
    ejes[1, 0].set_xlabel("Ingresos (millones)")
    ejes[1, 0].grid(axis="x", linestyle="--", alpha=0.5)

    # Panel 5: Segmentos de clientes
    ejes[1, 1].pie(segmentos["lineas"], labels=segmentos["segmento"], autopct="%1.1f%%",
                   colors=["#f1c40f", "#3498db", "#2ecc71", "#e74c3c"])
    ejes[1, 1].set_title("Distribucion de segmentos de clientes")

    # Panel 6: KPIs
    ejes[1, 2].axis("off")
    ejes[1, 2].set_title("KPIs del sistema")
    textos = [
        f"Ingresos totales: {kpis['Ingresos totales (COP)']:,.0f} COP",
        f"Lineas de venta: {kpis['Lineas de venta']:,.0f}",
        f"Clientes unicos: {kpis['Clientes unicos']:,.0f}",
        f"Ticket promedio: {kpis['Ticket promedio (COP)']:,.0f} COP"
    ]
    for i, t in enumerate(textos):
        ejes[1, 2].text(0.02, 0.95 - i * 0.22, t, transform=ejes[1, 2].transAxes,
                        fontsize=12, verticalalignment="top",
                        bbox=dict(boxstyle="round", facecolor="lightgray", alpha=0.5))

    plt.tight_layout(rect=(0, 0, 1, 0.95))
    plt.savefig(ARCHIVO_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] Imagen exportada: {os.path.abspath(ARCHIVO_PNG)}")


if __name__ == "__main__":
    inicio = time.time()

    client, db = conectar_bd()
    print(f"[OK] Conectado a MongoDB Atlas (base: {BASE_DE_DATOS})")

    registros = estadisticas_del_sistema(db)
    kpis, ventas_metodo, ventas_mensuales, top_productos, segmentos = metricas_analiticas(db)
    generar_imagen(registros, kpis, ventas_metodo, ventas_mensuales, top_productos, segmentos)

    print("\n" + "=" * 70)
    print(f"DASHBOARD COMPLETADO | Tiempo total: {time.time() - inicio:.2f} s")
    print("=" * 70)

    client.close()