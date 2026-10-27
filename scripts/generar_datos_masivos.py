import os
import random
import pymongo
from dotenv import load_dotenv
from faker import Faker
import time

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")
fake = Faker('es_CO')

# Cantidades a generar
NUM_CLIENTES = 5000
NUM_PRODUCTOS = 1000
NUM_REPARTIDORES = 300
NUM_PEDIDOS = 50000
BATCH_SIZE = 1000


def conectar_bd():
    client = pymongo.MongoClient(MONGO_URI)
    return client["urbanrush_db"]


def insertar_en_lotes(coleccion, datos, nombre_entidad):
    """Inserta datos en bloques, ignorando duplicados"""
    total = len(datos)
    print(f"Insertando {total} {nombre_entidad} en lotes de {BATCH_SIZE}...")

    for i in range(0, total, BATCH_SIZE):
        lote = datos[i:i + BATCH_SIZE]
        try:
            coleccion.insert_many(lote, ordered=False)
            progreso = min(i + BATCH_SIZE, total)
            print(f"  Progreso: {progreso}/{total} ({(progreso/total)*100:.1f}%)")
        except pymongo.errors.BulkWriteError as e:
            insertados = e.details.get('nInserted', 0)
            progreso = min(i + BATCH_SIZE, total)
            print(f"  Progreso: {progreso}/{total} (Se omitieron {len(lote) - insertados} duplicados)")

    print(f"  Proceso de {nombre_entidad} finalizado.\n")


def generar_datos():
    print("Iniciando generacion de datos masivos para MongoDB Atlas...\n")
    db = conectar_bd()
    inicio_total = time.time()

    # 1. GENERAR CLIENTES
    print("Generando clientes...")
    ciudades = ["Bogota", "Medellin", "Cali", "Barranquilla", "Cartagena", "Bucaramanga"]
    barrios = ["Chapinero", "El Poblado", "San Fernando", "Centro", "Bocagrande", "Cabecera"]
    clientes = []
    for _ in range(NUM_CLIENTES):
        clientes.append({
            "codigo_cliente": f"CLI{random.randint(10000, 99999)}",
            "nombre": fake.name(),
            "email": f"{fake.user_name()}{random.randint(1000, 9999)}@{fake.free_email_domain()}",
            "telefono": fake.phone_number(),
            "direccion": {
                "calle": fake.street_address(),
                "ciudad": random.choice(ciudades),
                "barrio": random.choice(barrios),
                "pais": "Colombia"
            },
            "fecha_registro": fake.date_time_between(start_date='-2y', end_date='now'),
            "activo": random.choice([True, True, True, False])
        })
    insertar_en_lotes(db.clientes, clientes, "clientes")

    clientes_ids = [c["_id"] for c in db.clientes.find({}, {"_id": 1})]

    # 2. GENERAR PRODUCTOS
    print("Generando productos...")
    categorias = ["Comida Rapida", "Hogar", "Ropa", "Deportes", "Tecnologia", "Mercado"]
    productos = []
    for _ in range(NUM_PRODUCTOS):
        productos.append({
            "sku": f"PROD{random.randint(10000, 99999)}",
            "nombre": f"{fake.word().capitalize()} {fake.word().capitalize()}",
            "descripcion": fake.catch_phrase(),
            "categoria": random.choice(categorias),
            "precio_unitario": round(random.uniform(5000, 500000), 2),
            "stock": random.randint(0, 500),
            "proveedor": fake.company(),
            "vendor_id": random.randint(1, 200),
            "fecha_creacion": fake.date_time_between(start_date='-1y', end_date='now')
        })
    insertar_en_lotes(db.productos, productos, "productos")

    productos_db = list(db.productos.find({}, {"_id": 1, "precio_unitario": 1, "nombre": 1}))

    # 3. GENERAR REPARTIDORES
    print("Generando repartidores...")
    vehiculos = ["Moto", "Bicicleta", "Carro", "Scooter"]
    estados_repartidor = ["ACTIVE", "ACTIVE", "ACTIVE", "INACTIVE"]
    repartidores = []
    for _ in range(NUM_REPARTIDORES):
        repartidores.append({
            "codigo_repartidor": f"REP{random.randint(1000, 9999)}",
            "nombre": fake.name(),
            "telefono": fake.phone_number(),
            "vehiculo": random.choice(vehiculos),
            "placa": fake.license_plate() if random.random() > 0.3 else None,
            "zona": random.choice(barrios),
            "estado": random.choice(estados_repartidor),
            "fecha_ingreso": fake.date_time_between(start_date='-2y', end_date='now')
        })
    insertar_en_lotes(db.repartidores, repartidores, "repartidores")

    repartidores_ids = [r["_id"] for r in db.repartidores.find({}, {"_id": 1})]

    # 4. GENERAR PEDIDOS
    print("Generando pedidos (esto puede tomar unos minutos)...")
    metodos_pago = ["Tarjeta de Credito", "Tarjeta Debito", "Nequi", "DaviPlata", "Efectivo", "PSE"]
    estados = ["Entregado", "Entregado", "Entregado", "En camino", "Pendiente", "Cancelado"]

    pedidos = []
    for _ in range(NUM_PEDIDOS):
        num_items = random.randint(1, 5)
        items_pedido = random.sample(productos_db, num_items)

        total_subtotal = 0
        items_detalle = []

        for prod in items_pedido:
            cantidad = random.randint(1, 3)
            subtotal = prod["precio_unitario"] * cantidad
            total_subtotal += subtotal

            items_detalle.append({
                "producto_id": prod["_id"],
                "nombre_producto": prod["nombre"],
                "cantidad": cantidad,
                "precio_unitario": prod["precio_unitario"],
                "subtotal": round(subtotal, 2)
            })

        delivery_fee = round(random.uniform(3000, 15000), 2)
        comision_plataforma = round(total_subtotal * 0.10, 2)

        pedidos.append({
            "numero_pedido": f"ORD-{fake.year()}-{random.randint(100000, 999999)}",
            "cliente_id": random.choice(clientes_ids),
            "repartidor_id": random.choice(repartidores_ids),
            "fecha_pedido": fake.date_time_between(start_date='-1y', end_date='now'),
            "items": items_detalle,
            "subtotal": round(total_subtotal, 2),
            "delivery_fee": delivery_fee,
            "comision_plataforma": comision_plataforma,
            "total": round(total_subtotal + delivery_fee, 2),
            "metodo_pago": random.choice(metodos_pago),
            "estado": random.choice(estados),
            "ciudad_entrega": random.choice(ciudades)
        })

        if len(pedidos) >= BATCH_SIZE:
            insertar_en_lotes(db.pedidos, pedidos, "pedidos (lote)")
            pedidos = []

    if len(pedidos) > 0:
        insertar_en_lotes(db.pedidos, pedidos, "pedidos (lote final)")

    # 5. RESUMEN FINAL
    tiempo_total = time.time() - inicio_total
    print("=" * 50)
    print("GENERACION DE DATOS COMPLETADA!")
    print(f"  Tiempo total de ejecucion: {tiempo_total:.2f} segundos")
    print(f"Clientes en BD: {db.clientes.count_documents({})}")
    print(f"Productos en BD: {db.productos.count_documents({})}")
    print(f"Repartidores en BD: {db.repartidores.count_documents({})}")
    print(f"Pedidos en BD: {db.pedidos.count_documents({})}")
    print("=" * 50)

    db.client.close()


if __name__ == "__main__":
    generar_datos()