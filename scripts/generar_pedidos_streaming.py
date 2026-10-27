import os
import random
import time
import pymongo
from dotenv import load_dotenv
from faker import Faker

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")
fake = Faker('es_CO')

NUM_PEDIDOS = 15
SEGUNDOS_ENTRE_PEDIDOS = 1.5
UMBRAL_ALERTA = 500000


def generar_pedido(productos_db, cliente_id, repartidor_id):
    """Genera un pedido realista para UrbanRush"""
    num_items = random.randint(1, 3)
    items_pedido = random.sample(productos_db, num_items)

    subtotal = 0
    items = []
    for prod in items_pedido:
        cantidad = random.randint(1, 3)
        subtotal += prod["precio_unitario"] * cantidad
        items.append({
            "producto_id": prod["_id"],
            "nombre_producto": prod["nombre"],
            "cantidad": cantidad,
            "precio_unitario": prod["precio_unitario"],
            "subtotal": prod["precio_unitario"] * cantidad
        })

    delivery_fee = round(random.uniform(3000, 15000), 2)
    comision = round(subtotal * 0.10, 2)

    return {
        "numero_pedido": f"STR-{fake.year()}-{random.randint(100000, 999999)}",
        "cliente_id": cliente_id,
        "repartidor_id": repartidor_id,
        "items": items,
        "subtotal": round(subtotal, 2),
        "delivery_fee": delivery_fee,
        "comision_plataforma": comision,
        "total": round(subtotal + delivery_fee, 2),
        "metodo_pago": random.choice(
            ["Tarjeta de Credito", "Nequi", "DaviPlata", "Efectivo", "PSE"]),
        "estado": random.choice(["Pendiente", "Pendiente", "En camino", "Entregado"]),
        "ciudad_entrega": random.choice(
            ["Bogota", "Medellin", "Cali", "Barranquilla", "Cartagena", "Bucaramanga"])
    }


def generar_streaming():
    print("Generando pedidos en tiempo real (simulando ventas)...\n")

    client = pymongo.MongoClient(MONGO_URI)
    db = client["urbanrush_db"]

    # Referencias reales de la base de datos
    productos_db = list(db.productos.find({}, {"_id": 1, "nombre": 1, "precio_unitario": 1}))
    cliente_id = db.clientes.find_one({}, {"_id": 1})["_id"]
    repartidor_id = db.repartidores.find_one({}, {"_id": 1})["_id"]

    ids_insertados = []
    con_alerta = 0

    for i in range(NUM_PEDIDOS):
        # ~30% de los pedidos son de alto valor (disparan la alerta)
        if random.random() < 0.3:
            for item in productos_db:
                item["precio_unitario"] = random.uniform(150000, 600000)
            con_alerta += 1

        pedido = generar_pedido(productos_db, cliente_id, repartidor_id)
        resultado = db.pedidos.insert_one(pedido)
        ids_insertados.append(resultado.inserted_id)

        print(f"Venta generada: Pedido {pedido['numero_pedido']} "
              f"Total ${pedido['total']:,.0f}")
        if pedido["total"] > UMBRAL_ALERTA:
            print(f"   -> Pedido de alto valor (supera ${UMBRAL_ALERTA:,.0f})")

        time.sleep(SEGUNDOS_ENTRE_PEDIDOS)

    # Mostrar los 3 tipos de evento: ahora un UPDATE y un DELETE
    print("\nActualizando un pedido (Pendiente -> Completada)...")
    db.pedidos.update_one(
        {"_id": ids_insertados[0]},
        {"$set": {"estado": "Completada"}}
    )
    print("Pedido actualizado.")

    print("Eliminando un pedido (prueba de auditoria)...")
    db.pedidos.delete_one({"_id": ids_insertados[1]})
    print("Pedido eliminado.")

    print(f"\nStreaming finalizado: {NUM_PEDIDOS} pedidos generados "
          f"({con_alerta} de alto valor).")
    client.close()


if __name__ == "__main__":
    generar_streaming()