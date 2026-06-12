import sys
import time

print("=== Inicializando base de datos ===", flush=True)

for intento in range(30):
    try:
        from app.models import init_db, engine
        from sqlmodel import SQLModel
        from sqlalchemy import inspect as sa_inspect

        # Crear tablas si no existen
        init_db()

        # Verificar que el schema esté actualizado (todas las columnas presentes)
        inspector = sa_inspect(engine)
        tablas_db = inspector.get_table_names()

        if "trabajador" in tablas_db:
            cols_db = {c["name"] for c in inspector.get_columns("trabajador")}
            cols_modelo = {c.name for c in SQLModel.metadata.tables["trabajador"].columns}
            faltantes = cols_modelo - cols_db

            if faltantes:
                print(f"Schema desactualizado — columnas faltantes: {faltantes}", flush=True)
                print("Recreando tablas con schema actual...", flush=True)
                SQLModel.metadata.drop_all(engine)
                SQLModel.metadata.create_all(engine)
                print("Tablas recreadas.", flush=True)
            else:
                print(f"Schema OK — todas las columnas presentes.", flush=True)

        tablas = list(SQLModel.metadata.tables.keys())
        print(f"Tablas activas: {tablas}", flush=True)
        sys.exit(0)

    except Exception as e:
        print(f"Intento {intento + 1}/30 fallido: {e}", flush=True)
        if intento < 29:
            time.sleep(3)

print("ERROR: no se pudo inicializar la BD después de 90 segundos.", flush=True)
sys.exit(1)
