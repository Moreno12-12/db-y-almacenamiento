import os
import pymongo
import time
import json
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")

# Regla de negocio: alerta si el pedido supera este valor (COP)
UMBRAL_ALERTA = 500000


def simular_streaming_kafka():
    print("Iniciando pipeline...")
    print("MongoDB Change Streams: escuchando cambios en la coleccion 'pedidos'")
    print("(inserciones, actualizaciones y eliminaciones en tiempo real)\n")

    client = pymongo.MongoClient(MONGO_URI)
    db = client["urbanrush_db"]
    contador = 0

    try:
        # watch() crea un cursor de streaming que NUNCA termina (como Kafka Consumer)
        with db.pedidos.watch() as stream:
            for change in stream:
                contador += 1
                hora = datetime.now().strftime("%H:%M:%S")
                operacion = change["operationType"]

                if operacion == "insert":
                    documento = change["fullDocument"]
                    numero_pedido = documento.get("numero_pedido", "?")
                    total = documento.get("total", 0)
                    print(f"[{hora}] INSERT Pedido {numero_pedido} Total ${total:,.0f}")

                    # Regla de negocio: alerta en tiempo real
                    if total > UMBRAL_ALERTA:
                        print(f"   *** ALERTA: Pedido de alto valor ({total:,.0f}) ***")

                elif operacion == "update":
                    id_pedido = change["documentKey"]["_id"]
                    print(f"[{hora}] UPDATE Pedido con ID {id_pedido} (ej: Pendiente -> Completada)")

                elif operacion == "delete":
                    id_pedido = change["documentKey"]["_id"]
                    print(f"[{hora}] DELETE Pedido con ID {id_pedido} (auditoria)")

                # Procesamiento periodico: simula un micro-batch de Spark Streaming
                if contador % 10 == 0:
                    print(f"   -> Procesados {contador} eventos...")

    except KeyboardInterrupt:
        print("\nStream cerrado por el usuario.")
    finally:
        client.close()
        print("Conexion cerrada correctamente.")


if __name__ == "__main__":
    print("INSTRUCCIONES:")
    print("1. Deja este script abierto (esta escuchando).")
    print("2. En otra terminal ejecuta: python scripts/generar_pedidos_streaming.py")
    print("3. Observa los eventos que llegan en tiempo real.\n")
    simular_streaming_kafka()