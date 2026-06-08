import sys
import time

print("=== Inicializando base de datos ===", flush=True)

for intento in range(30):
    try:
        from app.models import init_db
        init_db()
        from sqlmodel import SQLModel
        tablas = list(SQLModel.metadata.tables.keys())
        print(f"OK — tablas: {tablas}", flush=True)
        sys.exit(0)
    except Exception as e:
        print(f"Intento {intento + 1}/30 fallido: {e}", flush=True)
        if intento < 29:
            time.sleep(3)

print("ERROR: no se pudo inicializar la BD en 90 segundos.", flush=True)
sys.exit(1)
