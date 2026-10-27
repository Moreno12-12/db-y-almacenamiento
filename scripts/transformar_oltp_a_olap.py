import os
import pymongo
from dotenv import load_dotenv
import time

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")


def transformar_datos():
    print("Iniciando transformacion de datos OLTP a OLAP (Modelo Estrella)...\n")
    client = pymongo.MongoClient(MONGO_URI)
    db = client["urbanrush_db"]
    inicio = time.time()

    pipeline = [
        # 1. Unir con clientes (LEFT JOIN)
        {
            "$lookup": {
                "from": "clientes",
                "localField": "cliente_id",
                "foreignField": "_id",
                "as": "info_cliente"
            }
        },
        {"$unwind": "$info_cliente"},

        # 2. Descomponer items del pedido
        {"$unwind": "$items"},

        # 3. Unir con productos
        {
            "$lookup": {
                "from": "productos",
                "localField": "items.producto_id",
                "foreignField": "_id",
                "as": "info_producto"
            }
        },
        {"$unwind": "$info_producto"},

        # 4. Unir con repartidores
        {
            "$lookup": {
                "from": "repartidores",
                "localField": "repartidor_id",
                "foreignField": "_id",
                "as": "info_repartidor"
            }
        },
        {"$unwind": {"path": "$info_repartidor", "preserveNullAndEmptyArrays": True}},

        # 5. Proyectar al Modelo Dimensional
        {
            "$project": {
                "_id": 0,
                "fecha_pedido": 1,
                "anio": {"$year": "$fecha_pedido"},
                "mes": {"$month": "$fecha_pedido"},
                "dia": {"$dayOfMonth": "$fecha_pedido"},

                "cliente": {
                    "id": "$info_cliente._id",
                    "nombre": "$info_cliente.nombre",
                    "ciudad": "$info_cliente.direccion.ciudad",
                    "barrio": "$info_cliente.direccion.barrio",
                    "segmento": {
                        "$cond": [
                            {"$gte": ["$total", 150000]},
                            "Premium",
                            {
                                "$cond": [
                                    {"$gte": ["$total", 50000]},
                                    "Frecuente",
                                    "Regular"
                                ]
                            }
                        ]
                    }
                },

                "producto": {
                    "id": "$info_producto._id",
                    "nombre": "$info_producto.nombre",
                    "categoria": "$info_producto.categoria"
                },

                "repartidor": {
                    "id": "$info_repartidor._id",
                    "nombre": "$info_repartidor.nombre",
                    "vehiculo": "$info_repartidor.vehiculo",
                    "zona": "$info_repartidor.zona"
                },

                "cantidad": "$items.cantidad",
                "precio_unitario": "$items.precio_unitario",
                "subtotal_linea": "$items.subtotal",
                "delivery_fee": 1,
                "comision_plataforma": 1,
                "total_pedido": "$total",
                "ganancia_estimada": {"$multiply": ["$items.subtotal", 0.15]},

                "numero_pedido": 1,
                "metodo_pago": 1,
                "estado": 1,
                "ciudad_entrega": 1
            }
        },

        # 6. Guardar en coleccion OLAP
        {
            "$merge": {
                "into": "pedidos_analiticos",
                "on": "_id",
                "whenNotMatched": "insert"
            }
        }
    ]

    print("Ejecutando Aggregation Pipeline...")
    resultado = list(db.pedidos.aggregate(pipeline, allowDiskUse=True))

    tiempo_total = time.time() - inicio
    total_analitico = db.pedidos_analiticos.count_documents({})

    print("=" * 60)
    print("TRANSFORMACION OLTP A OLAP COMPLETADA!")
    print(f"  Tiempo de procesamiento: {tiempo_total:.2f} segundos")
    print(f"Registros analiticos generados: {total_analitico}")
    print("=" * 60)

    client.close()


if __name__ == "__main__":
    transformar_datos()