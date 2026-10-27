import os
import pymongo
from dotenv import load_dotenv
import time
import json

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")


def ejecutar_benchmark():
    print("Iniciando Benchmarking de 10 Consultas Analiticas Optimizadas...\n")
    client = pymongo.MongoClient(MONGO_URI)
    db = client["urbanrush_db"]
    coleccion = db["pedidos_analiticos"]

    # 1. Estrategia de indexacion compuesta selectiva
    print("Fase 1: Aplicando estrategia de indexacion para optimizacion...")
    coleccion.drop_indexes()
    coleccion.create_index([("anio", 1), ("mes", 1), ("dia", 1)], name="idx_fecha_completa")
    coleccion.create_index([("producto.categoria", 1), ("producto.nombre", 1)], name="idx_producto_categoria")
    coleccion.create_index([("estado", 1), ("cliente.segmento", 1), ("cliente.ciudad", 1)], name="idx_estado_segmento_ciudad")
    coleccion.create_index([("metodo_pago", 1)], name="idx_metodo_pago")
    coleccion.create_index([("cliente.id", 1)], name="idx_cliente")
    print("Indices compuestos verificados/creados exitosamente.\n")

    # 2. Consultas analiticas (10 escenarios de negocio)
    consultas = [
        {
            "nombre": "1. Ventas totales mensuales (Serie de tiempo)",
            "pipeline": [
                {"$group": {"_id": {"anio": "$anio", "mes": "$mes"},
                            "ingresos_totales": {"$sum": "$total_pedido"},
                            "transacciones": {"$sum": 1}}},
                {"$sort": {"_id.anio": 1, "_id.mes": 1}},
                {"$limit": 10}
            ]
        },
        {
            "nombre": "2. Top 5 Productos mas rentables por Categoria",
            "pipeline": [
                {"$group": {"_id": {"categoria": "$producto.categoria", "producto": "$producto.nombre"},
                            "ingresos": {"$sum": "$subtotal_linea"},
                            "unidades": {"$sum": "$cantidad"}}},
                {"$sort": {"_id.categoria": 1, "ingresos": -1}},
                {"$group": {"_id": "$_id.categoria",
                            "todos_productos": {"$push": {"producto": "$_id.producto", "ingresos": "$ingresos"}}}},
                {"$project": {"categoria": "$_id", "top_productos": {"$slice": ["$todos_productos", 5]}, "_id": 0}},
                {"$limit": 10}
            ]
        },
        {
            "nombre": "3. Rendimiento por Segmento de Cliente y Ciudad",
            "pipeline": [
                {"$match": {"estado": "Entregado"}},
                {"$group": {"_id": {"segmento": "$cliente.segmento", "ciudad": "$cliente.ciudad"},
                            "ingresos": {"$sum": "$total_pedido"},
                            "ganancia_estimada": {"$sum": "$ganancia_estimada"}}},
                {"$sort": {"ingresos": -1}},
                {"$limit": 10}
            ]
        },
        {
            "nombre": "4. Ticket Promedio y Volumen por Metodo de Pago",
            "pipeline": [
                {"$match": {"estado": "Entregado"}},
                {"$group": {"_id": "$metodo_pago",
                            "ticket_promedio": {"$avg": "$total_pedido"},
                            "total_transacciones": {"$sum": 1},
                            "ingresos_totales": {"$sum": "$total_pedido"}}},
                {"$sort": {"ingresos_totales": -1}},
                {"$limit": 10}
            ]
        },
        {
            "nombre": "5. Tendencia de Ventas: Comparativa Dia de la Semana",
            "pipeline": [
                {"$addFields": {"dia_semana": {"$dayOfWeek": "$fecha_pedido"}}},
                {"$group": {"_id": "$dia_semana",
                            "ingresos": {"$sum": "$total_pedido"},
                            "ventas_count": {"$sum": 1}}},
                {"$sort": {"_id": 1}},
                {"$limit": 10}
            ]
        },
        {
            "nombre": "6. Tasa de Cancelacion por Metodo de Pago",
            "pipeline": [
                {"$group": {
                    "_id": "$metodo_pago",
                    "total_ventas": {"$sum": 1},
                    "canceladas": {"$sum": {"$cond": [{"$eq": ["$estado", "Cancelado"]}, 1, 0]}}
                }},
                {"$project": {
                    "metodo_pago": "$_id",
                    "_id": 0,
                    "total_ventas": 1,
                    "canceladas": 1,
                    "tasa_cancelacion_pct": {
                        "$round": [{"$multiply": [{"$divide": ["$canceladas", "$total_ventas"]}, 100]}, 2]
                    }
                }},
                {"$sort": {"tasa_cancelacion_pct": -1}},
                {"$limit": 10}
            ]
        },
        {
            "nombre": "7. Top 10 Clientes VIP por Gasto Acumulado",
            "pipeline": [
                {"$group": {
                    "_id": "$cliente.id",
                    "nombre": {"$first": "$cliente.nombre"},
                    "compras": {"$sum": 1},
                    "gasto_total": {"$sum": "$total_pedido"}
                }},
                {"$project": {"_id": 0, "cliente_id": "$_id", "nombre": 1, "compras": 1,
                              "gasto_total": {"$round": ["$gasto_total", 2]}}},
                {"$sort": {"gasto_total": -1}},
                {"$limit": 10}
            ]
        },
        {
            "nombre": "8. Ventas Trimestrales (Analisis Estacional Q1-Q4)",
            "pipeline": [
                {"$group": {
                    "_id": {
                        "anio": "$anio",
                        "trimestre": {"$concat": ["Q", {"$toString": {"$ceil": {"$divide": ["$mes", 3]}}}]}
                    },
                    "ingresos": {"$sum": "$total_pedido"}
                }},
                {"$project": {"_id": 0, "anio": "$_id.anio", "trimestre": "$_id.trimestre",
                              "ingresos": {"$round": ["$ingresos", 2]}}},
                {"$sort": {"anio": 1, "trimestre": 1}},
                {"$limit": 10}
            ]
        },
        {
            "nombre": "9. Ticket Promedio por Ciudad y Segmento (Top 15)",
            "pipeline": [
                {"$match": {"estado": "Entregado"}},
                {"$group": {"_id": {"ciudad": "$cliente.ciudad", "segmento": "$cliente.segmento"},
                            "ticket_promedio": {"$avg": "$total_pedido"},
                            "transacciones": {"$sum": 1}}},
                {"$project": {"_id": 0, "ciudad": "$_id.ciudad", "segmento": "$_id.segmento",
                              "ticket_promedio": {"$round": ["$ticket_promedio", 2]}, "transacciones": 1}},
                {"$sort": {"ticket_promedio": -1}},
                {"$limit": 10}
            ]
        },
        {
            "nombre": "10. Top 10 Productos con Mayor Rotacion (Unidades Vendidas)",
            "pipeline": [
                {"$group": {"_id": "$producto.nombre",
                            "unidades_vendidas": {"$sum": "$cantidad"},
                            "ingresos_generados": {"$sum": "$subtotal_linea"}}},
                {"$project": {"_id": 0, "producto": "$_id", "unidades_vendidas": 1,
                              "ingresos_generados": {"$round": ["$ingresos_generados", 2]}}},
                {"$sort": {"unidades_vendidas": -1}},
                {"$limit": 10}
            ]
        }
    ]

    print("Fase 2: Ejecutando consultas y midiendo latencia...\n")
    print("-" * 70)

    tiempos_totales = []
    total = len(consultas)

    for indice, consulta in enumerate(consultas, start=1):
        print(f"[{indice}/{total}] {consulta['nombre']}")

        mejor_ms = None
        mejores_resultados = []
        for repeticion in range(3):
            inicio = time.perf_counter()
            resultados = list(coleccion.aggregate(consulta['pipeline'], allowDiskUse=True))
            fin = time.perf_counter()
            tiempo_ms = (fin - inicio) * 1000
            if mejor_ms is None or tiempo_ms < mejor_ms:
                mejor_ms = tiempo_ms
                mejores_resultados = resultados

        tiempo_ms = mejor_ms
        resultados = mejores_resultados
        tiempos_totales.append(tiempo_ms)

        print(f"   Latencia: {tiempo_ms:.2f} ms (mejor de 3) | Filas retornadas: {len(resultados)}")

        if len(resultados) > 0:
            resultado_limpio = json.loads(json.dumps(resultados[0], default=str))
            print(f"   Muestra: {resultado_limpio}")
        print("-" * 70)

    # 3. Resumen
    promedio_latencia = sum(tiempos_totales) / len(tiempos_totales)

    print("\n" + "=" * 70)
    print("RESUMEN DE BENCHMARKING")
    print("=" * 70)
    print(f"Consultas ejecutadas: {len(consultas)}")
    print(f"  Latencia promedio: {promedio_latencia:.2f} ms")
    print(f"Latencia maxima: {max(tiempos_totales):.2f} ms")
    print(f"Registros procesados: {coleccion.count_documents({})}")
    print("=" * 70)

    client.close()


if __name__ == "__main__":
    ejecutar_benchmark()