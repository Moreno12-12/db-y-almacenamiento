import os
import pymongo
from dotenv import load_dotenv
import time

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")

BASE_DE_DATOS = "urbanrush_db"
FUENTE = "pedidos_analiticos"
COLECCIONES_DW = ["dim_tiempo", "dim_cliente", "dim_producto", "fact_ventas"]


def conectar_bd():
    client = pymongo.MongoClient(MONGO_URI)
    return client, client[BASE_DE_DATOS]


def resetear_colecciones(db):
    """Empieza desde cero: elimina y recrea las colecciones del Data Warehouse."""
    print("Reiniciando colecciones del Data Warehouse...")
    for nombre in COLECCIONES_DW:
        db[nombre].drop()
        db.create_collection(nombre)
        print(f"  Coleccion '{nombre}' lista (desde cero)")

    # Indices unicos: $merge los exige para verificar unicidad del campo "on"
    db.dim_tiempo.create_index([("fecha_id", 1)], unique=True)
    db.dim_cliente.create_index([("cliente_id", 1)], unique=True)
    db.dim_producto.create_index([("producto_id", 1)], unique=True)
    print("  Indices unicos creados (fecha_id, cliente_id, producto_id)")


def crear_dim_tiempo(db):
    print("=" * 60)
    print("DIMENSION: dim_tiempo")
    print("=" * 60)
    pipeline = [
        # 1. Agrupar por fecha para eliminar duplicados
        {"$group": {
            "_id": {
                "fecha": {"$dateToString": {"format": "%Y-%m-%d", "date": "$fecha_pedido"}},
                "anio": "$anio",
                "mes": "$mes",
                "dia": "$dia"
            },
            "fecha_original": {"$first": "$fecha_pedido"}
        }},
        # 2. Proyectar al esquema de la dimension tiempo
        {"$project": {
            "_id": 0,
            "fecha_id": "$_id.fecha",
            "anio": "$_id.anio",
            "mes": "$_id.mes",
            "dia": "$_id.dia",
            "trimestre": {"$ceil": {"$divide": ["$_id.mes", 3]}},
            "es_fin_semana": {
                "$cond": [
                    {"$in": [{"$dayOfWeek": "$fecha_original"}, [1, 7]]},
                    "Si",
                    "No"
                ]
            }
        }},
        # 3. Guardar en dim_tiempo
        {"$merge": {
            "into": "dim_tiempo",
            "on": "fecha_id",
            "whenMatched": "replace",
            "whenNotMatched": "insert"
        }}
    ]

    resultado = list(db[FUENTE].aggregate(pipeline, allowDiskUse=True))
    print(f"  Registros en dim_tiempo: {db.dim_tiempo.count_documents({})}")


def crear_dim_cliente(db):
    print("=" * 60)
    print("DIMENSION: dim_cliente")
    print("=" * 60)
    pipeline = [
        # 1. Agrupar por cliente (cada venta puede aparecer muchas veces)
        {"$group": {
            "_id": "$cliente.id",
            "nombre": {"$first": "$cliente.nombre"},
            "ciudad": {"$first": "$cliente.ciudad"},
            "barrio": {"$first": "$cliente.barrio"},
            "segmento": {"$first": "$cliente.segmento"},
            "numero_compras": {"$sum": 1},
            "total_compras": {"$sum": "$total_pedido"},
            "ticket_promedio": {"$avg": "$total_pedido"}
        }},
        # 2. Proyectar al esquema de la dimension cliente
        {"$project": {
            "_id": 0,
            "cliente_id": "$_id",
            "nombre": 1,
            "ciudad": 1,
            "barrio": 1,
            "segmento": 1,
            "numero_compras": 1,
            "total_compras": {"$round": ["$total_compras", 2]},
            "ticket_promedio": {"$round": ["$ticket_promedio", 2]}
        }},
        # 3. Guardar en dim_cliente
        {"$merge": {
            "into": "dim_cliente",
            "on": "cliente_id",
            "whenMatched": "replace",
            "whenNotMatched": "insert"
        }}
    ]

    resultado = list(db[FUENTE].aggregate(pipeline, allowDiskUse=True))
    print(f"  Registros en dim_cliente: {db.dim_cliente.count_documents({})}")


def crear_dim_producto(db):
    print("=" * 60)
    print("DIMENSION: dim_producto")
    print("=" * 60)
    pipeline = [
        # 1. Agrupar por producto
        {"$group": {
            "_id": "$producto.id",
            "nombre": {"$first": "$producto.nombre"},
            "categoria": {"$first": "$producto.categoria"},
            "unidades_vendidas": {"$sum": "$cantidad"},
            "ingresos": {"$sum": "$subtotal_linea"},
            "pedidos": {"$addToSet": "$numero_pedido"}
        }},
        # 2. Proyectar al esquema de la dimension producto
        {"$project": {
            "_id": 0,
            "producto_id": "$_id",
            "nombre": 1,
            "categoria": 1,
            "unidades_vendidas": 1,
            "ingresos": {"$round": ["$ingresos", 2]},
            "numero_pedidos": {"$size": "$pedidos"}
        }},
        # 3. Guardar en dim_producto
        {"$merge": {
            "into": "dim_producto",
            "on": "producto_id",
            "whenMatched": "replace",
            "whenNotMatched": "insert"
        }}
    ]

    resultado = list(db[FUENTE].aggregate(pipeline, allowDiskUse=True))
    print(f"  Registros en dim_producto: {db.dim_producto.count_documents({})}")


def crear_fact_ventas(db):
    print("=" * 60)
    print("TABLA DE HECHOS: fact_ventas")
    print("=" * 60)
    pipeline = [
        # 1. Proyectar cada linea de venta como fila de hechos (solo llaves + medidas)
        {"$project": {
            "_id": 0,
            "venta_id": "$numero_pedido",
            "fecha_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$fecha_pedido"}},
            "cliente_id": "$cliente.id",
            "producto_id": "$producto.id",
            "repartidor_id": "$repartidor.id",
            "cantidad": 1,
            "precio_unitario": 1,
            "subtotal_linea": 1,
            "total_pedido": 1,
            "delivery_fee": 1,
            "comision_plataforma": 1,
            "ganancia_estimada": 1,
            "metodo_pago": 1,
            "estado": 1,
            "ciudad_entrega": 1
        }},
        # 2. Guardar en fact_ventas
        {"$merge": {
            "into": "fact_ventas",
            "whenMatched": "replace",
            "whenNotMatched": "insert"
        }}
    ]

    resultado = list(db[FUENTE].aggregate(pipeline, allowDiskUse=True))
    print(f"  Registros en fact_ventas: {db.fact_ventas.count_documents({})}")


if __name__ == "__main__":
    inicio = time.time()

    client, db = conectar_bd()
    print(f"[OK] Conectado a MongoDB Atlas (base: {BASE_DE_DATOS})")

    resetear_colecciones(db)

    crear_dim_tiempo(db)
    crear_dim_cliente(db)
    crear_dim_producto(db)
    crear_fact_ventas(db)

    print("=" * 60)
    print("DATA WAREHOUSE CONFIGURADO")
    print("=" * 60)
    for nombre in COLECCIONES_DW:
        print(f"  {nombre}: {db[nombre].count_documents({})} registros")
    print(f"  Tiempo total: {time.time() - inicio:.2f} segundos")
    print("=" * 60)

    client.close()