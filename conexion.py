import os
import pymongo
from dotenv import load_dotenv
from pymongo.errors import ConnectionFailure, ConfigurationError, OperationFailure

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")

def conectar_mongodb():
    try:
        print("Intentando conectar a MongoDB Atlas...")
        client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        print("Conexion exitosa a MongoDB Atlas!")

        db = client["urbanrush_db"]
        return client, db

    except ConnectionFailure:
        print("Error: No se pudo contactar al servidor.")
    except ConfigurationError as e:
        print(f"Error de configuracion: {e}")
    except OperationFailure as e:
        print(f"Error de autenticacion: {e}")

    return None, None

if __name__ == "__main__":
    client, db = conectar_mongodb()
    if client:
        client.close()
        print("Conexion cerrada.")