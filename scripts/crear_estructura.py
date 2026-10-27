import os
import pymongo
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")

def crear_estructura_urbanrush():
    client = pymongo.MongoClient(MONGO_URI)
    db = client["urbanrush_db"]

    print("Creando estructura de base de datos de UrbanRush...\n")

    # 1. Crear colecciones OLTP (Transaccionales)
    print("Creando colecciones transaccionales (OLTP)...")
    colecciones_oltp = ["clientes", "productos", "repartidores", "pedidos"]
    for col in colecciones_oltp:
        db.create_collection(col)
        print(f"  Coleccion '{col}' creada")

    # 2. Crear indices para optimizar consultas
    print("\nCreando indices...")
    db.clientes.create_index([("email", 1)], unique=True)
    db.productos.create_index([("sku", 1)], unique=True)
    db.pedidos.create_index([("fecha_pedido", -1)])
    db.pedidos.create_index([("cliente_id", 1)])
    db.repartidores.create_index([("zona", 1)])
    print("  Indices creados")

    # 3. Insertar datos de prueba
    print("\nInsertando datos de prueba...")

    cliente_ejemplo = {
        "codigo_cliente": "CLI001",
        "nombre": "Juan Perez",
        "email": "juan.perez@email.com",
        "telefono": "3001234567",
        "direccion": {
            "calle": "Calle 123 #45-67",
            "ciudad": "Bogota",
            "barrio": "Chapinero",
            "pais": "Colombia"
        },
        "fecha_registro": datetime.now(),
        "activo": True
    }
    db.clientes.insert_one(cliente_ejemplo)
    print("  Cliente insertado")

    producto_ejemplo = {
        "sku": "PROD001",
        "nombre": "Hamburguesa Clasica",
        "descripcion": "Doble carne, queso y papas a la francesa",
        "categoria": "Comida Rapida",
        "precio_unitario": 25000,
        "stock": 100,
        "proveedor": "Restaurante El Fogon",
        "vendor_id": 1,
        "fecha_creacion": datetime.now()
    }
    db.productos.insert_one(producto_ejemplo)
    print("  Producto insertado")

    repartidor_ejemplo = {
        "codigo_repartidor": "REP001",
        "nombre": "Carlos Rodriguez",
        "telefono": "3109876543",
        "vehiculo": "Moto",
        "placa": "ABC-123",
        "zona": "Chapinero",
        "estado": "ACTIVE",
        "fecha_ingreso": datetime.now()
    }
    db.repartidores.insert_one(repartidor_ejemplo)
    print("  Repartidor insertado")

    pedido_ejemplo = {
        "numero_pedido": "ORD-2026-0001",
        "cliente_id": db.clientes.find_one({"codigo_cliente": "CLI001"})["_id"],
        "repartidor_id": db.repartidores.find_one({"codigo_repartidor": "REP001"})["_id"],
        "fecha_pedido": datetime.now(),
        "items": [
            {
                "producto_id": db.productos.find_one({"sku": "PROD001"})["_id"],
                "nombre_producto": "Hamburguesa Clasica",
                "cantidad": 2,
                "precio_unitario": 25000,
                "subtotal": 50000
            }
        ],
        "subtotal": 50000,
        "delivery_fee": 5000,
        "comision_plataforma": 3500,
        "total": 55000,
        "metodo_pago": "Tarjeta de Credito",
        "estado": "Entregado",
        "ciudad_entrega": "Bogota"
    }
    db.pedidos.insert_one(pedido_ejemplo)
    print("  Pedido insertado")

    # 4. Crear coleccion OLAP (Analitica)
    print("\nCreando coleccion analitica (OLAP)...")
    db.create_collection("pedidos_analiticos")
    print("  Coleccion 'pedidos_analiticos' creada")

    print("\nEstructura de UrbanRush creada exitosamente en Atlas!")
    print("Abre MongoDB Compass para ver las colecciones creadas.")

    client.close()

if __name__ == "__main__":
    crear_estructura_urbanrush()